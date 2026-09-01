"""Execute PIT-safe insurance embedded-value reverse appraisal research.

Reviewed EV/NBV disclosures are combined with point-in-time market capitalization
to measure current P/EV and the market-implied NBV franchise multiple.  The
module publishes evidence/model/anchor/completion states explicitly.  It never
invents a fair franchise multiple and never creates Formal BUY eligibility.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping

import pandas as pd

from src.strategies.genge_cycle_bottom.fundamentals import PublicFundamentalLoader
from src.strategies.genge_opportunity_discovery.insurance_embedded_value_inputs import (
    InsuranceEmbeddedValueInputRepository,
    load_insurance_embedded_value_input_repository,
)
from src.strategies.genge_opportunity_discovery.insurance_valuation import (
    reverse_implied_nbv_franchise_multiple,
)

DISCLAIMER = "仅用于公开数据研究排序和人工复核，不构成买入或卖出建议，不应自动交易。"
INSURANCE_STRATEGY_ID = "insurance_embedded_value"
MARKET_CAP_INPUT_BASIS = "AKSHARE_BAIDU_TOTAL_MARKET_CAP_CNY_100M_X100_TO_CNY_MILLION"
INSURANCE_CACHE_NAMESPACE = "insurance_execution_v1"

OUTPUT_COLUMNS = [
    "insurance_model_executed",
    "insurance_model_execution_state",
    "insurance_model_status",
    "insurance_model_execution_reason",
    "insurance_input_id",
    "insurance_input_known_at",
    "insurance_input_evidence_as_of",
    "insurance_input_report_year",
    "insurance_evidence_status",
    "insurance_evidence_freshness_days",
    "insurance_evidence_max_age_days",
    "insurance_evidence_source_name",
    "insurance_evidence_source_url",
    "insurance_evidence_refs",
    "insurance_embedded_value_cny_million",
    "insurance_embedded_value_per_share",
    "insurance_normalized_annual_nbv_cny_million",
    "insurance_embedded_value_scope",
    "insurance_nbv_scope",
    "insurance_market_cap_raw_cny_100m",
    "insurance_market_cap_cny_million",
    "insurance_market_cap_date",
    "insurance_market_cap_provider",
    "insurance_market_cap_input_basis",
    "insurance_current_p_ev",
    "insurance_reference_discount_to_ev",
    "insurance_implied_nbv_franchise_multiple",
    "insurance_model_next_action",
    "insurance_model_formal_buy_eligible",
    "valuation_evidence_status",
    "valuation_model_status",
    "valuation_anchor_status",
    "valuation_completion_status",
    "valuation_reference_anchor_kind",
    "valuation_reference_anchor_cny_million",
    "valuation_reference_anchor_per_share",
]


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


def _latest_market_cap(frame: pd.DataFrame | None, *, as_of: date) -> tuple[float | None, str]:
    if frame is None or frame.empty or "date" not in frame.columns or "market_cap" not in frame.columns:
        return None, ""
    local = frame[["date", "market_cap"]].copy()
    local["date"] = pd.to_datetime(local["date"], errors="coerce").dt.date
    local["market_cap"] = pd.to_numeric(local["market_cap"], errors="coerce")
    local = local.dropna(subset=["date", "market_cap"])
    local = local[(local["date"] <= as_of) & (local["market_cap"] > 0)]
    if local.empty:
        return None, ""
    latest = local.sort_values("date").iloc[-1]
    return float(latest["market_cap"]), latest["date"].isoformat()


def _locked_base(row: Mapping[str, Any]) -> dict[str, Any]:
    output = dict(row)
    defaults = {column: "" for column in OUTPUT_COLUMNS}
    defaults.update(
        {
            "insurance_model_executed": False,
            "insurance_model_execution_state": "NOT_INSURANCE_ROUTE",
            "insurance_model_formal_buy_eligible": False,
            "valuation_evidence_status": "NOT_APPLICABLE",
            "valuation_model_status": "NOT_APPLICABLE",
            "valuation_anchor_status": "NOT_APPLICABLE",
            "valuation_completion_status": "NOT_APPLICABLE",
            "formal_signal_eligible": False,
            "automatic_promotion_allowed": False,
            "no_auto_trade": True,
            "disclaimer": DISCLAIMER,
        }
    )
    output.update(defaults)
    return output


def _apply_evidence(row: dict[str, Any], resolution, *, as_of: date) -> None:
    row["insurance_evidence_status"] = resolution.evidence_status
    row["valuation_evidence_status"] = resolution.evidence_status
    item = resolution.input
    if item is None:
        return
    row.update(
        {
            "insurance_input_id": item.input_id,
            "insurance_input_known_at": item.known_at.isoformat(),
            "insurance_input_evidence_as_of": item.evidence_as_of.isoformat(),
            "insurance_input_report_year": item.report_year,
            "insurance_evidence_freshness_days": item.freshness_days(as_of),
            "insurance_evidence_max_age_days": item.max_age_days,
            "insurance_evidence_source_name": item.source_name,
            "insurance_evidence_source_url": item.source_url,
            "insurance_evidence_refs": ";".join(item.evidence_refs),
            "insurance_embedded_value_cny_million": item.embedded_value,
            "insurance_embedded_value_per_share": (
                "" if item.embedded_value_per_share is None else item.embedded_value_per_share
            ),
            "insurance_normalized_annual_nbv_cny_million": item.normalized_annual_nbv,
            "insurance_embedded_value_scope": item.embedded_value_scope,
            "insurance_nbv_scope": item.nbv_scope,
            "valuation_anchor_status": "REFERENCE_AVAILABLE",
            "valuation_reference_anchor_kind": "DISCLOSED_EMBEDDED_VALUE",
            "valuation_reference_anchor_cny_million": item.embedded_value,
            "valuation_reference_anchor_per_share": (
                "" if item.embedded_value_per_share is None else item.embedded_value_per_share
            ),
        }
    )


def execute_insurance_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    as_of: date,
    loader: PublicFundamentalLoader,
    input_repository: InsuranceEmbeddedValueInputRepository,
    years: int = 3,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for raw in rows:
        row = _locked_base(raw)
        if str(row.get("valuation_primary_strategy_id") or "").strip() != INSURANCE_STRATEGY_ID:
            result.append(row)
            continue

        code = _normalize_code(row.get("code"))
        resolution = input_repository.resolve(code, as_of=as_of)
        _apply_evidence(row, resolution, as_of=as_of)
        if not resolution.execution_eligible or resolution.input is None:
            status = f"DISCLOSED_EV_NBV_INPUTS_{resolution.status}"
            row.update(
                {
                    "insurance_model_execution_state": "INSURANCE_MODEL_SELECTED_INPUTS_REQUIRED",
                    "insurance_model_status": status,
                    "insurance_model_execution_reason": status,
                    "insurance_model_next_action": (
                        "refresh_point_in_time_annual_ev_nbv_disclosure"
                        if resolution.status == "STALE"
                        else "collect_point_in_time_annual_ev_nbv_disclosure"
                    ),
                    "valuation_model_status": "NOT_EXECUTED",
                    "valuation_anchor_status": (
                        "REFERENCE_AVAILABLE" if resolution.input is not None else "UNAVAILABLE"
                    ),
                    "valuation_completion_status": "UNFINISHED",
                }
            )
            result.append(row)
            continue

        item = resolution.input
        try:
            frame, provider, errors, _ = loader.load_valuation(code, years=max(1, int(years)))
        except Exception as exc:
            row.update(
                {
                    "insurance_model_execution_state": "INSURANCE_MODEL_SELECTED_INPUTS_REQUIRED",
                    "insurance_model_status": "PUBLIC_MARKET_CAP_LOAD_FAILED",
                    "insurance_model_execution_reason": type(exc).__name__,
                    "insurance_model_next_action": "retry_point_in_time_market_cap_without_promoting_model_state",
                    "valuation_model_status": "NOT_EXECUTED",
                    "valuation_completion_status": "UNFINISHED",
                }
            )
            result.append(row)
            continue

        market_cap_raw, market_cap_date = _latest_market_cap(frame, as_of=as_of)
        if market_cap_raw is None:
            row.update(
                {
                    "insurance_model_execution_state": "INSURANCE_MODEL_SELECTED_INPUTS_REQUIRED",
                    "insurance_model_status": "POINT_IN_TIME_MARKET_CAP_UNAVAILABLE",
                    "insurance_model_execution_reason": ";".join(errors or []),
                    "insurance_model_next_action": "collect_point_in_time_total_market_cap",
                    "valuation_model_status": "NOT_EXECUTED",
                    "valuation_completion_status": "UNFINISHED",
                }
            )
            result.append(row)
            continue

        market_cap_cny_million = market_cap_raw * 100.0
        implied_multiple, status = reverse_implied_nbv_franchise_multiple(
            current_market_cap=market_cap_cny_million,
            embedded_value=item.embedded_value,
            normalized_annual_nbv=item.normalized_annual_nbv,
        )
        if status != "OK" or implied_multiple is None:
            row.update(
                {
                    "insurance_model_execution_state": "INSURANCE_MODEL_EXECUTED_FAIL_CLOSED",
                    "insurance_model_executed": True,
                    "insurance_model_status": status,
                    "insurance_model_execution_reason": status,
                    "insurance_model_next_action": "review_ev_nbv_market_cap_scope_and_units",
                    "insurance_market_cap_raw_cny_100m": market_cap_raw,
                    "insurance_market_cap_cny_million": market_cap_cny_million,
                    "insurance_market_cap_date": market_cap_date,
                    "insurance_market_cap_provider": provider,
                    "insurance_market_cap_input_basis": MARKET_CAP_INPUT_BASIS,
                    "valuation_model_status": "EXECUTED",
                    "valuation_completion_status": "COMPLETED_WITH_REFERENCE_ANCHOR",
                }
            )
            result.append(row)
            continue

        p_ev = market_cap_cny_million / item.embedded_value
        row.update(
            {
                "insurance_model_executed": True,
                "insurance_model_execution_state": "INSURANCE_MODEL_EXECUTED_RESEARCH_ONLY",
                "insurance_model_status": "OK",
                "insurance_model_execution_reason": "reverse_market_implied_nbv_franchise_multiple_only",
                "insurance_market_cap_raw_cny_100m": market_cap_raw,
                "insurance_market_cap_cny_million": market_cap_cny_million,
                "insurance_market_cap_date": market_cap_date,
                "insurance_market_cap_provider": provider,
                "insurance_market_cap_input_basis": MARKET_CAP_INPUT_BASIS,
                "insurance_current_p_ev": p_ev,
                "insurance_reference_discount_to_ev": 1.0 - p_ev,
                "insurance_implied_nbv_franchise_multiple": implied_multiple,
                "insurance_model_next_action": "review_market_implied_nbv_franchise_value_before_any_formal_decision",
                "valuation_model_status": "EXECUTED",
                "valuation_anchor_status": "REFERENCE_AVAILABLE",
                "valuation_completion_status": "COMPLETED_WITH_REFERENCE_ANCHOR",
            }
        )
        result.append(row)
    return result


def _latest_report_dir(report_root: Path) -> Path:
    if (report_root / "valuation_research_routed.csv").exists():
        return report_root
    candidates = sorted(
        {path.parent for path in report_root.glob("**/valuation_research_routed.csv") if path.is_file()},
        key=str,
    )
    if not candidates:
        raise FileNotFoundError(f"no valuation_research_routed.csv under {report_root}")
    return candidates[-1]


def _read_as_of(report_dir: Path) -> date:
    payload = json.loads((report_dir / "valuation_research_summary.json").read_text(encoding="utf-8"))
    value = str(payload.get("as_of_date") or "").strip()
    if not value:
        raise ValueError("valuation research as_of_date is unavailable")
    return date.fromisoformat(value)


def _write_csv(path: Path, rows: list[dict[str, Any]], source_fields: list[str]) -> None:
    fields = list(source_fields)
    for field in OUTPUT_COLUMNS:
        if field not in fields:
            fields.append(field)
    for field in ("formal_signal_eligible", "automatic_promotion_allowed", "no_auto_trade", "disclaimer"):
        if field not in fields:
            fields.append(field)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_insurance_execution_sidecar(
    report_root: Path,
    *,
    input_config: Path = Path("config/insurance_embedded_value_inputs.yaml"),
    cache_dir: Path = Path("data/cache/valuation_research_fundamentals"),
    years: int = 3,
    loader: PublicFundamentalLoader | None = None,
) -> dict[str, Any]:
    report_dir = _latest_report_dir(report_root)
    with (report_dir / "valuation_research_routed.csv").open(encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        source_fields = list(reader.fieldnames or [])
        source_rows = list(reader)
    as_of = _read_as_of(report_dir)
    repository = load_insurance_embedded_value_input_repository(input_config)
    dedicated_cache = cache_dir if cache_dir.name == INSURANCE_CACHE_NAMESPACE else cache_dir / INSURANCE_CACHE_NAMESPACE
    effective_loader = loader or PublicFundamentalLoader(cache_dir=dedicated_cache)
    executed = execute_insurance_rows(
        source_rows,
        as_of=as_of,
        loader=effective_loader,
        input_repository=repository,
        years=years,
    )
    _write_csv(report_dir / "insurance_valuation_execution.csv", executed, source_fields)

    insurance_rows = [
        row for row in executed
        if str(row.get("valuation_primary_strategy_id") or "") == INSURANCE_STRATEGY_ID
    ]
    summary = {
        "as_of_date": as_of.isoformat(),
        "row_count": len(executed),
        "insurance_selected_count": len(insurance_rows),
        "insurance_executed_count": sum(bool(row.get("insurance_model_executed")) for row in insurance_rows),
        "insurance_input_required_count": sum(
            row.get("valuation_completion_status") == "UNFINISHED" for row in insurance_rows
        ),
        "insurance_completed_with_anchor_count": sum(
            row.get("valuation_completion_status") == "COMPLETED_WITH_REFERENCE_ANCHOR"
            for row in insurance_rows
        ),
        "insurance_stale_evidence_count": sum(
            row.get("valuation_evidence_status") == "STALE" for row in insurance_rows
        ),
        "market_cap_input_basis": MARKET_CAP_INPUT_BASIS,
        "cache_namespace": INSURANCE_CACHE_NAMESPACE,
        "ranking_changed": False,
        "formal_buy_consumes_insurance_sidecar": False,
        "formal_signal_eligible": False,
        "automatic_promotion_allowed": False,
        "no_auto_trade": True,
        "disclaimer": DISCLAIMER,
    }
    (report_dir / "insurance_valuation_execution_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = [
        "# Insurance Reverse Appraisal Execution", "", DISCLAIMER, "",
        f"- as_of_date: {as_of.isoformat()}",
        f"- insurance_selected_count: {summary['insurance_selected_count']}",
        f"- insurance_executed_count: {summary['insurance_executed_count']}",
        f"- insurance_input_required_count: {summary['insurance_input_required_count']}",
        f"- insurance_completed_with_anchor_count: {summary['insurance_completed_with_anchor_count']}",
        "- fair_value_published: False", "- no_auto_trade: True", "",
    ]
    for row in insurance_rows:
        lines.extend([
            f"## {row.get('valuation_research_rank')}. {row.get('code')} {row.get('stock_name')}",
            f"- evidence: {row.get('valuation_evidence_status')} ({row.get('insurance_evidence_source_name')})",
            f"- model: {row.get('valuation_model_status')} / {row.get('insurance_model_status')}",
            f"- completion: {row.get('valuation_completion_status')}",
            f"- anchor: {row.get('valuation_anchor_status')} / {row.get('valuation_reference_anchor_per_share')}",
            f"- EV (CNYm): {row.get('insurance_embedded_value_cny_million')}",
            f"- annual NBV (CNYm): {row.get('insurance_normalized_annual_nbv_cny_million')}",
            f"- current P/EV: {row.get('insurance_current_p_ev')}",
            f"- implied NBV franchise multiple: {row.get('insurance_implied_nbv_franchise_multiple')}", "",
        ])
    (report_dir / "insurance_valuation_execution.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-root", type=Path, required=True)
    parser.add_argument("--input-config", type=Path, default=Path("config/insurance_embedded_value_inputs.yaml"))
    parser.add_argument("--cache-dir", type=Path, default=Path("data/cache/valuation_research_fundamentals"))
    parser.add_argument("--years", type=int, default=3)
    args = parser.parse_args(argv)
    write_insurance_execution_sidecar(
        args.report_root, input_config=args.input_config, cache_dir=args.cache_dir, years=args.years
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
