from src.strategies.genge_opportunity_discovery.investor_event_closure import (
    apply_event_closure,
    build_event_closure,
)


def _dashboard(action="HOLD"):
    return {
        "formal_action_source": "FINALIZED_CANONICAL_ONLY",
        "formal_action_recomputed": False,
        "no_auto_trade": True,
        "stock_portfolio": {
            "rows": [
                {"code": "603993", "name": "洛阳钼业", "formal_action": action},
                {"code": "600406", "name": "国电南瑞", "formal_action": "REDUCE_25"},
            ]
        },
        "opportunities": [
            {
                "code": "000426",
                "name": "兴业银锡",
                "formal_action": "",
                "hard_blockers": "scenario_valuation_incomplete;buy_condition_failed:clear_margin_of_safety",
            }
        ],
        "event_review": {"triggered": False, "status": "NO_EVENT_CONTEXT"},
    }


def _hourly():
    return {
        "rows": [
            {
                "code": "603993",
                "name": "洛阳钼业",
                "deep_review_priority": "RAISE",
                "latest_price": 18.46,
                "latest_price_observed_at": "2026-09-02T16:14:33+08:00",
                "price_evidence_status": "PRICE_GATE_PASS_RESEARCH_ONLY",
            },
            {
                "code": "000426",
                "name": "兴业银锡",
                "deep_review_priority": "RAISE",
                "latest_price": 38.02,
                "price_evidence_status": "VALUE_ANCHOR_UNAVAILABLE",
            },
        ]
    }


def _event():
    return {
        "canonical_snapshot_id": "old-snapshot",
        "canonical_source_run_id": "100",
        "dispatch_required": True,
        "signal_digest": "abc",
        "trigger_codes": ["603993"],
        "triggers": [
            {
                "code": "603993",
                "name": "洛阳钼业",
                "existing_formal_action": "HOLD",
                "priority": "P0",
                "trigger_reasons": ["PRICE_ATTRACTIVE_RESEARCH_LEAD", "SIGNIFICANT_HOLDING_PRICE_MOVE"],
            }
        ],
    }


def test_running_event_is_explicit_and_raise_only_is_distinct():
    section = build_event_closure(
        _dashboard(),
        _hourly(),
        _event(),
        {"status": "EVENT_TRIGGERED_RUNNING"},
    )
    by_code = {row["code"]: row for row in section["rows"]}
    assert by_code["603993"]["event_result_state"] == "EVENT_TRIGGERED_RUNNING"
    assert by_code["603993"]["formal_action_after"] == "HOLD"
    assert "完整 Deep Review" in by_code["603993"]["result"]
    assert by_code["000426"]["event_result_state"] == "RAISE_ONLY"
    assert "价值锚不可用" in by_code["000426"]["why_no_buy_or_add"]
    assert section["formal_action_recomputed"] is False
    assert section["no_auto_trade"] is True


def test_finalized_same_action_becomes_event_triggered_no_change():
    section = build_event_closure(
        _dashboard("HOLD"),
        _hourly(),
        _event(),
        {
            "status": "EVENT_TRIGGERED_FINALIZED",
            "event_research_source_run_id": "200",
            "event_finalizer_run_id": "300",
            "event_finalized_snapshot_id": "new-snapshot",
        },
    )
    row = next(row for row in section["rows"] if row["code"] == "603993")
    assert row["event_result_state"] == "EVENT_TRIGGERED_NO_CHANGE"
    assert row["formal_action_changed"] is False
    assert "重新计算后正式动作仍为 HOLD" in row["result"]
    assert section["event_finalizer_run_id"] == "300"


def test_finalized_changed_action_is_explicit_but_never_recomputed_here():
    dashboard = _dashboard("ADD")
    section = build_event_closure(
        dashboard,
        _hourly(),
        _event(),
        {"status": "EVENT_TRIGGERED_FINALIZED"},
    )
    row = next(row for row in section["rows"] if row["code"] == "603993")
    assert row["event_result_state"] == "EVENT_TRIGGERED_FINALIZED"
    assert row["formal_action_before"] == "HOLD"
    assert row["formal_action_after"] == "ADD"
    assert row["formal_action_changed"] is True
    assert section["formal_action_source"] == "FINALIZED_CANONICAL_ONLY"
    assert section["formal_action_recomputed"] is False


def test_failed_event_is_fail_closed_not_a_trade_signal():
    section = build_event_closure(
        _dashboard(),
        _hourly(),
        _event(),
        {"status": "EVENT_TRIGGER_FAILED"},
    )
    row = next(row for row in section["rows"] if row["code"] == "603993")
    assert row["event_result_state"] == "EVENT_TRIGGER_FAILED"
    assert row["formal_action_after"] == "HOLD"
    assert "不得把研究信号当作正式交易动作" in row["result"]


def test_markdown_replaces_vague_event_section_with_explicit_table():
    markdown = "# 投资决策驾驶舱\n\n## 7. 事件触发 / 深算变化\n\n- 当前没有需要单独展示的事件触发上下文。\n\n---\nfooter\n"
    dashboard, text = apply_event_closure(
        _dashboard(),
        markdown,
        _hourly(),
        _event(),
        {"status": "EVENT_TRIGGERED_RUNNING"},
    )
    assert "## 7. 事件深算闭环：到底算完没有" in text
    assert "EVENT_TRIGGERED_RUNNING" in text
    assert "RAISE_ONLY" in text
    assert "当前没有需要单独展示的事件触发上下文" not in text
    assert dashboard["event_review"]["triggered"] is True
    assert dashboard["event_review"]["closure_status"] == "EVENT_TRIGGERED_RUNNING"
