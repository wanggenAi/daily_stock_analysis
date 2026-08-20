from __future__ import annotations

from datetime import date

import pandas as pd

from src.strategies.genge_opportunity_discovery.forward_scenario_valuation import (
    ForwardConsensus,
    build_forward_scenario_row,
    build_forward_scenario_rows,
    extract_em_base_consensus,
    extract_ths_consensus,
    peer_forward_pe_evidence,
    reasonable_pe_from_peer_evidence,
    _em_record_map,
)


AS_OF = date(2026, 8, 20)


def _ths_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"年度": 2026, "预测机构数": 8, "最小值": 1.80, "均值": 2.00, "最大值": 2.20, "行业平均数": 1.1},
            {"年度": 2027, "预测机构数": 7, "最小值": 2.00, "均值": 2.24, "最大值": 2.50, "行业平均数": 1.2},
            {"年度": 2028, "预测机构数": 5, "最小值": 2.20, "均值": 2.50, "最大值": 2.80, "行业平均数": 1.3},
        ]
    )


def _em_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"代码": "603369", "名称": "目标", "研报数": 8, "2026预测每股收益": 2.00, "2027预测每股收益": 2.24},
            {"代码": "600001", "名称": "同行1", "研报数": 5, "2026预测每股收益": 2.00, "2027预测每股收益": 2.20},
            {"代码": "600002", "名称": "同行2", "研报数": 5, "2026预测每股收益": 2.00, "2027预测每股收益": 2.10},
            {"代码": "600003", "名称": "同行3", "研报数": 5, "2026预测每股收益": 2.00, "2027预测每股收益": 2.40},
            {"代码": "600004", "名称": "同行4", "研报数": 5, "2026预测每股收益": 2.00, "2027预测每股收益": 2.20},
            {"代码": "600005", "名称": "同行5", "研报数": 5, "2026预测每股收益": 2.00, "2027预测每股收益": 2.30},
            {"代码": "600006", "名称": "同行6", "研报数": 5, "2026预测每股收益": 2.00, "2027预测每股收益": 2.10},
            {"代码": "000999", "名称": "其他行业", "研报数": 9, "2026预测每股收益": 1.00, "2027预测每股收益": 2.00},
        ]
    )


def _raw_rows():
    return [
        {"code": "603369", "stock_name": "目标", "industry": "白酒", "current_price": 28.92},
        {"code": "600001", "stock_name": "同行1", "industry": "白酒", "current_price": 30.0},
        {"code": "600002", "stock_name": "同行2", "industry": "白酒", "current_price": 40.0},
        {"code": "600003", "stock_name": "同行3", "industry": "白酒", "current_price": 25.0},
        {"code": "600004", "stock_name": "同行4", "industry": "白酒", "current_price": 36.0},
        {"code": "600005", "stock_name": "同行5", "industry": "白酒", "current_price": 28.0},
        {"code": "600006", "stock_name": "同行6", "industry": "白酒", "current_price": 32.0},
        {"code": "000999", "stock_name": "其他", "industry": "软件", "current_price": 60.0},
    ]


def _target_row(**overrides):
    row = {
        "code": "603369",
        "stock_name": "目标",
        "industry": "白酒",
        "hard_logic_state": "PASS",
        "valuation_primary_strategy_id": "general_reverse_earnings",
        "valuation_diagnostic_status": "OK",
        "earnings_quality_score": 70,
        "latest_quarter_profit_yoy_pct": 10,
        "previous_quarter_profit_yoy_pct": -5,
        "historical_median_pe_reference": 99,
    }
    row.update(overrides)
    return row


def test_ths_min_mean_max_become_bear_base_bull_and_growth():
    result = extract_ths_consensus(_ths_frame(), as_of=AS_OF, min_institutions=3)

    assert result.status == "OK"
    assert result.forecast_year == 2026
    assert result.institution_count == 8
    assert result.eps_bear == 1.80
    assert result.eps_base == 2.00
    assert result.eps_bull == 2.20
    assert result.next_year == 2027
    assert result.next_eps_base == 2.24
    assert round(result.growth_base or 0, 4) == 0.12


def test_ths_low_coverage_falls_back_to_later_eligible_year():
    frame = _ths_frame().copy()
    frame.loc[0, "预测机构数"] = 1

    result = extract_ths_consensus(frame, as_of=AS_OF, min_institutions=3)

    assert result.forecast_year == 2027
    assert result.eps_base == 2.24
    assert result.next_year == 2028


def test_eastmoney_is_base_only_fallback_and_never_invents_bear_bull():
    records, columns = _em_record_map(_em_frame())
    result = extract_em_base_consensus(records["603369"], columns, as_of=AS_OF, min_reports=3)

    assert result.status == "BASE_ONLY"
    assert result.forecast_year == 2026
    assert result.eps_bear is None
    assert result.eps_base == 2.00
    assert result.eps_bull is None
    assert result.next_eps_base == 2.24


def test_peer_forward_pe_uses_same_industry_same_year_and_excludes_target():
    records, columns = _em_record_map(_em_frame())
    peers = peer_forward_pe_evidence(
        target_code="603369",
        industry="白酒",
        forecast_year=2026,
        raw_all_a_rows=_raw_rows(),
        em_records=records,
        forecast_columns=columns,
        min_peer_reports=2,
        min_peer_samples=6,
    )

    assert peers.status == "OK"
    assert peers.pe_sample_count == 6
    assert round(peers.pe_p25 or 0, 2) == 14.25
    assert round(peers.pe_median or 0, 2) == 15.50
    assert round(peers.pe_p75 or 0, 2) == 17.50
    assert peers.growth_sample_count == 6
    assert round((peers.growth_median or 0) * 100, 2) == 10.00


def test_reasonable_pe_is_peer_anchored_and_historical_pe_never_changes_it():
    records, columns = _em_record_map(_em_frame())
    peers = peer_forward_pe_evidence(
        target_code="603369",
        industry="白酒",
        forecast_year=2026,
        raw_all_a_rows=_raw_rows(),
        em_records=records,
        forecast_columns=columns,
        min_peer_reports=2,
        min_peer_samples=6,
    )
    consensus = extract_ths_consensus(_ths_frame(), as_of=AS_OF)

    high_history = reasonable_pe_from_peer_evidence(
        _target_row(historical_median_pe_reference=99),
        consensus=consensus,
        peers=peers,
    )
    low_history = reasonable_pe_from_peer_evidence(
        _target_row(historical_median_pe_reference=8),
        consensus=consensus,
        peers=peers,
    )

    assert high_history.status == "OK"
    assert high_history == low_history
    assert round(high_history.base or 0, 4) == 15.7705
    assert round(high_history.bear or 0, 4) == 13.4049
    assert round(high_history.bull or 0, 4) == 18.1360
    assert "historical_pe_used=false" in high_history.basis


def test_specialized_route_does_not_receive_a_fake_pe():
    records, columns = _em_record_map(_em_frame())
    peers = peer_forward_pe_evidence(
        target_code="603369",
        industry="白酒",
        forecast_year=2026,
        raw_all_a_rows=_raw_rows(),
        em_records=records,
        forecast_columns=columns,
        min_peer_samples=6,
    )
    decision = reasonable_pe_from_peer_evidence(
        _target_row(valuation_primary_strategy_id="resource_asset_nav"),
        consensus=extract_ths_consensus(_ths_frame(), as_of=AS_OF),
        peers=peers,
    )

    assert decision.status == "SPECIALIZED_MODEL_REQUIRED"
    assert decision.base is None


def test_insufficient_peer_evidence_refuses_to_invent_reasonable_pe():
    records, columns = _em_record_map(_em_frame())
    peers = peer_forward_pe_evidence(
        target_code="603369",
        industry="白酒",
        forecast_year=2026,
        raw_all_a_rows=_raw_rows()[:3],
        em_records=records,
        forecast_columns=columns,
        min_peer_samples=6,
    )
    decision = reasonable_pe_from_peer_evidence(
        _target_row(),
        consensus=extract_ths_consensus(_ths_frame(), as_of=AS_OF),
        peers=peers,
    )

    assert peers.status == "PEER_FORWARD_PE_INSUFFICIENT"
    assert decision.status == "PEER_EVIDENCE_INSUFFICIENT"
    assert decision.base is None


def test_forward_scenario_row_produces_explicit_fair_values():
    records, columns = _em_record_map(_em_frame())
    peers = peer_forward_pe_evidence(
        target_code="603369",
        industry="白酒",
        forecast_year=2026,
        raw_all_a_rows=_raw_rows(),
        em_records=records,
        forecast_columns=columns,
        min_peer_samples=6,
    )
    row = build_forward_scenario_row(
        _target_row(forecast_snapshot_date="2026-08-20"),
        consensus=extract_ths_consensus(_ths_frame(), as_of=AS_OF),
        peers=peers,
    )

    assert row["reasonable_pe_status"] == "OK"
    assert row["historical_pe_used_for_reasonable_pe"] is False
    assert row["scenario_valuation_status"] == "OK"
    assert round(float(row["scenario_fair_price_base"]), 4) == 31.5410
    assert round(float(row["scenario_fair_price_bear"]), 4) == 24.1288
    assert round(float(row["scenario_fair_price_bull"]), 4) == 39.8992


def test_build_rows_only_emits_strict_hard_logic_pass_names():
    routed = [
        _target_row(),
        {
            **_target_row(),
            "code": "600001",
            "stock_name": "同行1",
        },
    ]
    hard_logic = [
        {"code": "603369", "stock_name": "目标", "industry": "白酒", "hard_logic_state": "PASS"},
        {"code": "600001", "stock_name": "同行1", "industry": "白酒", "hard_logic_state": "REVIEW"},
    ]
    rows = build_forward_scenario_rows(
        routed_rows=routed,
        hard_logic_source_rows=hard_logic,
        raw_all_a_rows=_raw_rows(),
        em_forecast_frame=_em_frame(),
        ths_frames={"603369": _ths_frame()},
        as_of=AS_OF,
        min_peer_samples=6,
    )

    assert [row["code"] for row in rows] == ["603369"]
    assert rows[0]["hard_logic_state"] == "PASS"
    assert rows[0]["reasonable_pe_status"] == "OK"
