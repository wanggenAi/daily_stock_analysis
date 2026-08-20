"""Overlay auditable specialized fair values onto the unified scenario sidecar.

The forward-scenario producer intentionally refuses to assign PE multiples to
specialized valuation routes.  This adapter runs afterwards and fills only the
scenario fair prices that can be derived from an already-executed specialized
model without adding a new subjective assumption.

At present, an executed ``capital_markets_cycle`` model can provide a base fair
share price by converting its normalized current/fair P/B units.  Other routes
remain blank until their own model publishes an auditable per-share/equity fair
value.  Missing bear/bull specialized scenarios are never fabricated.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Mapping

from .specialized_scenario_bridge import bridge_specialized_scenario


PRICE_FIELDS = (
    "raw_latest_close",
    "latest_price",
    "current_price",
    "latest_close",
    "adjusted_latest_close",
    "close_price",
    "price",
    "close",
    "last_price",
    "收盘价",
    "最新价",
)
EXTRA_COLUMNS = (
    "specialized_scenario_bridge_status",
    "specialized_scenario_strategy_id",
    "specialized_scenario_basis",
)


def _positive(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _normalize_code(value: Any) -> str:
    text = str(value or "").strip().upper()
    if "." in text:
        base, suffix = text.rsplit(".", 1)
        if suffix in {"SH", "SZ", "BJ"} and base.isdigit():
            text = base
    for prefix in ("SH", "SZ", "BJ"):
        if text.startswith(prefix) and text[len(prefix):].isdigit():
            text = text[len(prefix):]
            break
    return text.zfill(6) if text.isdigit() else text


def _read_csv(path: Path | None) -> list[dict[str, Any]]:
    if path is None or not path.exists():
        return []
    with path.open(encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _choose_path(root: Path, filename: str, preferred_token: str = "") -> Path | None:
    paths = sorted((path for path in root.glob(f"**/{filename}") if path.is_file()), key=str)
    if not paths:
        return None
    if preferred_token:
        preferred = [path for path in paths if preferred_token in str(path)]
        if preferred:
            return preferred[-1]
    return paths[-1]


def _current_price(row: Mapping[str, Any]) -> float | None:
    for field in PRICE_FIELDS:
        value = _positive(row.get(field))
        if value is not None:
            return value
    return None


def overlay_specialized_scenarios(
    forward_rows: list[Mapping[str, Any]],
    specialized_rows: list[Mapping[str, Any]],
    raw_all_a_rows: list[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    specialized_by_code = {
        _normalize_code(row.get("code")): dict(row)
        for row in specialized_rows
        if _normalize_code(row.get("code"))
    }
    raw_by_code = {
        _normalize_code(row.get("code") or row.get("代码")): dict(row)
        for row in raw_all_a_rows
        if _normalize_code(row.get("code") or row.get("代码"))
    }
    stats = {
        "row_count": len(forward_rows),
        "specialized_route_count": 0,
        "specialized_base_fair_value_ready_count": 0,
        "specialized_unavailable_count": 0,
    }
    output: list[dict[str, Any]] = []
    for source in forward_rows:
        row = dict(source)
        code = _normalize_code(row.get("code"))
        specialized = specialized_by_code.get(code)
        if not specialized:
            output.append(row)
            continue
        strategy_id = str(specialized.get("valuation_primary_strategy_id") or "").strip()
        if not strategy_id or strategy_id == "general_reverse_earnings":
            output.append(row)
            continue

        stats["specialized_route_count"] += 1
        price = _current_price(raw_by_code.get(code, {})) or _current_price(row)
        bridge = bridge_specialized_scenario(specialized, current_price=price)
        row["specialized_scenario_bridge_status"] = bridge.status
        row["specialized_scenario_strategy_id"] = bridge.strategy_id
        row["specialized_scenario_basis"] = bridge.basis
        if bridge.fair_price_bear is not None:
            row["scenario_fair_price_bear"] = bridge.fair_price_bear
        if bridge.fair_price_base is not None:
            row["scenario_fair_price_base"] = bridge.fair_price_base
            row["scenario_valuation_status"] = "SPECIALIZED_BASE_ONLY"
            stats["specialized_base_fair_value_ready_count"] += 1
        if bridge.fair_price_bull is not None:
            row["scenario_fair_price_bull"] = bridge.fair_price_bull
        if bridge.fair_price_base is None:
            stats["specialized_unavailable_count"] += 1
        output.append(row)
    return output, stats


def write_specialized_scenario_overlay(
    *,
    artifact_root: Path,
    forward_dir: Path,
) -> list[dict[str, Any]]:
    forward_path = forward_dir / "forward_scenario_valuation.csv"
    specialized_path = _choose_path(
        artifact_root,
        "valuation_research_specialized.csv",
        "valuation_research_queue",
    )
    raw_path = _choose_path(
        artifact_root,
        "raw_all_a_universe.csv",
        "hard_logic_valuation_source",
    )
    forward_rows = _read_csv(forward_path)
    if not forward_rows:
        raise FileNotFoundError("forward_scenario_valuation.csv is missing or empty")
    specialized_rows = _read_csv(specialized_path)
    raw_rows = _read_csv(raw_path)
    if not raw_rows:
        raise FileNotFoundError("raw_all_a_universe.csv is missing or empty")

    rows, stats = overlay_specialized_scenarios(
        forward_rows,
        specialized_rows,
        raw_rows,
    )
    fields = list(forward_rows[0].keys())
    for field in EXTRA_COLUMNS:
        if field not in fields:
            fields.append(field)
    with forward_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        **stats,
        "specialized_sidecar_present": specialized_path is not None,
        "supported_specialized_bridge": "capital_markets_cycle_current_pb_to_fair_pb",
        "bear_bull_specialized_scenarios_invented": False,
        "unsupported_specialized_routes_invent_fair_value": False,
        "formal_signal_eligible": False,
        "automatic_promotion_allowed": False,
        "no_auto_trade": True,
    }
    (forward_dir / "specialized_scenario_bridge_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--forward-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    rows = write_specialized_scenario_overlay(
        artifact_root=args.artifact_root,
        forward_dir=args.forward_dir,
    )
    print(f"specialized_scenario_overlay={args.forward_dir};count={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
