import json
from decimal import Decimal

from src.strategies.genge_opportunity_discovery.formal_decision_outcomes import evaluate, load_daily_prices


def test_outcomes_remain_pending_until_enough_trading_dates():
    records = [{"record_id": "r1", "canonical_snapshot_id": "s1", "code": "600406", "name": "国电南瑞", "scope": "HOLDING", "formal_action": "HOLD", "decision_date": "2026-08-28", "current_price": "20", "valuation_confidence": "HIGH", "reason_codes": "X"}]
    prices = {"600406": {"2026-08-31": Decimal("21"), "2026-09-01": Decimal("22")}}
    payload = evaluate(records, prices)
    row = payload["records"][0]
    assert row["horizons"]["d5"]["status"] == "PENDING"
    assert payload["parameter_review_ready_bucket_count"] == 0
    assert payload["parameter_tuning_allowed"] is False
    assert payload["automatic_parameter_tuning_allowed"] is False
    assert payload["formal_action_recomputed"] is False


def test_five_day_outcome_uses_distinct_forward_dates_and_builds_group_stats():
    records = [{"record_id": "r1", "canonical_snapshot_id": "s1", "code": "600406", "name": "国电南瑞", "scope": "HOLDING", "formal_action": "BUY", "decision_date": "2026-08-28", "current_price": "20", "valuation_confidence": "HIGH", "reason_codes": "X"}]
    prices = {"600406": {
        "2026-08-31": Decimal("21"),
        "2026-09-01": Decimal("22"),
        "2026-09-02": Decimal("23"),
        "2026-09-03": Decimal("24"),
        "2026-09-04": Decimal("25"),
    }}
    payload = evaluate(records, prices)
    result = payload["records"][0]["horizons"]["d5"]
    assert result["status"] == "OBSERVED"
    assert result["target_date"] == "2026-09-04"
    assert result["return"] == "0.250000"
    stats = payload["group_statistics"]["BUY"]["d5"]
    assert stats["sample_count"] == 1
    assert stats["mean_return"] == "0.250000"
    assert stats["median_return"] == "0.250000"
    assert stats["review_readiness"] == "INSUFFICIENT_SAMPLE"
    assert payload["formal_action_eligible"] is False


def test_twenty_samples_only_unlock_human_review_not_parameter_tuning():
    records = []
    prices = {}
    forward_dates = [f"2026-09-{day:02d}" for day in range(1, 6)]
    for i in range(20):
        code = f"60{i:04d}"[-6:]
        records.append({"record_id": f"r{i}", "canonical_snapshot_id": "s", "code": code, "name": code, "scope": "CANDIDATE", "formal_action": "BUY", "decision_date": "2026-08-28", "current_price": "10", "valuation_confidence": "HIGH", "reason_codes": "X"})
        prices[code] = {d: Decimal("11") for d in forward_dates}
    payload = evaluate(records, prices)
    stats = payload["group_statistics"]["BUY"]["d5"]
    assert stats["sample_count"] == 20
    assert stats["review_readiness"] == "READY_FOR_HUMAN_REVIEW"
    assert payload["parameter_review_ready_bucket_count"] == 1
    assert payload["human_parameter_review_allowed_when_sample_ready"] is True
    assert payload["parameter_tuning_allowed"] is False
    assert payload["automatic_parameter_tuning_allowed"] is False


def _write_overlay(root, file_day, name, market_day, quote_time, *, price="21", status="OK", provider="tencent_quote"):
    folder = root / file_day
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text(json.dumps({
        "generated_at_beijing": f"{file_day}T08:00:00+08:00",
        "latest_trade_date": market_day,
        "rows": [{
            "code": "600406", "latest_price": price,
            "latest_price_status": status, "latest_price_provider": provider,
            "latest_price_observed_at": quote_time,
        }],
    }), encoding="utf-8")


def test_historical_outcomes_never_turn_same_stale_quote_into_multiple_sessions(tmp_path):
    # Two later reports generated on different calendar days are both 9/24 prices.
    _write_overlay(tmp_path, "2026-09-27", "22.json", "2026-09-24",
                   "2026-09-24T16:14:47+08:00")
    _write_overlay(tmp_path, "2026-09-28", "07.json", "2026-09-24",
                   "2026-09-24T16:14:47+08:00")
    prices = load_daily_prices(tmp_path)
    assert prices == {"600406": {"2026-09-24": Decimal("21")}}
    record = {"record_id": "r1", "canonical_snapshot_id": "s1", "code": "600406",
              "scope": "HOLDING", "formal_action": "HOLD",
              "decision_date": "2026-09-24", "current_price": "20"}
    result = evaluate([record], prices)
    assert result["records"][0]["horizons"]["d5"] == {
        "status": "PENDING", "observed_trading_days": 0,
    }
    assert result["observed_horizon_count"] == 0
    assert result["corporate_action_adjustment_verified"] is False
    assert result["independent_benchmark_verified"] is False
    assert result["full_v4_h4_acceptance"] is False


def test_historical_outcomes_fail_closed_on_quote_date_status_and_preclose(tmp_path):
    _write_overlay(tmp_path, "2026-09-24", "01.json", "2026-09-24",
                   "2026-09-23T16:14:47+08:00")  # mismatched quote day
    _write_overlay(tmp_path, "2026-09-24", "02.json", "2026-09-24",
                   "2026-09-24T14:20:00+08:00")  # before market close
    _write_overlay(tmp_path, "2026-09-24", "03.json", "2026-09-24",
                   "2026-09-24T16:14:47", price="999")  # no timezone
    _write_overlay(tmp_path, "2026-09-24", "04.json", "2026-09-24",
                   "2026-09-24T16:14:47+08:00", status="STALE", price="998")
    _write_overlay(tmp_path, "2026-09-24", "05.json", "2026-09-24",
                   "2026-09-24T16:14:47+08:00", provider="", price="997")
    assert load_daily_prices(tmp_path) == {}


def test_historical_outcomes_keep_latest_valid_quote_within_one_real_day(tmp_path):
    _write_overlay(tmp_path, "2026-09-24", "01.json", "2026-09-24",
                   "2026-09-24T16:10:00+08:00", price="21")
    _write_overlay(tmp_path, "2026-09-25", "01.json", "2026-09-24",
                   "2026-09-24T16:20:00+08:00", price="22")
    _write_overlay(tmp_path, "2026-09-26", "01.json", "2026-09-24",
                   "2026-09-24T16:11:00+08:00", price="23")
    got = load_daily_prices(tmp_path)
    assert got == {"600406": {"2026-09-24": Decimal("22")}}
