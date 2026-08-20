"""Combine fresh intraday sector/price data with the latest validated fair values.

This is an execution-context refresh, not a new valuation model.  Structural hard
logic, forward earnings and fair values come only from the latest completed
research artifacts.  Intraday data may:

* refresh the current market price;
* re-evaluate whether that price is below the already-frozen entry/deep ceiling;
* show the current industry opportunity state;
* flag sector confirmation, overheating or risk-off execution context.

Intraday sector strength can never manufacture BUY.  A company must already be a
strict HARD_LOGIC_PASS and have an auditable base fair value / safety-margin
ceiling from the stable research pipeline.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping


ACTION_PRIORITY = {
    "BUY_DEEP_VALUE": 0,
    "BUYABLE": 1,
    "HOLD_FAIR_VALUE": 2,
    "EXPECTATIONS_HIGH_WAIT": 3,
    "WAIT_FOR_BETTER_PRICE": 4,
    "OVERVALUED_WAIT": 5,
    "VALUATION_INCOMPLETE": 6,
    "NOT_ACTIONABLE_HARD_LOGIC": 7,
}

OUTPUT_COLUMNS = [
    "intraday_rank",
    "sector_rank",
    "industry",
    "sector_opportunity_state",
    "sector_research_action",
    "sector_opportunity_score",
    "sector_advance_ratio",
    "sector_excess_return_1d_pct",
    "sector_excess_return_5d_pct",
    "sector_expanding_activity_ratio",
    "sector_overheated",
    "code",
    "stock_name",
    "hard_logic_state",
    "intraday_current_price",
    "stable_price_snapshot",
    "scenario_fair_price_bear",
    "scenario_fair_price_base",
    "scenario_fair_price_bull",
    "entry_price_ceiling",
    "ideal_price_ceiling",
    "intraday_valuation_decision",
    "intraday_execution_context",
    "distance_to_entry_pct",
    "upside_to_base_fair_pct",
    "hard_logic_structural_driver",
    "hard_logic_company_edge",
    "hard_logic_profit_transmission",
    "hard_logic_invalidation",
    "hard_logic_evidence_sources",
    "sector_strength_is_hard_logic",
    "sector_strength_can_create_buy",
    "fair_value_recomputed_intraday",
    "historical_backtest_eligible",
    "formal_signal_eligible",
    "automatic_promotion_allowed",
    "no_auto_trade",
]


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _normalize_code(value: Any) -> str:
    text = str(value or "").strip().upper()
    if "." in text:
        base, suffix = text.rsplit(".", 1)
        if suffix in {"SH", "SZ", "BJ"} and base.isdigit():
            text = base
    for prefix in ("SH", "SZ", "BJ"):
        if text.startswith(prefix) and text[len(prefix):].isdigit():
            text = text[len(prefix):]
            break
    return text.zfill(6) if text.isdigit() else text


def _valuation_decision(row: Mapping[str, Any], current_price: float | None) -> str:
    if str(row.get("hard_logic_state") or "").strip().upper() != "PASS":
        return "NOT_ACTIONABLE_HARD_LOGIC"
    if current_price is None or current_price <= 0:
        return "VALUATION_INCOMPLETE"

    base = _finite(row.get("scenario_fair_price_base"))
    entry = _finite(row.get("entry_price_ceiling") or row.get("buyable_price_ceiling"))
    deep = _finite(row.get("ideal_price_ceiling") or row.get("deep_value_price_ceiling"))
    bull = _finite(row.get("scenario_fair_price_bull"))
    if base is None or base <= 0 or entry is None or entry <= 0:
        return "VALUATION_INCOMPLETE"
    if deep is not None and deep > 0 and current_price <= deep:
        return "BUY_DEEP_VALUE"
    if current_price <= entry:
        return "BUYABLE"
    if current_price <= base:
        return "HOLD_FAIR_VALUE"
    if bull is not None and bull > base:
        if current_price <= bull:
            return "EXPECTATIONS_HIGH_WAIT"
        return "OVERVALUED_WAIT"
    return "WAIT_FOR_BETTER_PRICE"


def _execution_context(decision: str, sector_state: str) -> str:
    state = str(sector_state or "").strip().upper()
    if decision not in {"BUY_DEEP_VALUE", "BUYABLE"}:
        return "NO_BUY_FROM_VALUATION"
    if state == "OVERHEATED":
        return "VALUATION_BUYABLE_BUT_SECTOR_OVERHEATED_AVOID_CHASE"
    if state == "RISK_OFF":
        return "VALUATION_BUYABLE_SECTOR_RISK_OFF_CAUTION"
    if state in {"EMERGING", "LEADING"}:
        return "BUYABLE_WITH_SECTOR_CONFIRMATION"
    if state == "HEALTHY":
        return "BUYABLE_HEALTHY_SECTOR"
    return "BUYABLE_WITHOUT_SECTOR_CONFIRMATION"


def build_intraday_action_rows(
    stable_price_rows: Iterable[Mapping[str, Any]],
    intraday_stock_rows: Iterable[Mapping[str, Any]],
    intraday_sector_rows: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    live_by_code = {
        _normalize_code(row.get("code")): dict(row)
        for row in intraday_stock_rows
        if _normalize_code(row.get("code"))
    }
    sector_by_industry = {
        str(row.get("industry") or "").strip(): dict(row)
        for row in intraday_sector_rows
        if str(row.get("industry") or "").strip()
    }

    output: list[dict[str, Any]] = []
    for raw in stable_price_rows:
        row = dict(raw)
        code = _normalize_code(row.get("code"))
        if not code:
            continue
        live = live_by_code.get(code)
        if live is None:
            continue
        industry = str(
            row.get("industry")
            or live.get("industry")
            or ""
        ).strip()
        sector = sector_by_industry.get(industry, {})
        current_price = _finite(
            live.get("intraday_latest_price")
            or live.get("raw_latest_close")
            or live.get("latest_price")
        )
        stable_price = _finite(row.get("current_price"))
        decision = _valuation_decision(row, current_price)
        entry = _finite(row.get("entry_price_ceiling") or row.get("buyable_price_ceiling"))
        base = _finite(row.get("scenario_fair_price_base"))
        distance_to_entry = (
            None
            if current_price is None or current_price <= 0 or entry is None
            else (entry / current_price - 1.0) * 100.0
        )
        upside_to_base = (
            None
            if current_price is None or current_price <= 0 or base is None
            else (base / current_price - 1.0) * 100.0
        )
        sector_state = str(sector.get("sector_opportunity_state") or "")
        output.append(
            {
                "intraday_rank": 0,
                "sector_rank": sector.get("sector_rank", ""),
                "industry": industry,
                "sector_opportunity_state": sector_state,
                "sector_research_action": sector.get("sector_research_action", ""),
                "sector_opportunity_score": sector.get("sector_opportunity_score", ""),
                "sector_advance_ratio": sector.get("advance_ratio", ""),
                "sector_excess_return_1d_pct": sector.get("excess_return_1d_pct", ""),
                "sector_excess_return_5d_pct": sector.get("excess_return_5d_pct", ""),
                "sector_expanding_activity_ratio": sector.get("expanding_activity_ratio", ""),
                "sector_overheated": sector.get("sector_overheated", ""),
                "code": code,
                "stock_name": row.get("stock_name") or live.get("stock_name") or "",
                "hard_logic_state": row.get("hard_logic_state") or "",
                "intraday_current_price": current_price if current_price is not None else "",
                "stable_price_snapshot": stable_price if stable_price is not None else "",
                "scenario_fair_price_bear": row.get("scenario_fair_price_bear") or "",
                "scenario_fair_price_base": row.get("scenario_fair_price_base") or "",
                "scenario_fair_price_bull": row.get("scenario_fair_price_bull") or "",
                "entry_price_ceiling": row.get("entry_price_ceiling") or row.get("buyable_price_ceiling") or "",
                "ideal_price_ceiling": row.get("ideal_price_ceiling") or row.get("deep_value_price_ceiling") or "",
                "intraday_valuation_decision": decision,
                "intraday_execution_context": _execution_context(decision, sector_state),
                "distance_to_entry_pct": "" if distance_to_entry is None else round(distance_to_entry, 4),
                "upside_to_base_fair_pct": "" if upside_to_base is None else round(upside_to_base, 4),
                "hard_logic_structural_driver": row.get("hard_logic_structural_driver") or "",
                "hard_logic_company_edge": row.get("hard_logic_company_edge") or "",
                "hard_logic_profit_transmission": row.get("hard_logic_profit_transmission") or "",
                "hard_logic_invalidation": row.get("hard_logic_invalidation") or "",
                "hard_logic_evidence_sources": row.get("hard_logic_evidence_sources") or "",
                "sector_strength_is_hard_logic": False,
                "sector_strength_can_create_buy": False,
                "fair_value_recomputed_intraday": False,
                "historical_backtest_eligible": False,
                "formal_signal_eligible": False,
                "automatic_promotion_allowed": False,
                "no_auto_trade": True,
            }
        )

    def rank_key(item: Mapping[str, Any]) -> tuple[float, int, float, str]:
        sector_rank = _finite(item.get("sector_rank"))
        action_rank = ACTION_PRIORITY.get(str(item.get("intraday_valuation_decision")), 99)
        distance = _finite(item.get("distance_to_entry_pct"))
        return (
            sector_rank if sector_rank is not None else 1e9,
            action_rank,
            -(distance if distance is not None else -1e9),
            str(item.get("code") or ""),
        )

    output.sort(key=rank_key)
    for rank, row in enumerate(output, 1):
        row["intraday_rank"] = rank
    return output


def _read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def write_intraday_action_map(
    *,
    stable_price_map_csv: Path,
    intraday_stock_csv: Path,
    intraday_sector_csv: Path,
    output_dir: Path,
) -> dict[str, Any]:
    rows = build_intraday_action_rows(
        _read_csv(stable_price_map_csv),
        _read_csv(intraday_stock_csv),
        _read_csv(intraday_sector_csv),
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "intraday_industry_action_map.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=OUTPUT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "candidate_count": len(rows),
        "hard_logic_pass_count": sum(row["hard_logic_state"] == "PASS" for row in rows),
        "buy_deep_value_count": sum(row["intraday_valuation_decision"] == "BUY_DEEP_VALUE" for row in rows),
        "buyable_count": sum(row["intraday_valuation_decision"] == "BUYABLE" for row in rows),
        "buyable_with_sector_confirmation_count": sum(
            row["intraday_execution_context"] == "BUYABLE_WITH_SECTOR_CONFIRMATION" for row in rows
        ),
        "sector_overheated_buyable_count": sum(
            row["intraday_execution_context"] == "VALUATION_BUYABLE_BUT_SECTOR_OVERHEATED_AVOID_CHASE"
            for row in rows
        ),
        "industry_first_action_refresh": True,
        "sector_strength_is_hard_logic": False,
        "sector_strength_can_create_buy": False,
        "fair_value_recomputed_intraday": False,
        "historical_backtest_eligible": False,
        "formal_signal_eligible": False,
        "automatic_promotion_allowed": False,
        "no_auto_trade": True,
    }
    (output_dir / "intraday_industry_action_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines = [
        "# Intraday Industry-First Action Map",
        "",
        "Fresh market price and sector context are overlaid on the latest validated hard logic / fair values. Sector strength cannot create BUY and fair value is not recomputed intraday.",
        "",
    ]
    for row in rows:
        if row["hard_logic_state"] != "PASS":
            continue
        lines.append(
            f"- #{row['intraday_rank']} sector#{row['sector_rank']} {row['industry']} | "
            f"{row['code']} {row['stock_name']} | sector={row['sector_opportunity_state']} | "
            f"price={row['intraday_current_price']} | fair={row['scenario_fair_price_base']} | "
            f"entry<={row['entry_price_ceiling']} | decision={row['intraday_valuation_decision']} | "
            f"context={row['intraday_execution_context']}"
        )
    (output_dir / "intraday_industry_action_map.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stable-price-map-csv", type=Path, required=True)
    parser.add_argument("--intraday-stock-csv", type=Path, required=True)
    parser.add_argument("--intraday-sector-csv", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    summary = write_intraday_action_map(
        stable_price_map_csv=args.stable_price_map_csv,
        intraday_stock_csv=args.intraday_stock_csv,
        intraday_sector_csv=args.intraday_sector_csv,
        output_dir=args.output_dir,
    )
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
