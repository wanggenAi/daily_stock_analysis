from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd
import pytest

from src.strategies.genge_opportunity_discovery.sector_opportunity_intraday import (
    SNAPSHOT_TYPE,
    build_intraday_sector_snapshot,
    normalize_realtime_rows,
    write_intraday_sector_snapshot,
)


def _baseline_rows() -> list[dict]:
    rows: list[dict] = []
    for i in range(6):
        rows.append({
            "code": f"6001{i:02d}",
            "stock_name": f"强{i}",
            "industry": "强行业",
            "board": "SSE_MAIN",
            "trade_date": "2026-08-19",
            "return_1d_pct": 0.2,
            "return_5d_pct": 1.0 + i * 0.1,
            "return_10d_pct": 2.0,
            "volume_ratio_20": 0.9,
            "amount_ratio_20": 0.9,
            "above_ma20": True,
            "above_ma60": True,
            "price_volume_state": "NEUTRAL",
            "exclusion_reason": "",
        })
    for i in range(6):
        rows.append({
            "code": f"0002{i:02d}",
            "stock_name": f"弱{i}",
            "industry": "弱行业",
            "board": "SZSE_MAIN",
            "trade_date": "2026-08-19",
            "return_1d_pct": 0.1,
            "return_5d_pct": -1.0 - i * 0.1,
            "return_10d_pct": -2.0,
            "volume_ratio_20": 0.9,
            "amount_ratio_20": 0.9,
            "above_ma20": False,
            "above_ma60": False,
            "price_volume_state": "NEUTRAL",
            "exclusion_reason": "",
        })
    return rows


def _live_frame() -> pd.DataFrame:
    data: list[dict] = []
    for i in range(6):
        data.append({
            "股票代码": f"6001{i:02d}",
            "股票名称": f"强{i}",
            "涨跌幅": 2.5 + i * 0.1,
            "最新价": 20 + i,
            "最高": 20.5 + i,
            "最低": 19 + i,
            "今开": 19.5 + i,
            "换手率": 2.0,
            "量比": 1.6,
            "成交额": 100000000 + i,
            "昨日收盘": 19.4 + i,
            "市场类型": "沪A",
        })
    for i in range(6):
        data.append({
            "股票代码": f"0002{i:02d}",
            "股票名称": f"弱{i}",
            "涨跌幅": -2.0 - i * 0.1,
            "最新价": 10 - i * 0.1,
            "最高": 10.3,
            "最低": 9.5,
            "今开": 10.1,
            "换手率": 2.2,
            "量比": 1.5,
            "成交额": 50000000 + i,
            "昨日收盘": 10.2,
            "市场类型": "深A",
        })
    # Non-Shanghai/Shenzhen rows must not contaminate the requested universe.
    data.append({
        "股票代码": "920001",
        "股票名称": "北交测试",
        "涨跌幅": 10,
        "最新价": 10,
        "市场类型": "北A",
    })
    return pd.DataFrame(data)


def test_normalize_realtime_quotes_keeps_only_shanghai_shenzhen_a():
    rows = normalize_realtime_rows(_live_frame())
    assert len(rows) == 12
    assert {row["market_type"] for row in rows} == {"沪A", "深A"}
    assert rows[0]["code"] == "600100"
    assert rows[0]["return_1d_pct"] == 2.5
    assert rows[0]["volume_ratio"] == 1.6


def test_intraday_overlay_reorders_industries_using_fresh_today_breadth():
    stock_rows, sectors, summary = build_intraday_sector_snapshot(
        _baseline_rows(),
        _live_frame(),
        snapshot_as_of="2026-08-20T14:20:00+08:00",
        min_match_ratio=0.95,
        min_industry_coverage_ratio=0.95,
    )
    by_industry = {row["industry"]: row for row in sectors}

    assert len(stock_rows) == 12
    assert summary["snapshot_type"] == SNAPSHOT_TYPE
    assert summary["realtime_match_ratio"] == 1.0
    assert summary["industry_mapping_coverage_ratio"] == 1.0
    assert summary["baseline_trade_date"] == "2026-08-19"
    assert summary["intraday_refresh_only"] is True
    assert summary["structural_research_reused_not_rerun"] is True
    assert summary["valuation_reused_not_rerun"] is True
    assert summary["sector_strength_is_hard_logic"] is False
    assert summary["sector_strength_can_create_buy"] is False
    assert summary["historical_backtest_eligible"] is False

    assert by_industry["强行业"]["sector_rank"] < by_industry["弱行业"]["sector_rank"]
    assert by_industry["强行业"]["median_return_1d_pct"] > 2.0
    assert by_industry["强行业"]["advance_ratio"] == 1.0
    assert by_industry["强行业"]["snapshot_type"] == SNAPSHOT_TYPE
    assert by_industry["弱行业"]["advance_ratio"] == 0.0
    # Current-day participation state is recomputed from live price/volume data.
    assert all(
        row["price_volume_state"] == "ACCUMULATION"
        for row in stock_rows
        if row["industry"] == "强行业"
    )


def test_intraday_refresh_fails_closed_when_baseline_mapping_is_stale():
    frame = _live_frame()
    with pytest.raises(RuntimeError, match="baseline match ratio too low"):
        build_intraday_sector_snapshot(
            _baseline_rows()[:2],
            frame,
            snapshot_as_of="2026-08-20T14:20:00+08:00",
            min_match_ratio=0.8,
            min_industry_coverage_ratio=0.8,
        )


def test_write_intraday_artifact_contract(tmp_path: Path):
    baseline = tmp_path / "all_a_quant_screen.csv"
    rows = _baseline_rows()
    fields = sorted({key for row in rows for key in row})
    with baseline.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    out = tmp_path / "out"
    summary = write_intraday_sector_snapshot(
        baseline,
        out,
        quote_fetcher=_live_frame,
        snapshot_as_of="2026-08-20T14:20:00+08:00",
        min_match_ratio=0.95,
        min_industry_coverage_ratio=0.95,
    )
    persisted = json.loads(
        (out / "sector_opportunity_intraday_summary.json").read_text(encoding="utf-8")
    )
    sector_rows = list(
        csv.DictReader((out / "sector_opportunity_intraday.csv").open(encoding="utf-8"))
    )

    assert summary == persisted
    assert len(sector_rows) == 2
    assert (out / "intraday_stock_snapshot.csv").exists()
    assert (out / "sector_opportunity_intraday.md").exists()
    assert persisted["snapshot_type"] == "INTRADAY_REALTIME_OVERLAY"
    assert persisted["historical_backtest_eligible"] is False
    assert persisted["formal_signal_eligible"] is False
    assert persisted["automatic_promotion_allowed"] is False
    assert persisted["no_auto_trade"] is True
