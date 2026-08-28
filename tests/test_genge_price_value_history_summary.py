from decimal import Decimal

from src.strategies.genge_opportunity_discovery.price_value_history_summary import _window, summarize


def test_window_separates_price_change_from_anchor_drift():
    rows = [
        {"price": "80", "value_anchor": "100", "price_to_value": "0.80"},
        {"price": "70", "value_anchor": "100", "price_to_value": "0.70"},
    ]
    result = _window(rows)
    assert result["days_at_or_below_0_80"] == 2
    assert result["price_change"] == "-0.125000"
    assert result["value_anchor_drift"] == "0.000000"


def test_summary_is_research_only():
    payload = summarize({"600406": [{"date": "2026-08-28", "price": Decimal("20"), "value_anchor": Decimal("25"), "price_to_value": Decimal("0.8"), "margin_of_safety": Decimal("0.2")}]})
    assert payload["security_count"] == 1
    assert payload["formal_action_recomputed"] is False
    assert payload["formal_action_eligible"] is False
    assert payload["no_auto_trade"] is True
