from __future__ import annotations

from src.strategies.genge_opportunity_discovery.deep_workset import retained_deep_codes


def test_unresolved_unknown_and_fail_gate_codes_are_retained_without_hardcoding():
    status = {
        "unresolved_reasons": {
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
            # Mirrors the production 601899 edge case: it is present in the
            # persisted Deep lineage with UNKNOWN gates even when the status
            # unresolved_reasons map does not name it.
            "601899": {
                "gates": {
                    "earnings_authenticity": {"status": "UNKNOWN"},
                    "financial_safety": {"status": "UNKNOWN"},
                    "long_term_demand": {"status": "UNKNOWN"},
                    "moat": {"status": "UNKNOWN"},
                    "predictability": {"status": "UNKNOWN"},
                }
            },
            "600000": {"gates": {"predictability": {"status": "PASS"}}},
        }
    }

    assert retained_deep_codes(status, profiles) == ["001316", "603233", "601899"]


def test_duplicate_continuity_sources_are_deduplicated_in_first_seen_order():
    status = {"unresolved_reasons": {"603233": {}, "601899": {}}}
    profiles = {
        "profiles": {
            "603233": {"gates": {"financial_safety": {"status": "FAIL"}}},
            "001316": {"gates": {"earnings_authenticity": {"status": "UNKNOWN"}}},
        }
    }

    assert retained_deep_codes(status, profiles) == ["603233", "601899", "001316"]


def test_missing_gate_status_is_retained_fail_closed():
    assert retained_deep_codes(
        {"unresolved_reasons": {}},
        {"profiles": {"601899": {"gates": {"predictability": {}}}}},
    ) == ["601899"]


def test_pass_only_profile_is_not_retained_by_continuity_rule():
    assert retained_deep_codes(
        {"unresolved_reasons": {}},
        {"profiles": {"600000": {"gates": {"predictability": {"status": "PASS"}}}}},
    ) == []
