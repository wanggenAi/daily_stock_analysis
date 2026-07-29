from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from src.strategies.genge_opportunity_discovery.real_world_signals import (
    build_industry_regimes,
    build_market_regime,
    enrich_real_world_signals,
    event_risk,
    history_snapshot,
    price_volume_state,
)


def _history(*, last_return: float = 0.0, last_volume_ratio: float = 1.0) -> pd.DataFrame:
    dates = pd.bdate_range("2026-01-01", periods=80)
    close = np.linspace(100.0, 108.0, len(dates))
    close[-1] = close[-2] * (1.0 + last_return / 100.0)
    volume = np.full(len(dates), 1_000_000.0)
    volume[-1] *= last_volume_ratio
    return pd.DataFrame({
        "date": dates.date,
        "open": close * 0.995,
        "close": close,
        "high": close * 1.01,
        "low": close * 0.99,
        "volume": volume,
        "amount": close * volume,
    })


def _row(code: int, *, industry: str = "半导体", daily_return: float = -3.0) -> dict:
    base = {
        "code": f"{code:06d}", "industry": industry, "board": "STAR",
        "return_1d_pct": daily_return, "volume_ratio_20": 1.5,
        "amount_ratio_20": 1.5, "close_location": 0.15,
        "gap_open_pct": -1.0, "above_ma20": False, "above_ma60": False,
    }
    base.update(price_volume_state(base))
    return base


def test_price_volume_distribution_uses_price_and_activity_together() -> None:
    assert price_volume_state(_row(1))["price_volume_state"] == "DISTRIBUTION"
    quiet = _row(2, daily_return=-1.0)
    quiet["volume_ratio_20"] = 0.7
    quiet["amount_ratio_20"] = 0.7
    assert price_volume_state(quiet)["price_volume_state"] == "WEAK_DEMAND"


def test_major_index_crash_forces_red_market_even_when_breadth_is_mixed() -> None:
    rows = [_row(index, industry="银行", daily_return=0.2 if index % 2 else -0.2) for index in range(1, 201)]
    regime = build_market_regime(
        rows,
        index_histories={"创业板指": _history(last_return=-7.35, last_volume_ratio=1.2)},
        external_histories={"纳斯达克综合": _history(last_return=-1.2)},
        as_of=_history().iloc[-1]["date"],
    )
    assert regime["status"] == "RED"
    assert regime["allow_new_buy"] is False
    assert "major_index_crash" in regime["risk_reasons"]


def test_partial_major_index_data_cannot_report_green_market() -> None:
    rows = [{
        "return_1d_pct": 1.0, "above_ma20": True, "above_ma60": True,
        "price_volume_state": "NEUTRAL", "board": "SZSE_MAIN",
    } for _ in range(200)]
    as_of = _history().iloc[-1]["date"]
    regime = build_market_regime(
        rows, index_histories={"上证指数": _history(last_return=1.0)}, as_of=as_of,
    )
    assert regime["data_quality"] == "PARTIAL"
    assert regime["status"] == "YELLOW"
    assert regime["position_multiplier"] == 0.5


def test_missing_all_major_indexes_forces_red_market() -> None:
    rows = [{
        "return_1d_pct": 1.0, "above_ma20": True, "above_ma60": True,
        "price_volume_state": "NEUTRAL", "board": "SZSE_MAIN",
    } for _ in range(200)]
    regime = build_market_regime(rows, index_histories={}, as_of=_history().iloc[-1]["date"])
    assert regime["status"] == "RED"
    assert regime["allow_new_buy"] is False
    assert "major_index_data_unavailable" in regime["risk_reasons"]


def test_high_external_risk_caps_otherwise_green_market_to_yellow() -> None:
    rows = [{
        "return_1d_pct": 1.0, "above_ma20": True, "above_ma60": True,
        "price_volume_state": "NEUTRAL", "board": "SZSE_MAIN",
    } for _ in range(200)]
    as_of = _history().iloc[-1]["date"]
    indices = {name: _history(last_return=1.0) for name in ("上证", "深证", "创业板")}
    regime = build_market_regime(
        rows,
        index_histories=indices,
        external_histories={"纳斯达克": _history(last_return=-3.0)},
        as_of=as_of,
        external_as_of=as_of,
    )
    assert regime["external_risk_level"] == "HIGH"
    assert regime["status"] == "YELLOW"


def test_stale_external_history_is_unknown() -> None:
    history = _history()
    as_of = history.iloc[-1]["date"]
    stale = history.iloc[:-10].copy()
    regime = build_market_regime(
        [_row(index, daily_return=0.2) for index in range(1, 201)],
        index_histories={name: history for name in ("上证", "深证", "创业板")},
        external_histories={"纳斯达克": stale},
        as_of=as_of,
        external_as_of=as_of,
    )
    assert regime["external_risk_level"] == "UNKNOWN"
    assert regime["external_available_count"] == 0
    assert regime["external_data_quality"] == "PARTIAL"
    assert regime["status"] != "GREEN"


def test_industry_crisis_detects_concentrated_sector_selloff() -> None:
    rows = [_row(index, daily_return=-4.0) for index in range(1, 21)]
    regimes = build_industry_regimes(rows)
    assert regimes["半导体"]["status"] == "CRISIS"
    assert regimes["半导体"]["distribution_ratio"] == 1.0


def test_recent_verified_critical_event_is_high_risk() -> None:
    evidence = [{
        "scope": "company", "code": "000001", "industry": "半导体",
        "evidence_date": "2026-07-20", "evidence_status": "VERIFIED",
        "evidence_kind": "risk_event",
        "direction": "NEGATIVE", "indicator": "监管立案调查",
        "normalized_summary": "公司收到监管立案通知",
    }]
    result = event_risk(evidence, {"code": "000001", "industry": "半导体"}, as_of=date(2026, 7, 28))
    assert result["event_risk_level"] == "HIGH"
    assert result["event_critical_evidence_count"] == 1


def _event_audit(status: str = "OK") -> list[dict]:
    return [{
        "code": "000001", "collector": "cninfo_material_event",
        "status": status,
        "issue": "material_event_scan_complete" if status != "FAILED" else "material_event_scan_failed",
    }]


def test_event_risk_is_unknown_without_completed_official_scan() -> None:
    result = event_risk([], {"code": "000001"}, as_of=date(2026, 7, 28))
    assert result["event_scan_status"] == "UNKNOWN"
    assert result["event_risk_level"] == "UNKNOWN"


def test_completed_official_scan_with_no_event_is_low_risk() -> None:
    result = event_risk(
        [], {"code": "000001"}, as_of=date(2026, 7, 28), event_scan_rows=_event_audit(),
    )
    assert result["event_scan_status"] == "OK"
    assert result["event_risk_level"] == "LOW"


def test_resolved_material_event_does_not_create_high_risk() -> None:
    evidence = [{
        "scope": "company", "code": "000001", "date": "2026-07-27",
        "evidence_status": "VERIFIED", "evidence_kind": "material_event",
        "event_type": "SHARE_FREEZE", "event_status": "RESOLVED",
        "risk_valid_until": "2027-01-01", "content_hash": "resolved-1",
    }]
    result = event_risk(
        evidence, {"code": "000001"}, as_of=date(2026, 7, 28), event_scan_rows=_event_audit(),
    )
    assert result["event_risk_level"] == "LOW"
    assert result["event_critical_evidence_count"] == 0


def test_duplicate_active_material_event_is_counted_once() -> None:
    event = {
        "scope": "company", "code": "000001", "date": "2026-07-20",
        "evidence_status": "VERIFIED", "evidence_kind": "material_event",
        "event_type": "REGULATORY_INVESTIGATION", "event_status": "ACTIVE",
        "risk_valid_until": "2027-01-01", "content_hash": "same-filing",
    }
    result = event_risk(
        [event, dict(event)], {"code": "000001"},
        as_of=date(2026, 7, 28), event_scan_rows=_event_audit(),
    )
    assert result["event_risk_level"] == "HIGH"
    assert result["event_critical_evidence_count"] == 1


def test_progress_filings_of_same_medium_event_type_count_once() -> None:
    base = {
        "scope": "company", "code": "000001", "date": "2026-07-20",
        "evidence_status": "VERIFIED", "evidence_kind": "material_event",
        "event_type": "SHARE_FREEZE", "event_severity": "MEDIUM",
        "event_status": "ACTIVE", "risk_valid_until": "2027-01-01",
    }
    result = event_risk(
        [
            {**base, "content_hash": "freeze-initial"},
            {**base, "date": "2026-07-25", "content_hash": "freeze-progress"},
        ],
        {"code": "000001"}, as_of=date(2026, 7, 28), event_scan_rows=_event_audit(),
    )
    assert result["event_risk_level"] == "MEDIUM"
    assert result["event_negative_evidence_count"] == 1


def test_single_medium_material_event_warns_without_becoming_critical() -> None:
    event = {
        "scope": "company", "code": "000001", "date": "2026-07-20",
        "evidence_status": "VERIFIED", "evidence_kind": "material_event",
        "event_type": "SHARE_REDUCTION", "event_severity": "MEDIUM",
        "event_status": "ACTIVE", "risk_valid_until": "2027-01-01",
        "content_hash": "reduction-plan",
    }
    result = event_risk(
        [event], {"code": "000001"},
        as_of=date(2026, 7, 28), event_scan_rows=_event_audit(),
    )
    assert result["event_risk_level"] == "MEDIUM"
    assert result["event_negative_evidence_count"] == 1
    assert result["event_critical_evidence_count"] == 0


def test_newer_broad_resolved_notice_does_not_hide_unlinked_active_event() -> None:
    active = {
        "scope": "company", "code": "000001", "date": "2026-07-10",
        "evidence_status": "VERIFIED", "evidence_kind": "material_event",
        "event_type": "SHARE_FREEZE", "event_status": "ACTIVE",
        "risk_valid_until": "2027-01-01", "content_hash": "active-freeze",
    }
    resolved = {
        **active, "date": "2026-07-20", "event_status": "RESOLVED",
        "content_hash": "partial-unfreeze",
    }
    result = event_risk(
        [active, resolved], {"code": "000001"},
        as_of=date(2026, 7, 28), event_scan_rows=_event_audit(),
    )
    assert result["event_risk_level"] == "HIGH"
    assert result["event_critical_evidence_count"] == 1


def test_verified_full_resolution_closes_older_event_of_same_type() -> None:
    active = {
        "scope": "company", "code": "000001", "date": "2026-07-10",
        "evidence_status": "VERIFIED", "evidence_kind": "material_event",
        "event_type": "REGULATORY_INVESTIGATION", "event_severity": "HIGH",
        "event_status": "ACTIVE", "risk_valid_until": "2028-07-01",
        "content_hash": "investigation",
    }
    resolved = {
        **active, "date": "2026-07-20", "event_status": "RESOLVED",
        "event_resolution_scope": "FULL", "content_hash": "investigation-closed",
    }
    result = event_risk(
        [active, resolved], {"code": "000001"},
        as_of=date(2026, 7, 28), event_scan_rows=_event_audit(),
    )
    assert result["event_risk_level"] == "LOW"
    assert result["event_negative_evidence_count"] == 0


def test_ordinary_company_and_industry_negatives_are_not_material_events() -> None:
    evidence = [
        {
            "scope": "company", "code": "000001", "date": "2026-07-20",
            "evidence_status": "VERIFIED", "direction": "NEGATIVE",
            "indicator": "定期报告原文数值",
            "normalized_summary": "营业收入同比下降 12%，应收款存在逾期",
        },
        {
            "scope": "industry", "industry": "银行", "date": "2026-07-21",
            "evidence_status": "VERIFIED", "direction": "NEGATIVE",
            "indicator": "行业数据", "normalized_summary": "行业利润下降 8%",
        },
    ]
    result = event_risk(
        evidence, {"code": "000001", "industry": "银行"},
        as_of=date(2026, 7, 28), event_scan_rows=_event_audit(),
    )
    assert result["event_risk_level"] == "LOW"
    assert result["event_negative_evidence_count"] == 0


def test_open_high_risk_event_remains_visible_beyond_180_days() -> None:
    evidence = [{
        "scope": "company", "code": "000001", "date": "2025-05-01",
        "evidence_status": "VERIFIED", "evidence_kind": "material_event",
        "event_type": "REGULATORY_INVESTIGATION", "event_severity": "HIGH",
        "event_status": "ACTIVE", "risk_valid_until": "2027-05-01",
        "content_hash": "old-open-investigation",
    }]
    result = event_risk(
        evidence, {"code": "000001"},
        as_of=date(2026, 7, 28), event_scan_rows=_event_audit(),
    )
    assert result["event_risk_level"] == "HIGH"
    assert result["event_critical_evidence_count"] == 1


def test_real_world_gate_blocks_crisis_industry_and_distribution() -> None:
    row = _row(1)
    result = enrich_real_world_signals(
        row,
        market_regime={"status": "YELLOW", "score": 50, "position_multiplier": 0.5, "external_risk_level": "MEDIUM"},
        industry_regimes={"半导体": {"status": "CRISIS", "score": 20, "sample_count": 30}},
        evidence_rows=[],
        as_of=date(2026, 7, 28),
    )
    assert result["real_world_gate_passed"] is False
    assert "industry_regime_crisis" in result["real_world_risk_flags"]
    assert "price_volume_distribution" in result["real_world_risk_flags"]


def test_real_world_composite_preserves_zero_scores() -> None:
    row = _row(1)
    result = enrich_real_world_signals(
        row,
        market_regime={"status": "RED", "score": 0, "position_multiplier": 0},
        industry_regimes={"半导体": {"status": "CRISIS", "score": 0, "sample_count": 20}},
        evidence_rows=[],
        as_of=date(2026, 7, 28),
    )
    assert result["market_regime_score"] == 0
    assert result["industry_regime_score"] == 0
    assert result["real_world_score"] < 20


def test_history_snapshot_is_point_in_time() -> None:
    frame = _history(last_return=3.0, last_volume_ratio=2.0)
    prior_date = frame.iloc[-2]["date"]
    snapshot = history_snapshot(frame, as_of=prior_date)
    assert snapshot["trade_date"] == prior_date.isoformat()
    assert snapshot["volume_ratio_20"] == 1.0
