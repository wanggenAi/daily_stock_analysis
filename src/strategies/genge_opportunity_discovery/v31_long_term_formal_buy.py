"""Frozen V3.1 authority for the long-term Formal BUY review.

The legacy evaluator is retained for operational safety checks and valuation
execution diagnostics. It no longer has authority to make TRY_POSITION or BUY
formal. A formal long-term BUY exists only when both the legacy production
safety checks and the complete frozen V3.1 contract pass.
"""
from __future__ import annotations

from typing import Any, Mapping

from src.strategies.genge_opportunity_discovery import long_term_formal_buy as base
from src.strategies.genge_opportunity_discovery import selection_framework_v31

POLICY_VERSION = "long_term_formal_buy_v2_v31_frozen"
_ORIGINAL_EVALUATE = base.evaluate_long_term_candidate


def evaluate_long_term_candidate(
    second_pass: Mapping[str, Any],
    plan: Mapping[str, Any] | None,
    valuation: Mapping[str, Any] | None,
    *,
    policy: base.LongTermPolicy = base.LongTermPolicy(),
) -> dict[str, Any]:
    legacy = _ORIGINAL_EVALUATE(second_pass, plan, valuation, policy=policy)
    merged = selection_framework_v31.merge_research_inputs(
        second_pass,
        plan or {},
        valuation or {},
        legacy,
    )
    assessment = selection_framework_v31.assess_v31(merged)

    legacy_blockers = [
        token for token in str(legacy.get("long_term_blockers") or "").split(";") if token
    ]
    v31_blockers = [f"v31:{token}" for token in assessment.blockers]
    production_safe = bool(legacy.get("long_term_formal_buy_eligible"))
    formal_buy = bool(production_safe and assessment.buy_ready)

    result = dict(legacy)
    result.update(assessment.as_dict())
    result["legacy_long_term_classification"] = legacy.get("long_term_classification") or ""
    result["legacy_long_term_formal_buy_eligible"] = production_safe
    result["long_term_formal_buy_eligible"] = formal_buy
    result["long_term_classification"] = (
        "LONG_TERM_BUY_READY" if formal_buy else "LONG_TERM_REVIEW_BLOCKED"
    )
    result["long_term_blockers"] = ";".join(
        dict.fromkeys(legacy_blockers + ([] if assessment.buy_ready else v31_blockers))
    )
    result["policy_version"] = POLICY_VERSION
    return result


def install() -> None:
    base.evaluate_long_term_candidate = evaluate_long_term_candidate
    base.POLICY_VERSION = POLICY_VERSION


def main(argv: list[str] | None = None) -> int:
    install()
    print("[LONG-TERM][V3.1] frozen-formal-buy-authority=enabled", flush=True)
    return base.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
