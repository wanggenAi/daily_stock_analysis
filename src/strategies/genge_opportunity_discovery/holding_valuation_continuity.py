"""Holding valuation-continuity guard for GenGe V3.1.1 production.

A valuation-driven reduction is not allowed to become a formal production sell
merely because a fresh run produced a lower neutral value.  When an existing
holding moves from a non-sell state into REDUCE/CORE_ONLY, production must prove
valuation continuity or present material, auditable fundamental evidence that
logically explains the re-underwrite.  Otherwise the action fails closed to
HOLD_REVIEW in :mod:`production_model`.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Mapping

STATE_PATH = Path("data/opportunity_snapshots/holding_valuation_continuity_state.json")
SELL_ACTIONS = {"REDUCE_25", "REDUCE_50", "CORE_ONLY"}
NON_SELL_ACTIONS = {"HOLD", "HOLD_NO_ADD", "HOLD_REVIEW", "BUY", "WAIT"}
NEUTRAL_JUMP_THRESHOLD = 0.20
NORMALIZED_EARNINGS_JUMP_THRESHOLD = 0.20

# Only economically material evidence classes may override a discontinuity.
# Free-form text by itself is deliberately insufficient.
MATERIAL_EVIDENCE_TYPES = {
    "EARNINGS_POWER_DETERIORATION",
    "GUIDANCE_CUT",
    "MARGIN_STRUCTURE_DETERIORATION",
    "CASH_FLOW_DETERIORATION",
    "BALANCE_SHEET_DETERIORATION",
    "MOAT_OR_COMPETITIVE_POSITION_DETERIORATION",
    "DEMAND_OR_INDUSTRY_THESIS_DETERIORATION",
    "REGULATORY_OR_POLICY_IMPAIRMENT",
    "CAPITAL_ALLOCATION_IMPAIRMENT",
    "VALUATION_MODEL_INPUT_CORRECTION",
}


def _finite(v: Any):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _truthy(v: Any) -> bool:
    return str(v or "").strip().lower() in {"1", "true", "yes", "y", "pass", "passed"}


def _code(v: Any):
    t = str(v or "").strip().upper()
    if "." in t:
        t = t.split(".")[0]
    for p in ("SH", "SZ", "BJ"):
        if t.startswith(p) and t[len(p):].isdigit():
            t = t[len(p):]
    return t.zfill(6) if t.isdigit() else t


def load_state(path: Path = STATE_PATH):
    if not path.exists():
        return {"contract_version": "V311_HOLDING_VALUATION_CONTINUITY_V2", "holdings": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data.get("holdings"), dict):
        raise ValueError("invalid holding valuation continuity state")
    return data


def _material_override_evidence(data: Mapping[str, Any]) -> tuple[bool, tuple[str, ...]]:
    """Require structured, material and auditable evidence to override review."""
    evidence_id = str(data.get("valuation_continuity_evidence_id") or "").strip()
    evidence_at = str(data.get("valuation_continuity_evidence_observed_at") or "").strip()
    evidence_reason = str(data.get("valuation_continuity_evidence_reason") or "").strip()
    evidence_type = str(data.get("valuation_continuity_evidence_type") or "").strip().upper()
    material = _truthy(data.get("valuation_continuity_evidence_material"))
    thesis_link = str(data.get("valuation_continuity_thesis_link") or "").strip()

    missing = []
    if not evidence_id:
        missing.append("SELL_EVIDENCE_ID_MISSING")
    if not evidence_at:
        missing.append("SELL_EVIDENCE_TIME_MISSING")
    if not evidence_reason:
        missing.append("SELL_EVIDENCE_REASON_MISSING")
    if evidence_type not in MATERIAL_EVIDENCE_TYPES:
        missing.append("SELL_EVIDENCE_TYPE_NOT_MATERIAL")
    if not material:
        missing.append("SELL_EVIDENCE_NOT_MARKED_MATERIAL")
    if not thesis_link:
        missing.append("SELL_EVIDENCE_THESIS_LINK_MISSING")

    # Require a non-trivial explanation.  A label such as "valuation lower" is
    # not a causal reason and cannot authorize a sell transition.
    if evidence_reason and len(evidence_reason) < 20:
        missing.append("SELL_EVIDENCE_REASON_TOO_THIN")

    return not missing, tuple(missing)


def continuity_review_required(data: Mapping[str, Any], action: str, *, path: Path = STATE_PATH):
    if action not in SELL_ACTIONS:
        return False, ()
    has_position = bool(data.get("v311_has_position") or data.get("v32_has_position"))
    if not has_position:
        return False, ()

    code = _code(data.get("code"))
    prev = load_state(path).get("holdings", {}).get(code)
    if not prev:
        # No trustworthy baseline means production cannot prove a HOLD->SELL
        # transition is continuous; fail closed rather than invent continuity.
        return True, ("VALUATION_CONTINUITY_BASELINE_MISSING",)

    prev_action = str(prev.get("action") or "")
    if prev_action not in NON_SELL_ACTIONS:
        return False, ()

    current_neutral = _finite(data.get("v31_neutral_value") or data.get("neutral_value"))
    previous_neutral = _finite(prev.get("neutral_value"))
    reasons = []
    if previous_neutral is None or previous_neutral <= 0 or current_neutral is None or current_neutral <= 0:
        reasons.append("VALUATION_CONTINUITY_BASELINE_INCOMPLETE")
    else:
        jump = abs(current_neutral / previous_neutral - 1.0)
        if jump >= NEUTRAL_JUMP_THRESHOLD:
            reasons.append("NEUTRAL_VALUE_DISCONTINUITY")

    current_norm = _finite(data.get("v31_normalized_profit") or data.get("normalized_earnings"))
    previous_norm = _finite(prev.get("normalized_earnings"))
    if previous_norm and current_norm:
        if abs(current_norm / previous_norm - 1.0) >= NORMALIZED_EARNINGS_JUMP_THRESHOLD:
            reasons.append("NORMALIZED_EARNINGS_DISCONTINUITY")

    if not reasons:
        return False, ()

    override_ok, override_failures = _material_override_evidence(data)
    if override_ok:
        return False, ()

    return True, tuple([*reasons, *override_failures])


def persist_from_snapshot(snapshot_path: Path, state_path: Path = STATE_PATH):
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    state = load_state(state_path)
    state["contract_version"] = "V311_HOLDING_VALUATION_CONTINUITY_V2"
    holdings = state.setdefault("holdings", {})
    for row in snapshot.get("production", {}).get("holding_decisions", []):
        code = _code(row.get("code"))
        if not code:
            continue
        holdings[code] = {
            "action": row.get("action"),
            "neutral_value": row.get("neutral_value"),
            "normalized_earnings": row.get("normalized_earnings"),
            "valuation_confidence": row.get("valuation_confidence"),
            "canonical_snapshot_id": snapshot.get("snapshot_id"),
            "canonical_source_run_id": snapshot.get("source_run_id"),
            "decision_date": row.get("decision_date"),
        }
    state["latest_applied_snapshot_id"] = snapshot.get("snapshot_id")
    state["latest_applied_source_run_id"] = snapshot.get("source_run_id")
    state["no_auto_trade"] = True
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return state
