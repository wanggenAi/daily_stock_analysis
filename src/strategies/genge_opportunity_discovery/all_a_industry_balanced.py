"""Production launcher for industry-balanced All-A research recall.

The legacy scanner is intentionally reused for data acquisition, risk gates,
price plans and lifecycle handling. This launcher replaces only the research
recall policy and fundamental-budget allocation so global Top-N competition
cannot erase an otherwise eligible industry before deep research.
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping

from src.strategies.genge_opportunity_discovery import all_a_full_scan as base
from src.strategies.genge_opportunity_discovery.industry_balanced_recall import (
    IndustryRecallPolicy,
    coverage_audit,
    industry_leaders,
    select_industry_balanced_rows,
)

DEFAULT_TOTAL_RECALL = 260
DEFAULT_GLOBAL_SEED = 80
DEFAULT_PER_INDUSTRY_TARGET = 3
DEFAULT_FULL_FUNDAMENTAL_LEADERS_PER_INDUSTRY = 1

_ORIGINAL_RESEARCH_QUEUE = base._research_queue
_ORIGINAL_FUNDAMENTALS = base._fundamentals


def _normalize_code(value: Any) -> str:
    text = str(value or "").strip()
    return text.zfill(6) if text.isdigit() else text


def _balanced_research_queue(
    quant_rows: list[Mapping[str, Any]], *, limit: int,
) -> list[dict[str, Any]]:
    return select_industry_balanced_rows(
        quant_rows,
        policy=IndustryRecallPolicy(
            total_limit=max(DEFAULT_TOTAL_RECALL, int(limit)),
            global_seed=DEFAULT_GLOBAL_SEED,
            per_industry_target=DEFAULT_PER_INDUSTRY_TARGET,
        ),
    )


def _balanced_fundamentals(
    quant_rows: list[dict[str, Any]],
    qfq_histories: Mapping[str, Any],
    config: Any,
    *,
    priority_codes: Iterable[str] = (),
    required_codes: Iterable[str] = (),
):
    """Guarantee one fully fetched company per eligible industry."""

    leaders = industry_leaders(
        quant_rows,
        per_industry=DEFAULT_FULL_FUNDAMENTAL_LEADERS_PER_INDUSTRY,
    )
    leader_codes = [_normalize_code(row.get("code")) for row in leaders]
    existing_required = {
        _normalize_code(code) for code in required_codes if _normalize_code(code)
    }
    mandatory = list(dict.fromkeys([*existing_required, *leader_codes]))
    original_limit = max(0, int(config.fundamental_limit))
    config.fundamental_limit = max(original_limit, len(mandatory) + original_limit)
    try:
        return _ORIGINAL_FUNDAMENTALS(
            quant_rows,
            qfq_histories,
            config,
            priority_codes=list(
                dict.fromkeys(
                    [
                        *[_normalize_code(code) for code in priority_codes],
                        *leader_codes,
                    ]
                )
            ),
            required_codes=mandatory,
        )
    finally:
        config.fundamental_limit = original_limit


def install_industry_balanced_policy() -> None:
    base._research_queue = _balanced_research_queue
    base._fundamentals = _balanced_fundamentals


def _read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def _write_csv(path: Path, rows: list[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fields})


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _latest_report_dir() -> Path:
    root = Path("reports/all_a_full_scan")
    candidates = [
        path.parent for path in root.glob("**/run_summary.json") if path.is_file()
    ]
    if not candidates:
        raise FileNotFoundError("no all-A run_summary.json found after scan")
    return max(candidates, key=lambda path: (path / "run_summary.json").stat().st_mtime)


def _postprocess(report_dir: Path) -> dict[str, Any]:
    quant_rows = _read_csv(report_dir / "all_a_quant_screen.csv")
    actual_rows = _read_csv(report_dir / "top80_evidence_queue.csv")
    if not quant_rows:
        raise RuntimeError("industry-balanced recall audit requires all_a_quant_screen.csv")
    expected_rows = _balanced_research_queue(quant_rows, limit=DEFAULT_TOTAL_RECALL)
    expected_codes = {_normalize_code(row.get("code")) for row in expected_rows}
    actual_codes = {_normalize_code(row.get("code")) for row in actual_rows}
    if actual_codes != expected_codes:
        missing = sorted(expected_codes - actual_codes)
        extra = sorted(actual_codes - expected_codes)
        raise RuntimeError(
            "production scanner did not use industry-balanced recall policy: "
            f"missing={missing[:10]};extra={extra[:10]}"
        )

    audit = coverage_audit(quant_rows, actual_rows)
    audit.update(
        {
            "policy_version": "industry_balanced_recall_v1",
            "global_seed": DEFAULT_GLOBAL_SEED,
            "per_industry_target": DEFAULT_PER_INDUSTRY_TARGET,
            "configured_total_recall_floor": DEFAULT_TOTAL_RECALL,
            "full_fundamental_leaders_per_industry": (
                DEFAULT_FULL_FUNDAMENTAL_LEADERS_PER_INDUSTRY
            ),
            "legacy_top80_filename_is_compatibility_alias": True,
        }
    )
    if not audit["all_eligible_industries_covered"]:
        raise RuntimeError(
            "industry recall invariant failed: "
            f"{audit['missing_eligible_industries']}"
        )

    leaders = industry_leaders(quant_rows, per_industry=1)
    top3 = industry_leaders(quant_rows, per_industry=DEFAULT_PER_INDUSTRY_TARGET)
    _write_csv(report_dir / "industry_balanced_research_queue.csv", actual_rows)
    _write_csv(report_dir / "industry_leaders.csv", leaders)
    _write_csv(report_dir / "industry_candidate_pool_top3.csv", top3)
    (report_dir / "industry_coverage_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    summary_path = report_dir / "run_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["industry_balanced_recall"] = audit
    summary["canonical_research_queue_file"] = "industry_balanced_research_queue.csv"
    summary["industry_leader_count"] = len(leaders)
    summary["industry_candidate_pool_top3_count"] = len(top3)
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    manifest = {
        path.name: _hash_file(path)
        for path in sorted(report_dir.iterdir())
        if path.is_file() and path.name != "report_manifest.json"
    }
    (report_dir / "report_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return audit


def _ensure_min_numeric_arg(argv: list[str], flag: str, minimum: int) -> list[str]:
    result = list(argv)
    try:
        index = result.index(flag)
    except ValueError:
        result.extend([flag, str(minimum)])
        return result
    if index + 1 >= len(result):
        raise SystemExit(f"{flag} requires a value")
    try:
        current = int(result[index + 1])
    except ValueError as exc:
        raise SystemExit(f"{flag} must be an integer") from exc
    if current < minimum:
        result[index + 1] = str(minimum)
    return result


def main(argv: list[str] | None = None) -> int:
    effective = list(sys.argv[1:] if argv is None else argv)
    effective = _ensure_min_numeric_arg(
        effective, "--evidence-queue-size", DEFAULT_TOTAL_RECALL
    )
    parsed = base.build_parser().parse_args(effective)
    install_industry_balanced_policy()
    exit_code = base.main(effective)
    report_dir = Path(parsed.output_dir) if parsed.output_dir else _latest_report_dir()
    audit = _postprocess(report_dir)
    print("industry_balanced_recall=" + json.dumps(audit, ensure_ascii=False, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
