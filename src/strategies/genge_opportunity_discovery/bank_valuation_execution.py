"""Execute bank residual-income/PB valuation from PIT-safe public inputs.

This research-only sidecar uses the same conservative public P/B and annual-ROE
history already used by the broker executor, but applies the bank-specific
residual-income bridge.  It works in normalized book-value units (BVPS=1,
price=current P/B), so no synthetic share count or total-equity substitution is
needed.  Missing P/B or fewer than the configured number of annual ROE samples
remain INPUTS_REQUIRED.  Nothing here creates Formal BUY or automatic trading.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any, Mapping

from src.strategies.genge_cycle_bottom.fundamentals import PublicFundamentalLoader
from src.strategies.genge_opportunity_discovery.bank_valuation import value_bank_common_equity
from src.strategies.genge_opportunity_discovery.specialized_valuation_execution import (
    DEFAULT_COST_OF_EQUITY,
    DEFAULT_LONG_TERM_GROWTH,
    DEFAULT_MAX_ANNUAL_ROE_SAMPLES,
    DEFAULT_MIN_ANNUAL_ROE_SAMPLES,
    ROE_INPUT_BASIS,
    _annual_roe_history,
    _latest_positive_pb,
    _normalize_code,
)

DISCLAIMER = "仅用于公开数据研究排序和人工复核，不构成买入或卖出建议，不应自动交易。"
BANK_STRATEGY_ID = "bank_residual_income"
CACHE_NAMESPACE = "bank_execution_v1"

OUTPUT_COLUMNS = [
    "bank_model_executed", "bank_model_state", "bank_model_status",
    "bank_current_pb", "bank_current_pb_date", "bank_mid_cycle_roe",
    "bank_roe_sample_count", "bank_roe_years", "bank_cost_of_equity",
    "bank_long_term_growth", "bank_fair_pb", "bank_implied_roe",
    "bank_expectation_gap_roe", "bank_margin_of_safety", "bank_next_action",
]


def _latest_report_dir(root: Path) -> Path:
    if (root / "valuation_research_routed.csv").exists():
        return root
    candidates = sorted(
        {p.parent for p in root.glob("**/valuation_research_routed.csv") if p.is_file()},
        key=str,
    )
    if not candidates:
        raise FileNotFoundError(f"no valuation_research_routed.csv under {root}")
    return candidates[-1]


def _read_as_of(report_dir: Path) -> date:
    payload = json.loads((report_dir / "valuation_research_summary.json").read_text(encoding="utf-8"))
    text = str(payload.get("as_of_date") or "").strip()
    if not text:
        raise ValueError("valuation research as_of_date is unavailable")
    return date.fromisoformat(text)


def execute_rows(
    rows: list[Mapping[str, Any]],
    *,
    as_of: date,
    loader: PublicFundamentalLoader,
    years: int = 7,
    minimum_annual_roe_samples: int = DEFAULT_MIN_ANNUAL_ROE_SAMPLES,
    maximum_annual_roe_samples: int = DEFAULT_MAX_ANNUAL_ROE_SAMPLES,
    cost_of_equity: float = DEFAULT_COST_OF_EQUITY,
    long_term_growth: float = DEFAULT_LONG_TERM_GROWTH,
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for raw in rows:
        row = dict(raw)
        row.update({
            "bank_model_executed": False,
            "bank_model_state": "NOT_BANK_ROUTE",
            "bank_model_status": "",
            "bank_current_pb": "",
            "bank_current_pb_date": "",
            "bank_mid_cycle_roe": "",
            "bank_roe_sample_count": "",
            "bank_roe_years": "",
            "bank_cost_of_equity": "",
            "bank_long_term_growth": "",
            "bank_fair_pb": "",
            "bank_implied_roe": "",
            "bank_expectation_gap_roe": "",
            "bank_margin_of_safety": "",
            "bank_next_action": "",
            "formal_signal_eligible": False,
            "automatic_promotion_allowed": False,
            "no_auto_trade": True,
            "disclaimer": DISCLAIMER,
        })
        if str(row.get("valuation_primary_strategy_id") or "") != BANK_STRATEGY_ID:
            output.append(row)
            continue

        code = _normalize_code(row.get("code"))
        try:
            fetched = loader.load(code, years=max(5, int(years)), fetch_valuation=True, fetch_financial=True)
        except Exception as exc:
            row.update({
                "bank_model_state": "INPUTS_REQUIRED",
                "bank_model_status": "PUBLIC_FUNDAMENTAL_LOAD_FAILED",
                "bank_next_action": f"retry_public_inputs:{type(exc).__name__}",
            })
            output.append(row)
            continue

        current_pb, pb_date = _latest_positive_pb(fetched.valuation_df, as_of=as_of)
        roe = _annual_roe_history(
            fetched.financial_df,
            as_of=as_of,
            max_samples=maximum_annual_roe_samples,
        )
        row.update({
            "bank_current_pb": current_pb if current_pb is not None else "",
            "bank_current_pb_date": pb_date,
            "bank_mid_cycle_roe": roe.median if roe.median is not None else "",
            "bank_roe_sample_count": len(roe.values),
            "bank_roe_years": ";".join(str(y) for y in roe.years),
            "bank_cost_of_equity": cost_of_equity,
            "bank_long_term_growth": long_term_growth,
        })

        missing: list[str] = []
        if current_pb is None:
            missing.append("current_pb_unavailable")
        if len(roe.values) < max(1, int(minimum_annual_roe_samples)):
            missing.append("insufficient_pit_safe_annual_roe_history")
        if cost_of_equity <= long_term_growth:
            missing.append("invalid_cost_of_equity_growth_relation")
        if missing:
            row.update({
                "bank_model_state": "INPUTS_REQUIRED",
                "bank_model_status": "BANK_PUBLIC_INPUTS_INCOMPLETE",
                "bank_next_action": ";".join(missing),
            })
            output.append(row)
            continue

        assert current_pb is not None and roe.median is not None
        model = value_bank_common_equity(
            common_bvps=1.0,
            sustainable_roe=roe.median,
            cost_of_equity=cost_of_equity,
            long_term_growth=long_term_growth,
            current_price=current_pb,
            current_common_pb=current_pb,
        )
        expectation_gap = (
            None if model.implied_sustainable_roe is None
            else roe.median - model.implied_sustainable_roe
        )
        row.update({
            "bank_model_executed": True,
            "bank_model_state": "EXECUTED_RESEARCH_ONLY" if model.valuation_model_applicable else "EXECUTED_FAIL_CLOSED",
            "bank_model_status": model.status,
            "bank_fair_pb": model.fair_common_pb if model.fair_common_pb is not None else "",
            "bank_implied_roe": model.implied_sustainable_roe if model.implied_sustainable_roe is not None else "",
            "bank_expectation_gap_roe": expectation_gap if expectation_gap is not None else "",
            "bank_margin_of_safety": model.margin_of_safety if model.margin_of_safety is not None else "",
            "bank_next_action": "review_asset_quality_cet1_npl_nim_before_any_formal_decision",
        })
        output.append(row)
    return output


def write_report(
    report_root: Path,
    *,
    cache_dir: Path,
    years: int,
    minimum_annual_roe_samples: int,
    maximum_annual_roe_samples: int,
    cost_of_equity: float,
    long_term_growth: float,
) -> dict[str, Any]:
    report_dir = _latest_report_dir(report_root)
    with (report_dir / "valuation_research_routed.csv").open(encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        fields = list(reader.fieldnames or [])
        rows = list(reader)
    as_of = _read_as_of(report_dir)
    loader = PublicFundamentalLoader(cache_dir=Path(cache_dir) / CACHE_NAMESPACE)
    executed = execute_rows(
        rows,
        as_of=as_of,
        loader=loader,
        years=years,
        minimum_annual_roe_samples=minimum_annual_roe_samples,
        maximum_annual_roe_samples=maximum_annual_roe_samples,
        cost_of_equity=cost_of_equity,
        long_term_growth=long_term_growth,
    )
    out_fields = list(fields)
    for field in OUTPUT_COLUMNS + ["formal_signal_eligible", "automatic_promotion_allowed", "no_auto_trade", "disclaimer"]:
        if field not in out_fields:
            out_fields.append(field)
    with (report_dir / "bank_valuation_execution.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=out_fields, extrasaction="ignore")
        writer.writeheader(); writer.writerows(executed)
    selected = [r for r in executed if str(r.get("valuation_primary_strategy_id") or "") == BANK_STRATEGY_ID]
    counts = Counter(str(r.get("bank_model_state") or "") for r in selected)
    summary = {
        "as_of_date": as_of.isoformat(),
        "row_count": len(executed),
        "bank_selected_count": len(selected),
        "bank_executed_count": sum(bool(r.get("bank_model_executed")) for r in selected),
        "bank_state_counts": dict(sorted(counts.items())),
        "input_basis": f"PB_DAILY_PIT;{ROE_INPUT_BASIS};MEDIAN_PIT_SAFE_ANNUAL_ROE;NORMALIZED_BOOK_UNITS",
        "cost_of_equity_assumption": cost_of_equity,
        "long_term_growth_assumption": long_term_growth,
        "formal_signal_eligible": False,
        "automatic_promotion_allowed": False,
        "no_auto_trade": True,
        "disclaimer": DISCLAIMER,
    }
    (report_dir / "bank_valuation_execution_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-root", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, default=Path("data/cache/valuation_research_fundamentals"))
    parser.add_argument("--years", type=int, default=7)
    parser.add_argument("--minimum-annual-roe-samples", type=int, default=3)
    parser.add_argument("--maximum-annual-roe-samples", type=int, default=5)
    parser.add_argument("--cost-of-equity", type=float, default=DEFAULT_COST_OF_EQUITY)
    parser.add_argument("--long-term-growth", type=float, default=DEFAULT_LONG_TERM_GROWTH)
    args = parser.parse_args(argv)
    summary = write_report(
        args.report_root,
        cache_dir=args.cache_dir,
        years=args.years,
        minimum_annual_roe_samples=args.minimum_annual_roe_samples,
        maximum_annual_roe_samples=args.maximum_annual_roe_samples,
        cost_of_equity=args.cost_of_equity,
        long_term_growth=args.long_term_growth,
    )
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
