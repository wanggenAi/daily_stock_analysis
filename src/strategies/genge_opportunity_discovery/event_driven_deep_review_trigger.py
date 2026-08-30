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

CONTRACT_VERSION = "GEN_GE_V3_1_1_EVENT_DRIVEN_DEEP_REVIEW_TRIGGER_V2"
FORMAL_ACTION_SOURCE = "FINALIZED_CANONICAL_ONLY"
DOWNSTREAM_WORKFLOW = "genge-v31-industry-research.yml"

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


def _price_signal_date(hourly_row: Mapping[str, Any], conclusion: str) -> str | None:
    if conclusion not in {
        "PRICE_ATTRACTIVE_RESEARCH_LEAD",
        "PRICE_ATTRACTIVE_AND_THESIS_STRENGTHENING_LEAD",
    }:
        return None
    observed = str(hourly_row.get("latest_price_observed_at") or "")
    return observed[:10] if len(observed) >= 10 else None


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
    return sorted(set(selected))


def build_decision(priority: Mapping[str, Any], hourly: Mapping[str, Any]) -> dict[str, Any]:
    """Return an auditable research-only Deep Review dispatch decision.

    Holdings are eligible when they have a genuinely urgent signal because money
    is already at risk. Merely being a holding, merely being P0, or merely having
    HOURLY_PRIORITY_RAISE is not enough. External candidates use the same urgent
    signal bar. Any resulting Formal action still has to come from the existing
    Every-Industry -> Production Finalizer authority chain.
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

        trigger_reasons = _trigger_reasons(row)
        if not trigger_reasons:
            continue

        reason_codes = {str(x) for x in (row.get("reason_codes") or [])}
        hourly_row = hourly_rows.get(code) or {}
        conclusion = str(row.get("hourly_research_conclusion") or "")
        material_evidence_ids = _material_evidence_ids(hourly_row)
        signal_counts = {
            "high_materiality_evidence_count_72h": int(hourly_row.get("high_materiality_evidence_count_72h") or 0),
            "material_weakening_evidence_count_72h": int(hourly_row.get("material_weakening_evidence_count_72h") or 0),
            "material_strengthening_evidence_count_72h": int(hourly_row.get("material_strengthening_evidence_count_72h") or 0),
        }
        trigger = {
            "code": code,
            "name": str(row.get("name") or hourly_row.get("name") or ""),
            "is_current_holding": "CURRENT_HOLDING" in reason_codes,
            "existing_formal_action": str(row.get("formal_action") or ""),
            "priority": str(row.get("priority") or ""),
            "priority_score": int(row.get("priority_score") or 0),
            "research_tier": str(row.get("research_tier") or ""),
            "thesis_status": str(row.get("thesis_status") or ""),
            "hourly_research_conclusion": conclusion,
            "price_evidence_status": str(hourly_row.get("price_evidence_status") or ""),
            "trigger_reasons": trigger_reasons,
            "material_evidence_ids": material_evidence_ids,
            "signal_counts": signal_counts,
            "price_signal_date": _price_signal_date(hourly_row, conclusion),
        }
        triggers.append(trigger)
        digest_rows.append(
            {
                "code": trigger["code"],
                "is_current_holding": trigger["is_current_holding"],
                "thesis_status": trigger["thesis_status"],
                "hourly_research_conclusion": trigger["hourly_research_conclusion"],
                "price_evidence_status": trigger["price_evidence_status"],
                "trigger_reasons": trigger["trigger_reasons"],
                "material_evidence_ids": trigger["material_evidence_ids"],
                "signal_counts": trigger["signal_counts"],
                "price_signal_date": trigger["price_signal_date"],
            }
        )

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
