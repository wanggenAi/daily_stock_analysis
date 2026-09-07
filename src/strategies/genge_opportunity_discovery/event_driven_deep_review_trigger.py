"""Select event-driven V3.1.1 Deep Review triggers without changing Formal actions.

This module decides whether fresh research signals justify launching the existing
V3.1.1 production Deep Review pipeline. It never computes or mutates
BUY/ADD/HOLD/REDUCE/EXIT decisions itself.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

CONTRACT_VERSION = "GEN_GE_V3_1_1_EVENT_DRIVEN_DEEP_REVIEW_TRIGGER_V4"
FORMAL_ACTION_SOURCE = "FINALIZED_CANONICAL_ONLY"
DOWNSTREAM_WORKFLOW = "genge-v31-industry-research.yml"
HOLDING_SIGNIFICANT_MOVE_PCT = 3.0  # Mirrors the existing hourly RAISE threshold.
SUCCESS_ARCHETYPE_MIN_SIMILARITY = 70.0
SUCCESS_ARCHETYPE_MIN_EVIDENCE_COVERAGE = 1.0

URGENT_CONCLUSIONS = {
    "PRICE_ATTRACTIVE_RESEARCH_LEAD",
    "PRICE_ATTRACTIVE_AND_THESIS_STRENGTHENING_LEAD",
    "NEW_EVIDENCE_REUNDERWRITE_LEAD",
}


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _require_research_only_contract(payload: Mapping[str, Any], *, label: str) -> None:
    if payload.get("formal_action_source") != FORMAL_ACTION_SOURCE:
        raise ValueError(f"{label}: unexpected formal_action_source")
    if payload.get("formal_action_recomputed") is not False:
        raise ValueError(f"{label}: formal actions must not be recomputed")
    if payload.get("no_auto_trade") is not True:
        raise ValueError(f"{label}: no_auto_trade must be true")
    if "formal_action_eligible" in payload and payload.get("formal_action_eligible") is not False:
        raise ValueError(f"{label}: research layer cannot be formal-action eligible")


def _material_evidence_ids(hourly_row: Mapping[str, Any]) -> list[str]:
    values: list[str] = []
    for item in hourly_row.get("latest_evidence") or []:
        if not isinstance(item, Mapping):
            continue
        if str(item.get("materiality") or "").upper() not in {"HIGH", "MEDIUM"}:
            continue
        if str(item.get("direction") or "").upper() not in {"WEAKENING", "STRENGTHENING"}:
            continue
        evidence_id = str(item.get("evidence_id") or "").strip()
        if evidence_id:
            values.append(evidence_id)
    return sorted(set(values))


def _observed_date(hourly_row: Mapping[str, Any]) -> str | None:
    observed = str(hourly_row.get("latest_price_observed_at") or "")
    return observed[:10] if len(observed) >= 10 else None


def _price_signal_date(hourly_row: Mapping[str, Any], conclusion: str) -> str | None:
    if conclusion not in {
        "PRICE_ATTRACTIVE_RESEARCH_LEAD",
        "PRICE_ATTRACTIVE_AND_THESIS_STRENGTHENING_LEAD",
    }:
        return None
    return _observed_date(hourly_row)


def _holding_move_bucket(hourly_row: Mapping[str, Any]) -> str | None:
    try:
        change_pct = float(hourly_row.get("latest_change_pct"))
    except (TypeError, ValueError):
        return None
    magnitude = abs(change_pct)
    if magnitude < HOLDING_SIGNIFICANT_MOVE_PCT:
        return None
    direction = "UP" if change_pct > 0 else "DOWN"
    if magnitude < 5.0:
        band = "3_TO_5"
    elif magnitude < 8.0:
        band = "5_TO_8"
    else:
        band = "8_PLUS"
    return f"{direction}_{band}"


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _high_confidence_success_archetype_recall(priority_row: Mapping[str, Any]) -> bool:
    reasons = {str(x) for x in (priority_row.get("reason_codes") or [])}
    if "SUCCESS_ARCHETYPE_RECALL" not in reasons:
        return False
    if str(priority_row.get("success_archetype_source_quant_status") or "") != "PRIORITY_RESEARCH":
        return False
    similarity = _safe_float(priority_row.get("success_archetype_similarity_score"))
    coverage = _safe_float(priority_row.get("success_archetype_evidence_coverage"))
    return bool(
        similarity is not None
        and similarity >= SUCCESS_ARCHETYPE_MIN_SIMILARITY
        and coverage is not None
        and coverage >= SUCCESS_ARCHETYPE_MIN_EVIDENCE_COVERAGE
    )


def _stable_tokens(values: Any) -> list[str]:
    tokens: list[str] = []
    for item in values or []:
        if isinstance(item, (Mapping, list)):
            tokens.append(json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        else:
            token = str(item).strip()
            if token:
                tokens.append(token)
    return sorted(set(tokens))


def _success_archetype_signal_state(priority_row: Mapping[str, Any]) -> dict[str, Any] | None:
    if not _high_confidence_success_archetype_recall(priority_row):
        return None
    similarity = float(priority_row.get("success_archetype_similarity_score"))
    similarity_band = "85_PLUS" if similarity >= 85.0 else "70_TO_85"
    return {
        "archetype_id": str(priority_row.get("success_archetype_id") or ""),
        "similarity_band": similarity_band,
        "near_buy_evidence_recovery_tier": str(priority_row.get("near_buy_evidence_recovery_tier") or ""),
        "missing_evidence": _stable_tokens(priority_row.get("missing_evidence")),
        "mapping_gaps": _stable_tokens(priority_row.get("mapping_gaps")),
    }


def _trigger_reasons(priority_row: Mapping[str, Any]) -> list[str]:
    conclusion = str(priority_row.get("hourly_research_conclusion") or "")
    priority = str(priority_row.get("priority") or "")
    reasons = {str(x) for x in (priority_row.get("reason_codes") or [])}
    selected: list[str] = []

    if conclusion in URGENT_CONCLUSIONS:
        selected.append(conclusion)
    if "REUNDERWRITE_REQUIRED" in reasons:
        selected.append("REUNDERWRITE_REQUIRED")
    if priority in {"P0", "P1"} and "MATERIAL_EVIDENCE_CHANGE" in reasons:
        selected.append("MATERIAL_EVIDENCE_CHANGE")
    if _high_confidence_success_archetype_recall(priority_row):
        selected.append("HIGH_CONFIDENCE_SUCCESS_ARCHETYPE_RECALL")
    return sorted(set(selected))


def build_decision(priority: Mapping[str, Any], hourly: Mapping[str, Any]) -> dict[str, Any]:
    """Return an auditable research-only Deep Review dispatch decision.

    Holdings are eligible when they have a genuinely urgent signal because money
    is already at risk. Merely being a holding, merely being P0, or merely having
    HOURLY_PRIORITY_RAISE is not enough. A holding can additionally trigger on
    the existing >=3% significant-move research threshold, but the signal is
    bucketed (3-5%, 5-8%, >=8%) so ordinary intraday noise cannot launch a review
    every hour. High-confidence Success Archetype recalls may also trigger a full
    authority re-review, but similarity only controls research dispatch: it never
    changes a Formal action or bypasses any Canonical/Hard Gate. Any resulting
    Formal action still has to come from the existing Every-Industry -> Production
    Finalizer authority chain.
    """

    _require_research_only_contract(priority, label="research_priority")
    _require_research_only_contract(hourly, label="hourly_research")

    priority_snapshot = str(priority.get("canonical_snapshot_id") or "")
    hourly_snapshot = str(hourly.get("canonical_snapshot_id") or "")
    if not priority_snapshot or priority_snapshot != hourly_snapshot:
        raise ValueError("research priority and hourly state must reference one canonical snapshot")

    hourly_rows = {
        str(row.get("code") or "").zfill(6): row
        for row in (hourly.get("rows") or [])
        if isinstance(row, Mapping) and row.get("code")
    }

    triggers: list[dict[str, Any]] = []
    digest_rows: list[dict[str, Any]] = []
    for row in priority.get("queue") or []:
        if not isinstance(row, Mapping):
            continue
        code = str(row.get("code") or "").zfill(6)
        if not code.strip("0"):
            continue

        reason_codes = {str(x) for x in (row.get("reason_codes") or [])}
        is_current_holding = "CURRENT_HOLDING" in reason_codes
        hourly_row = hourly_rows.get(code) or {}
        trigger_reasons = _trigger_reasons(row)
        holding_move_bucket = _holding_move_bucket(hourly_row) if is_current_holding else None
        if holding_move_bucket:
            trigger_reasons.append("SIGNIFICANT_HOLDING_PRICE_MOVE")
        trigger_reasons = sorted(set(trigger_reasons))
        if not trigger_reasons:
            continue

        conclusion = str(row.get("hourly_research_conclusion") or "")
        material_evidence_ids = _material_evidence_ids(hourly_row)
        success_archetype_signal_state = _success_archetype_signal_state(row)
        signal_counts = {
            "high_materiality_evidence_count_72h": int(hourly_row.get("high_materiality_evidence_count_72h") or 0),
            "material_weakening_evidence_count_72h": int(hourly_row.get("material_weakening_evidence_count_72h") or 0),
            "material_strengthening_evidence_count_72h": int(hourly_row.get("material_strengthening_evidence_count_72h") or 0),
        }
        trigger = {
            "code": code,
            "name": str(row.get("name") or hourly_row.get("name") or ""),
            "is_current_holding": is_current_holding,
            "existing_formal_action": str(row.get("formal_action") or ""),
            "priority": str(row.get("priority") or ""),
            "priority_score": int(row.get("priority_score") or 0),
            "research_tier": str(row.get("research_tier") or ""),
            "thesis_status": str(row.get("thesis_status") or ""),
            "hourly_research_conclusion": conclusion,
            "price_evidence_status": str(hourly_row.get("price_evidence_status") or ""),
            "latest_change_pct": hourly_row.get("latest_change_pct"),
            "holding_move_bucket": holding_move_bucket,
            "holding_move_signal_date": _observed_date(hourly_row) if holding_move_bucket else None,
            "trigger_reasons": trigger_reasons,
            "material_evidence_ids": material_evidence_ids,
            "signal_counts": signal_counts,
            "price_signal_date": _price_signal_date(hourly_row, conclusion),
        }
        if success_archetype_signal_state is not None:
            trigger["success_archetype_signal_state"] = success_archetype_signal_state
        triggers.append(trigger)
        digest_row = {
            "code": trigger["code"],
            "is_current_holding": trigger["is_current_holding"],
            "thesis_status": trigger["thesis_status"],
            "hourly_research_conclusion": trigger["hourly_research_conclusion"],
            "price_evidence_status": trigger["price_evidence_status"],
            "holding_move_bucket": trigger["holding_move_bucket"],
            "holding_move_signal_date": trigger["holding_move_signal_date"],
            "trigger_reasons": trigger["trigger_reasons"],
            "material_evidence_ids": trigger["material_evidence_ids"],
            "signal_counts": trigger["signal_counts"],
            "price_signal_date": trigger["price_signal_date"],
        }
        if success_archetype_signal_state is not None:
            digest_row["success_archetype_signal_state"] = success_archetype_signal_state
        digest_rows.append(digest_row)

    triggers.sort(key=lambda row: (-row["priority_score"], row["code"]))
    digest_rows.sort(key=lambda row: row["code"])
    signal_digest = ""
    if digest_rows:
        encoded = json.dumps(digest_rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        signal_digest = hashlib.sha256(encoded).hexdigest()

    return {
        "contract_version": CONTRACT_VERSION,
        "canonical_snapshot_id": priority_snapshot,
        "canonical_source_run_id": str(hourly.get("canonical_source_run_id") or ""),
        "dispatch_required": bool(triggers),
        "signal_digest": signal_digest,
        "trigger_count": len(triggers),
        "holding_trigger_count": sum(bool(row["is_current_holding"]) for row in triggers),
        "external_trigger_count": sum(not bool(row["is_current_holding"]) for row in triggers),
        "trigger_codes": [row["code"] for row in triggers],
        "triggers": triggers,
        "downstream_workflow": DOWNSTREAM_WORKFLOW,
        "downstream_semantics": "EXISTING_V31_FULL_DEEP_REVIEW_THEN_PRODUCTION_FINALIZER",
        "formal_action_source": FORMAL_ACTION_SOURCE,
        "formal_action_recomputed": False,
        "formal_action_eligible": False,
        "direct_formal_action_change_allowed": False,
        "no_auto_trade": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--priority", type=Path, default=Path("data/research_priority/latest.json"))
    parser.add_argument("--hourly", type=Path, default=Path("data/hourly_research_state/latest.json"))
    parser.add_argument("--output", type=Path, default=Path("reports/event_driven_deep_review/decision.json"))
    args = parser.parse_args(argv)

    decision = build_decision(_load(args.priority), _load(args.hourly))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(decision, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "dispatch_required": decision["dispatch_required"],
        "signal_digest": decision["signal_digest"],
        "trigger_codes": decision["trigger_codes"],
        "holding_trigger_count": decision["holding_trigger_count"],
        "external_trigger_count": decision["external_trigger_count"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
