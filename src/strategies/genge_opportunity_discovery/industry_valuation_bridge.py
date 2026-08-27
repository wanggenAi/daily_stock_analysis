"""Build an industry-aware source pool for reverse valuation research.

The global channel keeps the existing broad-recall leaders. A second channel
adds the best research-eligible names from every represented industry. Durable
research recall combines the static research pool with Active candidates from
``V31_CANDIDATE_LEDGER.md`` so old hard-logic names are continuously
re-underwritten instead of being forgotten by a bounded recall budget.
Archived/INVALIDATED ledger names are excluded from ordinary recall and cannot
auto-revive without an explicit evidence-backed ledger reactivation. Original
blockers are never erased and this module never grants Formal BUY status.
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
from pathlib import Path
from typing import Any, Iterable, Mapping

from src.strategies.genge_opportunity_discovery.industry_coverage import (
    find_latest_report,
)
from src.strategies.genge_opportunity_discovery.valuation_research_report import (
    RELAXABLE_TECHNICAL_BLOCKERS,
    select_wide_recall_rows,
)


def _code(row: Mapping[str, Any]) -> str:
    text = str(row.get("code") or "").strip().upper()
    if "." in text:
        base, suffix = text.rsplit(".", 1)
        if suffix in {"SH", "SZ", "BJ"}:
            text = base
    for prefix in ("SH", "SZ", "BJ"):
        if text.startswith(prefix) and text[len(prefix):].isdigit():
            text = text[len(prefix):]
            break
    return text.zfill(6) if text.isdigit() else text


def _read(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _blockers(row: Mapping[str, Any]) -> set[str]:
    value = row.get("hard_blockers") or row.get("hard_reject_blockers") or ""
    return {token.strip() for token in str(value).split(";") if token.strip()}


def _hard_blocked(row: Mapping[str, Any]) -> bool:
    """Only non-relaxable blockers may stop pre-valuation research recall."""
    return bool(_blockers(row) - RELAXABLE_TECHNICAL_BLOCKERS)


def _industry_rank(row: Mapping[str, Any]) -> int:
    try:
        return int(float(row.get("industry_research_rank") or 10**9))
    except (TypeError, ValueError):
        return 10**9


def _read_curated_codes(path: Path | None) -> set[str]:
    if path is None or not path.exists():
        return set()
    codes: set[str] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        value = raw.split("#", 1)[0].strip()
        if not value:
            continue
        code = _code({"code": value})
        if code:
            codes.add(code)
    return codes


def _read_candidate_ledger_codes(path: Path | None) -> tuple[set[str], set[str]]:
    """Return Active and Archived/INVALIDATED codes from the durable ledger.

    Only ``###`` stock headings inside the canonical Active/Archived sections
    are parsed. The CURRENT DEEP RESEARCH QUEUE and research-only observations
    are intentionally ignored so the ledger has one unambiguous lifecycle
    source for recall/exclusion semantics.
    """
    if path is None or not path.exists():
        return set(), set()

    active: set[str] = set()
    invalidated: set[str] = set()
    section: str | None = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line == "## Active candidate ledger":
            section = "active"
            continue
        if line.startswith("## Archived") or line.startswith("## INVALIDATED"):
            section = "invalidated"
            continue
        if line.startswith("## "):
            section = None
            continue
        if not line.startswith("### ") or section is None:
            continue
        token = line[4:].split(None, 1)[0]
        code = _code({"code": token})
        if len(code) != 6 or not code.isdigit():
            continue
        if section == "active":
            active.add(code)
        else:
            invalidated.add(code)

    return active - invalidated, invalidated


def _merge_industry_provenance(target: dict[str, Any], industry_row: Mapping[str, Any]) -> None:
    """Fill missing industry-recall provenance on an existing global row."""
    for key in (
        "industry",
        "normalized_industry",
        "raw_industry",
        "industry_research_rank",
        "industry_candidate_state",
        "industry_status",
    ):
        current = str(target.get(key) or "").strip()
        incoming = str(industry_row.get(key) or "").strip()
        if incoming and (not current or current == "UNCLASSIFIED"):
            target[key] = industry_row.get(key)


def _mark_research_only(row: dict[str, Any]) -> None:
    row["formal_signal_eligible"] = False
    row["automatic_promotion_allowed"] = False
    row["no_auto_trade"] = True


def merge_sources(
    all_a_rows: Iterable[Mapping[str, Any]],
    industry_rows: Iterable[Mapping[str, Any]],
    *,
    global_limit: int = 80,
    relaxed_reserve: int = 20,
    per_industry: int = 3,
    curated_codes: Iterable[str] = (),
    excluded_codes: Iterable[str] = (),
) -> list[dict[str, Any]]:
    """Return global + industry + durable curated research recall.

    ``excluded_codes`` is a lifecycle veto used for Archived/INVALIDATED ledger
    names. It overrides every ordinary source channel, including static curated
    recall, so an invalidated candidate cannot silently auto-revive. Curated
    recall remains research-only and never overrides downstream V3.1 gates.
    """
    all_a = [dict(row) for row in all_a_rows]
    excluded = {_code({"code": value}) for value in excluded_codes}
    excluded.discard("")

    global_selected = select_wide_recall_rows(
        all_a,
        research_limit=max(0, int(global_limit)),
        relaxed_reserve=max(0, int(relaxed_reserve)),
    )

    merged: list[dict[str, Any]] = []
    by_code: dict[str, dict[str, Any]] = {}
    for raw in global_selected:
        code = _code(raw)
        if not code or code in excluded or code in by_code:
            continue
        row = dict(raw)
        row["code"] = code
        row["valuation_source_channel"] = "GLOBAL_RECALL"
        _mark_research_only(row)
        merged.append(row)
        by_code[code] = row

    keep = max(1, int(per_industry))
    industry_selected = [
        dict(row)
        for row in industry_rows
        if _industry_rank(row) <= keep and not _hard_blocked(row)
    ]
    for raw in industry_selected:
        code = _code(raw)
        if not code or code in excluded:
            continue
        if code in by_code:
            existing = by_code[code]
            existing["valuation_source_channel"] = "BOTH"
            _merge_industry_provenance(existing, raw)
            _mark_research_only(existing)
            continue
        row = dict(raw)
        row["code"] = code
        row["valuation_source_channel"] = "INDUSTRY_CHAMPION"
        _mark_research_only(row)
        merged.append(row)
        by_code[code] = row

    requested = {_code({"code": value}) for value in curated_codes}
    requested.discard("")
    requested -= excluded
    for raw in all_a:
        code = _code(raw)
        if not code or code not in requested:
            continue
        if code in by_code:
            existing = by_code[code]
            existing["curated_research_recall"] = True
            existing["curated_research_reason"] = "DURABLE_V31_RESEARCH_POOL"
            _mark_research_only(existing)
            continue
        row = dict(raw)
        row["code"] = code
        row["valuation_source_channel"] = "CURATED_RESEARCH_POOL"
        row["curated_research_recall"] = True
        row["curated_research_reason"] = "DURABLE_V31_RESEARCH_POOL"
        row["wide_recall_reason"] = "CURATED_DURABLE_RESEARCH"
        row["source_hard_blockers"] = (
            row.get("hard_blockers") or row.get("hard_reject_blockers") or ""
        )
        _mark_research_only(row)
        merged.append(row)
        by_code[code] = row
    return merged


def _find_all_a_report(root: Path) -> Path:
    """Resolve the same canonical All-A report used by industry coverage."""
    return find_latest_report(root)


def _read_all_a(report: Path) -> list[dict[str, Any]]:
    for name in ("all_a_quant_screen.csv", "quant_screen_all.csv", "top80_evidence_queue.csv"):
        rows = _read(report / name)
        if rows:
            return rows
    return []


def write_merged_report(
    all_a_report: Path,
    industry_coverage: Path,
    output_dir: Path,
    *,
    global_limit: int = 80,
    relaxed_reserve: int = 20,
    per_industry: int = 3,
    curated_pool: Path | None = None,
    candidate_ledger: Path | None = Path("V31_CANDIDATE_LEDGER.md"),
) -> list[dict[str, Any]]:
    report = _find_all_a_report(all_a_report)
    all_a_rows = _read_all_a(report)
    industry_rows = _read(industry_coverage / "industry_top_candidates.csv")
    if not all_a_rows:
        raise FileNotFoundError("missing global All-A source")
    if not industry_rows:
        raise FileNotFoundError("missing industry coverage source")

    static_curated_codes = _read_curated_codes(curated_pool)
    ledger_active_codes, ledger_invalidated_codes = _read_candidate_ledger_codes(candidate_ledger)
    curated_codes = static_curated_codes | ledger_active_codes
    rows = merge_sources(
        all_a_rows,
        industry_rows,
        global_limit=global_limit,
        relaxed_reserve=relaxed_reserve,
        per_industry=per_industry,
        curated_codes=curated_codes,
        excluded_codes=ledger_invalidated_codes,
    )

    for row in rows:
        code = _code(row)
        if code in ledger_active_codes:
            row["ledger_candidate_recall"] = True
            row["ledger_candidate_state"] = "ACTIVE"
            _mark_research_only(row)

    output_dir.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with (output_dir / "all_a_quant_screen.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    for summary_name in ("run_summary.json", "quant_screen_summary.json"):
        source = report / summary_name
        if source.exists():
            shutil.copy2(source, output_dir / summary_name)
            break

    covered_industries = {
        str(row.get("industry") or "").strip()
        for row in industry_rows
        if str(row.get("industry") or "").strip()
    }
    selected_industries = {
        str(row.get("industry") or "").strip()
        for row in rows
        if (
            "INDUSTRY_CHAMPION" in str(row.get("valuation_source_channel") or "")
            or row.get("valuation_source_channel") == "BOTH"
        )
        and str(row.get("industry") or "").strip()
    }
    source_codes = {_code(row) for row in all_a_rows}
    found_curated = sorted(curated_codes & source_codes)
    missing_curated = sorted(curated_codes - source_codes)
    found_ledger = sorted(ledger_active_codes & source_codes)
    missing_ledger = sorted(ledger_active_codes - source_codes)
    summary = {
        "merged_count": len(rows),
        "global_limit": int(global_limit),
        "relaxed_reserve": int(relaxed_reserve),
        "per_industry_valuation_slots": int(per_industry),
        "represented_industry_count": len(covered_industries),
        "industries_with_clean_valuation_candidate_count": len(selected_industries),
        "global_only_count": sum(r.get("valuation_source_channel") == "GLOBAL_RECALL" for r in rows),
        "industry_only_count": sum(r.get("valuation_source_channel") == "INDUSTRY_CHAMPION" for r in rows),
        "both_count": sum(r.get("valuation_source_channel") == "BOTH" for r in rows),
        "curated_pool_requested_count": len(curated_codes),
        "curated_pool_found_count": len(found_curated),
        "curated_research_recall_count": sum(bool(r.get("curated_research_recall")) for r in rows),
        "curated_only_count": sum(r.get("valuation_source_channel") == "CURATED_RESEARCH_POOL" for r in rows),
        "curated_pool_missing_codes": missing_curated,
        "static_curated_pool_requested_count": len(static_curated_codes),
        "ledger_active_candidate_count": len(ledger_active_codes),
        "ledger_invalidated_exclusion_count": len(ledger_invalidated_codes),
        "ledger_active_found_count": len(found_ledger),
        "ledger_active_missing_codes": missing_ledger,
        "ledger_invalidated_suppressed_codes": sorted(ledger_invalidated_codes & source_codes),
        "formal_signal_eligible": False,
        "automatic_promotion_allowed": False,
        "no_auto_trade": True,
    }
    (output_dir / "industry_valuation_source_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all-a-report", type=Path, required=True)
    parser.add_argument("--industry-coverage", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--global-limit", type=int, default=80)
    parser.add_argument("--relaxed-reserve", type=int, default=20)
    parser.add_argument("--per-industry", type=int, default=3)
    parser.add_argument(
        "--curated-pool",
        type=Path,
        default=Path("stock_pools/genge_v31_research_pool.txt"),
    )
    parser.add_argument(
        "--candidate-ledger",
        type=Path,
        default=Path("V31_CANDIDATE_LEDGER.md"),
    )
    args = parser.parse_args(argv)
    rows = write_merged_report(
        args.all_a_report,
        args.industry_coverage,
        args.output_dir,
        global_limit=args.global_limit,
        relaxed_reserve=args.relaxed_reserve,
        per_industry=args.per_industry,
        curated_pool=args.curated_pool,
        candidate_ledger=args.candidate_ledger,
    )
    print(f"industry_valuation_source={args.output_dir};count={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
