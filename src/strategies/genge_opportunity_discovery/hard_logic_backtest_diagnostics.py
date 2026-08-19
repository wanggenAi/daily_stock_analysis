"""Diagnostics for the hard-logic historical walk-forward gate chain.

This is deliberately read-only: it does not alter entry/exit rules. It explains
why a data-ready company did or did not reach a historical BUY signal.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

from src.strategies.genge_cycle_bottom.features import prepare_price_frame
from src.strategies.genge_opportunity_discovery.hard_logic_historical_backtest import (
    BUY_DECISIONS,
    DEFAULT_STRIDE,
    MAX_ENTRY_PE_PERCENTILE,
    _finite,
    _price_map,
    fetch_case_data,
    load_cases,
    normalize_financial_point_in_time,
    point_in_time_hard_logic,
    point_in_time_valuation,
)


def diagnose_company(data, *, start_date: date, end_date: date, stride: int) -> dict[str, Any]:
    price = prepare_price_frame(data.price_df)
    price = price[(price["date"] >= start_date) & (price["date"] <= end_date)].reset_index(drop=True)
    financial = normalize_financial_point_in_time(data.financial_df)

    logic_states: Counter[str] = Counter()
    decisions: Counter[str] = Counter()
    first_examples: dict[str, Any] = {}
    evaluated = valuation_ready = buy_decision = low_zone = ceiling_ok = 0

    for i, bar in price.iterrows():
        if i % max(1, stride) != 0:
            continue
        close = _finite(bar.get("close"))
        if close is None or close <= 0:
            continue
        evaluated += 1
        day = bar["date"]
        valuation = point_in_time_valuation(data.valuation_df, day)
        if valuation is None:
            first_examples.setdefault("valuation_unavailable", str(day))
            continue
        valuation_ready += 1
        logic = point_in_time_hard_logic(financial, day)
        logic_states[str(logic.get("state"))] += 1
        if logic.get("state") != "PASS":
            first_examples.setdefault(
                f"logic_{logic.get('state')}",
                {"date": str(day), "score": logic.get("score"), "reasons": logic.get("reasons")},
            )
        pmap = _price_map(data, day, close, valuation, logic)
        decision = str(pmap.get("price_decision") or "")
        decisions[decision] += 1
        if logic.get("state") != "PASS" or decision not in BUY_DECISIONS:
            continue
        buy_decision += 1
        pe_pct = _finite(valuation.get("historical_pe_percentile"))
        low_ok = decision == "BUY_DEEP_VALUE" or (
            pe_pct is not None and pe_pct <= MAX_ENTRY_PE_PERCENTILE
        )
        if not low_ok:
            first_examples.setdefault(
                "entry_pe_percentile_too_high",
                {"date": str(day), "decision": decision, "pe_percentile": pe_pct},
            )
            continue
        low_zone += 1
        ceiling = _finite(pmap.get("buyable_price_ceiling"))
        if ceiling is None or close > ceiling:
            first_examples.setdefault(
                "price_above_buyable_ceiling",
                {"date": str(day), "close": close, "ceiling": ceiling, "decision": decision},
            )
            continue
        ceiling_ok += 1
        first_examples.setdefault(
            "first_buy_ready",
            {
                "date": str(day),
                "close": close,
                "decision": decision,
                "pe_percentile": pe_pct,
                "required_growth_pct": pmap.get("required_profit_growth_pct"),
                "supported_growth_base_pct": pmap.get("supported_profit_growth_base_pct"),
                "buyable_price_ceiling": ceiling,
            },
        )

    return {
        "code": data.code,
        "stock_name": data.stock_name,
        "price_rows": len(price),
        "financial_rows": len(financial),
        "valuation_rows": len(data.valuation_df),
        "evaluation_points": evaluated,
        "valuation_ready_points": valuation_ready,
        "logic_pass_points": logic_states.get("PASS", 0),
        "logic_review_points": logic_states.get("REVIEW", 0),
        "logic_blocked_points": logic_states.get("BLOCKED", 0),
        "buy_decision_points": buy_decision,
        "low_zone_points": low_zone,
        "buy_ready_points": ceiling_ok,
        "decision_counts": json.dumps(dict(decisions), ensure_ascii=False, sort_keys=True),
        "first_examples": json.dumps(first_examples, ensure_ascii=False, sort_keys=True),
        "financial_columns": ";".join(map(str, data.financial_df.columns)),
        "valuation_columns": ";".join(map(str, data.valuation_df.columns)),
        "warnings": ";".join(data.warnings),
    }


def run(cases_file: Path, start_date: date, end_date: date, output_dir: Path, cache_dir: Path, stride: int) -> list[dict[str, Any]]:
    cases = load_cases(cases_file)
    years = max(3, int((end_date - start_date).days / 365.25) + 2)
    ready, failures = fetch_case_data(cases, as_of=end_date, years=years, cache_dir=cache_dir)
    rows = [diagnose_company(x, start_date=start_date, end_date=end_date, stride=stride) for x in ready]
    output_dir.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0].keys()) if rows else ["code", "stock_name"]
    with (output_dir / "gate_diagnostics.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    (output_dir / "gate_diagnostics.json").write_text(
        json.dumps({"rows": rows, "failures": failures}, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases-file", type=Path, required=True)
    parser.add_argument("--start-date", type=date.fromisoformat, default=date(2018, 1, 1))
    parser.add_argument("--end-date", type=date.fromisoformat, default=date(2026, 8, 18))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, default=Path("data/cache/hard_logic_history_backtest"))
    parser.add_argument("--evaluation-stride", type=int, default=DEFAULT_STRIDE)
    args = parser.parse_args(argv)
    rows = run(
        args.cases_file,
        args.start_date,
        args.end_date,
        args.output_dir,
        args.cache_dir,
        max(1, args.evaluation_stride),
    )
    return 0 if rows else 2


if __name__ == "__main__":
    raise SystemExit(main())
