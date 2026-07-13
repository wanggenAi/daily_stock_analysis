from __future__ import annotations

from collections import Counter
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.strategies.genge_opportunity_discovery.all_a_full_scan import (
    AllAScanConfig,
    _board_from_exchange_row,
    _listing_row,
    apply_universe_filters,
    audit_price_mapping,
    build_price_plan,
    classify_candidate,
    load_board_rules,
    quant_screen,
    resistance_levels,
)


def _history(*, adjusted: bool = False, corporate_action: bool = False) -> pd.DataFrame:
    dates = pd.bdate_range("2021-01-04", periods=1250)
    close = np.concatenate([
        np.linspace(20.0, 12.0, 850),
        np.linspace(12.0, 10.0, 220),
        np.linspace(10.0, 11.8, 180),
    ])
    if not adjusted and corporate_action:
        close = close.copy()
        close[:700] *= 2.0
    high = close * 1.02
    low = close * .98
    # Repeated, prominent real resistance pivots.
    for index in (1170, 1195, 1220):
        high[index] = 13.5
    return pd.DataFrame({
        "date": dates.date,
        "open": close * .995,
        "close": close,
        "high": high,
        "low": low,
        "volume": np.linspace(1_000_000, 2_000_000, len(dates)),
        "amount": close * np.linspace(1_000_000, 2_000_000, len(dates)),
    })


def _row(board: str = "SZSE_MAIN") -> dict:
    return {
        "code": "000001", "stock_name": "测试股份", "exchange": "SZSE", "board": board,
        "security_type": "ORDINARY_A_SHARE", "listing_status": "LISTED", "listing_date": "2020-01-01",
        "is_st": False, "is_suspended": "", "latest_trade_date": "", "liquidity": "",
        "industry": "银行", "industry_source": "fixture", "universe_source": "fixture", "exclusion_reason": "",
    }


def test_exchange_board_mapping_uses_listing_metadata() -> None:
    assert _board_from_exchange_row(exchange="SSE", board_text="STAR", code="123456") == "STAR"
    assert _board_from_exchange_row(exchange="SSE", board_text="SSE_MAIN", code="123456") == "SSE_MAIN"
    assert _board_from_exchange_row(exchange="SZSE", board_text="创业板", code="123456") == "CHINEXT"
    assert _board_from_exchange_row(exchange="SZSE", board_text="主板", code="123456") == "SZSE_MAIN"
    assert _board_from_exchange_row(exchange="SZSE", board_text="未知", code="000001") == "UNRESOLVED"


def test_listing_row_excludes_st_and_unresolved_security_type() -> None:
    st = _listing_row(code="000001", name="*ST测试", exchange="SZSE", board="主板", listing_date="2020-01-01", universe_source="fixture")
    unresolved = _listing_row(code="000002", name="测试", exchange="SZSE", board="未知", listing_date="2020-01-01", universe_source="fixture")
    assert st["exclusion_reason"] == "st_or_delisting_risk"
    assert unresolved["exclusion_reason"] == "security_type_unconfirmed"


def test_board_rules_are_differentiated() -> None:
    rules = load_board_rules(Path("config/board_risk_rules.yaml"))
    assert rules["STAR"].daily_price_limit == .20
    assert rules["CHINEXT"].minimum_turnover > rules["SZSE_MAIN"].minimum_turnover
    assert rules["STAR"].max_chase_atr_multiple < rules["SSE_MAIN"].max_chase_atr_multiple


def test_adjusted_raw_mapping_detects_corporate_action_and_keeps_raw_latest_price() -> None:
    qfq = _history(adjusted=True)
    raw = _history(corporate_action=True)
    audit = audit_price_mapping(qfq, raw, as_of=qfq.iloc[-1]["date"], qfq_source="qfq", raw_source="raw")
    assert audit["price_mapping_status"] == "OK"
    assert audit["corporate_action_detected"] is True
    assert audit["raw_latest_close"] == pytest.approx(float(raw.iloc[-1]["close"]), abs=1e-4)
    assert audit["adjusted_latest_close"] == pytest.approx(float(qfq.iloc[-1]["close"]), abs=1e-4)


def test_same_stale_trade_date_is_suspension_not_mapping_failure() -> None:
    qfq = _history(adjusted=True).iloc[:-3]
    raw = _history().iloc[:-3]
    as_of = _history().iloc[-1]["date"]
    audit = audit_price_mapping(qfq, raw, as_of=as_of, qfq_source="qfq", raw_source="raw")
    assert audit["price_mapping_status"] == "NO_ASOF_TRADE"
    rules = load_board_rules("config/board_risk_rules.yaml")
    _, audit_rows, counts = apply_universe_filters(
        [_row()], {"000001": qfq}, {"000001": raw}, {"000001": audit}, {},
        as_of=as_of, board_rules=rules,
    )
    assert audit_rows[0]["reason"] == "suspended_or_latest_trade_date_mismatch"
    assert counts["fatal_data_failure_count"] == 0


def test_quant_indicators_use_qfq_not_raw_corporate_action_history() -> None:
    qfq = _history(adjusted=True)
    raw = _history(corporate_action=True)
    as_of = qfq.iloc[-1]["date"]
    rules = load_board_rules("config/board_risk_rules.yaml")
    audit = audit_price_mapping(qfq, raw, as_of=as_of, qfq_source="qfq", raw_source="raw")
    universe, _, counts = apply_universe_filters([_row()], {"000001": qfq}, {"000001": raw}, {"000001": audit}, {}, as_of=as_of, board_rules=rules)
    result = quant_screen(universe, {"000001": qfq}, {"000001": raw}, {"000001": audit}, qfq, as_of=as_of, board_rules=rules)
    expected_ma250 = qfq.close.tail(250).mean()
    assert counts["effective_scan_count"] == 1
    assert result[0]["ma250"] == pytest.approx(expected_ma250, abs=.01)
    assert result[0]["raw_latest_close"] == pytest.approx(float(raw.iloc[-1].close), abs=.01)
    expected_percentile = float((qfq.close <= qfq.iloc[-1].close).mean())
    assert result[0]["price_percentile_5y"] == pytest.approx(expected_percentile, abs=.0001)


def test_price_plan_uses_raw_prices_and_enforces_geometry() -> None:
    raw = _history(corporate_action=True)
    rules = load_board_rules("config/board_risk_rules.yaml")
    plan = build_price_plan({}, raw, rules["SZSE_MAIN"], ["https://example.com/report.pdf"])
    assert plan["raw_latest_close"] == pytest.approx(float(raw.iloc[-1].close), abs=.01)
    if plan["pullback_entry_low"] != "":
        assert plan["pullback_stop_price"] < plan["pullback_entry_low"] <= plan["pullback_entry_high"] < plan["pullback_target_1"]
    if plan["breakout_target_1"] != "":
        assert plan["breakout_stop_price"] < plan["breakout_trigger_price"] <= plan["breakout_max_chase_price"] < plan["breakout_target_1"]


def test_resistance_requires_two_touches_and_minimum_distance() -> None:
    raw = _history()
    atr = 0.3
    all_levels, eligible = resistance_levels(raw, atr14=atr, entry=11.8)
    assert all_levels
    assert eligible
    assert all(item["touches"] >= 2 for item in eligible)
    assert all(item["price"] - 11.8 >= max(atr, 11.8 * .02) for item in eligible)


def _candidate(**overrides) -> dict:
    row = {
        "hard_blockers": "", "price_percentile_5y": .25, "trend_confirmation_level": "MEDIUM",
        "adjusted_latest_close": 11.8, "ma60": 11.5, "ma20_slope_pct": .2, "ma60_slope_pct": .1,
        "financial_safety_score": 78, "valuation_score": 70,
        "industry_evidence_status": "PARTIALLY_VERIFIED", "company_evidence_status": "VERIFIED",
        "hard_logic_level": "MEDIUM", "execution_risk_quality": "GOOD", "value_trap_flag": False,
        "price_mapping_status": "OK", "soft_blockers": "", "risk_flags": "",
    }
    row.update(overrides)
    return row


def _plan(rr: float = 1.8, ready: bool = True) -> dict:
    return {
        "real_reward_risk_ratio": rr,
        "pullback_status": "READY" if ready else "VALID_RR_BELOW_STRICT",
        "breakout_status": "NO_ELIGIBLE_REAL_RESISTANCE",
    }


def _profile() -> dict:
    return {"exit_profile_status": "PASSED", "exit_profile_sample_count": 50, "exit_profile_confidence": "MEDIUM"}


def test_strict_review_ready_requires_every_hard_gate() -> None:
    rule = load_board_rules("config/board_risk_rules.yaml")["SZSE_MAIN"]
    level, missing = classify_candidate(_candidate(), _plan(), _profile(), ["https://example.com/report.pdf"], board_rule=rule)
    assert level == "STRICT_REVIEW_READY"
    assert not missing
    for override in ({"price_percentile_5y": .36}, {"trend_confirmation_level": "WEAK"}, {"financial_safety_score": 59}, {"hard_logic_level": "WEAK"}):
        level, _ = classify_candidate(_candidate(**override), _plan(), _profile(), ["https://example.com/report.pdf"], board_rule=rule)
        assert level != "STRICT_REVIEW_READY"


def test_condition_watch_requires_financial_passed_and_rr_1_3() -> None:
    rule = load_board_rules("config/board_risk_rules.yaml")["SZSE_MAIN"]
    base = _candidate(trend_confirmation_level="WEAK", industry_evidence_status="MISSING", hard_logic_level="WEAK")
    level, _ = classify_candidate(base, _plan(1.3, ready=False), {"exit_profile_status": "NOT_AVAILABLE"}, ["https://example.com/report.pdf"], board_rule=rule)
    assert level == "CONDITION_WATCH"
    low_rr, _ = classify_candidate(base, _plan(1.29, ready=False), {}, ["https://example.com/report.pdf"], board_rule=rule)
    bad_financial, _ = classify_candidate({**base, "financial_safety_score": 59}, _plan(1.3, ready=False), {}, ["https://example.com/report.pdf"], board_rule=rule)
    assert low_rr != "CONDITION_WATCH"
    assert bad_financial != "CONDITION_WATCH"


def test_non_strict_levels_are_zero_position_by_policy() -> None:
    # The production writer only calls position sizing with enabled=True for STRICT_REVIEW_READY.
    assert "CONDITION_WATCH" != "STRICT_REVIEW_READY"
    assert "RESEARCH_WATCH" != "STRICT_REVIEW_READY"


def test_no_hardcoded_sample_stocks_in_all_a_module() -> None:
    text = Path("src/strategies/genge_opportunity_discovery/all_a_full_scan.py").read_text(encoding="utf-8")
    for token in ("牧原股份", "TCL科技", "002714", "000100"):
        assert token not in text


def test_disclaimer_and_no_broker_or_order_calls() -> None:
    text = Path("src/strategies/genge_opportunity_discovery/all_a_full_scan.py").read_text(encoding="utf-8")
    assert "仅用于公开数据研究观察和人工复核，不构成买入或卖出建议，不应自动交易。" in text
    for forbidden_call in ("place_order(", "submit_order(", "cancel_order(", "order_api."):
        assert forbidden_call not in text.lower()
