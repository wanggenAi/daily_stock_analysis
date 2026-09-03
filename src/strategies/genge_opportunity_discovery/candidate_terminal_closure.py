"""Terminal candidate closure for the GenGe V3.1.1 postscan pipeline.

This layer never creates trade authority. BUY may only mirror an authoritative
V3.1.1 production BUY. Every deep-research candidate is nevertheless forced to
a terminal user-facing state: BUY, WAIT_PRICE, or REJECT. Missing evidence or
failed retrieval after the upstream exhaustive research cycle therefore cannot
leave a candidate parked indefinitely in RESEARCH_CANDIDATE/RAISE_ONLY.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping

from .production_model import FORMAL_BUY_MAX_PRICE_TO_NEUTRAL
from .selection_framework_v31 import execution_universe_status

TERMINAL_STATES = frozenset({"BUY", "WAIT_PRICE", "REJECT"})
PRICE_ONLY_REASON_CODES = frozenset(
    {
        "BUY_MARGIN_OF_SAFETY_INSUFFICIENT",
        "PRICE_TOO_CLOSE_TO_BASE_VALUE",
    }
)
CONFIDENCE_BLOCK_REASON_CODES = frozenset(
    {
        "BUY_VALUATION_CONFIDENCE_NOT_HIGH",
        "VALUATION_CONFIDENCE_NOT_HIGH",
        "STRICT_PIT_INPUT_INCOMPLETE",
    }
)


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


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "pass", "passed"}


def _tokens(value: Any) -> set[str]:
    text = str(value or "").replace(",", ";")
    return {token.strip() for token in text.split(";") if token.strip()}


def _read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _production_by_code(rows: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for raw in rows:
        if str(raw.get("decision_scope") or "").strip().upper() != "CANDIDATE":
            continue
        code = _code(raw.get("code"))
        if code:
            result[code] = dict(raw)
    return result


def _reject_row(
    formal: Mapping[str, Any],
    production: Mapping[str, Any] | None,
    reason: str,
) -> dict[str, Any]:
    production = dict(production or {})
    code = _code(formal.get("code") or production.get("code"))
    return {
        "code": code,
        "stock_name": production.get("stock_name") or formal.get("stock_name") or "",
        "terminal_candidate_state": "REJECT",
        "terminal_reason": reason,
        "wait_price_max": "",
        "source_production_action": production.get("production_action") or "",
        "valuation_confidence": production.get("valuation_confidence") or formal.get("valuation_confidence") or "",
        "current_price": production.get("current_price") or formal.get("current_price") or formal.get("v31_current_price") or "",
        "neutral_value": production.get("neutral_value") or formal.get("neutral_value") or formal.get("v31_neutral_value") or "",
        "source_reason_codes": production.get("reason_codes") or formal.get("reason_codes") or "",
        "strict_pit_input_status": production.get("v311_expectation_input_status") or "",
        "formal_buy_mirrored_only": True,
        "new_trade_authority_created": False,
        "no_auto_trade": True,
    }


def terminalize_candidate(
    formal: Mapping[str, Any],
    production: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Force one deep-research candidate to BUY/WAIT_PRICE/REJECT.

    WAIT_PRICE is intentionally narrow: the authoritative production decision
    must already be WAIT with HIGH valuation confidence and an explicit
    price-only reason. The wait price is the frozen V3.1.1 formal-BUY ceiling,
    currently 80% of neutral/base value. Any evidence/confidence gap becomes a
    terminal current-cycle REJECT rather than an indefinite research state.
    """
    code = _code(formal.get("code") or (production or {}).get("code"))
    if execution_universe_status(code) != "EXECUTION_ELIGIBLE":
        return _reject_row(formal, production, "EXECUTION_UNIVERSE_BLOCKED")
    if production is None:
        return _reject_row(
            formal,
            None,
            "AUTHORITATIVE_PRODUCTION_DECISION_MISSING_AFTER_EXHAUSTIVE_CLOSURE",
        )

    production = dict(production)
    action = str(production.get("production_action") or "").strip().upper()
    confidence = str(production.get("valuation_confidence") or "").strip().upper()
    reasons = _tokens(production.get("reason_codes"))
    neutral = _finite(production.get("neutral_value"))
    current = _finite(production.get("current_price"))
    ratio = _finite(production.get("formal_buy_max_price_to_neutral"))
    if ratio is None:
        ratio = FORMAL_BUY_MAX_PRICE_TO_NEUTRAL

    base = {
        "code": code,
        "stock_name": production.get("stock_name") or formal.get("stock_name") or "",
        "valuation_confidence": confidence,
        "current_price": current if current is not None else "",
        "neutral_value": neutral if neutral is not None else "",
        "source_production_action": action,
        "source_reason_codes": ";".join(sorted(reasons)),
        "strict_pit_input_status": production.get("v311_expectation_input_status") or "",
        "formal_buy_mirrored_only": True,
        "new_trade_authority_created": False,
        "no_auto_trade": True,
    }

    if action == "BUY":
        if confidence != "HIGH" or not _truthy(production.get("production_model_frozen", True)):
            return _reject_row(formal, production, "BUY_AUTHORITY_INVARIANT_FAILED")
        return {
            **base,
            "terminal_candidate_state": "BUY",
            "terminal_reason": "AUTHORITATIVE_V311_PRODUCTION_BUY",
            "wait_price_max": "",
        }

    price_only_wait = bool(reasons & PRICE_ONLY_REASON_CODES)
    confidence_blocked = bool(reasons & CONFIDENCE_BLOCK_REASON_CODES)
    if (
        action == "WAIT"
        and confidence == "HIGH"
        and price_only_wait
        and not confidence_blocked
        and neutral is not None
        and neutral > 0.0
        and current is not None
        and current > 0.0
        and ratio is not None
        and ratio > 0.0
    ):
        wait_price = round(neutral * ratio, 4)
        if current > wait_price:
            return {
                **base,
                "terminal_candidate_state": "WAIT_PRICE",
                "terminal_reason": "HIGH_CONFIDENCE_PRICE_ONLY_BLOCK",
                "wait_price_max": wait_price,
            }

    unresolved = _tokens(formal.get("long_term_blockers"))
    if unresolved:
        reason = "EVIDENCE_OR_MODEL_NOT_PROVEN_AFTER_EXHAUSTIVE_CLOSURE:" + ";".join(sorted(unresolved))
    elif action == "WAIT":
        reason = "NON_PRICE_WAIT_AFTER_EXHAUSTIVE_CLOSURE"
    else:
        reason = f"NON_BUY_CANDIDATE_ACTION_AFTER_EXHAUSTIVE_CLOSURE:{action or 'UNKNOWN'}"
    return _reject_row(formal, production, reason)


def build_terminal_rows(
    formal_rows: Iterable[Mapping[str, Any]],
    production_rows: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    production_map = _production_by_code(production_rows)
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for formal in formal_rows:
        code = _code(formal.get("code"))
        if not code or code in seen:
            continue
        rows.append(terminalize_candidate(formal, production_map.get(code)))
        seen.add(code)
    rows.sort(
        key=lambda row: (
            {"BUY": 0, "WAIT_PRICE": 1, "REJECT": 2}.get(row["terminal_candidate_state"], 9),
            row["code"],
        )
    )
    return rows


def write_terminal_report(
    formal_csv: Path,
    production_csv: Path,
    output_dir: Path,
) -> list[dict[str, Any]]:
    formal_rows = _read_csv(formal_csv)
    production_rows = _read_csv(production_csv)
    rows = build_terminal_rows(formal_rows, production_rows)
    output_dir.mkdir(parents=True, exist_ok=True)

    fields = [
        "code",
        "stock_name",
        "terminal_candidate_state",
        "terminal_reason",
        "wait_price_max",
        "source_production_action",
        "valuation_confidence",
        "current_price",
        "neutral_value",
        "source_reason_codes",
        "strict_pit_input_status",
        "formal_buy_mirrored_only",
        "new_trade_authority_created",
        "no_auto_trade",
    ]
    with (output_dir / "candidate_terminal_decisions.csv").open(
        "w", encoding="utf-8", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    counts = {state: sum(row["terminal_candidate_state"] == state for row in rows) for state in sorted(TERMINAL_STATES)}
    summary = {
        "candidate_count": len(rows),
        "terminal_counts": counts,
        "terminality_contract_satisfied": bool(rows) and sum(counts.values()) == len(rows),
        "non_terminal_count": sum(row["terminal_candidate_state"] not in TERMINAL_STATES for row in rows),
        "wait_price_without_price_count": sum(
            row["terminal_candidate_state"] == "WAIT_PRICE" and _finite(row.get("wait_price_max")) is None
            for row in rows
        ),
        "authoritative_production_decision_missing_count": sum(
            str(row.get("terminal_reason") or "").startswith("AUTHORITATIVE_PRODUCTION_DECISION_MISSING")
            for row in rows
        ),
        "formal_buy_mirrored_only": True,
        "new_trade_authority_created": False,
        "canonical_authority_preserved": True,
        "no_auto_trade": True,
    }
    (output_dir / "candidate_terminal_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    lines = [
        "# GenGe Candidate Terminal Closure",
        "",
        "Every deep-research candidate is closed to BUY / WAIT_PRICE / REJECT for the current cycle.",
        "BUY only mirrors the authoritative V3.1.1 production BUY; this layer never creates trade authority.",
        "",
    ]
    for row in rows:
        line = f"- {row['code']} {row['stock_name']}: **{row['terminal_candidate_state']}**"
        if row["terminal_candidate_state"] == "WAIT_PRICE":
            line += f" | wait <= {row['wait_price_max']}"
        line += f" | {row['terminal_reason']}"
        lines.append(line)
    (output_dir / "candidate_terminal_decisions.md").write_text("\n".join(lines), encoding="utf-8")
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--formal-csv", type=Path, required=True)
    parser.add_argument("--production-csv", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    rows = write_terminal_report(args.formal_csv, args.production_csv, args.output_dir)
    print(f"candidate_terminal_closure={args.output_dir};count={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
