"""Audited transaction ledger and holdings projection for GenGe.

This module is initially parallel to CURRENT_HOLDINGS.md. Production authority is
not switched automatically. A migration must first prove that the ledger-derived
projection exactly reconciles with manually confirmed holdings.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable, Mapping

CONTRACT_VERSION = "GEN_GE_TRANSACTION_LEDGER_V1"
EVENTS = {"OPENING_POSITION", "BUY", "SELL"}


def _code(value: Any) -> str:
    text = "".join(ch for ch in str(value or "") if ch.isdigit())[-6:]
    return text.zfill(6) if text else ""


def _decimal(value: Any) -> Decimal:
    try:
        result = Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, AttributeError):
        raise ValueError(f"invalid decimal: {value!r}")
    if result < 0:
        raise ValueError("negative values are not allowed")
    return result


def _plain_decimal(value: Decimal) -> str:
    """Serialize Decimal without exponent notation while trimming spare zeros."""
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def normalize_transaction(raw: Mapping[str, Any]) -> dict[str, Any]:
    event = str(raw.get("event") or raw.get("side") or "").strip().upper()
    code = _code(raw.get("code"))
    transaction_id = str(raw.get("transaction_id") or raw.get("trade_id") or "").strip()
    evidence_source = str(raw.get("evidence_source") or "").strip()
    trade_date = str(raw.get("trade_date") or "").strip()
    if event not in EVENTS or not code or not transaction_id or not evidence_source or not trade_date:
        raise ValueError("transaction requires event, code, transaction_id, trade_date and evidence_source")
    quantity = _decimal(raw.get("quantity"))
    price = _decimal(raw.get("price"))
    if quantity <= 0:
        raise ValueError("transaction quantity must be positive")
    return {
        "contract_version": CONTRACT_VERSION,
        "transaction_id": transaction_id,
        "event": event,
        "code": code,
        "name": str(raw.get("name") or "").strip(),
        "quantity": _plain_decimal(quantity),
        "price": _plain_decimal(price),
        "trade_date": trade_date,
        "evidence_source": evidence_source,
        "confirmed_at": str(raw.get("confirmed_at") or datetime.now(timezone.utc).isoformat()),
        "no_auto_trade": True,
    }


def load_ledger(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows = []
    ids = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = normalize_transaction(json.loads(line))
        if row["transaction_id"] in ids:
            raise ValueError(f"duplicate transaction_id: {row['transaction_id']}")
        ids.add(row["transaction_id"])
        rows.append(row)
    return rows


def project_holdings(rows: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    quantity: dict[str, Decimal] = defaultdict(Decimal)
    cost_value: dict[str, Decimal] = defaultdict(Decimal)
    names: dict[str, str] = {}
    for raw in rows:
        row = normalize_transaction(raw)
        code = row["code"]
        names[code] = row.get("name") or names.get(code, "")
        qty = _decimal(row["quantity"])
        price = _decimal(row["price"])
        if row["event"] in {"OPENING_POSITION", "BUY"}:
            quantity[code] += qty
            cost_value[code] += qty * price
        else:
            if qty > quantity[code]:
                raise ValueError(f"sell quantity exceeds projected holding for {code}")
            avg = cost_value[code] / quantity[code] if quantity[code] else Decimal(0)
            quantity[code] -= qty
            cost_value[code] -= avg * qty
            if quantity[code] == 0:
                cost_value[code] = Decimal(0)
    result = {}
    for code in sorted(quantity):
        if quantity[code] <= 0:
            continue
        avg = cost_value[code] / quantity[code]
        result[code] = {
            "code": code,
            "name": names.get(code, ""),
            "confirmed_quantity": _plain_decimal(quantity[code]),
            "average_cost": format(avg.quantize(Decimal("0.0001")), "f"),
            "source": "TRANSACTION_LEDGER_PROJECTION",
        }
    return result


def write_projection(ledger_path: Path, output_path: Path) -> dict[str, Any]:
    rows = load_ledger(ledger_path)
    holdings = project_holdings(rows)
    payload = {
        "contract_version": CONTRACT_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "transaction_count": len(rows),
        "holding_count": len(holdings),
        "holdings": holdings,
        "production_source_of_truth": False,
        "migration_required_before_production_use": True,
        "no_auto_trade": True,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--ledger", type=Path, default=Path("data/transactions/ledger.jsonl"))
    p.add_argument("--output", type=Path, default=Path("data/transactions/holdings_projection.json"))
    args = p.parse_args(argv)
    print(json.dumps(write_projection(args.ledger, args.output), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
