"""Evaluate forward market outcomes of immutable Formal decisions.

This is an audit/learning layer only. It never changes V3.1.1 thresholds or
Formal actions. Horizons are measured in distinct persisted hourly observation
trading dates after the decision date; insufficient history remains PENDING.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

CONTRACT_VERSION = "GEN_GE_FORMAL_DECISION_OUTCOMES_V1"
HORIZONS = (5, 20, 60)


def _dec(value: Any) -> Decimal | None:
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return d if d > 0 else None


def load_history(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            row = json.loads(line)
            if isinstance(row, dict):
                rows.append(row)
    return rows


def load_daily_prices(root: Path) -> dict[str, dict[str, Decimal]]:
    by_code: dict[str, dict[str, Decimal]] = defaultdict(dict)
    # Last persisted observation of each date wins, approximating the latest
    # available price for that trading date without inventing missing closes.
    for path in sorted(root.glob("????-??-??/*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        date = str(payload.get("generated_at_beijing") or payload.get("generated_at") or path.parent.name)[:10]
        for row in payload.get("rows") or []:
            if not isinstance(row, dict):
                continue
            code = str(row.get("code") or "").zfill(6)
            price = _dec(row.get("latest_price"))
            if code and price is not None:
                by_code[code][date] = price
    return by_code


def evaluate(records: list[dict[str, Any]], daily_prices: dict[str, dict[str, Decimal]]) -> dict[str, Any]:
    out = []
    for record in records:
        code = str(record.get("code") or "").zfill(6)
        decision_date = str(record.get("decision_date") or "")[:10]
        entry = _dec(record.get("current_price"))
        dates = sorted(d for d in daily_prices.get(code, {}) if d > decision_date)
        horizons: dict[str, Any] = {}
        for h in HORIZONS:
            key = f"d{h}"
            if entry is None or len(dates) < h:
                horizons[key] = {"status": "PENDING", "observed_trading_days": len(dates)}
                continue
            target_date = dates[h - 1]
            px = daily_prices[code][target_date]
            ret = (px / entry) - Decimal("1")
            horizons[key] = {
                "status": "OBSERVED",
                "target_date": target_date,
                "price": str(px),
                "return": str(ret.quantize(Decimal("0.000001"))),
            }
        out.append({
            "record_id": record.get("record_id"),
            "canonical_snapshot_id": record.get("canonical_snapshot_id"),
            "code": code,
            "name": record.get("name"),
            "scope": record.get("scope"),
            "formal_action": record.get("formal_action"),
            "decision_date": decision_date,
            "decision_price": str(entry) if entry is not None else None,
            "valuation_confidence": record.get("valuation_confidence"),
            "reason_codes": record.get("reason_codes"),
            "horizons": horizons,
        })
    return {
        "contract_version": CONTRACT_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "horizons_trading_days": list(HORIZONS),
        "record_count": len(out),
        "observed_horizon_count": sum(v.get("status") == "OBSERVED" for r in out for v in r["horizons"].values()),
        "pending_horizon_count": sum(v.get("status") == "PENDING" for r in out for v in r["horizons"].values()),
        "formal_action_recomputed": False,
        "formal_action_eligible": False,
        "parameter_tuning_allowed": False,
        "no_auto_trade": True,
        "records": out,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--history", type=Path, default=Path("data/formal_decision_history/history.jsonl"))
    p.add_argument("--price-history-root", type=Path, default=Path("data/hourly_deep_overlay"))
    p.add_argument("--output", type=Path, default=Path("data/formal_decision_outcomes/latest.json"))
    args = p.parse_args(argv)
    payload = evaluate(load_history(args.history), load_daily_prices(args.price_history_root))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"record_count": payload["record_count"], "observed_horizon_count": payload["observed_horizon_count"], "pending_horizon_count": payload["pending_horizon_count"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
