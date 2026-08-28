from decimal import Decimal

from src.strategies.genge_opportunity_discovery.formal_decision_outcomes import evaluate


def test_outcomes_remain_pending_until_enough_trading_dates():
    records = [{"record_id": "r1", "canonical_snapshot_id": "s1", "code": "600406", "name": "国电南瑞", "scope": "HOLDING", "formal_action": "HOLD", "decision_date": "2026-08-28", "current_price": "20", "valuation_confidence": "HIGH", "reason_codes": "X"}]
    prices = {"600406": {"2026-08-31": Decimal("21"), "2026-09-01": Decimal("22")}}
    payload = evaluate(records, prices)
    row = payload["records"][0]
    assert row["horizons"]["d5"]["status"] == "PENDING"
    assert payload["parameter_tuning_allowed"] is False
    assert payload["formal_action_recomputed"] is False


def test_five_day_outcome_uses_distinct_forward_dates():
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
    assert payload["formal_action_eligible"] is False
