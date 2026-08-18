"""Industry-complete research coverage for the All-A scan.

This is a research recall layer, not a buy-signal layer.  It prevents an entire
industry from disappearing merely because a global ranking exhausted the
research budget.  Hard blockers remain visible and are never converted into
buy eligibility.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

DEFAULT_PER_INDUSTRY = 5
UNKNOWN_INDUSTRY = "UNCLASSIFIED"


def _float(value: Any, default: float = -1e18) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _industry(row: Mapping[str, Any]) -> str:
    return str(
        row.get("industry")
        or row.get("normalized_industry")
        or row.get("raw_industry")
        or UNKNOWN_INDUSTRY
    ).strip() or UNKNOWN_INDUSTRY


def _blockers(row: Mapping[str, Any]) -> str:
    return str(row.get("hard_blockers") or row.get("hard_reject_blockers") or "").strip()


def _status(row: Mapping[str, Any]) -> str:
    return str(row.get("quant_status") or row.get("quant_screen_status") or "").strip().upper()


def _research_key(row: Mapping[str, Any]) -> tuple[int, float, float, str]:
    """Rank investable research names first without hiding blocked names."""
    hard = bool(_blockers(row))
    status_rank = {
        "PRIORITY_RESEARCH": 0,
        "SECONDARY_RESEARCH": 1,
        "LOW_PRIORITY": 2,
        "HARD_REJECT": 3,
    }.get(_status(row), 2)
    return (
        1 if hard else 0,
        status_rank,
        -_float(row.get("quant_score")),
        str(row.get("code") or ""),
    )


def select_industry_coverage(
    rows: Iterable[Mapping[str, Any]], *, per_industry: int = DEFAULT_PER_INDUSTRY
) -> list[dict[str, Any]]:
    """Return up to N research names for every represented industry.

    The function deliberately does not require a stock to pass Formal BUY or
    strict gates.  An industry with no clean names is still represented by its
    best blocked research names, explicitly labelled NO_INVESTABLE_CANDIDATE.
    """
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen: set[str] = set()
    for raw in rows:
        code = str(raw.get("code") or "").strip()
        if not code or code in seen:
            continue
        row = dict(raw)
        row["industry"] = _industry(row)
        buckets[row["industry"]].append(row)
        seen.add(code)

    result: list[dict[str, Any]] = []
    keep = max(1, int(per_industry))
    for industry in sorted(buckets):
        ranked = sorted(buckets[industry], key=_research_key)
        clean_count = sum(not bool(_blockers(row)) for row in ranked)
        industry_state = "RESEARCH_CANDIDATES_AVAILABLE" if clean_count else "NO_INVESTABLE_CANDIDATE"
        for industry_rank, row in enumerate(ranked[:keep], 1):
            result.append({
                **row,
                "industry": industry,
                "industry_research_rank": industry_rank,
                "industry_candidate_state": "BLOCKED_RESEARCH_ONLY" if _blockers(row) else "RESEARCH_CANDIDATE",
                "industry_status": industry_state,
                "formal_signal_eligible": False,
                "automatic_promotion_allowed": False,
                "no_auto_trade": True,
            })
    return result


def _read_source(report_dir: Path) -> list[dict[str, Any]]:
    for name in ("all_a_quant_screen.csv", "quant_screen_all.csv", "top80_evidence_queue.csv"):
        path = report_dir / name
        if path.exists():
            with path.open(encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            if rows:
                return rows
    raise FileNotFoundError(f"no All-A quant source under {report_dir}")


def _flattened_artifact_fallback(root: Path, names: tuple[str, ...]) -> Path | None:
    """Resolve GitHub artifact extraction that strips the uploaded parent path.

    `actions/upload-artifact` stores files relative to the least-common uploaded
    root.  A later download can therefore yield `upstream/YYYYMMDD/...` even
    though callers historically expect `upstream/reports/all_a_full_scan/...`.
    When that happens, search only the nearest existing ancestor (`upstream` in
    production), then materialize the legacy requested path as a directory
    symlink.  Subsequent Postscan modules can keep using the same stable path.
    """
    if root.exists():
        return None
    ancestor = next((parent for parent in root.parents if parent.exists()), None)
    if ancestor is None:
        return None
    candidates = sorted(
        {p.parent for name in names for p in ancestor.glob(f"**/{name}") if p.is_file()},
        key=str,
    )
    if not candidates:
        return None
    report = candidates[-1]
    try:
        root.parent.mkdir(parents=True, exist_ok=True)
        root.symlink_to(report.resolve(), target_is_directory=True)
        print(f"all_a_artifact_alias={root}->{report.resolve()}")
    except OSError as exc:
        # Returning the discovered report still lets this module proceed; the
        # message makes an alias failure diagnosable instead of silent.
        print(f"all_a_artifact_alias_warning={type(exc).__name__}:{exc}")
    return report


def find_latest_report(root: Path) -> Path:
    names = ("all_a_quant_screen.csv", "quant_screen_all.csv", "top80_evidence_queue.csv")
    if any((root / name).exists() for name in names):
        return root
    candidates = sorted({p.parent for name in names for p in root.glob(f"**/{name}") if p.is_file()}, key=str)
    if not candidates:
        fallback = _flattened_artifact_fallback(root, names)
        if fallback is not None:
            return fallback
        raise FileNotFoundError(f"no All-A report under {root}")
    return candidates[-1]


def write_industry_coverage(report_dir: Path, output_dir: Path, *, per_industry: int = DEFAULT_PER_INDUSTRY) -> list[dict[str, Any]]:
    rows = select_industry_coverage(_read_source(report_dir), per_industry=per_industry)
    output_dir.mkdir(parents=True, exist_ok=True)
    fields = [
        "industry", "industry_research_rank", "industry_candidate_state", "industry_status",
        "code", "stock_name", "quant_status", "quant_rank", "quant_score", "hard_blockers",
        "formal_signal_eligible", "automatic_promotion_allowed", "no_auto_trade",
    ]
    with (output_dir / "industry_top_candidates.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    industries = sorted({row["industry"] for row in rows})
    summary = {
        "industry_count": len(industries),
        "candidate_count": len(rows),
        "per_industry_target": int(per_industry),
        "industries_without_clean_candidate": sorted({row["industry"] for row in rows if row["industry_status"] == "NO_INVESTABLE_CANDIDATE"}),
        "formal_signal_eligible": False,
        "automatic_promotion_allowed": False,
        "no_auto_trade": True,
    }
    (output_dir / "industry_coverage_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = ["# All-A Industry Coverage", "", "Every represented industry keeps research visibility; blocked names never become buy signals.", ""]
    current = None
    for row in rows:
        if row["industry"] != current:
            current = row["industry"]
            lines.extend([f"## {current}", f"- status: {row['industry_status']}"])
        lines.append(f"- {row['industry_research_rank']}. {row.get('code','')} {row.get('stock_name','')} | {row['industry_candidate_state']} | quant={row.get('quant_score','')}")
    (output_dir / "industry_top_candidates.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--per-industry", type=int, default=DEFAULT_PER_INDUSTRY)
    args = parser.parse_args(argv)
    report_dir = find_latest_report(args.report_root)
    rows = write_industry_coverage(report_dir, args.output_dir, per_industry=args.per_industry)
    print(f"industry_coverage={args.output_dir};candidates={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
