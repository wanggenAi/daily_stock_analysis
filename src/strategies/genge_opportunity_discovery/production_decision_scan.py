"""Build auditable GenGe V3.1.1 candidate and holding decisions."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from .production_model import (
    ALLOWED_ACTIONS,
    PRODUCTION_MODEL_NAME,
    PRODUCTION_MODEL_VERSION,
    production_payload,
)


def _read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


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


def read_holdings_markdown(path: Path) -> list[dict[str, Any]]:
    """Read the confirmed-holdings table; cost remains display-only metadata."""
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    in_table = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("| Code | Name | Quantity |"):
            in_table = True
            continue
        if not in_table:
            continue
        if line.startswith("| ---"):
            continue
        if not line.startswith("|"):
            break
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 6:
            continue
        rows.append(
            {
                "code": _code(cells[0]),
                "stock_name": cells[1],
                "confirmed_quantity": cells[2],
                "display_only_average_cost": cells[3],
                "holding_status": cells[4],
                "holding_evidence_date": cells[5],
            }
        )
    return rows


def build_decisions(
    candidate_rows: Iterable[Mapping[str, Any]],
    holding_rows: Iterable[Mapping[str, Any]] = (),
) -> list[dict[str, Any]]:
    candidates = {_code(row.get("code")): dict(row) for row in candidate_rows if _code(row.get("code"))}
    holdings = {_code(row.get("code")): dict(row) for row in holding_rows if _code(row.get("code"))}
    result: list[dict[str, Any]] = []
    for code in sorted(set(candidates) | set(holdings)):
        candidate = candidates.get(code, {})
        holding = holdings.get(code, {})
        merged = {**candidate, **{key: value for key, value in holding.items() if str(value or "").strip()}}
        merged["code"] = code
        merged["v32_has_position"] = bool(holding)
        payload = production_payload(merged)
        if not holding and merged.get("production_model_version") == PRODUCTION_MODEL_VERSION:
            for key in tuple(payload):
                if str(merged.get(key) or "").strip():
                    payload[key] = merged[key]
        action = payload["production_action"]
        if action not in ALLOWED_ACTIONS:
            raise ValueError(f"unsupported production action: {action}")
        result.append(
            {
                "code": code,
                "stock_name": merged.get("stock_name") or merged.get("name") or "",
                "decision_scope": "HOLDING" if holding else "CANDIDATE",
                **payload,
                "hard_gate_failures": merged.get("v31_hard_gate_failures") or "",
                "hard_gate_unknowns": merged.get("v31_hard_gate_unknowns") or "",
                "source_normalized_earnings": merged.get("v31_normalized_profit") or "",
                "source_realistic_growth": merged.get("v31_realistic_profit_cagr") or "",
                "source_market_implied_growth": merged.get("v31_market_implied_profit_cagr") or "",
                "source_expectation_gap": merged.get("v31_expectation_gap_pct") or "",
                "source_neutral_value": merged.get("v31_neutral_value") or "",
                "source_current_price": merged.get("v31_current_price") or merged.get("raw_latest_close") or "",
                "confirmed_quantity": holding.get("confirmed_quantity") or "",
                "display_only_average_cost": holding.get("display_only_average_cost") or "",
                "holding_evidence_date": holding.get("holding_evidence_date") or "",
                "cost_basis_used_by_decision": False,
                "no_auto_trade": True,
            }
        )
    return result


def write_reports(
    candidate_csv: Path,
    output_dir: Path,
    *,
    holdings_md: Path | None = None,
) -> list[dict[str, Any]]:
    rows = build_decisions(
        _read_csv(candidate_csv),
        read_holdings_markdown(holdings_md) if holdings_md else (),
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    preferred = [
        "code", "stock_name", "decision_scope", "production_model_version",
        "production_model_name", "production_promotion_decision", "production_sell_contract",
        "production_action", "production_target_position_fraction", "valuation_confidence",
        "valuation_confidence_reason_codes", "reason_codes", "normalized_earnings",
        "realistic_growth", "market_implied_growth", "expectation_gap", "neutral_value",
        "current_price", "price_to_neutral", "hard_gate_failures", "hard_gate_unknowns",
        "confirmed_quantity", "display_only_average_cost", "holding_evidence_date",
        "cost_basis_used_by_decision", "production_model_frozen", "no_auto_trade",
    ]
    extras = sorted({key for row in rows for key in row if key not in preferred})
    with (output_dir / "production_decisions.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=preferred + extras, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "production_model": PRODUCTION_MODEL_NAME,
        "row_count": len(rows),
        "candidate_count": sum(row["decision_scope"] == "CANDIDATE" for row in rows),
        "holding_count": sum(row["decision_scope"] == "HOLDING" for row in rows),
        "action_counts": {
            action: sum(row["production_action"] == action for row in rows)
            for action in sorted(ALLOWED_ACTIONS)
        },
        "cost_basis_used_by_decision": False,
        "no_auto_trade": True,
    }
    (output_dir / "production_decision_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = [
        f"# {PRODUCTION_MODEL_NAME} Decision Scan",
        "",
        "Manual execution only. Personal cost basis is displayed for reconciliation and never used by the decision.",
        "",
    ]
    for row in rows:
        lines.extend(
            [
                f"## {row['code']} {row['stock_name']} - {row['production_action']}",
                f"- scope: {row['decision_scope']}",
                f"- valuation confidence: {row['valuation_confidence']}",
                f"- price / neutral: {row['price_to_neutral']}",
                f"- reason codes: {row['reason_codes']}",
                "",
            ]
        )
    (output_dir / "production_decisions.md").write_text("\n".join(lines), encoding="utf-8")
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-csv", type=Path, required=True)
    parser.add_argument("--holdings-md", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    rows = write_reports(args.candidate_csv, args.output_dir, holdings_md=args.holdings_md)
    print(f"production_decisions={args.output_dir};count={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
