from decimal import Decimal

from src.strategies.genge_opportunity_discovery.success_archetype_outcomes import (
    append_cohort,
    evaluate,
)


def _priority():
    return {
        "contract_version": "GEN_GE_SUCCESS_ARCHETYPE_RECALL_V2_BOUNDED_WIDE_FINANCIAL_FETCH",
        "archetype_id": "RUNBEI_TEST",
        "as_of": "2026-09-04",
        "source_terminal_run_id": "12345",
        "changes_research_order_only": True,
        "changes_thresholds": False,
        "formal_action_eligible": False,
        "formal_action_recomputed": False,
        "canonical_authority_unchanged": True,
        "automatic_promotion_allowed": False,
        "starter_position_allowed": False,
        "no_auto_trade": True,
        "queue": [
            {
                "code": "600001",
                "name": "测试股",
                "similarity_score": 82.5,
                "evidence_coverage": 1.0,
                "source_quant_status": "HARD_REJECT",
                "source_financial_review_status": "NOT_SELECTED_FOR_DEEP_FINANCIAL_REVIEW",
                "financial_evidence_origin": "ARCHETYPE_BOUNDED_FINANCIAL_FETCH",
                "source_price": 10,
                "source_price_field": "terminal_current_price",
                "source_price_known_by_recall": True,
            }
        ],
    }


def _prices():
    rows = {
        "2026-09-04": Decimal("10"),
        "2026-09-07": Decimal("10.1"),
        "2026-09-08": Decimal("10.2"),
        "2026-09-09": Decimal("10.3"),
        "2026-09-10": Decimal("10.4"),
        "2026-09-11": Decimal("11"),
    }
    return {"600001": rows}


def test_append_cohort_is_idempotent_and_freezes_terminal_price_baseline():
    first = append_cohort([], _priority(), _prices())
    second = append_cohort(first, _priority(), _prices())
    assert len(first) == 1
    assert len(second) == 1
    assert first[0]["baseline_date"] == "2026-09-04"
    assert first[0]["baseline_price"] == "10"
    assert first[0]["baseline_source"] == "SUCCESS_ARCHETYPE_TERMINAL_CURRENT_PRICE"
    assert first[0]["similarity_bucket"] == "S80_PLUS"


def test_terminal_price_baseline_does_not_require_hourly_overlay_membership():
    records = append_cohort([], _priority(), {})
    assert records[0]["baseline_date"] == "2026-09-04"
    assert records[0]["baseline_price"] == "10"
    assert records[0]["baseline_source"] == "SUCCESS_ARCHETYPE_TERMINAL_CURRENT_PRICE"


def test_evaluate_observes_fifth_distinct_trading_day_and_never_changes_authority():
    records = append_cohort([], _priority(), _prices())
    payload = evaluate(records, _prices())
    row = payload["records"][0]
    assert row["horizons"]["d5"]["status"] == "OBSERVED"
    assert row["horizons"]["d5"]["target_date"] == "2026-09-11"
    assert row["horizons"]["d5"]["return"] == "0.100000"
    assert row["horizons"]["d20"]["status"] == "PENDING"
    assert payload["formal_action_recomputed"] is False
    assert payload["formal_action_eligible"] is False
    assert payload["parameter_tuning_allowed"] is False
    assert payload["automatic_parameter_tuning_allowed"] is False
    assert payload["no_auto_trade"] is True


def test_missing_baseline_price_stays_pending_instead_of_becoming_pass():
    priority = _priority()
    priority["queue"][0]["source_price"] = None
    priority["queue"][0]["source_price_known_by_recall"] = False
    records = append_cohort([], priority, {})
    assert records[0]["baseline_price"] is None
    assert records[0]["baseline_source"] == "UNAVAILABLE"
    payload = evaluate(records, {})
    assert payload["records"][0]["horizons"]["d5"]["status"] == "PENDING"
    assert payload["observed_horizon_count"] == 0
    assert payload["pending_horizon_count"] == 3


def test_legacy_v1_without_as_of_skips_outcome_cohort_without_fabricating_date():
    priority = _priority()
    priority["contract_version"] = "GEN_GE_SUCCESS_ARCHETYPE_RECALL_V1"
    priority.pop("as_of")
    priority.pop("source_terminal_run_id")
    existing = [
        {
            "record_id": "existing-record",
            "archetype_id": "RUNBEI_OLD",
            "cohort_date": "2026-09-01",
            "code": "600002",
        }
    ]
    records = append_cohort(existing, priority, _prices())
    assert records == existing
    assert all(row.get("cohort_date") != "" for row in records)


def test_current_contract_missing_as_of_still_fails_closed():
    priority = _priority()
    priority.pop("as_of")
    try:
        append_cohort([], priority, _prices())
    except ValueError as exc:
        assert "requires as_of and archetype_id" in str(exc)
    else:
        raise AssertionError("current recall contract missing as_of must fail closed")


def test_priority_authority_violation_fails_closed():
    priority = _priority()
    priority["formal_action_eligible"] = True
    try:
        append_cohort([], priority, _prices())
    except ValueError as exc:
        assert "Formal authority" in str(exc)
    else:
        raise AssertionError("authority violation must fail closed")
