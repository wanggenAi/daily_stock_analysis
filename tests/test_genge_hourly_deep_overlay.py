from datetime import datetime, timezone

from src.strategies.genge_opportunity_discovery.hourly_deep_overlay import (
    Quote,
    build_overlay,
    extract_workset,
    is_tradeable_mainboard,
)


def _bundle():
    return {
        "snapshot_id": "snap-1",
        "source_run_id": "run-1",
        "latest_trade_date": "2026-08-27",
        "research_as_of": "2026-08-28T02:37:09Z",
        "hourly": {
            "canonical_snapshot_id": "snap-1",
            "canonical_source_run_id": "run-1",
            "holding_decisions": [
                {
                    "code": "600406",
                    "name": "国电南瑞",
                    "formal_action": "REDUCE_25",
                    "current_price": 23.06,
                    "neutral_value": 17.46,
                }
            ],
            "deep_review_focus": [
                {
                    "code": "600312",
                    "name": "平高电气",
                    "action": "WAIT",
                    "current_price": 20.01,
                    "neutral_value": 25.50,
                },
                {
                    "code": "300001",
                    "name": "创业板示例",
                    "action": "BUY",
                    "current_price": 10.0,
                    "neutral_value": 20.0,
                },
            ],
        },
    }


def test_tradeable_scope_only_mainboards():
    assert is_tradeable_mainboard("600312")
    assert is_tradeable_mainboard("000682")
    assert is_tradeable_mainboard("002595")
    assert not is_tradeable_mainboard("300001")
    assert not is_tradeable_mainboard("688001")


def test_extract_workset_excludes_non_mainboard():
    rows = extract_workset(_bundle()["hourly"])
    assert [row["code"] for row in rows] == ["600406", "600312"]
    assert rows[0]["scope"] == "HOLDING"


def test_overlay_never_recomputes_formal_action_and_computes_price_evidence():
    quotes = {
        "600406": Quote("600406", "国电南瑞", 22.92, 23.06, -0.6071, "2026-08-28T14:00:00+08:00", "fixture"),
        "600312": Quote("600312", "平高电气", 19.80, 20.01, -1.0495, "2026-08-28T14:00:00+08:00", "fixture"),
    }
    payload = build_overlay(
        _bundle(),
        quote_provider=lambda codes: {code: quotes[code] for code in codes},
        generated_at=datetime(2026, 8, 28, 6, 0, tzinfo=timezone.utc),
    )
    assert payload["formal_action_recomputed"] is False
    assert payload["overlay_may_overwrite_formal_action"] is False
    assert payload["price_overlay_is_formal_buy"] is False

    by_code = {row["code"]: row for row in payload["rows"]}
    assert by_code["600406"]["formal_action"] == "REDUCE_25"
    assert by_code["600406"]["hourly_research_conclusion"] == "FORMAL_ACTION_UNCHANGED"

    pinggao = by_code["600312"]
    assert pinggao["formal_action"] == "WAIT"
    assert pinggao["price_to_value"] == round(19.80 / 25.50, 6)
    assert pinggao["margin_of_safety"] == round(1 - 19.80 / 25.50, 6)
    assert pinggao["price_evidence_status"] == "PRICE_GATE_PASS_RESEARCH_ONLY"
    assert pinggao["hourly_research_conclusion"] == "PRICE_ATTRACTIVE_RESEARCH_LEAD"
    assert pinggao["deep_review_priority"] == "RAISE"
