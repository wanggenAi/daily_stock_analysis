from __future__ import annotations

import csv
import json
from pathlib import Path

from src.strategies.genge_opportunity_discovery.intraday_industry_action_overlay import (
    build_intraday_action_rows,
    write_intraday_action_map,
)


def _stable(code: str, industry: str, *, price: float, base: float, entry: float, deep: float,
            bull: float | str = "", hard: str = "PASS") -> dict:
    return {
        "code": code,
        "stock_name": code,
        "industry": industry,
        "hard_logic_state": hard,
        "current_price": price,
        "scenario_fair_price_bear": "",
        "scenario_fair_price_base": base,
        "scenario_fair_price_bull": bull,
        "entry_price_ceiling": entry,
        "ideal_price_ceiling": deep,
        "hard_logic_structural_driver": "长期结构需求",
        "hard_logic_company_edge": "公司壁垒",
        "hard_logic_profit_transmission": "需求到利润传导",
        "hard_logic_invalidation": "份额与需求失效条件",
        "hard_logic_evidence_sources": "annual report",
    }


def _live(code: str, industry: str, price: float) -> dict:
    return {
        "code": code,
        "stock_name": code,
        "industry": industry,
        "intraday_latest_price": price,
    }


def _sector(industry: str, rank: int, state: str) -> dict:
    return {
        "industry": industry,
        "sector_rank": rank,
        "sector_opportunity_state": state,
        "sector_research_action": "PRIORITY_RESEARCH" if state in {"EMERGING", "LEADING"} else "RESEARCH",
        "sector_opportunity_score": 80 - rank,
        "advance_ratio": 0.8,
        "excess_return_1d_pct": 2.0,
        "excess_return_5d_pct": 3.0,
        "expanding_activity_ratio": 0.6,
        "sector_overheated": state == "OVERHEATED",
    }


def test_live_price_can_enter_frozen_buy_zone_but_sector_strength_does_not_create_buy():
    rows = build_intraday_action_rows(
        [
            _stable("600001", "行业A", price=30, base=30, entry=25.5, deep=22.5),
            _stable("600002", "行业B", price=30, base=30, entry=25.5, deep=22.5),
        ],
        [
            _live("600001", "行业A", 25.0),
            _live("600002", "行业B", 29.0),
        ],
        [
            _sector("行业A", 1, "LEADING"),
            _sector("行业B", 2, "LEADING"),
        ],
    )
    by_code = {row["code"]: row for row in rows}

    assert by_code["600001"]["intraday_valuation_decision"] == "BUYABLE"
    assert by_code["600001"]["intraday_execution_context"] == "BUYABLE_WITH_SECTOR_CONFIRMATION"
    # Same strong sector state cannot turn an over-entry price into BUY.
    assert by_code["600002"]["intraday_valuation_decision"] == "HOLD_FAIR_VALUE"
    assert by_code["600002"]["intraday_execution_context"] == "NO_BUY_FROM_VALUATION"
    assert all(row["sector_strength_can_create_buy"] is False for row in rows)
    assert all(row["fair_value_recomputed_intraday"] is False for row in rows)


def test_overheated_sector_marks_execution_caution_without_changing_valuation_buyability():
    rows = build_intraday_action_rows(
        [_stable("600001", "热门行业", price=28, base=30, entry=25.5, deep=22.5)],
        [_live("600001", "热门行业", 25.0)],
        [_sector("热门行业", 1, "OVERHEATED")],
    )
    row = rows[0]
    assert row["intraday_valuation_decision"] == "BUYABLE"
    assert row["intraday_execution_context"] == "VALUATION_BUYABLE_BUT_SECTOR_OVERHEATED_AVOID_CHASE"
    assert row["scenario_fair_price_base"] == 30


def test_deep_value_and_base_only_wait_are_recomputed_from_live_price():
    rows = build_intraday_action_rows(
        [
            _stable("600001", "行业A", price=25, base=30, entry=25.5, deep=22.5),
            _stable("600002", "行业B", price=25, base=30, entry=25.5, deep=22.5),
        ],
        [
            _live("600001", "行业A", 22.0),
            _live("600002", "行业B", 31.0),
        ],
        [_sector("行业A", 2, "HEALTHY"), _sector("行业B", 1, "EMERGING")],
    )
    by_code = {row["code"]: row for row in rows}
    assert by_code["600001"]["intraday_valuation_decision"] == "BUY_DEEP_VALUE"
    assert by_code["600002"]["intraday_valuation_decision"] == "WAIT_FOR_BETTER_PRICE"


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_write_intraday_action_map_contract(tmp_path: Path):
    stable = tmp_path / "stable.csv"
    live = tmp_path / "live.csv"
    sector = tmp_path / "sector.csv"
    out = tmp_path / "out"
    _write_csv(stable, [_stable("600001", "行业A", price=28, base=30, entry=25.5, deep=22.5)])
    _write_csv(live, [_live("600001", "行业A", 25.0)])
    _write_csv(sector, [_sector("行业A", 1, "LEADING")])

    summary = write_intraday_action_map(
        stable_price_map_csv=stable,
        intraday_stock_csv=live,
        intraday_sector_csv=sector,
        output_dir=out,
    )
    persisted = json.loads((out / "intraday_industry_action_summary.json").read_text(encoding="utf-8"))
    rows = list(csv.DictReader((out / "intraday_industry_action_map.csv").open(encoding="utf-8")))

    assert summary == persisted
    assert len(rows) == 1
    assert rows[0]["intraday_valuation_decision"] == "BUYABLE"
    assert persisted["industry_first_action_refresh"] is True
    assert persisted["sector_strength_is_hard_logic"] is False
    assert persisted["sector_strength_can_create_buy"] is False
    assert persisted["fair_value_recomputed_intraday"] is False
    assert persisted["historical_backtest_eligible"] is False
    assert persisted["no_auto_trade"] is True
    assert (out / "intraday_industry_action_map.md").exists()
