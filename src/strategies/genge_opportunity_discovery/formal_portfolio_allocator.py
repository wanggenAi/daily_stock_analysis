"""Portfolio-level allocator for already-qualified long-term candidates.

Candidate selection remains upstream.  This module only converts eligible
BUY_READY / TRY_POSITION rows into mutually consistent portfolio allocations so
several individually sensible positions cannot collectively violate gross,
industry or aggregate stop-risk limits.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from .drawdown_risk_policy import (
    DEFAULT_DRAWDOWN_POLICY,
    DrawdownRiskPolicy,
    drawdown_magnitude,
    position_fraction,
)

RULE_VERSION = "formal_portfolio_allocator_v1"
ELIGIBLE_CLASSES = {"LONG_TERM_BUY_READY", "LONG_TERM_TRY_POSITION"}


@dataclass
class AllocationState:
    portfolio_drawdown_pct: float = 0.0
    total_fraction: float = 0.0
    open_risk_pct: float = 0.0
    name_allocations: dict[str, float] | None = None
    industry_allocations: dict[str, float] | None = None

    def __post_init__(self) -> None:
        self.name_allocations = dict(self.name_allocations or {})
        self.industry_allocations = dict(self.industry_allocations or {})


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _bool(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


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


def _fraction(value: Any) -> float:
    number = _finite(value)
    if number is None or number <= 0:
        return 0.0
    if number > 1.0 and number <= 100.0:
        number /= 100.0
    return max(0.0, min(1.0, number))


def load_state(path: Path | None) -> AllocationState:
    if path is None:
        return AllocationState()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("portfolio state must be a JSON object")
    names = {
        _code(code): _fraction(value)
        for code, value in dict(payload.get("name_allocations") or {}).items()
    }
    industries = {
        str(industry): _fraction(value)
        for industry, value in dict(payload.get("industry_allocations") or {}).items()
    }
    explicit_total = _finite(payload.get("total_allocated_fraction"))
    total = _fraction(explicit_total) if explicit_total is not None else min(1.0, sum(names.values()))
    return AllocationState(
        portfolio_drawdown_pct=float(payload.get("portfolio_drawdown_pct") or 0.0),
        total_fraction=total,
        open_risk_pct=max(0.0, float(payload.get("open_risk_pct") or 0.0)),
        name_allocations=names,
        industry_allocations=industries,
    )


def _risk_geometry(row: Mapping[str, Any]) -> tuple[float | None, float | None]:
    low = _finite(row.get("entry_low"))
    high = _finite(row.get("entry_high"))
    stop = _finite(row.get("risk_invalidation_price"))
    if low is None or high is None or stop is None or low <= 0 or high <= 0:
        return None, None
    reference = (low + high) / 2.0
    if stop >= reference:
        return reference, None
    return reference, (reference - stop) / reference * 100.0


def allocate_candidates(
    rows: Iterable[Mapping[str, Any]],
    *,
    state: AllocationState | None = None,
    policy: DrawdownRiskPolicy = DEFAULT_DRAWDOWN_POLICY,
) -> list[dict[str, Any]]:
    """Allocate in upstream rank order while mutating one portfolio risk ledger."""

    state = state or AllocationState()
    result: list[dict[str, Any]] = []

    for position, raw in enumerate(rows, 1):
        row = dict(raw)
        code = _code(row.get("code"))
        industry = str(row.get("industry") or "")
        classification = str(row.get("long_term_classification") or "")
        eligible = _bool(row.get("long_term_formal_buy_eligible")) and classification in ELIGIBLE_CLASSES
        reference_entry, stop_distance = _risk_geometry(row)

        allocated = 0.0
        status = "INELIGIBLE"
        if eligible and stop_distance is None:
            status = "INVALID_RISK_GEOMETRY"
        elif eligible:
            allocated = position_fraction(
                stop_distance_pct=float(stop_distance),
                portfolio_drawdown_pct=state.portfolio_drawdown_pct,
                current_industry_fraction=state.industry_allocations.get(industry, 0.0),
                current_name_fraction=state.name_allocations.get(code, 0.0),
                current_total_fraction=state.total_fraction,
                current_open_risk_pct=state.open_risk_pct,
                policy=policy,
            )
            if classification == "LONG_TERM_TRY_POSITION":
                allocated *= 0.5
            allocated = round(max(0.0, allocated), 6)
            status = "ALLOCATED" if allocated > 0 else "NO_PORTFOLIO_RISK_CAPACITY"

        incremental_risk_pct = 0.0
        if allocated > 0 and stop_distance is not None:
            incremental_risk_pct = allocated * float(stop_distance)
            state.total_fraction += allocated
            state.open_risk_pct += incremental_risk_pct
            state.name_allocations[code] = state.name_allocations.get(code, 0.0) + allocated
            state.industry_allocations[industry] = state.industry_allocations.get(industry, 0.0) + allocated

        result.append(
            {
                **row,
                "portfolio_allocation_order": position,
                "portfolio_allocation_status": status,
                "portfolio_reference_entry": round(reference_entry, 6) if reference_entry is not None else None,
                "portfolio_stop_distance_pct": round(stop_distance, 6) if stop_distance is not None else None,
                "portfolio_incremental_risk_pct": round(incremental_risk_pct, 6),
                "portfolio_allocated_fraction": allocated,
                "portfolio_allocated_pct": round(allocated * 100.0, 4),
                "portfolio_total_fraction_after": round(state.total_fraction, 6),
                "portfolio_total_pct_after": round(state.total_fraction * 100.0, 4),
                "portfolio_open_risk_pct_after": round(state.open_risk_pct, 6),
                "portfolio_industry_fraction_after": round(state.industry_allocations.get(industry, 0.0), 6),
                "portfolio_industry_pct_after": round(state.industry_allocations.get(industry, 0.0) * 100.0, 4),
                "portfolio_drawdown_pct": drawdown_magnitude(state.portfolio_drawdown_pct),
                "max_total_gross_pct": policy.max_total_gross_fraction * 100.0,
                "max_total_open_risk_pct": policy.max_total_open_risk_pct,
                "max_single_name_pct": policy.max_single_name_fraction * 100.0,
                "max_industry_pct": policy.max_industry_fraction * 100.0,
                "allocator_rule_version": RULE_VERSION,
            }
        )
    return result


def _read(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _write(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = sorted({key for row in rows for key in row}) if rows else ["code", "portfolio_allocation_status"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--portfolio-state", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    rows = allocate_candidates(_read(args.candidates), state=load_state(args.portfolio_state))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    _write(args.output, rows)
    allocated = [row for row in rows if row["portfolio_allocation_status"] == "ALLOCATED"]
    print(json.dumps({
        "row_count": len(rows),
        "allocated_count": len(allocated),
        "allocated_codes": [row.get("code") for row in allocated],
        "rule_version": RULE_VERSION,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
