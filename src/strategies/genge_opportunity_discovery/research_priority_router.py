"""Route research work without changing V3.1.1 Formal actions.

Combines hourly research state, candidate lifecycle, reviewed mapping coverage,
an optional Near-BUY evidence-recovery queue and an optional success-archetype
recall queue into an auditable Deep Review / mapping queue. Research overlays
can change order only, never thresholds, gate outcomes or Formal actions.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

CONTRACT_VERSION = "GEN_GE_RESEARCH_PRIORITY_ROUTER_V6_DEEP_QUALIFIED_FOLLOWUP"
STRUCTURAL_REUNDERWRITE_PRICE_STATUSES = {"VALUE_ANCHOR_UNAVAILABLE"}
RECOVERY_TIER_BOOST = {"A": 45, "B": 30, "C": 20}
ARCHETYPE_SIMILARITY_BOOST = ((70.0, 28), (60.0, 24), (50.0, 18))
MIN_ARCHETYPE_EVIDENCE_COVERAGE = 0.60
DEEP_QUALIFIED_PRIORITY_BOOST = 45
REQUIRED_DEEP_HARD_GATES = (
    "earnings_authenticity",
    "financial_safety",
    "long_term_demand",
    "moat",
    "predictability",
)


def _load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _tier_score(tier: str) -> int:
    text = (tier or "").upper()
    if "A1" in text:
        return 30
    if "A2" in text:
        return 20
    if "BUY_REVIEW" in text:
        return 18
    if "WAIT_PRICE" in text:
        return 15
    if "DOWNGRADED" in text:
        return 12
    return 5


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "pass", "passed"}


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _recovery_map(payload: Mapping[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not payload:
        return {}
    if _bool(payload.get("formal_action_eligible")) or _bool(payload.get("formal_action_recomputed")):
        raise AssertionError("Near-BUY recovery artifact attempted Formal authority")
    if _bool(payload.get("automatic_promotion_allowed")) or _bool(payload.get("starter_position_allowed")):
        raise AssertionError("Near-BUY recovery artifact attempted automatic promotion/starter authority")
    if payload.get("priority_changes_order_only") is False or payload.get("threshold_changes_allowed") is True:
        raise AssertionError("Near-BUY recovery artifact attempted threshold semantics change")
    result: dict[str, dict[str, Any]] = {}
    for raw in payload.get("queue") or []:
        if not isinstance(raw, Mapping):
            continue
        code = str(raw.get("code") or "").strip().zfill(6)
        tier = str(raw.get("recovery_tier") or "").strip().upper()
        if not code or tier not in RECOVERY_TIER_BOOST:
            continue
        if _bool(raw.get("formal_action_eligible")) or _bool(raw.get("formal_action_recomputed")):
            raise AssertionError(f"Near-BUY recovery row attempted Formal authority: {code}")
        if _bool(raw.get("automatic_promotion_allowed")):
            raise AssertionError(f"Near-BUY recovery row attempted automatic promotion: {code}")
        result[code] = {
            "code": code,
            "name": str(raw.get("name") or ""),
            "recovery_tier": tier,
            "priority_boost": RECOVERY_TIER_BOOST[tier],
            "missing_evidence_items": list(raw.get("missing_evidence_items") or []),
        }
    return result


def _archetype_boost(similarity_score: float) -> int:
    for minimum, boost in ARCHETYPE_SIMILARITY_BOOST:
        if similarity_score >= minimum:
            return boost
    return 0


def _archetype_map(payload: Mapping[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not payload:
        return {}
    if _bool(payload.get("formal_action_eligible")) or _bool(payload.get("formal_action_recomputed")):
        raise AssertionError("Success-archetype recall attempted Formal authority")
    if _bool(payload.get("automatic_promotion_allowed")) or _bool(payload.get("starter_position_allowed")):
        raise AssertionError("Success-archetype recall attempted promotion/starter authority")
    if payload.get("changes_research_order_only") is False or payload.get("changes_thresholds") is True:
        raise AssertionError("Success-archetype recall attempted threshold semantics change")
    if payload.get("unknown_evidence_is_pass") is True:
        raise AssertionError("Success-archetype recall attempted UNKNOWN->PASS")
    result: dict[str, dict[str, Any]] = {}
    for raw in payload.get("queue") or []:
        if not isinstance(raw, Mapping):
            continue
        code = str(raw.get("code") or "").strip().zfill(6)
        similarity = _float(raw.get("similarity_score"))
        coverage = _float(raw.get("evidence_coverage"))
        if not code or similarity is None or coverage is None or coverage < MIN_ARCHETYPE_EVIDENCE_COVERAGE:
            continue
        boost = _archetype_boost(similarity)
        if boost <= 0:
            continue
        if _bool(raw.get("formal_action_eligible")) or _bool(raw.get("formal_action_recomputed")):
            raise AssertionError(f"Success-archetype row attempted Formal authority: {code}")
        if _bool(raw.get("automatic_promotion_allowed")) or _bool(raw.get("starter_position_allowed")):
            raise AssertionError(f"Success-archetype row attempted promotion/starter authority: {code}")
        result[code] = {
            "code": code,
            "name": str(raw.get("name") or ""),
            "archetype_id": str(raw.get("archetype_id") or payload.get("archetype_id") or ""),
            "similarity_score": similarity,
            "evidence_coverage": coverage,
            "priority_boost": boost,
            "source_quant_status": str(raw.get("source_quant_status") or ""),
        }
    return result


def _deep_qualified_map(
    payload: Mapping[str, Any] | None,
    status: Mapping[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    """Return current-runtime profiles whose five research hard gates are all PASS.

    This is research-order evidence only. It cannot create a Formal action, change
    a hard-gate threshold, or turn UNKNOWN into PASS.
    """

    if not payload or not status:
        return {}
    if _bool(payload.get("formal_trading_authority")) or _bool(payload.get("automatic_formal_buy_allowed")):
        raise AssertionError("Deep profile artifact attempted Formal authority")
    if payload.get("unknown_is_pass") is True:
        raise AssertionError("Deep profile artifact attempted UNKNOWN->PASS")
    if payload.get("no_auto_trade") is False:
        raise AssertionError("Deep profile artifact attempted auto trade")

    profile_run_id = str(payload.get("lambda_run_id") or "").strip()
    status_run_id = str(status.get("lambda_run_id") or "").strip()
    if (
        not profile_run_id
        or profile_run_id != status_run_id
        or str(status.get("execution_status") or "").strip().upper() != "SUCCESS"
    ):
        return {}

    raw_profiles = payload.get("profiles")
    if not isinstance(raw_profiles, Mapping):
        return {}

    result: dict[str, dict[str, Any]] = {}
    for raw_code, profile in raw_profiles.items():
        if not isinstance(profile, Mapping):
            continue
        code = str(raw_code or "").strip().zfill(6)
        gates = profile.get("gates")
        if not code or not isinstance(gates, Mapping):
            continue
        statuses = {
            gate: str((gates.get(gate) or {}).get("status") or "UNKNOWN").strip().upper()
            if isinstance(gates.get(gate), Mapping)
            else "UNKNOWN"
            for gate in REQUIRED_DEEP_HARD_GATES
        }
        if not all(statuses[gate] == "PASS" for gate in REQUIRED_DEEP_HARD_GATES):
            continue
        result[code] = {
            "code": code,
            "name": str(profile.get("name") or ""),
            "industry": str(profile.get("industry") or ""),
            "hard_gate_pass_count": len(REQUIRED_DEEP_HARD_GATES),
            "hard_gate_total_count": len(REQUIRED_DEEP_HARD_GATES),
            "priority_boost": DEEP_QUALIFIED_PRIORITY_BOOST,
            "source_lambda_run_id": profile_run_id,
        }
    return result


def _requires_structural_reunderwrite(*, is_current_holding: bool, hourly_row: Mapping[str, Any]) -> bool:
    if not is_current_holding:
        return False
    if str(hourly_row.get("formal_action") or "") != "HOLD_REVIEW":
        return False
    if str(hourly_row.get("price_evidence_status") or "") not in STRUCTURAL_REUNDERWRITE_PRICE_STATUSES:
        return False
    return hourly_row.get("validated_value_anchor") is None


def build_queue(
    hourly: Mapping[str, Any],
    lifecycle: Mapping[str, Any],
    coverage: Mapping[str, Any],
    near_buy_recovery: Mapping[str, Any] | None = None,
    success_archetype_recall: Mapping[str, Any] | None = None,
    deep_profiles: Mapping[str, Any] | None = None,
    deep_status: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    life = lifecycle.get("candidates") or {}
    coverage_rows = {str(r.get("code") or "").zfill(6): r for r in (coverage.get("securities") or []) if isinstance(r, Mapping)}
    hourly_rows = {str(r.get("code") or "").zfill(6): r for r in (hourly.get("rows") or []) if isinstance(r, Mapping)}
    recovery_rows = _recovery_map(near_buy_recovery)
    archetype_rows = _archetype_map(success_archetype_recall)
    deep_qualified_rows = _deep_qualified_map(deep_profiles, deep_status)
    codes = sorted(
        set(life)
        | set(coverage_rows)
        | set(hourly_rows)
        | set(recovery_rows)
        | set(archetype_rows)
        | set(deep_qualified_rows)
    )
    queue: list[dict[str, Any]] = []
    for code in codes:
        l = life.get(code) or {}
        c = coverage_rows.get(code) or {}
        h = hourly_rows.get(code) or {}
        recovery = recovery_rows.get(code) or {}
        archetype = archetype_rows.get(code) or {}
        deep_qualified = deep_qualified_rows.get(code) or {}
        reasons: list[str] = []
        score = 0
        is_current_holding = str(h.get("scope") or "").upper() == "HOLDING"
        if is_current_holding:
            score += 50
            reasons.append("CURRENT_HOLDING")
        lifecycle_state = str(l.get("lifecycle_state") or "ACTIVE").strip().upper()
        tier = str(l.get("research_tier") or "")
        conclusion = str(h.get("hourly_research_conclusion") or "")
        thesis = str(h.get("thesis_status") or "")
        structural_reunderwrite = _requires_structural_reunderwrite(
            is_current_holding=is_current_holding,
            hourly_row=h,
        )
        deep_qualified_boost = int(deep_qualified.get("priority_boost") or 0)
        dormant_reactivation_signal = lifecycle_state == "DORMANT" and (
            is_current_holding
            or conclusion == "NEW_EVIDENCE_REUNDERWRITE_LEAD"
            or thesis
            in {
                "REUNDERWRITE_REQUIRED",
                "WEAKENING_RESEARCH_SIGNAL",
                "MIXED_NEW_EVIDENCE",
                "STRENGTHENING_RESEARCH_SIGNAL",
            }
            or structural_reunderwrite
            or deep_qualified_boost > 0
        )
        dormant_locked = (
            lifecycle_state == "DORMANT"
            and not is_current_holding
            and not dormant_reactivation_signal
        )
        if lifecycle_state == "DORMANT":
            ts = 0
            reasons.append("RESEARCH_DORMANT_WAIT_NEW_EVIDENCE")
            if dormant_reactivation_signal:
                reasons.append("DORMANT_NEW_EVIDENCE_REACTIVATION_SIGNAL")
            else:
                reasons.append("RESEARCH_DORMANT_NON_MATERIAL_SIGNALS_SUPPRESSED")
        else:
            ts = _tier_score(tier)
            score += ts
            if ts >= 15:
                reasons.append("HIGH_RESEARCH_TIER")
        if (
            not dormant_locked
            and conclusion
            in {
                "PRICE_ATTRACTIVE_RESEARCH_LEAD",
                "PRICE_ATTRACTIVE_AND_THESIS_STRENGTHENING_LEAD",
            }
        ):
            score += 35
            reasons.append(conclusion)
        if (
            conclusion == "NEW_EVIDENCE_REUNDERWRITE_LEAD"
            or thesis == "REUNDERWRITE_REQUIRED"
            or structural_reunderwrite
        ):
            score += 45
            reasons.append("REUNDERWRITE_REQUIRED")
            if structural_reunderwrite:
                reasons.append("VALUE_ANCHOR_REUNDERWRITE_REQUIRED")
        elif thesis in {"WEAKENING_RESEARCH_SIGNAL", "MIXED_NEW_EVIDENCE"}:
            score += 25
            reasons.append("MATERIAL_EVIDENCE_CHANGE")
        elif thesis == "STRENGTHENING_RESEARCH_SIGNAL" and lifecycle_state == "DORMANT":
            score += 25
            reasons.append("MATERIAL_EVIDENCE_CHANGE")
        if not dormant_locked and str(h.get("deep_review_priority") or "") == "RAISE":
            score += 15
            reasons.append("HOURLY_PRIORITY_RAISE")
        mapping_gaps: list[str] = []
        if not c.get("industry_mapped"):
            mapping_gaps.append("INDUSTRY")
        commodity_state = str(c.get("commodity_monitoring_state") or "")
        if commodity_state == "APPLICABLE_UNMAPPED":
            mapping_gaps.append("COMMODITY")
        elif commodity_state == "PARTIAL_MAPPED":
            mapping_gaps.append("COMMODITY_PARTIAL")
        if c.get("peer_monitoring_state") == "APPLICABLE_UNMAPPED":
            mapping_gaps.append("PEER")
        if mapping_gaps and not dormant_locked:
            score += min(15, 5 * len(mapping_gaps))
            reasons.append("MAPPING_GAP")
        recovery_tier = str(recovery.get("recovery_tier") or "")
        recovery_boost = RECOVERY_TIER_BOOST.get(recovery_tier, 0)
        archetype_boost = int(archetype.get("priority_boost") or 0)
        if recovery_tier and not dormant_locked:
            reasons.append(f"NEAR_BUY_EVIDENCE_RECOVERY_{recovery_tier}")
        if archetype_boost and not dormant_locked:
            reasons.append("SUCCESS_ARCHETYPE_RECALL")
            if archetype.get("archetype_id"):
                reasons.append(f"ARCHETYPE:{archetype['archetype_id']}")
        research_overlay_boost = (
            0 if dormant_locked else max(recovery_boost, archetype_boost)
        )
        score += research_overlay_boost
        if deep_qualified_boost:
            score += deep_qualified_boost
            reasons.append("DEEP_HARD_GATES_COMPLETE_RESEARCH_FOLLOWUP")
        if score >= 70:
            priority = "P0"
        elif score >= 45:
            priority = "P1"
        elif score >= 25:
            priority = "P2"
        else:
            priority = "P3"
        queue.append({
            "code": code,
            "name": c.get("name") or l.get("stock_name") or h.get("name") or recovery.get("name") or archetype.get("name") or deep_qualified.get("name") or "",
            "priority": priority,
            "priority_score": score,
            "research_tier": tier,
            "lifecycle_state": lifecycle_state,
            "thesis_status": thesis or None,
            "hourly_research_conclusion": conclusion or None,
            "mapping_gaps": mapping_gaps,
            "near_buy_evidence_recovery_tier": recovery_tier or None,
            "near_buy_missing_evidence_items": recovery.get("missing_evidence_items") or [],
            "success_archetype_id": archetype.get("archetype_id") or None,
            "success_archetype_similarity_score": archetype.get("similarity_score"),
            "success_archetype_evidence_coverage": archetype.get("evidence_coverage"),
            "success_archetype_source_quant_status": archetype.get("source_quant_status") or None,
            "research_overlay_priority_boost": research_overlay_boost,
            "research_overlay_boost_combination": "MAX_NOT_SUM",
            "deep_hard_gate_complete": bool(deep_qualified),
            "deep_hard_gate_pass_count": deep_qualified.get("hard_gate_pass_count", 0),
            "deep_hard_gate_total_count": deep_qualified.get("hard_gate_total_count", len(REQUIRED_DEEP_HARD_GATES)),
            "deep_profile_source_lambda_run_id": deep_qualified.get("source_lambda_run_id"),
            "reason_codes": reasons,
            "formal_action": h.get("formal_action"),
            "formal_action_recomputed": False,
            "formal_action_eligible": False,
        })
    queue.sort(key=lambda r: (-int(r["priority_score"]), r["code"]))
    now = datetime.now(timezone.utc).isoformat()
    return {
        "contract_version": CONTRACT_VERSION,
        "generated_at": now,
        "canonical_snapshot_id": hourly.get("canonical_snapshot_id"),
        "formal_action_source": "FINALIZED_CANONICAL_ONLY",
        "formal_action_recomputed": False,
        "formal_action_eligible": False,
        "no_auto_trade": True,
        "near_buy_recovery_integrated": bool(recovery_rows),
        "near_buy_recovery_count": len(recovery_rows),
        "near_buy_recovery_changes_order_only": True,
        "near_buy_recovery_changes_thresholds": False,
        "success_archetype_recall_integrated": bool(archetype_rows),
        "success_archetype_recall_count": len(archetype_rows),
        "success_archetype_recall_changes_order_only": True,
        "success_archetype_recall_changes_thresholds": False,
        "deep_qualified_profile_integrated": bool(deep_qualified_rows),
        "deep_qualified_profile_count": len(deep_qualified_rows),
        "deep_qualified_profile_changes_order_only": True,
        "deep_qualified_profile_changes_thresholds": False,
        "research_overlay_boost_combination": "MAX_NOT_SUM",
        "queue_count": len(queue),
        "p0_count": sum(r["priority"] == "P0" for r in queue),
        "p1_count": sum(r["priority"] == "P1" for r in queue),
        "mapping_gap_count": sum(bool(r["mapping_gaps"]) for r in queue),
        "partial_mapping_gap_count": sum("COMMODITY_PARTIAL" in r["mapping_gaps"] for r in queue),
        "queue": queue,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hourly", type=Path, default=Path("data/hourly_research_state/latest.json"))
    parser.add_argument("--lifecycle", type=Path, default=Path("data/opportunity_snapshots/candidate_lifecycle_state.json"))
    parser.add_argument("--coverage", type=Path, default=Path("data/research_mapping/coverage.json"))
    parser.add_argument("--near-buy-recovery", type=Path)
    parser.add_argument("--success-archetype-recall", type=Path)
    parser.add_argument("--deep-profiles", type=Path)
    parser.add_argument("--deep-status", type=Path)
    parser.add_argument("--output", type=Path, default=Path("data/research_priority/latest.json"))
    args = parser.parse_args(argv)
    recovery = _load(args.near_buy_recovery) if args.near_buy_recovery else {}
    archetype = _load(args.success_archetype_recall) if args.success_archetype_recall else {}
    deep_profiles = _load(args.deep_profiles) if args.deep_profiles else {}
    deep_status = _load(args.deep_status) if args.deep_status else {}
    payload = build_queue(
        _load(args.hourly),
        _load(args.lifecycle),
        _load(args.coverage),
        recovery,
        archetype,
        deep_profiles,
        deep_status,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: payload[key] for key in ("queue_count", "p0_count", "p1_count", "mapping_gap_count", "partial_mapping_gap_count", "near_buy_recovery_count", "success_archetype_recall_count", "deep_qualified_profile_count")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
