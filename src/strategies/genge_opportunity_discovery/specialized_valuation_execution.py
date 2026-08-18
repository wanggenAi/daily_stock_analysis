"""Execute specialized valuation models only when auditable inputs are available.

Routing a company to a specialized model is not the same thing as executing the
model.  This sidecar closes that gap conservatively.  The first executable
family is the traditional securities-broker P/B residual-income bridge because
existing public-data infrastructure can provide point-in-time P/B and historical
annual ROE without inventing segment economics, embedded value, normalized FCFE,
or lease-consistent transport debt.

The broker model is executed in normalized book-value units: common BVPS is set
to 1 and current price is set to current P/B.  This is algebraically equivalent
to valuing actual BVPS while avoiding a synthetic share-count/book-value bridge.
The output therefore reports fair P/B, market-implied mid-cycle ROE and P/B-based
margin of safety, not a fabricated per-share fair price.

Annual ROE is deliberately conservative:
* only fiscal-year rows (12-31) are used;
* an actual disclosure date must be on/before the research as-of date, otherwise
  the statutory latest annual-report deadline (April 30 of the next year) must
  have passed;
* provider ROE is treated as percentage points and converted to a ratio / 100;
* at least three annual observations are required by default;
* the median of the most recent bounded history is the mid-cycle normalization.

Other specialized families remain explicitly INPUTS_REQUIRED until their real
model-specific evidence can be sourced.  Nothing in this module creates a
Formal BUY, changes ranking, or enables automatic trading.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping

import pandas as pd

from src.strategies.genge_cycle_bottom.fundamentals import PublicFundamentalLoader
from src.strategies.genge_opportunity_discovery.capital_markets_valuation import (
    value_traditional_broker,
)
from src.strategies.genge_opportunity_discovery.valuation_research_long_term_runner import (
    _statutory_latest_disclosure_date,
)

DISCLAIMER = "仅用于公开数据研究排序和人工复核，不构成买入或卖出建议，不应自动交易。"
CAPITAL_MARKETS_STRATEGY_ID = "capital_markets_cycle"
GENERAL_REVERSE_STRATEGY_ID = "general_reverse_earnings"
DEFAULT_MIN_ANNUAL_ROE_SAMPLES = 3
DEFAULT_MAX_ANNUAL_ROE_SAMPLES = 5
DEFAULT_COST_OF_EQUITY = 0.11
DEFAULT_LONG_TERM_GROWTH = 0.03
ROE_INPUT_BASIS = "AKSHARE_SINA_ROE_PERCENTAGE_POINTS_DIV100"
BROKER_NORMALIZATION_BASIS = "MEDIAN_PIT_SAFE_ANNUAL_ROE"

SPECIALIZED_OUTPUT_COLUMNS = [
    "specialized_model_executed",
    "specialized_model_execution_state",
    "specialized_model_status",
    "specialized_model_execution_reason",
    "specialized_model_input_basis",
    "specialized_model_input_report_years",
    "specialized_model_roe_sample_count",
    "specialized_current_pb",
    "specialized_current_pb_date",
    "specialized_normalized_mid_cycle_roe",
    "specialized_cost_of_equity_assumption",
    "specialized_long_term_growth_assumption",
    "specialized_fair_pb",
    "specialized_implied_mid_cycle_roe",
    "specialized_expectation_gap_roe",
    "specialized_margin_of_safety",
    "specialized_model_next_action",
    "specialized_model_formal_buy_eligible",
]


@dataclass(frozen=True)
class AnnualRoeHistory:
    values: tuple[float, ...]
    years: tuple[int, ...]

    @property
    def median(self) -> float | None:
        return statistics.median(self.values) if self.values else None


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _bool_text(value: bool) -> bool:
    return bool(value)


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


def _date_value(value: Any) -> date | None:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.date()


def _latest_positive_pb(
    frame: pd.DataFrame | None,
    *,
    as_of: date,
) -> tuple[float | None, str]:
    if frame is None or frame.empty or "date" not in frame.columns or "pb" not in frame.columns:
        return None, ""
    local = frame[["date", "pb"]].copy()
    local["date"] = pd.to_datetime(local["date"], errors="coerce").dt.date
    local["pb"] = pd.to_numeric(local["pb"], errors="coerce")
    local = local.dropna(subset=["date", "pb"])
    local = local[(local["date"] <= as_of) & (local["pb"] > 0)]
    if local.empty:
        return None, ""
    latest = local.sort_values("date").iloc[-1]
    return float(latest["pb"]), latest["date"].isoformat()


def _annual_roe_history(
    frame: pd.DataFrame | None,
    *,
    as_of: date,
    max_samples: int = DEFAULT_MAX_ANNUAL_ROE_SAMPLES,
) -> AnnualRoeHistory:
    """Return PIT-safe annual ROE ratios, never quarterly annualizations."""
    if frame is None or frame.empty or "report_date" not in frame.columns or "roe" not in frame.columns:
        return AnnualRoeHistory((), ())

    rows: list[tuple[date, float]] = []
    for raw in frame.to_dict("records"):
        report_date = _date_value(raw.get("report_date"))
        if report_date is None or (report_date.month, report_date.day) != (12, 31):
            continue

        disclosure_date = _date_value(raw.get("disclosure_date"))
        if disclosure_date is not None:
            if disclosure_date > as_of:
                continue
        else:
            safe_date = _statutory_latest_disclosure_date(report_date)
            if safe_date is None or safe_date > as_of:
                continue

        roe_percentage_points = _finite(raw.get("roe"))
        if roe_percentage_points is None:
            continue
        roe_ratio = roe_percentage_points / 100.0
        # Reject obviously corrupt unit/value observations rather than clipping.
        if not math.isfinite(roe_ratio) or abs(roe_ratio) > 2.0:
            continue
        rows.append((report_date, roe_ratio))

    dedup = {report_date: value for report_date, value in rows}
    ordered = sorted(dedup.items())
    if max_samples > 0:
        ordered = ordered[-int(max_samples):]
    return AnnualRoeHistory(
        values=tuple(value for _, value in ordered),
        years=tuple(report_date.year for report_date, _ in ordered),
    )


def _unimplemented_requirement(strategy_id: str) -> tuple[str, str]:
    requirements = {
        "insurance_embedded_value": (
            "DISCLOSED_EV_NBV_INPUTS_REQUIRED",
            "collect_point_in_time_embedded_value_and_new_business_value_disclosures",
        ),
        "transport_cycle": (
            "THROUGH_CYCLE_EBITDA_AND_LEASE_CONSISTENT_NET_DEBT_REQUIRED",
            "collect_through_cycle_ebitda_multiple_and_lease_consistent_net_debt",
        ),
        "yield_asset": (
            "NORMALIZED_FCFE_INPUTS_REQUIRED",
            "separate_maintenance_growth_capex_and_prepare_normalized_fcfe",
        ),
        "bank_residual_income": (
            "BANK_COMMON_EQUITY_AND_SUSTAINABLE_ROE_INPUTS_REQUIRED",
            "prepare_bank_specific_common_equity_and_sustainable_roe_evidence",
        ),
        "real_estate_nav": (
            "PROJECT_NAV_INPUTS_REQUIRED",
            "collect_project_level_nav_inputs_and_debt_bridge",
        ),
        "biotech_rnpv": (
            "PIPELINE_RNPV_INPUTS_REQUIRED",
            "collect_pipeline_probability_timeline_and_financing_inputs",
        ),
        "consumer_compounder_dcf": (
            "OWNER_EARNINGS_DCF_INPUTS_REQUIRED",
            "prepare_owner_earnings_growth_duration_and_reinvestment_inputs",
        ),
    }
    return requirements.get(
        strategy_id,
        ("SPECIALIZED_INPUTS_REQUIRED", f"collect_required_inputs_for:{strategy_id}"),
    )


def _locked_base(row: Mapping[str, Any]) -> dict[str, Any]:
    output = dict(row)
    output.update(
        {
            "specialized_model_executed": False,
            "specialized_model_execution_state": "NOT_SPECIALIZED_ROUTE",
            "specialized_model_status": "",
            "specialized_model_execution_reason": "",
            "specialized_model_input_basis": "",
            "specialized_model_input_report_years": "",
            "specialized_model_roe_sample_count": "",
            "specialized_current_pb": "",
            "specialized_current_pb_date": "",
            "specialized_normalized_mid_cycle_roe": "",
            "specialized_cost_of_equity_assumption": "",
            "specialized_long_term_growth_assumption": "",
            "specialized_fair_pb": "",
            "specialized_implied_mid_cycle_roe": "",
            "specialized_expectation_gap_roe": "",
            "specialized_margin_of_safety": "",
            "specialized_model_next_action": "",
            "specialized_model_formal_buy_eligible": False,
            "formal_signal_eligible": False,
            "automatic_promotion_allowed": False,
            "no_auto_trade": True,
            "disclaimer": DISCLAIMER,
        }
    )
    return output


def execute_specialized_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    as_of: date,
    loader: PublicFundamentalLoader,
    years: int = 7,
    minimum_annual_roe_samples: int = DEFAULT_MIN_ANNUAL_ROE_SAMPLES,
    maximum_annual_roe_samples: int = DEFAULT_MAX_ANNUAL_ROE_SAMPLES,
    cost_of_equity: float = DEFAULT_COST_OF_EQUITY,
    long_term_growth: float = DEFAULT_LONG_TERM_GROWTH,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for raw in rows:
        row = _locked_base(raw)
        strategy_id = str(row.get("valuation_primary_strategy_id") or "").strip()
        original_state = str(row.get("valuation_model_execution_state") or "").strip()

        if not strategy_id or strategy_id == GENERAL_REVERSE_STRATEGY_ID:
            result.append(row)
            continue

        if strategy_id != CAPITAL_MARKETS_STRATEGY_ID:
            reason, next_action = _unimplemented_requirement(strategy_id)
            row.update(
                {
                    "specialized_model_execution_state": "SPECIALIZED_MODEL_SELECTED_INPUTS_REQUIRED",
                    "specialized_model_status": reason,
                    "specialized_model_execution_reason": reason,
                    "specialized_model_next_action": next_action,
                }
            )
            result.append(row)
            continue

        code = _normalize_code(row.get("code"))
        try:
            fetched = loader.load(
                code,
                years=max(5, int(years)),
                fetch_valuation=True,
                fetch_financial=True,
            )
        except Exception as exc:
            row.update(
                {
                    "specialized_model_execution_state": "SPECIALIZED_MODEL_SELECTED_INPUTS_REQUIRED",
                    "specialized_model_status": "PUBLIC_FUNDAMENTAL_LOAD_FAILED",
                    "specialized_model_execution_reason": f"{type(exc).__name__}",
                    "specialized_model_next_action": "retry_public_fundamental_inputs_without_promoting_model_state",
                }
            )
            result.append(row)
            continue

        current_pb, pb_date = _latest_positive_pb(fetched.valuation_df, as_of=as_of)
        roe_history = _annual_roe_history(
            fetched.financial_df,
            as_of=as_of,
            max_samples=maximum_annual_roe_samples,
        )
        row.update(
            {
                "specialized_model_input_basis": (
                    f"PB_DAILY_PIT;{ROE_INPUT_BASIS};{BROKER_NORMALIZATION_BASIS}"
                ),
                "specialized_model_input_report_years": ";".join(str(year) for year in roe_history.years),
                "specialized_model_roe_sample_count": len(roe_history.values),
                "specialized_current_pb": current_pb if current_pb is not None else "",
                "specialized_current_pb_date": pb_date,
                "specialized_normalized_mid_cycle_roe": (
                    roe_history.median if roe_history.median is not None else ""
                ),
                "specialized_cost_of_equity_assumption": cost_of_equity,
                "specialized_long_term_growth_assumption": long_term_growth,
            }
        )

        missing: list[str] = []
        if current_pb is None:
            missing.append("current_pb_unavailable")
        if len(roe_history.values) < max(1, int(minimum_annual_roe_samples)):
            missing.append("insufficient_pit_safe_annual_roe_history")
        if cost_of_equity <= long_term_growth:
            missing.append("invalid_cost_of_equity_growth_relation")
        if missing:
            row.update(
                {
                    "specialized_model_execution_state": "SPECIALIZED_MODEL_SELECTED_INPUTS_REQUIRED",
                    "specialized_model_status": "BROKER_INPUTS_INCOMPLETE",
                    "specialized_model_execution_reason": ";".join(missing),
                    "specialized_model_next_action": "complete_broker_pb_and_mid_cycle_roe_inputs",
                }
            )
            result.append(row)
            continue

        normalized_roe = roe_history.median
        assert current_pb is not None and normalized_roe is not None
        model = value_traditional_broker(
            common_bvps=1.0,
            normalized_mid_cycle_roe=normalized_roe,
            cost_of_equity=cost_of_equity,
            long_term_growth=long_term_growth,
            current_price=current_pb,
        )
        expectation_gap = (
            None
            if model.implied_mid_cycle_roe is None
            else normalized_roe - model.implied_mid_cycle_roe
        )
        executed_state = (
            "SPECIALIZED_MODEL_EXECUTED_RESEARCH_ONLY"
            if model.valuation_model_applicable
            else "SPECIALIZED_MODEL_EXECUTED_FAIL_CLOSED"
        )
        row.update(
            {
                "specialized_model_executed": True,
                "specialized_model_execution_state": executed_state,
                "specialized_model_status": model.status,
                "specialized_model_execution_reason": (
                    "traditional_broker_pb_residual_income_in_normalized_book_units"
                ),
                "specialized_fair_pb": model.fair_common_pb if model.fair_common_pb is not None else "",
                "specialized_implied_mid_cycle_roe": (
                    model.implied_mid_cycle_roe if model.implied_mid_cycle_roe is not None else ""
                ),
                "specialized_expectation_gap_roe": expectation_gap if expectation_gap is not None else "",
                "specialized_margin_of_safety": model.margin_of_safety if model.margin_of_safety is not None else "",
                "specialized_model_next_action": (
                    "review_broker_mid_cycle_pb_roe_gap_before_any_formal_decision"
                ),
            }
        )
        # Do not overwrite the original routing field.  The sidecar state above
        # is the auditable proof of execution while downstream Formal BUY remains
        # unchanged until a separately tested integration explicitly consumes it.
        row["valuation_model_execution_state"] = original_state
        result.append(row)
    return result


def _read_as_of(report_dir: Path) -> date:
    payload = json.loads((report_dir / "valuation_research_summary.json").read_text(encoding="utf-8"))
    text = str(payload.get("as_of_date") or "").strip()
    if not text:
        raise ValueError("valuation research as_of_date is unavailable")
    return date.fromisoformat(text)


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


def _write_csv(path: Path, rows: list[dict[str, Any]], source_fields: list[str]) -> None:
    fields = list(source_fields)
    for field in SPECIALIZED_OUTPUT_COLUMNS:
        if field not in fields:
            fields.append(field)
    for field in ("formal_signal_eligible", "automatic_promotion_allowed", "no_auto_trade", "disclaimer"):
        if field not in fields:
            fields.append(field)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_specialized_execution_sidecar(
    report_root: Path,
    *,
    cache_dir: Path = Path("data/cache/valuation_research_fundamentals"),
    years: int = 7,
    minimum_annual_roe_samples: int = DEFAULT_MIN_ANNUAL_ROE_SAMPLES,
    maximum_annual_roe_samples: int = DEFAULT_MAX_ANNUAL_ROE_SAMPLES,
    cost_of_equity: float = DEFAULT_COST_OF_EQUITY,
    long_term_growth: float = DEFAULT_LONG_TERM_GROWTH,
    loader: PublicFundamentalLoader | None = None,
) -> dict[str, Any]:
    report_dir = _latest_report_dir(report_root)
    routed_path = report_dir / "valuation_research_routed.csv"
    with routed_path.open(encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        source_fields = list(reader.fieldnames or [])
        rows = list(reader)
    as_of = _read_as_of(report_dir)
    effective_loader = loader or PublicFundamentalLoader(cache_dir=cache_dir)
    executed = execute_specialized_rows(
        rows,
        as_of=as_of,
        loader=effective_loader,
        years=years,
        minimum_annual_roe_samples=minimum_annual_roe_samples,
        maximum_annual_roe_samples=maximum_annual_roe_samples,
        cost_of_equity=cost_of_equity,
        long_term_growth=long_term_growth,
    )

    output_csv = report_dir / "valuation_research_specialized.csv"
    _write_csv(output_csv, executed, source_fields)

    specialized = [
        row for row in executed
        if str(row.get("valuation_primary_strategy_id") or "")
        not in {"", GENERAL_REVERSE_STRATEGY_ID}
    ]
    strategy_counts = Counter(str(row.get("valuation_primary_strategy_id") or "") for row in specialized)
    execution_counts = Counter(str(row.get("specialized_model_execution_state") or "") for row in specialized)
    broker_rows = [
        row for row in specialized
        if row.get("valuation_primary_strategy_id") == CAPITAL_MARKETS_STRATEGY_ID
    ]
    summary = {
        "as_of_date": as_of.isoformat(),
        "row_count": len(executed),
        "specialized_selected_count": len(specialized),
        "specialized_strategy_counts": dict(sorted(strategy_counts.items())),
        "specialized_execution_counts": dict(sorted(execution_counts.items())),
        "capital_markets_selected_count": len(broker_rows),
        "capital_markets_executed_count": sum(bool(row.get("specialized_model_executed")) for row in broker_rows),
        "capital_markets_input_required_count": sum(
            row.get("specialized_model_execution_state") == "SPECIALIZED_MODEL_SELECTED_INPUTS_REQUIRED"
            for row in broker_rows
        ),
        "broker_policy": {
            "minimum_annual_roe_samples": int(minimum_annual_roe_samples),
            "maximum_annual_roe_samples": int(maximum_annual_roe_samples),
            "cost_of_equity_assumption": float(cost_of_equity),
            "long_term_growth_assumption": float(long_term_growth),
            "roe_input_basis": ROE_INPUT_BASIS,
            "normalization_basis": BROKER_NORMALIZATION_BASIS,
            "valuation_space": "NORMALIZED_BOOK_VALUE_UNITS",
        },
        "ranking_changed": False,
        "formal_buy_consumes_specialized_sidecar": False,
        "formal_signal_eligible": False,
        "automatic_promotion_allowed": False,
        "no_auto_trade": True,
        "disclaimer": DISCLAIMER,
    }
    (report_dir / "specialized_valuation_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    lines = [
        "# Specialized Valuation Execution",
        "",
        DISCLAIMER,
        "",
        f"- as_of_date: {as_of.isoformat()}",
        f"- specialized_selected_count: {len(specialized)}",
        f"- capital_markets_selected_count: {len(broker_rows)}",
        f"- capital_markets_executed_count: {summary['capital_markets_executed_count']}",
        "- ranking_changed: False",
        "- formal_buy_consumes_specialized_sidecar: False",
        "- no_auto_trade: True",
        "",
    ]
    for row in specialized:
        lines.extend(
            [
                f"## {row.get('valuation_research_rank')}. {row.get('code')} {row.get('stock_name')}",
                f"- strategy: {row.get('valuation_primary_strategy_id')}",
                f"- execution: {row.get('specialized_model_execution_state')}",
                f"- status: {row.get('specialized_model_status')}",
                f"- current_pb: {row.get('specialized_current_pb')}",
                f"- normalized_mid_cycle_roe: {row.get('specialized_normalized_mid_cycle_roe')}",
                f"- fair_pb: {row.get('specialized_fair_pb')}",
                f"- implied_mid_cycle_roe: {row.get('specialized_implied_mid_cycle_roe')}",
                f"- margin_of_safety: {row.get('specialized_margin_of_safety')}",
                f"- next: {row.get('specialized_model_next_action')}",
                "",
            ]
        )
    (report_dir / "valuation_research_specialized.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-root", type=Path, required=True)
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path("data/cache/valuation_research_fundamentals"),
    )
    parser.add_argument("--years", type=int, default=7)
    parser.add_argument("--minimum-annual-roe-samples", type=int, default=DEFAULT_MIN_ANNUAL_ROE_SAMPLES)
    parser.add_argument("--maximum-annual-roe-samples", type=int, default=DEFAULT_MAX_ANNUAL_ROE_SAMPLES)
    parser.add_argument("--cost-of-equity", type=float, default=DEFAULT_COST_OF_EQUITY)
    parser.add_argument("--long-term-growth", type=float, default=DEFAULT_LONG_TERM_GROWTH)
    args = parser.parse_args(argv)

    summary = write_specialized_execution_sidecar(
        args.report_root,
        cache_dir=args.cache_dir,
        years=args.years,
        minimum_annual_roe_samples=args.minimum_annual_roe_samples,
        maximum_annual_roe_samples=args.maximum_annual_roe_samples,
        cost_of_equity=args.cost_of_equity,
        long_term_growth=args.long_term_growth,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
