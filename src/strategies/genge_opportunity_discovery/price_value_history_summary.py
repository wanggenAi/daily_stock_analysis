"""Summarize persisted Price/Value history without recomputing Formal actions."""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

CONTRACT_VERSION = "GEN_GE_PRICE_VALUE_HISTORY_SUMMARY_V1"
WINDOWS = (1, 5, 20)


def _d(v: Any) -> Decimal | None:
    try:
        return Decimal(str(v))
    except (InvalidOperation, TypeError, ValueError):
        return None


def load_daily(root: Path) -> dict[str, list[dict[str, Any]]]:
    per_code_date: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
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
            if code:
                per_code_date[code][date] = {
                    "date": date,
                    "price": row.get("latest_price"),
                    "value_anchor": row.get("validated_value_anchor"),
                    "price_to_value": row.get("price_to_value"),
                    "margin_of_safety": row.get("margin_of_safety"),
                }
    return {code: [dates[d] for d in sorted(dates)] for code, dates in per_code_date.items()}


def _window(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ratios = [_d(r.get("price_to_value")) for r in rows]
    ratios = [x for x in ratios if x is not None]
    anchors = [_d(r.get("value_anchor")) for r in rows]
    anchors = [x for x in anchors if x is not None]
    prices = [_d(r.get("price")) for r in rows]
    prices = [x for x in prices if x is not None]
    anchor_drift = None
    if len(anchors) >= 2 and anchors[0] != 0:
        anchor_drift = (anchors[-1] / anchors[0]) - Decimal("1")
    price_change = None
    if len(prices) >= 2 and prices[0] != 0:
        price_change = (prices[-1] / prices[0]) - Decimal("1")
    return {
        "observed_days": len(rows),
        "days_at_or_below_0_80": sum(x <= Decimal("0.80") for x in ratios),
        "price_to_value_min": str(min(ratios)) if ratios else None,
        "price_to_value_max": str(max(ratios)) if ratios else None,
        "price_to_value_latest": str(ratios[-1]) if ratios else None,
        "value_anchor_drift": str(anchor_drift.quantize(Decimal("0.000001"))) if anchor_drift is not None else None,
        "price_change": str(price_change.quantize(Decimal("0.000001"))) if price_change is not None else None,
    }


def summarize(daily: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    rows = []
    for code, observations in sorted(daily.items()):
        item = {"code": code, "distinct_trading_days": len(observations), "latest": observations[-1] if observations else None, "windows": {}}
        for window in WINDOWS:
            item["windows"][f"d{window}"] = _window(observations[-window:])
        rows.append(item)
    return {
        "contract_version": CONTRACT_VERSION,
        "formal_action_recomputed": False,
        "formal_action_eligible": False,
        "no_auto_trade": True,
        "security_count": len(rows),
        "rows": rows,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--history-root", type=Path, default=Path("data/hourly_deep_overlay"))
    p.add_argument("--output", type=Path, default=Path("data/price_value_history/summary.json"))
    args = p.parse_args(argv)
    payload = summarize(load_daily(args.history_root))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"security_count": payload["security_count"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
