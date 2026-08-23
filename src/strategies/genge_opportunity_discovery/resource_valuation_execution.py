"""Execute finite-life resource NAV for routed resource owners.

The executor is deliberately evidence-gated.  It never invents reserves,
commodity prices, costs, ownership, tax, royalties or discount rates.  A company
must have an as-of-safe entry in ``config/resource_asset_inputs.yaml``.  When
complete inputs exist, four scenario decks (extreme_stress/bear/base/bull) are
valued with the existing finite-life resource model and bridged to common equity.
Missing inputs remain INPUTS_REQUIRED and can never create a Formal BUY.
"""
from __future__ import annotations

import argparse
import csv
import json
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml

from src.strategies.genge_opportunity_discovery.resource_asset_valuation import (
    bridge_resource_equity_nav,
    value_finite_life_resource_asset,
)

DISCLAIMER = "仅用于公开数据研究排序和人工复核，不构成买入或卖出建议，不应自动交易。"
RESOURCE_STRATEGY_ID = "resource_asset_nav"
SCENARIOS = ("extreme_stress", "bear", "base", "bull")
DEFAULT_CONFIG = Path("config/resource_asset_inputs.yaml")

OUTPUT_COLUMNS = [
    "resource_nav_executed", "resource_nav_status", "resource_nav_input_as_of",
    "resource_nav_evidence_urls", "resource_nav_extreme_stress_value",
    "resource_nav_bear_value", "resource_nav_base_value", "resource_nav_bull_value",
    "resource_nav_extreme_stress_per_share", "resource_nav_bear_per_share",
    "resource_nav_base_per_share", "resource_nav_bull_per_share",
    "resource_nav_base_margin_of_safety", "resource_nav_next_action",
]


def _code(value: Any) -> str:
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


def _load_config(path: Path) -> dict[str, Mapping[str, Any]]:
    if not path.exists():
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    companies = payload.get("companies") or {}
    if not isinstance(companies, Mapping):
        raise ValueError("resource_asset_inputs.companies must be a mapping")
    return {_code(key): value for key, value in companies.items() if _code(key) and isinstance(value, Mapping)}


def _as_of_safe(company: Mapping[str, Any], *, as_of: date) -> tuple[bool, str]:
    raw = str(company.get("input_as_of") or "").strip()
    if not raw:
        return False, "RESOURCE_INPUT_AS_OF_REQUIRED"
    try:
        input_as_of = date.fromisoformat(raw)
    except ValueError:
        return False, "RESOURCE_INPUT_AS_OF_INVALID"
    if input_as_of > as_of:
        return False, "RESOURCE_INPUT_FROM_FUTURE"
    review_after = str(company.get("review_after") or "").strip()
    if review_after:
        try:
            if as_of > date.fromisoformat(review_after):
                return False, "RESOURCE_INPUT_STALE"
        except ValueError:
            return False, "RESOURCE_REVIEW_AFTER_INVALID"
    return True, "OK"


def _scenario_value(company: Mapping[str, Any], scenario_name: str, *, current_market_cap: Any) -> tuple[Any, list[str]]:
    scenarios = company.get("scenarios") or {}
    scenario = scenarios.get(scenario_name) if isinstance(scenarios, Mapping) else None
    if not isinstance(scenario, Mapping):
        return None, [f"scenario_missing:{scenario_name}"]

    assets_raw = scenario.get("assets") or []
    if not isinstance(assets_raw, list) or not assets_raw:
        return None, [f"assets_missing:{scenario_name}"]

    asset_results = []
    errors: list[str] = []
    for index, raw in enumerate(assets_raw):
        if not isinstance(raw, Mapping):
            errors.append(f"asset_invalid:{scenario_name}:{index}")
            continue
        result = value_finite_life_resource_asset(
            asset_id=raw.get("asset_id"),
            economic_scope_id=raw.get("economic_scope_id"),
            economic_ownership=raw.get("economic_ownership"),
            recoverable_units_100pct=raw.get("recoverable_units_100pct"),
            annual_production_units_100pct=raw.get("annual_production_units_100pct"),
            normalized_realized_unit_price=raw.get("normalized_realized_unit_price"),
            unit_cash_operating_cost=raw.get("unit_cash_operating_cost"),
            sustaining_capex_per_unit=raw.get("sustaining_capex_per_unit"),
            royalty_rate_on_revenue=raw.get("royalty_rate_on_revenue"),
            cash_tax_rate_on_positive_pretax_cash_flow=raw.get("cash_tax_rate_on_positive_pretax_cash_flow"),
            required_return=raw.get("required_return"),
            closure_and_reclamation_cash_outflow_100pct=raw.get("closure_and_reclamation_cash_outflow_100pct", 0.0),
        )
        asset_results.append(result)
        if result.status != "OK":
            errors.append(f"{scenario_name}:{result.asset_id or index}:{result.status}")

    bridge = scenario.get("equity_bridge") or {}
    if not isinstance(bridge, Mapping):
        return None, errors + [f"equity_bridge_invalid:{scenario_name}"]
    equity = bridge_resource_equity_nav(
        resource_asset_results=asset_results,
        non_resource_segment_value=bridge.get("non_resource_segment_value"),
        unrestricted_cash=bridge.get("unrestricted_cash"),
        interest_bearing_debt_not_in_resource_cash_flows=bridge.get("interest_bearing_debt_not_in_resource_cash_flows"),
        other_corporate_liability_pv_not_in_resource_cash_flows=bridge.get("other_corporate_liability_pv_not_in_resource_cash_flows"),
        explicit_equity_adjustment=bridge.get("explicit_equity_adjustment", 0.0),
        current_market_cap=current_market_cap,
        total_common_shares=bridge.get("total_common_shares"),
    )
    if equity.status != "OK":
        errors.append(f"{scenario_name}:bridge:{equity.status}")
    return equity, errors


def execute_rows(rows: Iterable[Mapping[str, Any]], *, as_of: date, config_path: Path = DEFAULT_CONFIG) -> list[dict[str, Any]]:
    configs = _load_config(config_path)
    output: list[dict[str, Any]] = []
    for raw in rows:
        row = dict(raw)
        for column in OUTPUT_COLUMNS:
            row[column] = ""
        row.update({"resource_nav_executed": False, "formal_signal_eligible": False,
                    "automatic_promotion_allowed": False, "no_auto_trade": True, "disclaimer": DISCLAIMER})
        if str(row.get("valuation_primary_strategy_id") or "") != RESOURCE_STRATEGY_ID:
            row["resource_nav_status"] = "NOT_RESOURCE_ROUTE"
            output.append(row)
            continue

        code = _code(row.get("code"))
        company = configs.get(code)
        if company is None:
            row.update({"resource_nav_status": "RESOURCE_INPUTS_REQUIRED",
                        "resource_nav_next_action": "collect_reserves_production_cost_ownership_and_four_scenario_price_decks"})
            output.append(row)
            continue
        safe, status = _as_of_safe(company, as_of=as_of)
        row["resource_nav_input_as_of"] = company.get("input_as_of") or ""
        urls = company.get("evidence_urls") or []
        row["resource_nav_evidence_urls"] = ";".join(str(x) for x in urls) if isinstance(urls, list) else str(urls)
        if not safe:
            row.update({"resource_nav_status": status, "resource_nav_next_action": "refresh_resource_asset_evidence"})
            output.append(row)
            continue

        results: dict[str, Any] = {}
        errors: list[str] = []
        current_market_cap = row.get("current_market_cap") or company.get("current_market_cap")
        for name in SCENARIOS:
            result, scenario_errors = _scenario_value(company, name, current_market_cap=current_market_cap)
            results[name] = result
            errors.extend(scenario_errors)
        if errors or any(results[name] is None or not results[name].valuation_model_applicable for name in SCENARIOS):
            row.update({"resource_nav_status": "RESOURCE_SCENARIO_INPUTS_INCOMPLETE",
                        "resource_nav_next_action": ";".join(errors[:20])})
            output.append(row)
            continue

        for name in SCENARIOS:
            result = results[name]
            row[f"resource_nav_{name}_value"] = result.fair_equity_nav
            row[f"resource_nav_{name}_per_share"] = result.fair_nav_per_share
        row["resource_nav_base_margin_of_safety"] = results["base"].margin_of_safety
        row.update({"resource_nav_executed": True, "resource_nav_status": "OK",
                    "resource_nav_next_action": "map_four_scenario_nav_into_v31_deep_review"})
        output.append(row)
    return output


def _latest_dir(root: Path) -> Path:
    if (root / "valuation_research_routed.csv").exists():
        return root
    candidates = sorted(p.parent for p in root.glob("**/valuation_research_routed.csv") if p.is_file())
    if not candidates:
        raise FileNotFoundError(f"no valuation_research_routed.csv under {root}")
    return candidates[-1]


def write_report(report_root: Path, *, config_path: Path = DEFAULT_CONFIG) -> list[dict[str, Any]]:
    report_dir = _latest_dir(report_root)
    with (report_dir / "valuation_research_routed.csv").open(encoding="utf-8") as stream:
        reader = csv.DictReader(stream); source_fields = list(reader.fieldnames or []); source_rows = list(reader)
    summary_path = report_dir / "valuation_research_summary.json"
    summary_payload = json.loads(summary_path.read_text(encoding="utf-8"))
    as_of = date.fromisoformat(str(summary_payload["as_of_date"]))
    rows = execute_rows(source_rows, as_of=as_of, config_path=config_path)
    fields = source_fields + [x for x in OUTPUT_COLUMNS if x not in source_fields]
    out = report_dir / "valuation_research_resource_nav.csv"
    with out.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore"); writer.writeheader(); writer.writerows(rows)
    summary = {
        "as_of_date": as_of.isoformat(), "row_count": len(rows),
        "resource_route_count": sum(r.get("resource_nav_status") != "NOT_RESOURCE_ROUTE" for r in rows),
        "resource_nav_executed_count": sum(bool(r.get("resource_nav_executed")) for r in rows),
        "inputs_required_count": sum(r.get("resource_nav_status") in {"RESOURCE_INPUTS_REQUIRED", "RESOURCE_SCENARIO_INPUTS_INCOMPLETE"} for r in rows),
        "formal_signal_eligible": False, "automatic_promotion_allowed": False, "no_auto_trade": True,
    }
    (report_dir / "resource_valuation_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-root", type=Path, required=True)
    parser.add_argument("--input-config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args(argv)
    rows = write_report(args.report_root, config_path=args.input_config)
    print(f"resource_valuation_execution={args.report_root};count={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
