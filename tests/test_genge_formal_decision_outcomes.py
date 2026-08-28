from decimal import Decimal

from src.strategies.genge_opportunity_discovery.formal_decision_outcomes import evaluate


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
