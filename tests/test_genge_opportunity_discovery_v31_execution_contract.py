from src.strategies.genge_opportunity_discovery.selection_framework_v31 import (
    execution_universe_status,
    exit_action_from_valuation,
)


def test_v31_execution_universe_allows_only_user_main_board_prefixes():
    allowed = ["600118", "601899", "603035", "605123", "000657", "001316", "002493", "003816"]
    blocked = ["688281", "300693", "301123", "830000", "900901"]

    for code in allowed:
        assert execution_universe_status(code) == "EXECUTION_ELIGIBLE"
    for code in blocked:
        assert execution_universe_status(code) == "RESEARCH_ONLY"


def test_v31_execution_universe_normalizes_exchange_suffixes():
    assert execution_universe_status("600118.SH") == "EXECUTION_ELIGIBLE"
    assert execution_universe_status("SZ001316") == "EXECUTION_ELIGIBLE"
    assert execution_universe_status("688281.SH") == "RESEARCH_ONLY"
    assert execution_universe_status("not-a-code") == "UNKNOWN"


def test_v31_exit_ladder_is_valuation_driven_when_hard_logic_intact():
    assert exit_action_from_valuation(current_price=99, neutral_value=100)[0] == "HOLD"
    assert exit_action_from_valuation(current_price=100, neutral_value=100)[0] == "HOLD_NO_ADD"
    assert exit_action_from_valuation(current_price=120, neutral_value=100) == (
        "REDUCE_25",
        "price_to_neutral=1.200>=1.20",
        0.75,
    )
    assert exit_action_from_valuation(current_price=140, neutral_value=100) == (
        "REDUCE_50",
        "price_to_neutral=1.400>=1.40",
        0.50,
    )
    assert exit_action_from_valuation(current_price=170, neutral_value=100) == (
        "CORE_ONLY",
        "price_to_neutral=1.700>=1.70",
        0.25,
    )


def test_v31_broken_hard_logic_overrides_valuation_and_exits():
    action, reason, target = exit_action_from_valuation(
        current_price=60,
        neutral_value=100,
        hard_gate_failures=("long_term_demand",),
    )
    assert action == "EXIT"
    assert reason == "hard_logic_broken:long_term_demand"
    assert target == 0.0
