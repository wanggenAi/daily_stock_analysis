from src.strategies.genge_opportunity_discovery.long_term_valuation_merge import merge_long_term_into_valuation


def test_long_term_candidate_is_added_and_never_promoted():
    rows = merge_long_term_into_valuation(
        [{"code": "000001", "valuation_source_channel": "GLOBAL_RECALL"}],
        [{
            "code": "603369",
            "stock_name": "今世缘",
            "long_term_second_pass_status": "PASSED_ALL_NON_EXIT_PROFILE_HARD_GATES",
            "hard_blockers": "",
            "quant_status": "SECONDARY_RESEARCH",
        }],
    )
    by_code = {row["code"]: row for row in rows}
    assert "603369" in by_code
    assert by_code["603369"]["valuation_source_channel"] == "LONG_TERM_SECOND_PASS"
    assert by_code["603369"]["formal_signal_eligible"] is False
    assert by_code["603369"]["automatic_promotion_allowed"] is False
    assert by_code["603369"]["no_auto_trade"] is True


def test_existing_candidate_is_marked_both_channels():
    rows = merge_long_term_into_valuation(
        [{"code": "603369", "valuation_source_channel": "BOTH"}],
        [{
            "code": "603369",
            "long_term_second_pass_status": "PASSED_ALL_NON_EXIT_PROFILE_HARD_GATES",
            "hard_blockers": "",
        }],
    )
    assert len(rows) == 1
    assert rows[0]["valuation_source_channel"] == "BOTH+LONG_TERM_SECOND_PASS"


def test_hard_blocked_second_pass_row_is_rejected():
    rows = merge_long_term_into_valuation(
        [{"code": "000001", "valuation_source_channel": "GLOBAL_RECALL"}],
        [{
            "code": "999999",
            "long_term_second_pass_status": "PASSED_ALL_NON_EXIT_PROFILE_HARD_GATES",
            "hard_blockers": "financial_integrity",
        }],
    )
    assert {row["code"] for row in rows} == {"000001"}
