"""Read-only operating views over one canonical GenGe V3.1.1 snapshot.

Hourly and daily jobs intentionally have different responsibilities while sharing
exactly the same production truth.  This module never recalculates valuation,
changes a production action, filters the broad discovery universe, or promotes a
research overlay into a trading decision.

HOURLY_MONITOR is an incremental monitoring surface: every confirmed holding plus
the canonical deep-review focus names and their already-produced decisions.
DAILY_SETTLEMENT is the full settlement surface: complete published discovery,
deep-review and production decision state for lifecycle/metabolism processing.
"""
from __future__ import annotations

import argparse
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping

from .canonical_snapshot import PRODUCTION_VERSION, validate_snapshot

OPERATING_VIEW_CONTRACT_VERSION = "GEN_GE_V31_CANONICAL_OPERATING_VIEW_V1"
HOURLY_MONITOR = "HOURLY_MONITOR"
DAILY_SETTLEMENT = "DAILY_SETTLEMENT"
_ALLOWED_MODES = {HOURLY_MONITOR, DAILY_SETTLEMENT}
_A_SHARE_STANDARD_LOT = 100
_REDUCE_ACTION_RE = re.compile(r"^REDUCE_(\d+(?:\.\d+)?)$")


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


def _positive_integer(value: Any) -> int | None:
    try:
        parsed = Decimal(str(value or "").strip())
    except (InvalidOperation, ValueError):
        return None
    if not parsed.is_finite() or parsed <= 0 or parsed != parsed.to_integral_value():
        return None
    return int(parsed)


def _sell_quantity_is_legal_for_a_share(*, holding_quantity: int, sell_quantity: int) -> bool:
    """Validate one manual A-share sell quantity without changing the Formal action."""
    if sell_quantity <= 0 or sell_quantity > holding_quantity:
        return False
    if sell_quantity % _A_SHARE_STANDARD_LOT == 0:
        return True
    odd_lot = holding_quantity % _A_SHARE_STANDARD_LOT
    return odd_lot != 0 and sell_quantity % _A_SHARE_STANDARD_LOT == odd_lot


def _manual_execution_advisory(row: Mapping[str, Any]) -> dict[str, Any]:
    """Project lot-size feasibility only; never create or mutate a Formal action/order."""
    action = str(row.get("action") or row.get("production_action") or "").strip().upper()
    base = {
        "advisory_only": True,
        "no_auto_trade": True,
        "broker_order_created": False,
        "formal_action": action,
        "lot_size": _A_SHARE_STANDARD_LOT,
    }
    if action not in {"EXIT"} and not action.startswith("REDUCE"):
        return {**base, "status": "NOT_APPLICABLE"}

    holding_quantity = _positive_integer(row.get("confirmed_quantity"))
    if holding_quantity is None:
        return {
            **base,
            "status": "BLOCKED_INPUT_INCOMPLETE",
            "reason": "CONFIRMED_QUANTITY_REQUIRED_FOR_MANUAL_EXECUTION",
        }

    if action == "EXIT":
        return {
            **base,
            "status": "MANUAL_ORDER_EXECUTABLE",
            "holding_quantity": holding_quantity,
            "intended_sell_quantity": holding_quantity,
            "manual_sell_quantity": holding_quantity,
            "reason": "FULL_POSITION_EXIT_IS_SINGLE_MANUAL_SELL",
        }

    match = _REDUCE_ACTION_RE.fullmatch(action)
    if match is None:
        return {
            **base,
            "status": "BLOCKED_ACTION_FORMAT",
            "holding_quantity": holding_quantity,
            "reason": "REDUCE_ACTION_REQUIRES_EXPLICIT_PERCENTAGE",
        }

    percentage = Decimal(match.group(1))
    if percentage <= 0 or percentage >= 100:
        return {
            **base,
            "status": "BLOCKED_ACTION_FORMAT",
            "holding_quantity": holding_quantity,
            "reduce_percentage": str(percentage),
            "reason": "REDUCE_PERCENTAGE_MUST_BE_BETWEEN_0_AND_100",
        }

    intended = Decimal(holding_quantity) * percentage / Decimal(100)
    if intended != intended.to_integral_value():
        return {
            **base,
            "status": "BLOCKED_NON_INTEGER_SHARE_TARGET",
            "holding_quantity": holding_quantity,
            "reduce_percentage": str(percentage),
            "intended_sell_quantity": str(intended.normalize()),
            "reason": "FORMAL_REDUCTION_DOES_NOT_MAP_TO_WHOLE_SHARES",
        }

    intended_quantity = int(intended)
    if not _sell_quantity_is_legal_for_a_share(
        holding_quantity=holding_quantity,
        sell_quantity=intended_quantity,
    ):
        return {
            **base,
            "status": "BLOCKED_LOT_SIZE_CONFLICT",
            "holding_quantity": holding_quantity,
            "reduce_percentage": str(percentage),
            "intended_sell_quantity": intended_quantity,
            "manual_sell_quantity": None,
            "reason": "DO_NOT_ROUND_FORMAL_REDUCTION_TO_A_DIFFERENT_POSITION_CHANGE",
        }

    return {
        **base,
        "status": "MANUAL_ORDER_EXECUTABLE",
        "holding_quantity": holding_quantity,
        "reduce_percentage": str(percentage),
        "intended_sell_quantity": intended_quantity,
        "manual_sell_quantity": intended_quantity,
        "reason": "FORMAL_REDUCTION_MAPS_TO_ONE_LEGAL_MANUAL_SELL_QUANTITY",
    }


def _decision_index(snapshot: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    production = snapshot.get("production") or {}
    rows = list(production.get("candidate_decisions") or []) + list(production.get("holding_decisions") or [])
    return {
        _code(row.get("code")): dict(row)
        for row in rows
        if isinstance(row, Mapping) and _code(row.get("code"))
    }


def _hourly_focus(snapshot: Mapping[str, Any]) -> list[dict[str, Any]]:
    decisions = _decision_index(snapshot)
    deep_rows = list((snapshot.get("deep_review") or {}).get("rows") or [])
    focus: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in deep_rows:
        if not isinstance(raw, Mapping):
            continue
        code = _code(raw.get("code"))
        if not code or code in seen:
            continue
        seen.add(code)
        row = dict(raw)
        row["canonical_decision"] = decisions.get(code, {})
        focus.append(row)
    return focus


def build_operating_view(snapshot: Mapping[str, Any], *, mode: str) -> dict[str, Any]:
    """Build a consumer view without mutating or recomputing canonical decisions."""
    validate_snapshot(snapshot)
    normalized_mode = str(mode or "").strip().upper()
    if normalized_mode not in _ALLOWED_MODES:
        raise ValueError(f"unsupported operating mode: {mode}")

    snapshot_id = str(snapshot["snapshot_id"])
    production = snapshot.get("production") or {}
    holdings = []
    for raw in production.get("holding_decisions") or []:
        row = dict(raw)
        row["manual_execution_advisory"] = _manual_execution_advisory(row)
        holdings.append(row)
    candidates = [dict(row) for row in (production.get("candidate_decisions") or [])]
    discovery = [dict(row) for row in ((snapshot.get("discovery") or {}).get("rows") or [])]
    deep_review = [dict(row) for row in ((snapshot.get("deep_review") or {}).get("rows") or [])]

    common = {
        "contract_version": OPERATING_VIEW_CONTRACT_VERSION,
        "mode": normalized_mode,
        "canonical_snapshot_id": snapshot_id,
        "source_run_id": str(snapshot.get("source_run_id") or ""),
        "upstream_run_id": str(snapshot.get("upstream_run_id") or ""),
        "production_version": str(snapshot.get("production_version") or ""),
        "latest_trade_date": str(snapshot.get("latest_trade_date") or ""),
        "generated_at": str(snapshot.get("generated_at") or ""),
        "research_as_of": str(snapshot.get("research_as_of") or ""),
        "action_counts": dict(production.get("action_counts") or {}),
        "consumer_contract": {
            "same_canonical_truth_required": True,
            "decision_recalculation_allowed": False,
            "decision_mutation_allowed": False,
            "research_overlay_may_overwrite_canonical_action": False,
            "fresh_price_or_news_overlay_allowed": True,
            "formal_action_change_requires_new_validated_canonical_snapshot": True,
            "candidate_ledger_may_filter_broad_discovery": False,
            "production_threshold_change_allowed": False,
            "manual_execution_advisory_may_mutate_formal_action": False,
            "manual_execution_advisory_may_create_broker_order": False,
        },
    }

    if normalized_mode == HOURLY_MONITOR:
        focus = _hourly_focus(snapshot)
        return {
            **common,
            "job_contract": {
                "responsibility": "INCREMENTAL_MONITORING",
                "full_market_reunderwrite": False,
                "monitor_all_confirmed_holdings": True,
                "monitor_canonical_deep_review_focus": True,
                "lifecycle_settlement": False,
            },
            "holding_decisions": holdings,
            "focus_candidates": focus,
            "counts": {
                "holdings": len(holdings),
                "focus_candidates": len(focus),
                "canonical_candidate_decisions": len(candidates),
            },
        }

    return {
        **common,
        "job_contract": {
            "responsibility": "FULL_DAILY_SETTLEMENT",
            "full_market_reunderwrite": True,
            "monitor_all_confirmed_holdings": True,
            "settle_candidate_lifecycle": True,
            "allow_evidence_backed_upgrade_downgrade_archive": True,
        },
        "discovery": discovery,
        "deep_review": deep_review,
        "candidate_decisions": candidates,
        "holding_decisions": holdings,
        "counts": {
            "discovery": len(discovery),
            "deep_review": len(deep_review),
            "candidate_decisions": len(candidates),
            "holding_decisions": len(holdings),
        },
    }


def write_operating_views(snapshot_path: Path, output_dir: Path) -> dict[str, Path]:
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    validate_snapshot(snapshot)
    if snapshot.get("production_version") != PRODUCTION_VERSION:
        raise ValueError("operating view requires V3.1.1 production canonical snapshot")
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: dict[str, Path] = {}
    for mode, filename in ((HOURLY_MONITOR, "hourly.json"), (DAILY_SETTLEMENT, "daily.json")):
        view = build_operating_view(snapshot, mode=mode)
        path = output_dir / filename
        path.write_text(json.dumps(view, ensure_ascii=False, indent=2), encoding="utf-8")
        outputs[mode] = path
    return outputs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    outputs = write_operating_views(args.snapshot, args.output_dir)
    print(";".join(f"{mode}={path}" for mode, path in outputs.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
