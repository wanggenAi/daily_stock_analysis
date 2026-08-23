"""Build the frozen V3.1 deep-review queue after broad All-A recall.

This module intentionally does NOT infer qualitative hard gates from legacy
scores, technical signals or cheap valuation. It joins machine-generated
financial/valuation diagnostics to the research shortlist, pre-fills only facts
that preserve their original semantics, and leaves judgement-heavy V3.1 fields
blank/UNKNOWN for evidence-backed deep research.

Pipeline semantics:
    broad recall -> V3.1 deep review -> A1/A2/A3 -> valuation/buy decision

The queue is a research hand-off, never a trade authorization.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from src.strategies.genge_opportunity_discovery import selection_framework_v31

DISCLAIMER = "仅用于公开数据研究与人工复核，不构成买入或卖出建议，不应自动交易。"
POLICY_VERSION = "v31_deep_review_queue_v1"

JUDGEMENT_FIELDS = (
    "v31_predictability_status",
    "v31_long_term_demand_status",
    "v31_moat_status",
    "v31_financial_safety_status",
    "v31_earnings_authenticity_status",
    "v31_candidate_class",
    "v31_score_long_term_demand",
    "v31_score_moat_direction",
    "v31_score_earnings_quality",
    "v31_score_roic_incremental_roic",
    "v31_score_capital_allocation",
    "v31_score_growth_runway",
    "v31_score_normalized_earnings_certainty",
    "v31_score_expectation_gap",
    "v31_score_valuation_margin_of_safety",
    "v31_score_market_position",
    "v31_pessimistic_value",
    "v31_neutral_value",
    "v31_optimistic_value",
    "v31_extreme_stress_value",
    "v31_market_implied_profit_cagr",
    "v31_realistic_profit_cagr",
    "v31_expectation_gap_pct",
    "v31_expectation_gap_thesis",
    "v31_risk_adjusted_3y_cagr",
    "v31_potential_max_fundamental_loss_pct",
    "v31_why_can_buy",
    "v31_strongest_bear_case",
    "v31_falsification_status",
    "v31_margin_of_safety_status",
    "v31_cagr_attractiveness_status",
    "v31_pessimistic_loss_status",
    "v31_portfolio_exposure_status",
    "v31_market_position_status",
)

PREFILL_FIELDS = (
    "v31_current_price",
    "v31_normalized_profit",
    "v31_normalized_profit_method",
)


def _read(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _code(value: Any) -> str:
    text = str(value or "").strip().upper()
    if "." in text:
        base, suffix = text.rsplit(".", 1)
        if suffix in {"SH", "SZ", "BJ"}:
            text = base
    for prefix in ("SH", "SZ", "BJ"):
        if text.startswith(prefix) and text[len(prefix):].isdigit():
            text = text[len(prefix):]
            break
    return text.zfill(6) if text.isdigit() else text


def _latest_valuation_dir(root: Path) -> Path:
    if (root / "valuation_research_routed.csv").exists():
        return root
    candidates = sorted(
        {p.parent for p in root.glob("**/valuation_research_routed.csv") if p.is_file()},
        key=str,
    )
    if not candidates:
        raise FileNotFoundError(f"no valuation_research_routed.csv under {root}")
    return candidates[-1]


def _latest_all_a_dir(root: Path) -> Path:
    if (root / "run_summary.json").exists():
        return root
    candidates = sorted(
        {p.parent for p in root.glob("**/run_summary.json") if p.is_file()},
        key=str,
    )
    if not candidates:
        raise FileNotFoundError(f"no All-A run_summary.json under {root}")
    return candidates[-1]


def _plan_map(report_dir: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for name in (
        "daily_candidate_top5.csv",
        "top30_deep_review.csv",
        "condition_watch.csv",
        "research_watch.csv",
        "tomorrow_watchlist.csv",
    ):
        for raw in _read(report_dir / name):
            code = _code(raw.get("code"))
            if not code:
                continue
            target = result.setdefault(code, {})
            for key, value in raw.items():
                if str(value or "").strip() and not str(target.get(key) or "").strip():
                    target[key] = value
    return result


def _rank_value(row: Mapping[str, Any]) -> tuple[int, str]:
    try:
        rank = int(float(row.get("valuation_research_rank") or 10**9))
    except (TypeError, ValueError):
        rank = 10**9
    return rank, _code(row.get("code"))


def build_review_rows(
    valuation_rows: Iterable[Mapping[str, Any]],
    *,
    plan_map: Mapping[str, Mapping[str, Any]],
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Create an explicit UNKNOWN-until-researched V3.1 queue.

    The only automatic prefills are direct semantic mappings:
    - current tradable price from the All-A plan
    - normalized core operating profit from financial review
    - the existing normalization method name

    In particular, financial/earnings scores are NOT converted into PASS/FAIL
    hard gates and reverse-PE growth is NOT relabelled as a V3.1 CAGR.
    """
    selected = sorted((dict(row) for row in valuation_rows if _code(row.get("code"))), key=_rank_value)
    rows: list[dict[str, Any]] = []
    for raw in selected[: max(0, int(limit))]:
        code = _code(raw.get("code"))
        plan = dict(plan_map.get(code) or {})
        row: dict[str, Any] = {
            "v31_review_rank": len(rows) + 1,
            "code": code,
            "stock_name": raw.get("stock_name") or plan.get("stock_name") or "",
            "industry": raw.get("industry") or plan.get("industry") or "",
            "valuation_research_rank": raw.get("valuation_research_rank") or "",
            "valuation_source_channel": raw.get("valuation_source_channel") or "",
            "quant_score": raw.get("quant_score") or plan.get("quant_score") or "",
            "valuation_diagnostic_status": raw.get("valuation_diagnostic_status") or "",
            "financial_review_status": raw.get("financial_review_status") or "",
            "earnings_quality_score_source": raw.get("earnings_quality_score") or "",
            "earnings_quality_confidence_source": raw.get("earnings_quality_confidence") or "",
            "required_profit_growth_vs_reference_source": raw.get("required_profit_growth_vs_reference") or "",
            "v31_current_price": plan.get("raw_latest_close") or "",
            "v31_normalized_profit": raw.get("normalized_core_operating_profit") or "",
            "v31_normalized_profit_method": raw.get("earnings_normalization_method") or "",
            "v31_review_status": "RESEARCH_REQUIRED",
            "v31_review_evidence_urls": "",
            "formal_signal_eligible": False,
            "automatic_promotion_allowed": False,
            "no_auto_trade": True,
            "review_policy_version": POLICY_VERSION,
            "disclaimer": DISCLAIMER,
        }
        for field in JUDGEMENT_FIELDS:
            row[field] = ""
        assessment = selection_framework_v31.assess_v31(row)
        row.update(assessment.as_dict())
        rows.append(row)
    return rows


def write_report(
    valuation_root: Path,
    all_a_report_root: Path,
    output_dir: Path,
    *,
    limit: int = 100,
) -> list[dict[str, Any]]:
    valuation_dir = _latest_valuation_dir(valuation_root)
    all_a_dir = _latest_all_a_dir(all_a_report_root)
    rows = build_review_rows(
        _read(valuation_dir / "valuation_research_routed.csv"),
        plan_map=_plan_map(all_a_dir),
        limit=limit,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    preferred = [
        "v31_review_rank", "code", "stock_name", "industry",
        "valuation_research_rank", "valuation_source_channel", "quant_score",
        "valuation_diagnostic_status", "financial_review_status",
        "earnings_quality_score_source", "earnings_quality_confidence_source",
        "required_profit_growth_vs_reference_source",
        *PREFILL_FIELDS,
        *JUDGEMENT_FIELDS,
        "v31_hard_gates_passed", "v31_hard_gate_failures", "v31_hard_gate_unknowns",
        "v31_score_total", "v31_score_complete", "v31_a_eligible", "v31_buy_ready",
        "v31_blockers", "v31_review_status", "v31_review_evidence_urls",
        "formal_signal_eligible", "automatic_promotion_allowed", "no_auto_trade",
        "review_policy_version", "disclaimer",
    ]
    extra = sorted({key for row in rows for key in row if key not in preferred})
    with (output_dir / "v31_review_queue.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=preferred + extra, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "candidate_count": len(rows),
        "research_required_count": sum(row.get("v31_review_status") == "RESEARCH_REQUIRED" for row in rows),
        "automatic_gate_inference_allowed": False,
        "formal_signal_eligible": False,
        "automatic_promotion_allowed": False,
        "no_auto_trade": True,
        "policy_version": POLICY_VERSION,
        "semantics": "broad recall to evidence-backed frozen V3.1 deep-review handoff",
    }
    (output_dir / "v31_review_queue_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = [
        "# Frozen V3.1 Deep Review Queue",
        "",
        "Broad recall is not A-grade qualification. Qualitative gates remain UNKNOWN until evidence-backed review.",
        "",
        f"- queued: {len(rows)}",
        "- automatic qualitative gate inference: disabled",
        "- automatic promotion/trading: disabled",
        "",
    ]
    for row in rows[:50]:
        lines.append(
            f"- #{row['v31_review_rank']} {row['code']} {row['stock_name']} | "
            f"{row['industry']} | valuation_rank={row['valuation_research_rank']} | "
            f"gate_unknowns={row['v31_hard_gate_unknowns']}"
        )
    (output_dir / "v31_review_queue.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--valuation-root", type=Path, required=True)
    parser.add_argument("--all-a-report-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args(argv)
    rows = write_report(
        args.valuation_root,
        args.all_a_report_root,
        args.output_dir,
        limit=args.limit,
    )
    print(f"v31_review_queue={args.output_dir};count={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
