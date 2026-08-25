"""Build an industry-aware source pool for reverse valuation research.

The global channel keeps the existing broad-recall leaders. A second channel
adds the best research-eligible names from every represented industry. An
optional durable curated channel guarantees that already deep-researched names
cannot disappear merely because a bounded quant/technical recall budget is
exhausted. Original blockers are never erased and this module never grants
Formal BUY status.
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


def _merge_industry_provenance(target: dict[str, Any], industry_row: Mapping[str, Any]) -> None:
    """Fill missing industry-recall provenance on an existing global row.

    A name can enter the valuation source through global recall before the
    industry channel sees it. In that case the global row may not carry the
    normalized ``industry`` column. Marking the row ``BOTH`` without copying
    the industry provenance makes downstream coverage validation incorrectly
    conclude that the industry disappeared even though its champion is present.
    Only missing provenance is filled; global ranking/valuation fields and hard
    blockers are never overwritten.
    """
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
) -> list[dict[str, Any]]:
    """Return global + industry + durable curated research recall.

    Curated recall is deliberately not a score override. It only ensures the
    row reaches valuation/V3.1 review. Original quant status, price/technical
    blockers, true hard blockers and all downstream frozen gates remain intact.
    """
    all_a = [dict(row) for row in all_a_rows]
    global_selected = select_wide_recall_rows(
        all_a,
        research_limit=max(0, int(global_limit)),
        relaxed_reserve=max(0, int(relaxed_reserve)),
    )

    merged: list[dict[str, Any]] = []
    by_code: dict[str, dict[str, Any]] = {}
    for raw in global_selected:
        code = _code(raw)
        if not code or code in by_code:
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
        if not code:
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
    """Resolve the same canonical All-A report used by industry coverage.

    Production artifacts contain both the full dated All-A screen and nested
    deep-review ``quant_screen_all.csv`` files. A union-of-filenames followed by
    lexicographic sorting can incorrectly select the nested bounded review. The
    canonical resolver prioritizes ``all_a_quant_screen.csv`` and its production
    ``run_summary.json`` so durable research recall is matched against the full
    universe rather than a downstream sample.
    """
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
) -> list[dict[str, Any]]:
    report = _find_all_a_report(all_a_report)
    all_a_rows = _read_all_a(report)
    industry_rows = _read(industry_coverage / "industry_top_candidates.csv")
    if not all_a_rows:
        raise FileNotFoundError("missing global All-A source")
    if not industry_rows:
        raise FileNotFoundError("missing industry coverage source")

    curated_codes = _read_curated_codes(curated_pool)
    rows = merge_sources(
        all_a_rows,
        industry_rows,
        global_limit=global_limit,
        relaxed_reserve=relaxed_reserve,
        per_industry=per_industry,
        curated_codes=curated_codes,
    )
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
    args = parser.parse_args(argv)
    rows = write_merged_report(
        args.all_a_report,
        args.industry_coverage,
        args.output_dir,
        global_limit=args.global_limit,
        relaxed_reserve=args.relaxed_reserve,
        per_industry=args.per_industry,
        curated_pool=args.curated_pool,
    )
    print(f"industry_valuation_source={args.output_dir};count={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())