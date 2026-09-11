from __future__ import annotations

from src.strategies.genge_opportunity_discovery.deep_workset import retained_deep_codes


def test_unresolved_and_fail_gate_codes_are_retained_without_hardcoding():
    status = {
        "unresolved_reasons": {
            "601899": {"predictability": "INSUFFICIENT_EVIDENCE"},
            "001316": {"moat": "NO_STRICT_MACHINE_RULE"},
        },
        "formal_trading_authority": False,
        "automatic_formal_buy_allowed": False,
        "unknown_is_pass": False,
        "no_auto_trade": True,
    }
    profiles = {
        "profiles": {
            "603233": {
                "gates": {
                    "financial_safety": {
                        "status": "FAIL",
                        "rationale": "verified active funds occupation",
                    }
                }
            },
            "600000": {"gates": {"predictability": {"status": "PASS"}}},
        }
    }

    assert retained_deep_codes(status, profiles) == ["601899", "001316", "603233"]


def test_duplicate_continuity_sources_are_deduplicated_in_first_seen_order():
    status = {"unresolved_reasons": {"603233": {}, "601899": {}}}
    profiles = {
        "profiles": {
            "603233": {"gates": {"financial_safety": {"status": "FAIL"}}},
            "001316": {"gates": {"earnings_authenticity": {"status": "FAIL"}}},
        }
    }

    assert retained_deep_codes(status, profiles) == ["603233", "601899", "001316"]


def test_pass_only_profile_is_not_retained_by_continuity_rule():
    assert retained_deep_codes(
        {"unresolved_reasons": {}},
        {"profiles": {"600000": {"gates": {"predictability": {"status": "PASS"}}}}},
    ) == []
