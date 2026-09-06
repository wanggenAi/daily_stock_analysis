"""Production guard: no Formal BUY can bypass the frozen V3.1 framework.

The existing scanners remain broad research/discovery engines. This guard wraps
whatever classifier is currently installed (strict or risk-capped) and demotes a
would-be formal BUY to CONDITION_WATCH unless the complete V3.1 decision contract
is explicitly satisfied. Missing qualitative evidence is UNKNOWN, never PASS.

A second, non-negotiable execution-scope gate restricts Formal BUY output to the
user's tradable universe: Shanghai A-shares and Shenzhen A-shares only.
"""
from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from typing import Any

from src.strategies.genge_opportunity_discovery import all_a_full_scan as core
from src.strategies.genge_opportunity_discovery import selection_framework_v31
from src.strategies.genge_opportunity_discovery.user_trade_universe import (
    is_user_tradable_a_share,
    trade_universe_rejection_reason,
)

V31_FORMAL_GATE = "frozen_v31_formal_buy_ready"
V31_TRADE_UNIVERSE_GATE = "user_trade_universe_sh_sz_a_only"


def _guarded_classifier(original):
    def classify_candidate(
        row: Mapping[str, Any],
        plan: Mapping[str, Any],
        profile: Mapping[str, Any],
        evidence_urls: list[str],
        *,
        board_rule: core.BoardRule,
    ) -> tuple[str, list[str]]:
        level, missing = original(
            row,
            plan,
            profile,
            evidence_urls,
            board_rule=board_rule,
        )

        code = row.get("code") or plan.get("code") or profile.get("code")
        if not is_user_tradable_a_share(code):
            if isinstance(row, MutableMapping):
                row["user_trade_universe_eligible"] = False
                row["user_trade_universe_rejection_reason"] = trade_universe_rejection_reason(code)
            blocked = list(missing)
            blocked.append(V31_TRADE_UNIVERSE_GATE)
            return "CONDITION_WATCH", list(dict.fromkeys(blocked))

        if isinstance(row, MutableMapping):
            row["user_trade_universe_eligible"] = True
            row["user_trade_universe_rejection_reason"] = ""

        merged = selection_framework_v31.merge_research_inputs(row, plan, profile)
        assessment = selection_framework_v31.assess_v31(merged)

        if isinstance(row, MutableMapping):
            row.update(assessment.as_dict())

        if level != "STRICT_REVIEW_READY":
            return level, missing
        if assessment.buy_ready:
            return level, missing

        blocked = list(missing)
        blocked.append(V31_FORMAL_GATE)
        blocked.extend(f"v31:{item}" for item in assessment.blockers)
        return "CONDITION_WATCH", list(dict.fromkeys(blocked))

    classify_candidate.__name__ = "v31_guarded_classify_candidate"
    setattr(classify_candidate, "_v31_formal_guard", True)
    return classify_candidate


def install() -> None:
    """Wrap the currently installed classifier; safe to call repeatedly."""
    current = core.classify_candidate
    if getattr(current, "_v31_formal_guard", False):
        return
    core.classify_candidate = _guarded_classifier(current)
