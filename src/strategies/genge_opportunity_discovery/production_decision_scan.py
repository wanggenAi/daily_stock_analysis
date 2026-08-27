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
    PRODUCTION_POLICY_SOURCE,
    production_payload,
)
from .selection_framework_v31 import execution_universe_status


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


def _candidate_policy_matches_production(candidate: Mapping[str, Any]) -> bool:
    """Report whether upstream claims the same frozen policy.

    This is audit metadata only. Production-owned decision fields are always
    recomputed by ``production_payload`` and are never reused from artifacts.
    """
    return bool(
        str(candidate.get("production_model_version") or "").strip() == PRODUCTION_MODEL_VERSION
        and str(candidate.get("production_policy_source") or "").strip() == PRODUCTION_POLICY_SOURCE
    )


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
        if not holding and execution_universe_status(code) != "EXECUTION_ELIGIBLE":
            continue
        merged = {**candidate, **{key: value for key, value in holding.items() if str(value or "").strip()}}
        merged["code"] = code
        merged["v311_has_position"] = bool(holding)
        # Kept only as an input alias for older upstream payloads; V3.1.1 does
        # not depend on V3.2 policy or SELL confirmation.
        merged["v32_has_position"] = bool(holding)

        # Authority boundary: artifacts may supply raw/derived inputs, but every
        # production-owned gate/decision field is generated fresh here. Never
        # copy production_payload keys back from an upstream CSV, even when its
        # version/policy labels match, because labels do not prove freshness or
        # provenance and stale/tampered artifacts must not control live output.
        payload = production_payload(merged)
        upstream_policy_matches = bool(not holding and _candidate_policy_matches_production(candidate))
        strict_pit_status = str(merged.get("v311_expectation_input_status") or "").strip()

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
                # Keep strict-PIT provenance visible all the way to the final
                # production CSV so canonical/hourly/daily consumers can audit
                # which filing period and availability date actually drove the
                # action instead of merely trusting a fresh run timestamp.
                "strict_pit_refresh_applied": bool(strict_pit_status),
                "v311_expectation_input_status": strict_pit_status,
                "decision_date": merged.get("decision_date") or "",
                "price_date": merged.get("price_date") or "",
                "fund_available_date": merged.get("fund_available_date") or "",
                "financial_report_date": merged.get("financial_report_date") or "",
                "current_price_source": merged.get("current_price_source") or "",
                "v311_input_error": merged.get("v311_input_error") or "",
                "v311_production_bridge": merged.get("v311_production_bridge") or "",
                "v311_same_run_evidence_joined": merged.get("v311_same_run_evidence_joined") or False,
                "v311_source_scope": merged.get("v311_source_scope") or "",
                "upstream_policy_reused": False,
                "upstream_policy_matches": upstream_policy_matches,
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
    """Low-level renderer for already-authoritative V3.1.1 production inputs.

    Scheduled/CLI callers must enter through :mod:`v311_production_bridge`,
    which refreshes strict point-in-time expectation inputs before this function
    recomputes the frozen production gate and action.
    """
    candidate_rows = _read_csv(candidate_csv)
    holding_rows = read_holdings_markdown(holdings_md) if holdings_md else []
    holding_codes = {_code(row.get("code")) for row in holding_rows}
    rows = build_decisions(candidate_rows, holding_rows)
    output_dir.mkdir(parents=True, exist_ok=True)
    preferred = [
        "code", "stock_name", "decision_scope", "production_model_version",
        "production_model_name", "production_promotion_decision", "production_sell_contract",
        "production_policy_source", "v32_sell_confirmation_enabled", "production_action",
        "production_target_position_fraction", "valuation_confidence",
        "valuation_confidence_reason_codes", "reason_codes", "normalized_earnings",
        "realistic_growth", "market_implied_growth", "expectation_gap", "neutral_value",
        "current_price", "price_to_neutral", "hard_gate_failures", "hard_gate_unknowns",
        "strict_pit_refresh_applied", "v311_expectation_input_status", "decision_date",
        "price_date", "fund_available_date", "financial_report_date", "current_price_source",
        "v311_input_error", "v311_production_bridge", "v311_same_run_evidence_joined",
        "v311_source_scope", "upstream_policy_reused", "upstream_policy_matches",
        "confirmed_quantity", "display_only_average_cost", "holding_evidence_date",
        "cost_basis_used_by_decision", "production_model_frozen", "no_auto_trade",
    ]
    extras = sorted({key for row in rows for key in row if key not in preferred})
    with (output_dir / "production_decisions.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=preferred + extras, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    strict_pit_count = sum(bool(row["strict_pit_refresh_applied"]) for row in rows)
    summary = {
        "production_model": PRODUCTION_MODEL_NAME,
        "production_model_version": PRODUCTION_MODEL_VERSION,
        "production_policy_source": PRODUCTION_POLICY_SOURCE,
        "row_count": len(rows),
        "candidate_count": sum(row["decision_scope"] == "CANDIDATE" for row in rows),
        "holding_count": sum(row["decision_scope"] == "HOLDING" for row in rows),
        "research_only_candidates_excluded": sum(
            bool(_code(row.get("code")))
            and _code(row.get("code")) not in holding_codes
            and execution_universe_status(row.get("code")) != "EXECUTION_ELIGIBLE"
            for row in candidate_rows
        ),
        "upstream_policy_reused_count": 0,
        "upstream_policy_match_count": sum(bool(row["upstream_policy_matches"]) for row in rows),
        "strict_pit_refresh_applied_count": strict_pit_count,
        "strict_pit_refresh_complete": bool(rows) and strict_pit_count == len(rows),
        "financial_report_dates": sorted(
            {str(row.get("financial_report_date") or "") for row in rows if row.get("financial_report_date")}
        ),
        "action_counts": {
            action: sum(row["production_action"] == action for row in rows)
            for action in sorted(ALLOWED_ACTIONS)
        },
        "cost_basis_used_by_decision": False,
        "v32_sell_confirmation_enabled": False,
        "fresh_production_decision_authority": True,
        "no_auto_trade": True,
    }
    (output_dir / "production_decision_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = [
        f"# {PRODUCTION_MODEL_NAME} Decision Scan",
        "",
        "Manual execution only. Personal cost basis is displayed for reconciliation and never used by the decision.",
        f"Frozen policy source: `{PRODUCTION_POLICY_SOURCE}`.",
        "Production gate and action are recomputed fresh; upstream decision fields are never reused.",
        "",
    ]
    for row in rows:
        lines.extend(
            [
                f"## {row['code']} {row['stock_name']} - {row['production_action']}",
                f"- scope: {row['decision_scope']}",
                f"- valuation confidence: {row['valuation_confidence']}",
                f"- strict-PIT input: {row['v311_expectation_input_status']}",
                f"- financial report / available: {row['financial_report_date']} / {row['fund_available_date']}",
                f"- price date / source: {row['price_date']} / {row['current_price_source']}",
                f"- price / neutral: {row['price_to_neutral']}",
                f"- reason codes: {row['reason_codes']}",
                f"- upstream exact-policy label matches: {row['upstream_policy_matches']}",
                "- upstream decision reused: False",
                "",
            ]
        )
    (output_dir / "production_decisions.md").write_text("\n".join(lines), encoding="utf-8")
    return rows


def main(argv: list[str] | None = None) -> int:
    """Compatibility CLI that cannot bypass the strict-PIT production bridge."""
    parser = argparse.ArgumentParser(
        description="Legacy alias; authoritative execution is delegated to v311_production_bridge."
    )
    parser.add_argument("--candidate-csv", type=Path, required=True)
    parser.add_argument("--evidence-csv", type=Path)
    parser.add_argument("--codes-csv", type=Path)
    parser.add_argument("--holdings-md", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--as-of")
    args = parser.parse_args(argv)

    # Import lazily to avoid a module-level cycle: the bridge intentionally uses
    # write_reports() above as its final low-level renderer after strict-PIT
    # refresh. Any legacy CLI invocation is therefore forced through the bridge.
    from .v311_production_bridge import main as bridge_main

    bridge_argv = [
        "--source-csv", str(args.candidate_csv),
        "--output-dir", str(args.output_dir),
    ]
    if args.evidence_csv:
        bridge_argv.extend(["--evidence-csv", str(args.evidence_csv)])
    if args.codes_csv:
        bridge_argv.extend(["--codes-csv", str(args.codes_csv)])
    if args.holdings_md:
        bridge_argv.extend(["--holdings-md", str(args.holdings_md)])
    if args.as_of:
        bridge_argv.extend(["--as-of", str(args.as_of)])
    return bridge_main(bridge_argv)


if __name__ == "__main__":
    raise SystemExit(main())
