"""Project event-driven deep-review closure into the investor dashboard.

Presentation only: this module never computes Formal actions.  It copies the
current action from the already-authorized investor dashboard and explains
whether an event-triggered full production cycle is still running, finalized,
or failed.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Mapping

FORMAL_ACTION_SOURCE = "FINALIZED_CANONICAL_ONLY"
NO_AUTO_TRADE = True


def _load(path: Path | None) -> dict[str, Any]:
    if path is None or not path.is_file():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object JSON: {path}")
    return value


def _code(value: Any) -> str:
    text = str(value or "").strip().upper()
    if "." in text:
        text = text.split(".", 1)[0]
    for prefix in ("SH", "SZ", "BJ"):
        if text.startswith(prefix) and text[len(prefix):].isdigit():
            text = text[len(prefix):]
            break
    return text.zfill(6) if text.isdigit() else text


def _action_map(dashboard: Mapping[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for row in dashboard.get("stock_portfolio", {}).get("rows") or []:
        result[_code(row.get("code"))] = str(row.get("formal_action") or "").strip().upper()
    for row in dashboard.get("opportunities") or []:
        code = _code(row.get("code"))
        action = str(row.get("formal_action") or "").strip().upper()
        if code and action:
            result[code] = action
    return result


def _hourly_map(hourly: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {_code(row.get("code")): dict(row) for row in hourly.get("rows") or [] if _code(row.get("code"))}


def _human_blocker(action: str, hourly: Mapping[str, Any], raw: str = "") -> str:
    action = str(action or "").upper()
    price_status = str(hourly.get("price_evidence_status") or "")
    confidence = str(hourly.get("valuation_confidence") or "").upper()
    if action in {"BUY", "ADD"}:
        return "已形成正式 BUY/ADD；仍遵守 no-auto-trade，由用户决定是否执行。"
    if action in {"EXIT", "SELL", "REDUCE", "REDUCE_25", "REDUCE_50"}:
        return f"当前 Canonical 正式动作是 {action}，本轮没有形成反向 BUY/ADD。"
    if price_status == "VALUE_ANCHOR_UNAVAILABLE":
        return "价格可以继续研究，但正式价值锚不可用；在估值与 Confidence Gate 补齐前不能升级 BUY/ADD。"
    if price_status == "PRICE_GATE_PASS_RESEARCH_ONLY":
        return "价格已进入研究价值区，但这只代表研究触发；仍需完整 Hard/Confidence Gate 与正式估值通过后才可 BUY/ADD。"
    if confidence in {"LOW", "INVALID"}:
        return f"估值置信度为 {confidence}，正式 BUY/ADD 仍被 Confidence Gate 阻止。"
    raw_text = str(raw or "")
    if "hard_gate_unknown" in raw_text or "all_hard_logic_gates" in raw_text:
        return "核心硬逻辑/护城河/长期需求等 Hard Gate 仍有未验证项，暂不能正式买入。"
    if "scenario_valuation_incomplete" in raw_text or "clear_margin_of_safety" in raw_text:
        return "正式情景估值或安全边际尚未闭合，暂不能正式买入。"
    return f"当前正式动作仍为 {action or 'NO_ACTION'}；没有足够证据跨过 BUY/ADD 的全部生产门槛。"


def build_event_closure(
    dashboard: Mapping[str, Any],
    hourly: Mapping[str, Any],
    event: Mapping[str, Any],
    closure: Mapping[str, Any],
) -> dict[str, Any]:
    if dashboard.get("formal_action_source") != FORMAL_ACTION_SOURCE:
        raise ValueError("dashboard Formal source is not finalized Canonical")
    if dashboard.get("formal_action_recomputed") is not False or dashboard.get("no_auto_trade") is not True:
        raise ValueError("dashboard lost Formal/no-auto-trade contract")

    actions = _action_map(dashboard)
    hourly_by_code = _hourly_map(hourly)
    trigger_rows = {_code(row.get("code")): dict(row) for row in event.get("triggers") or []}
    trigger_codes = {_code(code) for code in event.get("trigger_codes") or []}
    overall = str(closure.get("status") or ("EVENT_TRIGGERED_RUNNING" if event.get("dispatch_required") else "NO_EVENT_TRIGGER"))

    rows: list[dict[str, Any]] = []
    universe: set[str] = set(actions)
    universe.update(trigger_codes)
    universe.update(code for code, row in hourly_by_code.items() if str(row.get("deep_review_priority") or "").upper() == "RAISE")

    names: dict[str, str] = {}
    blockers: dict[str, str] = {}
    for row in dashboard.get("stock_portfolio", {}).get("rows") or []:
        names[_code(row.get("code"))] = str(row.get("name") or "")
    for row in dashboard.get("opportunities") or []:
        code = _code(row.get("code"))
        names.setdefault(code, str(row.get("name") or ""))
        blockers[code] = str(row.get("hard_blockers") or row.get("why_not_buy_yet") or "")
    for code, row in trigger_rows.items():
        names[code] = str(row.get("name") or names.get(code) or "")

    for code in sorted(universe):
        h = hourly_by_code.get(code, {})
        trigger = trigger_rows.get(code, {})
        current = actions.get(code, str(trigger.get("existing_formal_action") or "").upper())
        before = str(trigger.get("existing_formal_action") or current or "").upper()
        priority = str(h.get("deep_review_priority") or "").upper()
        if code in trigger_codes:
            if overall == "EVENT_TRIGGERED_FINALIZED":
                state = "EVENT_TRIGGERED_FINALIZED" if current and current != before else "EVENT_TRIGGERED_NO_CHANGE"
            elif overall == "EVENT_TRIGGER_FAILED":
                state = "EVENT_TRIGGER_FAILED"
            else:
                state = "EVENT_TRIGGERED_RUNNING"
        elif priority == "RAISE":
            state = "RAISE_ONLY"
        else:
            continue

        if state == "RAISE_ONLY":
            result = "研究优先级已提高，但当前信号未达到事件型完整生产重算触发条件。"
        elif state == "EVENT_TRIGGERED_RUNNING":
            result = "事件已触发完整 Deep Review → Finalizer 链；正式动作在新 Canonical 产出前保持不变。"
        elif state == "EVENT_TRIGGER_FAILED":
            result = "事件要求深算，但完整生产链未成功闭环；不得把研究信号当作正式交易动作。"
        elif state == "EVENT_TRIGGERED_FINALIZED":
            result = f"事件深算已 Finalize，正式动作由 {before or '—'} 变为 {current or '—'}。"
        else:
            result = f"事件深算已 Finalize；重新计算后正式动作仍为 {current or before or '—'}，不是‘还没算’。"

        rows.append({
            "code": code,
            "name": names.get(code, ""),
            "event_result_state": state,
            "deep_review_priority": priority or str(trigger.get("priority") or ""),
            "trigger_reasons": list(trigger.get("trigger_reasons") or []),
            "formal_action_before": before,
            "formal_action_after": current,
            "formal_action_changed": bool(current and before and current != before) if state in {"EVENT_TRIGGERED_FINALIZED", "EVENT_TRIGGERED_NO_CHANGE"} else None,
            "result": result,
            "why_no_buy_or_add": _human_blocker(current, h, blockers.get(code, "")),
            "latest_price": h.get("latest_price"),
            "latest_price_observed_at": h.get("latest_price_observed_at") or "",
            "price_evidence_status": h.get("price_evidence_status") or "",
        })

    rank = {"EVENT_TRIGGER_FAILED": 0, "EVENT_TRIGGERED_FINALIZED": 1, "EVENT_TRIGGERED_NO_CHANGE": 2, "EVENT_TRIGGERED_RUNNING": 3, "RAISE_ONLY": 4}
    rows.sort(key=lambda r: (rank.get(r["event_result_state"], 9), r["code"]))
    return {
        "contract_version": "GEN_GE_INVESTOR_EVENT_CLOSURE_V1",
        "formal_action_source": FORMAL_ACTION_SOURCE,
        "formal_action_recomputed": False,
        "no_auto_trade": NO_AUTO_TRADE,
        "signal_digest": event.get("signal_digest") or "",
        "event_source_snapshot_id": event.get("canonical_snapshot_id") or "",
        "event_source_run_id": event.get("canonical_source_run_id") or "",
        "closure_status": overall,
        "event_research_source_run_id": closure.get("event_research_source_run_id") or "",
        "event_finalizer_run_id": closure.get("event_finalizer_run_id") or "",
        "event_finalized_snapshot_id": closure.get("event_finalized_snapshot_id") or "",
        "rows": rows,
    }


def _render_section(section: Mapping[str, Any]) -> str:
    lines = [
        "## 7. 事件深算闭环：到底算完没有",
        "",
        f"- 总状态：**{section.get('closure_status','NO_EVENT_TRIGGER')}**。正式动作只来自 finalized Canonical，事件层不会偷改买卖结论。",
    ]
    if section.get("event_research_source_run_id"):
        lines.append(f"- 事件深算生产 run：`{section['event_research_source_run_id']}`；Finalizer：`{section.get('event_finalizer_run_id') or '尚未完成'}`。")
    rows = section.get("rows") or []
    if rows:
        lines += ["", "| 股票 | 闭环状态 | 正式结果 | 为什么没有BUY/ADD / 结果解释 |", "|---|---|---|---|"]
        for row in rows:
            name = f"{row.get('name','')} {row.get('code','')}".strip()
            action = row.get("formal_action_after") or row.get("formal_action_before") or "—"
            explanation = row.get("why_no_buy_or_add") or row.get("result") or "—"
            lines.append(f"| {name} | **{row.get('event_result_state')}** | **{action}** | {explanation} |")
    else:
        lines.append("- 当前没有事件触发或 RAISE 深算对象。")
    return "\n".join(lines)


def apply_event_closure(
    dashboard: dict[str, Any],
    markdown: str,
    hourly: Mapping[str, Any],
    event: Mapping[str, Any],
    closure: Mapping[str, Any],
) -> tuple[dict[str, Any], str]:
    section = build_event_closure(dashboard, hourly, event, closure)
    dashboard["event_deep_review_closure"] = section
    # Keep the legacy field useful instead of allowing a later HOURLY render to erase event history.
    dashboard["event_review"] = {
        **dict(dashboard.get("event_review") or {}),
        "triggered": bool(event.get("dispatch_required")),
        "trigger_codes": list(event.get("trigger_codes") or []),
        "signal_digest": event.get("signal_digest") or "",
        "closure_status": section["closure_status"],
        "formal_action_source": FORMAL_ACTION_SOURCE,
        "formal_action_recomputed": False,
    }
    replacement = _render_section(section)
    pattern = re.compile(r"## 7\. (?:事件触发 / 深算变化|事件深算闭环：到底算完没有)\n.*?(?=\n---\n)", re.S)
    if pattern.search(markdown):
        markdown = pattern.sub(replacement + "\n", markdown)
    else:
        markdown = markdown.rstrip() + "\n\n" + replacement + "\n"
    return dashboard, markdown


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dashboard-json", type=Path, required=True)
    parser.add_argument("--dashboard-markdown", type=Path, required=True)
    parser.add_argument("--hourly", type=Path)
    parser.add_argument("--event-decision", type=Path)
    parser.add_argument("--event-closure", type=Path)
    args = parser.parse_args(argv)

    dashboard = _load(args.dashboard_json)
    markdown = args.dashboard_markdown.read_text(encoding="utf-8")
    dashboard, markdown = apply_event_closure(
        dashboard,
        markdown,
        _load(args.hourly),
        _load(args.event_decision),
        _load(args.event_closure),
    )
    args.dashboard_json.write_text(json.dumps(dashboard, ensure_ascii=False, indent=2), encoding="utf-8")
    args.dashboard_markdown.write_text(markdown, encoding="utf-8")
    print(f"event_closure={dashboard['event_deep_review_closure']['closure_status']};rows={len(dashboard['event_deep_review_closure']['rows'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
