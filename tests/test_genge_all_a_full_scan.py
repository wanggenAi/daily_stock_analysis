from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.strategies.genge_opportunity_discovery.all_a_full_scan import (
    RULE_VERSION,
    _apply_position_budget,
    _board_from_exchange_row,
    _listing_row,
    apply_universe_filters,
    audit_price_mapping,
    build_actionable_execution_list,
    build_daily_signals,
    build_price_plan,
    classify_candidate,
    enrich_exit_profile,
    load_board_rules,
    mark_listings_after_as_of,
    quant_screen,
    resistance_levels,
    strict_official_evidence_audit,
)
from src.strategies.genge_opportunity_discovery.exit_profile import _triggered_entry, refresh_exit_profiles_from_price_history


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


def test_price_history_exit_refresh_replaces_stale_seed_with_traceable_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.strategies.genge_opportunity_discovery.exit_profile as exit_profile

    output = tmp_path / "exit_profile.csv"
    output.write_text(
        "code,stock_name,balanced_exit_historical_profile,signal_count\n000001,旧名称,PASSED,999\n",
        encoding="utf-8",
    )
    samples = [
        {"as_of_date": date(2026, 1, 1), "return": 3.0, "drawdown": -4.0}
        for _ in range(30)
    ]
    monkeypatch.setattr(exit_profile, "_price_setup_samples", lambda **_kwargs: samples)

    path, summary = refresh_exit_profiles_from_price_history(
        output_file=output,
        candidates=[{"code": "000001", "stock_name": "新名称"}],
        histories={"000001": _history(adjusted=True)},
        as_of=date(2026, 7, 22),
    )
    row = pd.read_csv(path, dtype={"code": str}).iloc[0]

    assert row["stock_name"] == "新名称"
    assert row["signal_count"] == 30
    assert row["balanced_exit_historical_profile"] == "PASSED"
    assert row["exit_profile_entry_mode"] == "pullback"
    assert row["pullback_profile_status"] == "PASSED"
    assert row["breakout_profile_status"] == "PASSED"
    assert str(row["profile_data_version"]).startswith("sha256:")
    assert summary["strict_metadata_eligible_count"] == 1


def test_trigger_aligned_entries_replay_pullback_and_breakout_separately() -> None:
    dates = pd.bdate_range("2026-01-01", periods=32)
    frame = pd.DataFrame({
        "date": dates.date,
        "open": [100.0] * 32,
        "high": [101.0] * 32,
        "low": [99.0] * 32,
        "close": [100.0] * 32,
        "volume": [1_000.0] * 32,
    })
    frame.loc[21, ["open", "high", "low", "close", "volume"]] = [100.5, 102.0, 99.2, 101.5, 1_500.0]

    pullback = _triggered_entry(
        frame=frame, setup_index=20, entry_mode="pullback",
        breakout_volume_ratio=1.2, max_chase_atr_multiple=.35,
        volatility_multiplier=1.0,
    )
    breakout = _triggered_entry(
        frame=frame, setup_index=20, entry_mode="breakout",
        breakout_volume_ratio=1.2, max_chase_atr_multiple=.35,
        volatility_multiplier=1.0,
    )

    assert pullback is not None and pullback[0] == 21
    assert breakout is not None and breakout[0] == 21
    assert pullback[1] < breakout[1]


def test_actionable_execution_list_keeps_every_current_strict_trigger() -> None:
    rows = [{
        "code": "000001", "stock_name": "测试股份", "preferred_plan": "pullback",
        "pullback_entry_low": 9.8, "pullback_entry_high": 10.0,
        "pullback_stop_price": 9.4, "pullback_logic_invalidation_price": 9.2,
        "pullback_target_1": 11.2, "pullback_target_2": 12.0,
        "real_reward_risk_ratio": 2.0, "risk_budget_initial_position_pct": 3.0,
        "risk_budget_max_position_pct": 5.0, "cancel_conditions": "重大负面公告",
        "industry_evidence_status": "VERIFIED", "company_evidence_status": "VERIFIED",
        "hard_logic_level": "MEDIUM", "exit_profile_status": "PASSED",
        "exit_profile_entry_mode": "pullback", "evidence_urls": "https://example.com",
    }]

    result = build_actionable_execution_list(strict_rows=rows, next_trade_date=date(2026, 7, 23))

    assert result[0]["execution_action"] == "BUY_IF_TRIGGERED"
    assert result[0]["max_buy_price"] == 10.0
    assert result[0]["risk_budget_max_position_pct"] == 5.0


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


def test_listing_after_as_of_is_skipped_without_fatal_price_failure() -> None:
    as_of = date(2026, 7, 20)
    future = _row(board="STAR")
    future.update({
        "code": "688806",
        "stock_name": "N泰诺",
        "exchange": "SSE",
        "listing_date": "2026-07-21",
    })
    rows = mark_listings_after_as_of([future], as_of=as_of)

    assert rows[0]["exclusion_reason"] == "listing_after_as_of"
    universe, audit_rows, counts = apply_universe_filters(
        rows, {}, {}, {}, {"688806:raw": "history unavailable"},
        as_of=as_of, board_rules=load_board_rules("config/board_risk_rules.yaml"),
    )

    assert universe[0]["exclusion_reason"] == "listing_after_as_of"
    assert audit_rows[0]["reason"] == "listing_after_as_of"
    assert counts["listing_after_as_of"] == 1
    assert counts["fatal_data_failure_count"] == 0


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
        "strict_official_evidence_count": 1,
        "strict_official_evidence_domains": "static.cninfo.com.cn",
        "strict_official_evidence_passed": True,
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
    return {
        "exit_profile_status": "PASSED", "exit_profile_sample_count": 50,
        "exit_profile_confidence": "MEDIUM", "profile_data_end_date": "2025-12-31",
        "recent_2y_sample_count": 20,
        "profile_rule_version": RULE_VERSION, "exit_profile_freshness_days": 30,
        "exit_profile_rule_version_match": True, "exit_profile_freshness_passed": True,
        "exit_profile_data_version": "fixture-v1", "exit_profile_data_traceable": True,
    }


def test_strict_review_ready_requires_every_hard_gate() -> None:
    rule = load_board_rules("config/board_risk_rules.yaml")["SZSE_MAIN"]
    level, missing = classify_candidate(_candidate(), _plan(), _profile(), ["https://example.com/report.pdf"], board_rule=rule)
    assert level == "STRICT_REVIEW_READY"
    assert not missing
    for override in ({"price_percentile_5y": .36}, {"trend_confirmation_level": "WEAK"}, {"financial_safety_score": 59}, {"hard_logic_level": "WEAK"}):
        level, _ = classify_candidate(_candidate(**override), _plan(), _profile(), ["https://example.com/report.pdf"], board_rule=rule)
        assert level != "STRICT_REVIEW_READY"


def _evidence(**overrides) -> dict:
    row = {
        "scope": "company", "code": "000001", "industry": "银行",
        "evidence_date": "2026-07-01", "source_type": "EXCHANGE_DISCLOSURE",
        "original_url": "https://static.cninfo.com.cn/finalpage/report.pdf",
        "evidence_status": "VERIFIED", "parse_status": "OK",
        "normalized_summary": "正式公告已解析并核验。", "warning_flags": "",
    }
    row.update(overrides)
    return row


def test_news_url_cannot_satisfy_strict_official_evidence() -> None:
    audit = strict_official_evidence_audit([
        _evidence(source_type="NEWS", original_url="https://news.example.com/story")
    ], _row(), as_of=date(2026, 7, 13))
    assert audit["strict_official_evidence_count"] == 0
    assert audit["strict_official_evidence_passed"] is False


@pytest.mark.parametrize("url", [
    "https://static.cninfo.com.cn/finalpage/report.pdf",
    "https://www.sse.com.cn/disclosure/report.pdf",
    "https://www.szse.cn/disclosure/report.pdf",
    "https://www.stats.gov.cn/report.html",
])
def test_formal_official_domains_satisfy_strict_evidence(url: str) -> None:
    audit = strict_official_evidence_audit(
        [_evidence(original_url=url)], _row(), as_of=date(2026, 7, 13)
    )
    assert audit["strict_official_evidence_count"] == 1
    assert audit["strict_official_evidence_passed"] is True


def test_url_without_parsed_content_cannot_satisfy_strict_evidence() -> None:
    audit = strict_official_evidence_audit([
        _evidence(normalized_summary="", raw_excerpt="", content_hash="", extracted_value="")
    ], _row(), as_of=date(2026, 7, 13))
    assert audit["strict_official_evidence_passed"] is False


def _raw_profile(**overrides) -> dict:
    profile = {
        "exit_profile_status": "PASSED", "exit_profile_sample_count": 50,
        "exit_profile_confidence": "MEDIUM", "profile_data_end_date": "2026-07-01",
        "recent_2y_sample_count": 20,
        "profile_rule_version": RULE_VERSION, "exit_profile_data_version": "fixture-v1",
    }
    profile.update(overrides)
    return profile


@pytest.mark.parametrize("overrides", [
    {"profile_data_end_date": ""},
    {"profile_data_end_date": "2025-01-01"},
    {"profile_rule_version": "old-rule-version"},
])
def test_invalid_exit_profile_metadata_cannot_be_strict(overrides: dict) -> None:
    profile = enrich_exit_profile(_raw_profile(**overrides), as_of=date(2026, 7, 13))
    level, missing = classify_candidate(
        _candidate(), _plan(), profile, ["https://static.cninfo.com.cn/report.pdf"],
        board_rule=load_board_rules("config/board_risk_rules.yaml")["SZSE_MAIN"],
    )
    assert level != "STRICT_REVIEW_READY"
    assert any(name.startswith("exit_profile_") for name in missing)


def test_condition_watch_requires_financial_passed_and_rr_1_3() -> None:
    rule = load_board_rules("config/board_risk_rules.yaml")["SZSE_MAIN"]
    base = _candidate(trend_confirmation_level="WEAK", industry_evidence_status="MISSING", hard_logic_level="WEAK")
    level, _ = classify_candidate(base, _plan(1.3, ready=False), {"exit_profile_status": "NOT_AVAILABLE"}, ["https://example.com/report.pdf"], board_rule=rule)
    assert level == "CONDITION_WATCH"
    low_rr, _ = classify_candidate(base, _plan(1.29, ready=False), {}, ["https://example.com/report.pdf"], board_rule=rule)
    bad_financial, _ = classify_candidate({**base, "financial_safety_score": 59}, _plan(1.3, ready=False), {}, ["https://example.com/report.pdf"], board_rule=rule)
    assert low_rr != "CONDITION_WATCH"
    assert bad_financial != "CONDITION_WATCH"


def test_non_strict_actual_output_rows_have_zero_position(tmp_path: Path) -> None:
    rows = []
    plan = {
        **_plan(1.3, ready=False), "preferred_plan": "pullback",
        "pullback_entry_high": 11.0, "pullback_stop_price": 10.0,
        "breakout_max_chase_price": 11.2,
    }
    for level in ("CONDITION_WATCH", "RESEARCH_WATCH", "NOT_QUALIFIED"):
        row = {"code": level, "user_visible_level": level}
        _apply_position_budget(row, plan, level)
        rows.append(row)
    output = tmp_path / "actual_output.csv"
    pd.DataFrame(rows).to_csv(output, index=False)
    actual = pd.read_csv(output)
    assert set(actual["user_visible_level"]) == {"CONDITION_WATCH", "RESEARCH_WATCH", "NOT_QUALIFIED"}
    assert (actual["risk_budget_initial_position_pct"] == 0).all()
    assert (actual["risk_budget_max_position_pct"] == 0).all()


def test_daily_signals_emit_only_strict_buy_and_prior_strict_exit() -> None:
    current_strict = {
        **_candidate(), **_plan(), "code": "000001", "stock_name": "严格候选",
        "user_visible_level": "STRICT_REVIEW_READY", "preferred_plan": "pullback",
        "raw_latest_close": 10.5, "latest_trade_date": "2026-07-17",
        "pullback_entry_low": 10.1, "pullback_entry_high": 10.4,
        "pullback_stop_price": 9.6, "pullback_logic_invalidation_price": 9.5,
        "pullback_target_1": 11.5, "pullback_target_2": 12.0,
        "risk_budget_initial_position_pct": 2.0, "risk_budget_max_position_pct": 5.0,
    }
    current_watch = {
        **current_strict, "code": "000002", "stock_name": "观察候选",
        "user_visible_level": "CONDITION_WATCH", "missing_conditions": "industry_evidence",
        "risk_budget_initial_position_pct": 0.0, "risk_budget_max_position_pct": 0.0,
    }
    previous = {
        "000003": {
            **current_strict, "code": "000003", "stock_name": "昨日严格候选",
            "user_visible_level": "STRICT_REVIEW_READY",
        }
    }
    signals = build_daily_signals(
        current_rows=[current_strict, current_watch], previous=previous,
        as_of=date(2026, 7, 17), next_trade_date=date(2026, 7, 20),
    )
    by_code = {row["code"]: row for row in signals}
    assert by_code["000001"]["signal_action"] == "BUY_IF_TRIGGERED"
    assert by_code["000002"]["signal_action"] == "WATCH_ONLY"
    assert by_code["000003"]["signal_action"] == "SELL_EXIT"
    assert by_code["000003"]["risk_budget_initial_position_pct"] == 0.0
    assert by_code["000003"]["risk_budget_max_position_pct"] == 0.0
    assert by_code["000003"]["signal_data_status"] == "CURRENT_ROW_MISSING"
    assert by_code["000002"]["risk_budget_initial_position_pct"] == 0.0


def test_daily_signal_exits_when_previous_stop_is_breached() -> None:
    previous = {
        "000001": {
            "code": "000001", "stock_name": "测试", "user_visible_level": "STRICT_REVIEW_READY",
            "preferred_plan": "pullback", "pullback_stop_price": 10.0,
            "pullback_logic_invalidation_price": 9.8,
        }
    }
    current = {
        **previous["000001"], "raw_latest_close": 9.7, "latest_trade_date": "2026-07-17",
        "missing_conditions": "", "risk_budget_initial_position_pct": 2.0,
        "risk_budget_max_position_pct": 5.0,
    }
    signal = build_daily_signals(
        current_rows=[current], previous=previous,
        as_of=date(2026, 7, 17), next_trade_date=date(2026, 7, 20),
    )[0]
    assert signal["signal_action"] == "SELL_EXIT"
    assert signal["risk_budget_initial_position_pct"] == 0.0
    assert signal["risk_budget_max_position_pct"] == 0.0
    assert signal["signal_reason"] == "previous_stop_or_invalidation_breached"


def test_no_hardcoded_sample_stocks_in_all_a_module() -> None:
    text = Path("src/strategies/genge_opportunity_discovery/all_a_full_scan.py").read_text(encoding="utf-8")
    for token in ("牧原股份", "TCL科技", "002714", "000100"):
        assert token not in text


def test_disclaimer_and_no_broker_or_order_calls() -> None:
    text = Path("src/strategies/genge_opportunity_discovery/all_a_full_scan.py").read_text(encoding="utf-8")
    assert "仅用于公开数据研究观察和人工复核，不构成买入或卖出建议，不应自动交易。" in text
    for forbidden_call in ("place_order(", "submit_order(", "cancel_order(", "order_api."):
        assert forbidden_call not in text.lower()
