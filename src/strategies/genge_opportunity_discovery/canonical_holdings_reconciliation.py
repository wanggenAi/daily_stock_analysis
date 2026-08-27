"""Reconcile manually confirmed holdings with one canonical V3.1.1 snapshot.

The canonical snapshot is immutable, while ``CURRENT_HOLDINGS.md`` may change
when the user confirms a trade.  A downstream consumer must therefore know
whether the holding actions inside a finalized snapshot still describe the
currently confirmed portfolio.

This module never invents a holding action.  A mismatch produces the explicit
``HOLDINGS_OUT_OF_SYNC`` state: candidate decisions remain part of the canonical
truth, but holding actions from that snapshot must not be presented as current
portfolio instructions until a new production cycle includes the updated
holdings and is finalized.
"""
from __future__ import annotations

import argparse
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping

from .canonical_snapshot import validate_snapshot
from .production_decision_scan import read_holdings_markdown

HOLDINGS_RECONCILIATION_VERSION = "GEN_GE_V31_HOLDINGS_RECONCILIATION_V1"
HOLDINGS_IN_SYNC = "HOLDINGS_IN_SYNC"
HOLDINGS_OUT_OF_SYNC = "HOLDINGS_OUT_OF_SYNC"


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


def _quantity(value: Any) -> Decimal | None:
    raw = str(value or "").replace(",", "").strip()
    if not raw:
        return None
    try:
        number = Decimal(raw)
    except InvalidOperation:
        return None
    return number if number >= 0 else None


def _current_holdings(path: Path) -> dict[str, dict[str, Any]]:
    rows = read_holdings_markdown(path)
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        code = _code(row.get("code"))
        if not code:
            continue
        quantity = _quantity(row.get("confirmed_quantity"))
        if quantity is None:
            raise ValueError(f"confirmed holding quantity is invalid for {code}")
        if code in result:
            raise ValueError(f"duplicate confirmed holding in CURRENT_HOLDINGS.md: {code}")
        result[code] = {
            **dict(row),
            "code": code,
            "quantity_normalized": str(quantity.normalize()),
        }
    return result


def reconcile_holdings(snapshot: Mapping[str, Any], holdings_md: Path) -> dict[str, Any]:
    validate_snapshot(snapshot)
    current = _current_holdings(holdings_md)

    production = snapshot.get("production") or {}
    canonical_rows = list(production.get("holding_decisions") or [])
    canonical: dict[str, dict[str, Any]] = {}
    invalid_canonical_quantities: list[str] = []
    for raw in canonical_rows:
        if not isinstance(raw, Mapping):
            continue
        code = _code(raw.get("code"))
        if not code:
            continue
        quantity = _quantity(raw.get("confirmed_quantity"))
        if quantity is None:
            invalid_canonical_quantities.append(code)
            continue
        if code in canonical:
            raise ValueError(f"duplicate canonical holding decision: {code}")
        canonical[code] = {
            **dict(raw),
            "code": code,
            "quantity_normalized": str(quantity.normalize()),
        }

    current_codes = set(current)
    canonical_codes = set(canonical)
    current_not_in_canonical = sorted(current_codes - canonical_codes)
    canonical_not_in_current = sorted(canonical_codes - current_codes)
    quantity_mismatches: list[dict[str, str]] = []
    for code in sorted(current_codes & canonical_codes):
        current_quantity = _quantity(current[code].get("confirmed_quantity"))
        canonical_quantity = _quantity(canonical[code].get("confirmed_quantity"))
        if current_quantity != canonical_quantity:
            quantity_mismatches.append(
                {
                    "code": code,
                    "current_quantity": str(current_quantity),
                    "canonical_quantity": str(canonical_quantity),
                }
            )

    in_sync = not (
        current_not_in_canonical
        or canonical_not_in_current
        or quantity_mismatches
        or invalid_canonical_quantities
    )
    status = HOLDINGS_IN_SYNC if in_sync else HOLDINGS_OUT_OF_SYNC

    return {
        "contract_version": HOLDINGS_RECONCILIATION_VERSION,
        "status": status,
        "in_sync": in_sync,
        "canonical_snapshot_id": str(snapshot.get("snapshot_id") or ""),
        "canonical_source_run_id": str(snapshot.get("source_run_id") or ""),
        "canonical_latest_trade_date": str(snapshot.get("latest_trade_date") or ""),
        "current_holdings_source": str(holdings_md),
        "current_holding_count": len(current),
        "canonical_holding_count": len(canonical_rows),
        "current_codes": sorted(current_codes),
        "canonical_codes": sorted(canonical_codes),
        "current_not_in_canonical": current_not_in_canonical,
        "canonical_not_in_current": canonical_not_in_current,
        "quantity_mismatches": quantity_mismatches,
        "invalid_canonical_quantities": sorted(invalid_canonical_quantities),
        "formal_holding_actions_currently_usable": in_sync,
        "candidate_formal_actions_affected_by_holdings_mismatch": False,
        "mismatch_policy": (
            "USE_CANONICAL_HOLDING_ACTIONS"
            if in_sync
            else "FAIL_CLOSED_FOR_HOLDING_ACTIONS_UNTIL_NEW_FINALIZED_SNAPSHOT"
        ),
        "no_auto_trade": True,
    }


def write_reconciliation(snapshot_path: Path, holdings_md: Path, output_path: Path) -> dict[str, Any]:
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    if not isinstance(snapshot, dict):
        raise ValueError("canonical snapshot must be a JSON object")
    result = reconcile_holdings(snapshot, holdings_md)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--holdings-md", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = write_reconciliation(args.snapshot, args.holdings_md, args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    # A mismatch is an explicit safe state rather than a process error.  The
    # consumer must inspect the status and fail closed only for holding actions.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
