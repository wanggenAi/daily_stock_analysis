"""Industry-balanced launcher for reverse-valuation research.

The original reverse-valuation implementation is reused for PE diagnostics,
point-in-time financial selection and earnings-quality normalization. Research
recall and deep-financial budgeting are industry-protected so global Top-N
competition cannot erase an otherwise eligible industry before valuation work.

This is deliberately a sidecar over the completed All-A quant screen. It does
not change the execution-oriented All-A queue, exit-profile refresh, Formal BUY,
position sizing, stops, or trading lifecycle.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping

from src.strategies.genge_opportunity_discovery import valuation_research_report as base
from src.strategies.genge_opportunity_discovery.industry_balanced_recall import (
    IndustryRecallPolicy,
    coverage_audit,
    industry_leaders,
    select_industry_balanced_rows,
)

DEFAULT_TOTAL_RECALL = 260
DEFAULT_GLOBAL_SEED = 80
DEFAULT_PER_INDUSTRY_TARGET = 3


def _normalize_code(value: Any) -> str:
    text = str(value or "").strip()
    return text.zfill(6) if text.isdigit() else text


def _industry(row: Mapping[str, Any]) -> str:
    return str(
        row.get("industry")
        or row.get("normalized_industry")
        or row.get("raw_industry")
        or "UNRESOLVED"
    ).strip() or "UNRESOLVED"


def _annotated_candidates(
    source_rows: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Apply the existing wide-recall safety policy before industry balancing."""

    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in source_rows:
        code = base._normalize_code(raw.get("code"))
        if not code or code in seen:
            continue
        reason = base._wide_recall_reason(raw)
        if reason is None:
            continue
        row = dict(raw)
        row["code"] = code
        row["wide_recall_reason"] = reason
        row["source_hard_blockers"] = (
            row.get("hard_blockers") or row.get("hard_reject_blockers") or ""
        )
        result.append(row)
        seen.add(code)
    return result


def _balanced_select(
    source_rows: Iterable[Mapping[str, Any]],
    *,
    research_limit: int = base.DEFAULT_RESEARCH_LIMIT,
    relaxed_reserve: int = base.DEFAULT_RELAXED_RESERVE,
) -> list[dict[str, Any]]:
    """Union global leaders with protected per-industry candidates.

    ``relaxed_reserve`` remains accepted for CLI/backward compatibility, but it
    is no longer allowed to erase an entire industry from *research*. The base
    `_wide_recall_reason` still decides which technical hard blockers are safe
    to recover for research and which true hard risks remain excluded. Once a
    row passes that boundary, industry recall ranks it by original quant merit
    rather than by its former screening-status label.
    """

    del relaxed_reserve
    candidates = _annotated_candidates(source_rows)
    return select_industry_balanced_rows(
        candidates,
        policy=IndustryRecallPolicy(
            total_limit=max(DEFAULT_TOTAL_RECALL, int(research_limit)),
            global_seed=DEFAULT_GLOBAL_SEED,
            per_industry_target=DEFAULT_PER_INDUSTRY_TARGET,
        ),
        eligibility=lambda row: True,
        order_key=base._quant_order_key,
    )


def _financial_review_codes(
    provisional_rows: Iterable[Mapping[str, Any]], *, global_limit: int,
) -> list[str]:
    """Keep the global deep-financial budget and add one PE-usable row per industry."""

    applicable = [
        dict(row) for row in provisional_rows
        if row.get("valuation_diagnostic_status") == "OK"
    ]
    applicable.sort(key=base._rank_key)
    global_codes = [
        base._normalize_code(row.get("code"))
        for row in applicable[: max(0, int(global_limit))]
    ]
    industry_codes: list[str] = []
    seen_industries: set[str] = set()
    for row in applicable:
        industry = _industry(row)
        if industry in seen_industries:
            continue
        seen_industries.add(industry)
        industry_codes.append(base._normalize_code(row.get("code")))
    return list(dict.fromkeys([*global_codes, *industry_codes]))


def _balanced_build_valuation_research_rows(
    source_rows: Iterable[Mapping[str, Any]],
    *,
    as_of,
    loader,
    research_limit: int = base.DEFAULT_RESEARCH_LIMIT,
    relaxed_reserve: int = base.DEFAULT_RELAXED_RESERVE,
    financial_review_limit: int = base.DEFAULT_FINANCIAL_REVIEW_LIMIT,
    minimum_pe_samples: int = 1,
    years: int = 5,
    max_workers: int = 1,
) -> list[dict[str, Any]]:
    selected = _balanced_select(
        source_rows,
        research_limit=research_limit,
        relaxed_reserve=relaxed_reserve,
    )
    valuation_results = base._load_many(
        loader,
        [row.get("code") for row in selected],
        years=years,
        fetch_valuation=True,
        fetch_financial=False,
        max_workers=max_workers,
    )
    provisional: list[dict[str, Any]] = []
    for source in selected:
        code = base._normalize_code(source.get("code"))
        fetched = valuation_results.get(code)
        valuation_frame = (
            None
            if isinstance(fetched, Exception) or fetched is None
            else fetched.valuation_df
        )
        pe_diag = base.build_pe_reference_diagnostic(
            valuation_frame,
            as_of=as_of,
            minimum_history_samples=minimum_pe_samples,
        )
        provisional.append(base._base_row(source, pe_diag))

    provisional.sort(key=base._rank_key)
    financial_codes = _financial_review_codes(
        provisional,
        global_limit=financial_review_limit,
    )
    financial_results = base._load_many(
        loader,
        financial_codes,
        years=years,
        fetch_valuation=False,
        fetch_financial=True,
        max_workers=max_workers,
    )

    reviewed: list[dict[str, Any]] = []
    financial_code_set = set(financial_codes)
    for row in provisional:
        code = base._normalize_code(row.get("code"))
        if code not in financial_code_set:
            reviewed.append(dict(row))
            continue
        fetched = financial_results.get(code)
        financial_frame = (
            None
            if isinstance(fetched, Exception) or fetched is None
            else fetched.financial_df
        )
        reviewed.append(base._add_financial_review(row, financial_frame, as_of=as_of))

    reviewed.sort(key=base._rank_key)
    for rank, row in enumerate(reviewed, 1):
        row["valuation_research_rank"] = rank
    return reviewed


def install_industry_balanced_policy() -> None:
    base.select_wide_recall_rows = _balanced_select
    base.build_valuation_research_rows = _balanced_build_valuation_research_rows


def _read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def _write_csv(path: Path, rows: list[Mapping[str, Any]]) -> None:
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


def _find_output_run(output_root: Path, report_dir: Path) -> Path:
    if output_root.exists():
        candidates = [
            path for path in output_root.iterdir()
            if path.is_dir() and (path / "valuation_research_summary.json").exists()
        ]
        if candidates:
            return max(
                candidates,
                key=lambda path: (
                    path / "valuation_research_summary.json"
                ).stat().st_mtime,
            )
    if (report_dir / "valuation_research_summary.json").exists():
        return report_dir
    raise FileNotFoundError("valuation research summary not found after run")


def _postprocess(
    *, source_report_dir: Path, output_run_dir: Path,
) -> dict[str, Any]:
    source_rows = _read_csv(source_report_dir / "all_a_quant_screen.csv")
    if not source_rows:
        source_rows = _read_csv(source_report_dir / "quant_screen_all.csv")
    selected_rows = _read_csv(output_run_dir / "valuation_research_queue.csv")
    annotated = _annotated_candidates(source_rows)
    audit = coverage_audit(
        annotated,
        selected_rows,
        eligibility=lambda row: True,
        order_key=base._quant_order_key,
    )
    audit.update(
        {
            "policy_version": "industry_balanced_valuation_recall_v1",
            "global_seed": DEFAULT_GLOBAL_SEED,
            "per_industry_target": DEFAULT_PER_INDUSTRY_TARGET,
            "configured_total_recall_floor": DEFAULT_TOTAL_RECALL,
            "formal_signal_eligible": False,
            "automatic_promotion_allowed": False,
            "no_auto_trade": True,
        }
    )
    if not audit["all_eligible_industries_covered"]:
        raise RuntimeError(
            "valuation industry coverage invariant failed: "
            f"{audit['missing_eligible_industries']}"
        )

    selected_meta = {
        _normalize_code(row.get("code")): row
        for row in _balanced_select(
            source_rows,
            research_limit=DEFAULT_TOTAL_RECALL,
            relaxed_reserve=base.DEFAULT_RELAXED_RESERVE,
        )
    }
    enriched: list[dict[str, Any]] = []
    for row in selected_rows:
        code = _normalize_code(row.get("code"))
        meta = selected_meta.get(code, {})
        enriched.append(
            {
                **row,
                "research_recall_sources": meta.get("research_recall_sources", ""),
                "industry_recall_rank": meta.get("industry_recall_rank", ""),
                "global_recall_rank": meta.get("global_recall_rank", ""),
                "industry_recall_guaranteed": meta.get(
                    "industry_recall_guaranteed", False
                ),
            }
        )

    leaders = industry_leaders(
        annotated,
        per_industry=1,
        eligibility=lambda row: True,
        order_key=base._quant_order_key,
    )
    top3 = industry_leaders(
        annotated,
        per_industry=DEFAULT_PER_INDUSTRY_TARGET,
        eligibility=lambda row: True,
        order_key=base._quant_order_key,
    )
    _write_csv(output_run_dir / "valuation_research_industry_balanced.csv", enriched)
    _write_csv(output_run_dir / "industry_leaders.csv", leaders)
    _write_csv(output_run_dir / "industry_candidate_pool_top3.csv", top3)
    (output_run_dir / "valuation_industry_coverage_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    summary_path = output_run_dir / "valuation_research_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["industry_balanced_recall"] = audit
    summary["canonical_research_queue_file"] = (
        "valuation_research_industry_balanced.csv"
    )
    summary["industry_leader_count"] = len(leaders)
    summary["industry_candidate_pool_top3_count"] = len(top3)
    summary["industry_recall_ordering"] = (
        "wide-recall safety first; then original quant_rank/quant_score within research"
    )
    summary["financial_review_semantics"] = (
        "global financial-review budget plus one PE-usable representative per industry"
    )
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
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
        effective, "--research-limit", DEFAULT_TOTAL_RECALL
    )
    report_root: Path | None = None
    report_dir: Path | None = None
    output_root: Path | None = None
    for index, item in enumerate(effective):
        if item == "--report-root" and index + 1 < len(effective):
            report_root = Path(effective[index + 1])
        elif item == "--report-dir" and index + 1 < len(effective):
            report_dir = Path(effective[index + 1])
        elif item == "--output-dir" and index + 1 < len(effective):
            output_root = Path(effective[index + 1])

    install_industry_balanced_policy()
    exit_code = base.main(effective)
    source = report_dir or base.find_latest_report(report_root or Path("."))
    output_run = _find_output_run(output_root or source, source)
    audit = _postprocess(source_report_dir=source, output_run_dir=output_run)
    print(
        "valuation_industry_balanced_recall="
        + json.dumps(audit, ensure_ascii=False, sort_keys=True)
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
