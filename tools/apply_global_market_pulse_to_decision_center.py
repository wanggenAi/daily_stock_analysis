#!/usr/bin/env python3
"""Attach research-only global/pre-open context to the existing decision-center artifact.

This is deliberately a post-composition enrichment step. It cannot recompute or
mutate Canonical/Formal actions, valuation anchors, quantities, or orders.
Malformed/unsafe global pulse input is rejected rather than promoted.
"""
from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SECTION_MARKER = "## 全球市场脉搏 / 复市前情报"


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def _code(value: Any) -> str:
    text = str(value or "").strip().upper()
    if "." in text:
        text = text.split(".", 1)[0]
    for prefix in ("SH", "SZ", "BJ"):
        if text.startswith(prefix):
            text = text[len(prefix):]
            break
    return text.zfill(6) if text.isdigit() else text


def _pulse_is_safe(pulse: Mapping[str, Any]) -> tuple[bool, str]:
    if not pulse:
        return False, "GLOBAL_PULSE_MISSING"
    if pulse.get("authority") != "RESEARCH_ONLY":
        return False, "GLOBAL_PULSE_AUTHORITY_INVALID"
    if pulse.get("formal_trading_authority") is not False:
        return False, "GLOBAL_PULSE_FORMAL_AUTHORITY_INVALID"
    if pulse.get("formal_action_mutation_allowed") is not False:
        return False, "GLOBAL_PULSE_FORMAL_MUTATION_INVALID"
    if pulse.get("automatic_promotion_allowed") is not False:
        return False, "GLOBAL_PULSE_AUTOMATIC_PROMOTION_INVALID"
    if pulse.get("no_auto_trade") is not True:
        return False, "GLOBAL_PULSE_AUTO_TRADE_GUARD_INVALID"
    if pulse.get("unknown_is_pass") not in (None, False):
        return False, "GLOBAL_PULSE_UNKNOWN_POLICY_INVALID"
    return True, "SAFE"


def _key_factor_view(series: Mapping[str, Any]) -> dict[str, Any]:
    keys = (
        "SP500", "NASDAQ", "NASDAQ100", "SOX", "VIX", "US10Y", "US2Y",
        "CURVE_2S10S", "DXY", "USDCNH", "HANGSENG", "HANGSENGTECH",
        "NIKKEI225", "DAX", "EUROSTOXX50", "COPPER", "GOLD", "SILVER",
        "CRUDE_OIL", "NATURAL_GAS", "BTC", "ETH",
    )
    return {key: deepcopy(series[key]) for key in keys if key in series}


def apply_global_pulse(
    decision_center: Mapping[str, Any],
    pulse: Mapping[str, Any],
) -> dict[str, Any]:
    payload = deepcopy(dict(decision_center))
    if not payload:
        raise ValueError("decision center missing")
    safe, reason = _pulse_is_safe(pulse)
    pillar2 = payload.setdefault("pillar_2_world_social_market_capital_map", {})
    readiness = payload.setdefault("decision_readiness", {})
    summary = payload.setdefault("executive_summary", {})

    if not safe:
        pillar2["global_market_pulse"] = {
            "status": "REJECTED_FAIL_CLOSED",
            "reason": reason,
            "authority": "RESEARCH_ONLY",
            "formal_action_eligible": False,
            "no_auto_trade": True,
        }
        pillar2["global_transmission"] = []
        pillar2["pre_open_intelligence"] = {"status": "UNAVAILABLE", "reason": reason}
        readiness["global_market_pulse_available"] = False
        readiness["pre_open_intelligence_available"] = False
        summary["global_market_pulse_status"] = "REJECTED_FAIL_CLOSED"
        return payload

    coverage = deepcopy(dict(pulse.get("coverage") or {}))
    risk_regime = deepcopy(dict(pulse.get("risk_regime") or {}))
    pre_open = deepcopy(dict(pulse.get("pre_open_intelligence") or {}))
    transmission = [deepcopy(dict(row)) for row in (pulse.get("security_transmission") or []) if isinstance(row, Mapping)]
    pillar2["global_market_pulse"] = {
        "status": coverage.get("status") or "UNAVAILABLE",
        "contract_version": pulse.get("contract_version"),
        "generated_at": pulse.get("generated_at"),
        "clock": pulse.get("clock"),
        "a_share_market_clock": deepcopy(pulse.get("a_share_market_clock") or {}),
        "global_research_clock": deepcopy(pulse.get("global_research_clock") or {}),
        "coverage": coverage,
        "risk_regime": risk_regime,
        "key_market_factors": _key_factor_view(pulse.get("series") or {}),
        "global_context": deepcopy(pulse.get("global_context") or []),
        "authority": "RESEARCH_ONLY",
        "formal_action_eligible": False,
        "formal_action_mutation_allowed": False,
        "automatic_promotion_allowed": False,
        "no_auto_trade": True,
    }
    pillar2["global_transmission"] = transmission
    pillar2["pre_open_intelligence"] = pre_open

    by_code = {_code(row.get("code")): row for row in transmission if _code(row.get("code"))}
    impacted_holdings = 0
    holdings = (payload.get("pillar_1_holdings_deep_analysis") or {}).get("rows") or []
    for row in holdings:
        if not isinstance(row, dict):
            continue
        impact = by_code.get(_code(row.get("code")))
        row["global_market_impact"] = deepcopy(impact) if impact else {
            "status": "NO_EXPLICIT_SECURITY_TRANSMISSION",
            "authority": "RESEARCH_ONLY",
            "formal_action_eligible": False,
            "no_auto_trade": True,
        }
        if impact:
            impacted_holdings += 1

    opportunities = payload.get("pillar_3_deep_opportunities") or {}
    impacted_research_codes: set[str] = set()
    for bucket in (
        "buy_now", "wait_price", "research_buy", "research_wait_price",
        "research_gap", "deep_qualified_research_leads", "urgent_evidence_queue",
    ):
        for row in opportunities.get(bucket) or []:
            if not isinstance(row, dict):
                continue
            impact = by_code.get(_code(row.get("code")))
            if impact:
                row["global_market_impact"] = deepcopy(impact)
                impacted_research_codes.add(_code(row.get("code")))

    readiness["global_market_pulse_available"] = coverage.get("status") in {"OK", "PARTIAL"}
    readiness["pre_open_intelligence_available"] = pre_open.get("status") in {"AVAILABLE", "PARTIAL"}
    readiness["global_market_pulse_formal_authority_granted"] = False
    summary["global_market_pulse_status"] = coverage.get("status") or "UNAVAILABLE"
    summary["global_risk_regime"] = risk_regime.get("status") or "UNKNOWN"
    summary["holiday_gap_risk"] = pre_open.get("holiday_gap_risk") or "UNKNOWN"
    summary["holiday_positive_accumulation"] = pre_open.get("holiday_positive_accumulation") or "UNKNOWN"
    summary["global_impacted_holding_count"] = impacted_holdings
    summary["global_impacted_research_security_count"] = len(impacted_research_codes)
    summary["global_security_transmission_count"] = len(transmission)
    return payload


def _fmt_pct(value: Any) -> str:
    try:
        return f"{float(value):+.2f}%"
    except (TypeError, ValueError):
        return "—"


def render_global_section(payload: Mapping[str, Any]) -> str:
    pillar2 = payload.get("pillar_2_world_social_market_capital_map") or {}
    pulse = pillar2.get("global_market_pulse") or {}
    pre = pillar2.get("pre_open_intelligence") or {}
    factors = pulse.get("key_market_factors") or {}
    transmissions = pillar2.get("global_transmission") or []
    lines = [
        SECTION_MARKER,
        "",
        f"- Global Pulse：**{pulse.get('status') or 'UNAVAILABLE'}**；全球风险状态：**{(pulse.get('risk_regime') or {}).get('status') or 'UNKNOWN'}**；A股最近有效交易日：**{(pulse.get('a_share_market_clock') or {}).get('last_valid_trade_date') or '—'}**。",
        f"- 休市累计外部缺口风险：**{pre.get('holiday_gap_risk') or 'UNKNOWN'}**；正向累积：**{pre.get('holiday_positive_accumulation') or 'UNKNOWN'}**。",
        "- 以下均为研究上下文，不产生 Formal BUY/SELL，不自动交易。",
        "",
        "### A股休市以来关键外部变化",
        "",
    ]
    for key in ("SP500", "NASDAQ", "SOX", "VIX", "US10Y", "DXY", "USDCNH", "HANGSENG", "COPPER", "GOLD", "CRUDE_OIL", "BTC"):
        row = factors.get(key)
        if not isinstance(row, Mapping):
            continue
        lines.append(
            f"- **{key}**：休市以来 {_fmt_pct(row.get('since_last_a_share_close_pct'))}；"
            f"最近1日 {_fmt_pct(row.get('change_24h_pct'))}；5日 {_fmt_pct(row.get('change_5d_pct'))}；"
            f"market_date={row.get('market_date') or '—'}；freshness={row.get('freshness') or '—'}。"
        )
    lines.extend(["", "### 对持仓 / 研究对象的明确传导", ""])
    if transmissions:
        for row in transmissions[:20]:
            factors_text = "、".join(
                f"{factor.get('factor_id')}休市以来{_fmt_pct(factor.get('since_last_a_share_close_pct'))}({factor.get('direction')})"
                for factor in row.get("factors") or []
            ) or "无可用因子"
            lines.append(
                f"- **{row.get('code')} {row.get('name') or ''}**：**{row.get('direction')} / {row.get('magnitude')}**；"
                f"{factors_text}；研究动作：**{row.get('research_implication')}**。"
            )
    else:
        lines.append("- 当前没有证据支持的逐股全球传导；禁止凭行业名称自行套用商品影响。")
    lines.extend(["", "### 下一次A股开盘最该盯什么", ""])
    for item in pre.get("next_a_share_open_watch") or []:
        lines.append(f"- {item}")
    if pre.get("holiday_gap_risk_flags"):
        lines.append(f"- Gap risk flags：{', '.join(pre.get('holiday_gap_risk_flags') or [])}。")
    if pre.get("holiday_positive_flags"):
        lines.append(f"- Positive accumulation flags：{', '.join(pre.get('holiday_positive_flags') or [])}。")
    lines.extend(["", "> 全球市场层只能强化/弱化研究和触发重算；Canonical/Formal authority 保持原样，no_auto_trade=true。", ""])
    return "\n".join(lines)


def replace_or_append_section(markdown: str, section: str) -> str:
    if SECTION_MARKER not in markdown:
        return markdown.rstrip() + "\n\n" + section.rstrip() + "\n"
    before, remainder = markdown.split(SECTION_MARKER, 1)
    # This section is always appended by this tool, so replacing from marker to EOF is deterministic.
    return before.rstrip() + "\n\n" + section.rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decision-json", type=Path, default=Path("data/decision_center/latest.json"))
    parser.add_argument("--decision-md", type=Path, default=Path("LATEST_DECISION_CENTER.md"))
    parser.add_argument("--global-pulse", type=Path, default=Path("data/global_market_pulse/latest.json"))
    args = parser.parse_args()

    decision = _load(args.decision_json)
    pulse = _load(args.global_pulse)
    enriched = apply_global_pulse(decision, pulse)
    args.decision_json.write_text(json.dumps(enriched, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    existing_md = args.decision_md.read_text(encoding="utf-8") if args.decision_md.is_file() else ""
    args.decision_md.write_text(
        replace_or_append_section(existing_md, render_global_section(enriched)),
        encoding="utf-8",
    )
    print(json.dumps(enriched.get("executive_summary") or {}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
