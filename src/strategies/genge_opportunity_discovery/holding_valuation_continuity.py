"""Holding sell-rationale and valuation-continuity guard for GenGe V3.1.1.

A formal REDUCE/CORE_ONLY must have a causal, auditable reason.  Production may
not sell merely because one fresh run emitted a lower neutral value.  A
valuation-driven sell is allowed only when a trustworthy prior holding baseline
exists and either:

1. intrinsic-value inputs are continuous and the current price is genuinely
   overextended versus that stable value basis; or
2. material, structured new evidence explains why the prior thesis/value basis
   must be re-underwritten.

Otherwise production fails closed to HOLD_REVIEW.  Hard-gate EXIT is outside
this module and remains immediate.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Mapping

from src.genge_v311_persistence_order import PersistenceOrder, classify_persistence_order

STATE_PATH = Path("data/opportunity_snapshots/holding_valuation_continuity_state.json")
SELL_ACTIONS = {"REDUCE_25", "REDUCE_50", "CORE_ONLY"}
NON_SELL_ACTIONS = {"HOLD", "HOLD_NO_ADD", "HOLD_REVIEW", "BUY", "WAIT"}
NEUTRAL_JUMP_THRESHOLD = 0.20
NORMALIZED_EARNINGS_JUMP_THRESHOLD = 0.20
MIN_STABLE_VALUE_OVEREXTENSION = 1.20

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
        return {"contract_version": "V311_HOLDING_SELL_RATIONALE_V3", "holdings": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data.get("holdings"), dict):
        raise ValueError("invalid holding valuation continuity state")
    return data


def _material_override_evidence(data: Mapping[str, Any]) -> tuple[bool, tuple[str, ...]]:
    """Only structured, material, thesis-linked evidence can justify re-underwrite."""
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
    if evidence_reason and len(evidence_reason) < 20:
        missing.append("SELL_EVIDENCE_REASON_TOO_THIN")
    return not missing, tuple(missing)


def sell_review_required(data: Mapping[str, Any], action: str, *, path: Path = STATE_PATH):
    """Return whether a valuation-driven formal sell must fail closed to review.

    The result includes explicit reason codes so every blocked or permitted
    transition is explainable.  Stable-value overextension is a legitimate sell
    reason; a one-run value collapse is not.
    """
    if action not in SELL_ACTIONS:
        return False, ()
    if not bool(data.get("v311_has_position") or data.get("v32_has_position")):
        return False, ()

    code = _code(data.get("code"))
    prev = load_state(path).get("holdings", {}).get(code)
    if not prev:
        return True, ("SELL_RATIONALE_BASELINE_MISSING",)

    current_neutral = _finite(data.get("v31_neutral_value") or data.get("neutral_value"))
    current_norm = _finite(data.get("v31_normalized_profit") or data.get("normalized_earnings"))
    current_price = _finite(
        data.get("v31_current_price") or data.get("current_price") or data.get("raw_latest_close")
    )
    previous_neutral = _finite(prev.get("neutral_value"))
    previous_norm = _finite(prev.get("normalized_earnings"))

    continuity_failures = []
    if previous_neutral is None or previous_neutral <= 0 or current_neutral is None or current_neutral <= 0:
        continuity_failures.append("VALUATION_CONTINUITY_BASELINE_INCOMPLETE")
    else:
        neutral_jump = abs(current_neutral / previous_neutral - 1.0)
        if neutral_jump >= NEUTRAL_JUMP_THRESHOLD:
            continuity_failures.append("NEUTRAL_VALUE_DISCONTINUITY")

    if previous_norm and current_norm:
        if abs(current_norm / previous_norm - 1.0) >= NORMALIZED_EARNINGS_JUMP_THRESHOLD:
            continuity_failures.append("NORMALIZED_EARNINGS_DISCONTINUITY")

    # Any discontinuity requires genuinely material new evidence.  A fresh model
    # output or a short free-text note is not enough.
    if continuity_failures:
        override_ok, override_failures = _material_override_evidence(data)
        if override_ok:
            return False, ("SELL_RATIONALE_MATERIAL_REUNDERWRITE_EVIDENCE",)
        return True, tuple(["SELL_RATIONALE_NOT_PROVEN", *continuity_failures, *override_failures])

    # With a stable value basis, valuation itself can be a valid causal sell
    # reason only when the market price is materially above that stable basis.
    if current_price is None or current_price <= 0 or current_neutral is None or current_neutral <= 0:
        return True, ("SELL_RATIONALE_PRICE_OR_VALUE_INVALID",)
    price_to_neutral = current_price / current_neutral
    if price_to_neutral < MIN_STABLE_VALUE_OVEREXTENSION:
        return True, (
            "SELL_RATIONALE_NOT_MATERIAL",
            "STABLE_VALUE_OVEREXTENSION_BELOW_MINIMUM",
        )

    return False, ("SELL_RATIONALE_STABLE_VALUE_PRICE_OVEREXTENSION",)


# Backward-compatible alias used by production_model.
def continuity_review_required(data: Mapping[str, Any], action: str, *, path: Path = STATE_PATH):
    return sell_review_required(data, action, path=path)


def persist_from_snapshot(snapshot_path: Path, state_path: Path = STATE_PATH):
    """Persist only if the authorized snapshot does not move durable state backward."""
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    if not isinstance(snapshot, dict):
        raise ValueError("canonical snapshot must be an object")
    state_exists = state_path.is_file()
    state = load_state(state_path)

    current_sid = state.get("latest_applied_snapshot_id")
    current_run = state.get("latest_applied_source_run_id")
    if state_exists and (current_sid in (None, "") and current_run in (None, "")):
        # A pre-monotonic state containing baselines but no durable Canonical
        # identity cannot safely be treated as empty.  Fail closed rather than
        # silently assigning it an arbitrary order.
        if state.get("holdings"):
            raise ValueError("holding continuity state has baselines but no durable Canonical identity")

    order = classify_persistence_order(
        incoming_snapshot_id=snapshot.get("snapshot_id"),
        incoming_source_run_id=snapshot.get("source_run_id"),
        current_snapshot_id=current_sid,
        current_source_run_id=current_run,
    )
    if order in {PersistenceOrder.SAME, PersistenceOrder.STALE}:
        return state

    state["contract_version"] = "V311_HOLDING_SELL_RATIONALE_V3"
    holdings = state.setdefault("holdings", {})
    for row in snapshot.get("production", {}).get("holding_decisions", []):
        code = _code(row.get("code"))
        if not code:
            continue
        holdings[code] = {
            "action": row.get("action"),
            "neutral_value": row.get("neutral_value"),
            "normalized_earnings": row.get("normalized_earnings"),
            "current_price": row.get("current_price"),
            "price_to_neutral": row.get("price_to_neutral"),
            "valuation_confidence": row.get("valuation_confidence"),
            "reason_codes": row.get("reason_codes"),
            "canonical_snapshot_id": snapshot.get("snapshot_id"),
            "canonical_source_run_id": str(snapshot.get("source_run_id")),
            "decision_date": row.get("decision_date"),
        }
    state["latest_applied_snapshot_id"] = snapshot.get("snapshot_id")
    state["latest_applied_source_run_id"] = str(snapshot.get("source_run_id"))
    state["no_auto_trade"] = True
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return state
