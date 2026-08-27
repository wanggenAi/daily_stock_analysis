"""Stateful candidate metabolism for finalized GenGe V3.1.1 snapshots.

This module is downstream memory. It must never filter broad Discovery and it
must never manufacture a Formal BUY/ADD/REDUCE/EXIT action. Its purpose is to
make candidate lifecycle bookkeeping idempotent and auditable:

* one canonical snapshot may increment a candidate's ``seen_count`` at most once;
* absence from one snapshot never archives a candidate automatically;
* Archived/INVALIDATED candidates may be rediscovered but never auto-reactivate;
* upgrades, downgrades, invalidations and reactivations require an explicit,
  uniquely identified evidence event;
* out-of-order canonical snapshots are rejected instead of silently rewriting
  later state with older research;
* generic production-only HOLD_REVIEW rows do not inflate durable candidate
  memory. New names enter automatically only through Deep Review or a meaningful
  non-HOLD_REVIEW candidate action, while already-known candidates may continue
  to be observed through production re-underwriting.
"""
from __future__ import annotations

import argparse
import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .canonical_snapshot import validate_snapshot

LIFECYCLE_CONTRACT_VERSION = "GEN_GE_V31_CANDIDATE_LIFECYCLE_V1"
ACTIVE = "ACTIVE"
ARCHIVED = "ARCHIVED"
INVALIDATED = "INVALIDATED"
_ALLOWED_STATES = {ACTIVE, ARCHIVED, INVALIDATED}

SYSTEM_NEW = "NEW"
SYSTEM_RESEEN = "RESEEN"
SYSTEM_REDISCOVERED_REVIEW_REQUIRED = "REDISCOVERED_REVIEW_REQUIRED"

EXPLICIT_UPGRADED = "UPGRADED"
EXPLICIT_DOWNGRADED = "DOWNGRADED"
EXPLICIT_PRICE_ONLY_CHANGE = "PRICE_ONLY_CHANGE"
EXPLICIT_ARCHIVED = "ARCHIVED"
EXPLICIT_INVALIDATED = "INVALIDATED"
EXPLICIT_REACTIVATED = "REACTIVATED"
_EXPLICIT_EVENTS = {
    EXPLICIT_UPGRADED,
    EXPLICIT_DOWNGRADED,
    EXPLICIT_PRICE_ONLY_CHANGE,
    EXPLICIT_ARCHIVED,
    EXPLICIT_INVALIDATED,
    EXPLICIT_REACTIVATED,
}

_DURABLE_PRODUCTION_ENTRY_ACTIONS = {"BUY", "ADD", "REDUCE", "EXIT"}


def _code(value: Any) -> str:
    text = str(value or "").strip().upper()
    if "." in text:
        base, suffix = text.rsplit(".", 1)
        if suffix in {"SH", "SZ", "BJ"}:
            text = base
    for prefix in ("SH", "SZ", "BJ"):
        if text.startswith(prefix) and text[len(prefix):].isdigit():
            text = text[len(prefix):]
            break
    return text.zfill(6) if text.isdigit() else text


def _parse_timestamp(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def empty_state() -> dict[str, Any]:
    return {
        "contract_version": LIFECYCLE_CONTRACT_VERSION,
        "latest_applied_snapshot_id": "",
        "latest_research_as_of": "",
        "applied_snapshot_ids": [],
        "candidates": {},
        "event_count": 0,
        "no_auto_trade": True,
        "discovery_is_filtered_by_lifecycle": False,
    }


def _validate_state(state: Mapping[str, Any]) -> None:
    if state.get("contract_version") != LIFECYCLE_CONTRACT_VERSION:
        raise ValueError("candidate lifecycle contract version mismatch")
    if state.get("no_auto_trade") is not True:
        raise ValueError("candidate lifecycle no-auto-trade contract missing")
    if state.get("discovery_is_filtered_by_lifecycle") is not False:
        raise ValueError("candidate lifecycle must not filter broad discovery")
    candidates = state.get("candidates")
    if not isinstance(candidates, Mapping):
        raise ValueError("candidate lifecycle candidates must be an object")
    for code, candidate in candidates.items():
        if _code(code) != code or not isinstance(candidate, Mapping):
            raise ValueError(f"invalid candidate lifecycle entry: {code}")
        if candidate.get("lifecycle_state") not in _ALLOWED_STATES:
            raise ValueError(f"invalid candidate lifecycle state: {code}")


def _observed_candidates(
    snapshot: Mapping[str, Any],
    *,
    existing_codes: Iterable[str] = (),
) -> dict[str, dict[str, Any]]:
    """Return durable-research observations, never the broad Discovery pool.

    Deep Review is the normal automatic entry path. Production candidate rows
    enrich those observations. A production-only row is admitted when the name
    is already in lifecycle memory (continuous re-underwriting) or when the row
    carries a meaningful non-HOLD_REVIEW candidate action. This prevents
    hundreds of ordinary fail-closed production rows from becoming a fake
    long-term candidate pool.
    """
    known = {_code(code) for code in existing_codes if _code(code)}
    result: dict[str, dict[str, Any]] = {}
    deep_rows = list((snapshot.get("deep_review") or {}).get("rows") or [])
    production_rows = list((snapshot.get("production") or {}).get("candidate_decisions") or [])

    for raw in deep_rows:
        if not isinstance(raw, Mapping):
            continue
        code = _code(raw.get("code"))
        if not code:
            continue
        result[code] = {
            "code": code,
            "stock_name": str(raw.get("stock_name") or ""),
            "research_tier": str(raw.get("candidate_class") or ""),
            "valuation_confidence": str(raw.get("valuation_confidence") or ""),
            "formal_action": "",
            "observed_scope": "DEEP_REVIEW",
        }

    for raw in production_rows:
        if not isinstance(raw, Mapping):
            continue
        code = _code(raw.get("code"))
        if not code:
            continue
        action = str(raw.get("action") or "").strip().upper()
        if code not in result and code not in known and action not in _DURABLE_PRODUCTION_ENTRY_ACTIONS:
            continue
        existing = result.setdefault(
            code,
            {
                "code": code,
                "stock_name": str(raw.get("stock_name") or ""),
                "research_tier": "",
                "valuation_confidence": "",
                "formal_action": "",
                "observed_scope": "PRODUCTION_REUNDERWRITE",
            },
        )
        existing["stock_name"] = str(raw.get("stock_name") or existing.get("stock_name") or "")
        existing["valuation_confidence"] = str(
            raw.get("valuation_confidence") or existing.get("valuation_confidence") or ""
        )
        existing["formal_action"] = action
        existing["observed_scope"] = (
            "DEEP_REVIEW+PRODUCTION_DECISION"
            if existing.get("observed_scope") == "DEEP_REVIEW"
            else "PRODUCTION_REUNDERWRITE"
        )
    return result


def _append_event(candidate: dict[str, Any], event: dict[str, Any]) -> None:
    history = candidate.setdefault("history", [])
    history.append(event)
    if len(history) > 100:
        del history[:-100]
    candidate["last_event"] = event["event"]
    candidate["last_event_at"] = event["observed_at"]


def apply_snapshot(
    state: Mapping[str, Any] | None,
    snapshot: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Apply one canonical snapshot exactly once."""
    validate_snapshot(snapshot)
    next_state = copy.deepcopy(dict(state) if state is not None else empty_state())
    _validate_state(next_state)

    snapshot_id = str(snapshot.get("snapshot_id") or "")
    source_run_id = str(snapshot.get("source_run_id") or "")
    research_as_of = str(snapshot.get("research_as_of") or snapshot.get("generated_at") or "")
    applied = list(next_state.get("applied_snapshot_ids") or [])
    if snapshot_id in applied:
        return next_state, []

    prior_time = _parse_timestamp(next_state.get("latest_research_as_of"))
    incoming_time = _parse_timestamp(research_as_of)
    if prior_time is not None and incoming_time is not None and incoming_time < prior_time:
        raise ValueError("out-of-order canonical snapshot rejected by candidate lifecycle")

    candidates = next_state["candidates"]
    observations = _observed_candidates(snapshot, existing_codes=candidates.keys())
    events: list[dict[str, Any]] = []
    for code, observation in sorted(observations.items()):
        candidate = candidates.get(code)
        if candidate is None:
            candidate = {
                "code": code,
                "stock_name": observation.get("stock_name") or "",
                "lifecycle_state": ACTIVE,
                "research_tier": observation.get("research_tier") or "",
                "first_seen_snapshot_id": snapshot_id,
                "first_seen_source_run_id": source_run_id,
                "last_seen_snapshot_id": "",
                "last_seen_source_run_id": "",
                "seen_count": 0,
                "last_formal_action": "",
                "last_valuation_confidence": "",
                "last_event": "",
                "last_event_at": "",
                "applied_evidence_ids": [],
                "history": [],
            }
            candidates[code] = candidate
            event_name = SYSTEM_NEW
        elif candidate.get("lifecycle_state") in {ARCHIVED, INVALIDATED}:
            event_name = SYSTEM_REDISCOVERED_REVIEW_REQUIRED
        else:
            event_name = SYSTEM_RESEEN

        if candidate.get("last_seen_snapshot_id") == snapshot_id:
            continue

        candidate["stock_name"] = observation.get("stock_name") or candidate.get("stock_name") or ""
        if observation.get("research_tier"):
            candidate["research_tier"] = observation["research_tier"]
        candidate["last_formal_action"] = observation.get("formal_action") or ""
        candidate["last_valuation_confidence"] = observation.get("valuation_confidence") or ""
        candidate["last_seen_snapshot_id"] = snapshot_id
        candidate["last_seen_source_run_id"] = source_run_id
        candidate["seen_count"] = int(candidate.get("seen_count") or 0) + 1

        event = {
            "event": event_name,
            "code": code,
            "snapshot_id": snapshot_id,
            "source_run_id": source_run_id,
            "observed_at": research_as_of,
            "observed_scope": observation.get("observed_scope") or "",
            "formal_action": observation.get("formal_action") or "",
            "valuation_confidence": observation.get("valuation_confidence") or "",
            "lifecycle_state_after": candidate["lifecycle_state"],
            "automatic_reactivation": False,
        }
        _append_event(candidate, event)
        events.append(event)

    applied.append(snapshot_id)
    next_state["applied_snapshot_ids"] = applied[-200:]
    next_state["latest_applied_snapshot_id"] = snapshot_id
    next_state["latest_research_as_of"] = research_as_of
    next_state["event_count"] = int(next_state.get("event_count") or 0) + len(events)
    _validate_state(next_state)
    return next_state, events


def apply_explicit_transition(
    state: Mapping[str, Any],
    transition: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Apply one evidence-backed lifecycle transition idempotently."""
    next_state = copy.deepcopy(dict(state))
    _validate_state(next_state)

    code = _code(transition.get("code"))
    event_name = str(transition.get("event") or "").strip().upper()
    evidence_id = str(transition.get("evidence_id") or "").strip()
    observed_at = str(transition.get("evidence_observed_at") or "").strip()
    reason = str(transition.get("reason") or "").strip()
    target_tier = str(transition.get("target_tier") or "").strip()
    snapshot_id = str(transition.get("snapshot_id") or next_state.get("latest_applied_snapshot_id") or "")

    if not code or code not in next_state["candidates"]:
        raise ValueError("explicit lifecycle transition requires an existing candidate")
    if event_name not in _EXPLICIT_EVENTS:
        raise ValueError(f"unsupported explicit lifecycle event: {event_name}")
    if not evidence_id or not observed_at or not reason:
        raise ValueError("explicit lifecycle transition requires evidence_id, evidence_observed_at and reason")
    if _parse_timestamp(observed_at) is None:
        raise ValueError("explicit lifecycle evidence_observed_at must be ISO-8601")

    candidate = next_state["candidates"][code]
    evidence_ids = list(candidate.get("applied_evidence_ids") or [])
    if evidence_id in evidence_ids:
        return next_state, None

    prior_state = str(candidate.get("lifecycle_state") or ACTIVE)
    if event_name == EXPLICIT_ARCHIVED:
        new_state = ARCHIVED
    elif event_name == EXPLICIT_INVALIDATED:
        new_state = INVALIDATED
    elif event_name == EXPLICIT_REACTIVATED:
        if prior_state not in {ARCHIVED, INVALIDATED}:
            raise ValueError("REACTIVATED requires an Archived/INVALIDATED candidate")
        new_state = ACTIVE
    else:
        new_state = prior_state

    if prior_state in {ARCHIVED, INVALIDATED} and event_name in {
        EXPLICIT_UPGRADED,
        EXPLICIT_DOWNGRADED,
        EXPLICIT_PRICE_ONLY_CHANGE,
    }:
        new_state = prior_state

    candidate["lifecycle_state"] = new_state
    if target_tier:
        candidate["research_tier"] = target_tier
    evidence_ids.append(evidence_id)
    candidate["applied_evidence_ids"] = evidence_ids[-200:]

    event = {
        "event": event_name,
        "code": code,
        "snapshot_id": snapshot_id,
        "source_run_id": str(transition.get("source_run_id") or ""),
        "observed_at": observed_at,
        "evidence_id": evidence_id,
        "reason": reason,
        "prior_lifecycle_state": prior_state,
        "lifecycle_state_after": new_state,
        "target_tier": target_tier,
        "automatic_reactivation": False,
    }
    _append_event(candidate, event)
    next_state["event_count"] = int(next_state.get("event_count") or 0) + 1
    _validate_state(next_state)
    return next_state, event


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return empty_state()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("candidate lifecycle state must be a JSON object")
    _validate_state(payload)
    return payload


def write_state(path: Path, state: Mapping[str, Any]) -> None:
    _validate_state(state)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--transitions-json", type=Path)
    args = parser.parse_args(argv)

    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    if not isinstance(snapshot, dict):
        raise ValueError("canonical snapshot must be a JSON object")
    state = load_state(args.state)
    state, snapshot_events = apply_snapshot(state, snapshot)

    transition_events: list[dict[str, Any]] = []
    if args.transitions_json:
        payload = json.loads(args.transitions_json.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError("transitions JSON must be an array")
        for transition in payload:
            if not isinstance(transition, Mapping):
                raise ValueError("lifecycle transition must be an object")
            state, event = apply_explicit_transition(state, transition)
            if event is not None:
                transition_events.append(event)

    target = args.output or args.state
    write_state(target, state)
    print(
        json.dumps(
            {
                "contract_version": LIFECYCLE_CONTRACT_VERSION,
                "snapshot_id": snapshot.get("snapshot_id"),
                "snapshot_events": snapshot_events,
                "transition_events": transition_events,
                "candidate_count": len(state["candidates"]),
                "event_count": state["event_count"],
                "no_auto_trade": True,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
