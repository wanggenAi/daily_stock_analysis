"""Engine-aware research-funnel policy for opportunity discovery.

The production strict gate cannot discover a strong-trend or earnings-inflection
candidate if an earlier research stage discarded it solely because its five-year
price percentile was not low. This module removes that hidden coupling while
preserving every non-price hard blocker.

Upstream admission is research-only. Final eligibility is still decided by
``opportunity_engine_policy`` plus the complete legacy strict gate set and the
risk-capped exit-history policy.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Mapping

import pandas as pd

from src.strategies.genge_opportunity_discovery import opportunity_engine_policy
from src.strategies.genge_opportunity_discovery import pipeline


_ORIGINAL_BUILD_QUANT_ROWS = pipeline._build_quant_rows
_ORIGINAL_SCREEN_BLOCKERS = pipeline._screen_blockers
_ORIGINAL_SCREEN_STATUS = pipeline._screen_status
_ORIGINAL_TIER_ROW = pipeline._tier_row

DIAGNOSTIC_COLUMNS = (
    "preliminary_opportunity_engine",
    "net_profit_yoy",
    "previous_net_profit_yoy",
    "earnings_inflection_confirmed",
    "earnings_inflection_reason",
    "earnings_inflection_report_date",
)


def _finite_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(number):
        return None
    return number


def _preliminary_engine(row: Mapping[str, Any]) -> str:
    """Return an upstream research engine without pretending final gates passed.

    Factor evidence is checked only against the matching setup. A negative
    momentum regime therefore cannot erase an otherwise independent valley
    candidate, and negative reversal evidence cannot erase a trend candidate.
    """

    percentile = _finite_float(row.get("price_percentile_5y"))
    if (
        percentile is not None
        and percentile <= 0.35
        and opportunity_engine_policy.factor_validity_for_engine(
            row, "VALLEY_REPAIR"
        ) != "INVALID"
    ):
        return "VALLEY_REPAIR"
    if (
        str(row.get("trend_confirmation_level") or "").upper() == "STRONG"
        and opportunity_engine_policy.factor_validity_for_engine(
            row, "STRONG_TREND_PULLBACK"
        ) != "INVALID"
    ):
        return "STRONG_TREND_RESEARCH"
    if (
        opportunity_engine_policy.earnings_inflection_confirmed(row)
        and opportunity_engine_policy.factor_validity_for_engine(
            row, "EARNINGS_INFLECTION"
        ) != "INVALID"
    ):
        return "EARNINGS_INFLECTION"
    return "NONE"


def _same_fiscal_period_prior_year(report_date: date) -> date:
    try:
        return report_date.replace(year=report_date.year - 1)
    except ValueError:
        return report_date.replace(year=report_date.year - 1, day=28)


def _profit_growth(current: float, prior: float) -> float | None:
    if prior <= 0:
        return None
    return (current / prior - 1.0) * 100.0


def financial_inflection_metrics(financial_df: Any, *, as_of: date) -> dict[str, Any]:
    """Derive auditable earnings-inflection fields from published net profit."""

    empty = {
        "net_profit_yoy": None,
        "previous_net_profit_yoy": None,
        "earnings_inflection_confirmed": False,
        "earnings_inflection_reason": "financial_history_insufficient",
        "earnings_inflection_report_date": "",
    }
    if not isinstance(financial_df, pd.DataFrame) or financial_df.empty:
        return empty
    if "report_date" not in financial_df.columns or "net_profit" not in financial_df.columns:
        return empty

    local = financial_df.copy()
    as_of_ts = pd.Timestamp(as_of)
    local["report_date"] = pd.to_datetime(local["report_date"], errors="coerce")
    local["net_profit"] = pd.to_numeric(local["net_profit"], errors="coerce")
    local = local.dropna(subset=["report_date", "net_profit"])
    local = local[local["report_date"] <= as_of_ts]
    if "disclosure_date" in local.columns:
        disclosure = pd.to_datetime(local["disclosure_date"], errors="coerce")
        local = local[disclosure.isna() | (disclosure <= as_of_ts)]
    if local.empty:
        return empty

    local = local.sort_values("report_date").drop_duplicates("report_date", keep="last")
    values = {
        pd.Timestamp(row.report_date).date(): float(row.net_profit)
        for row in local.itertuples(index=False)
    }
    report_dates = list(values)

    def yoy_for(period: date) -> tuple[float | None, bool]:
        prior_period = _same_fiscal_period_prior_year(period)
        if prior_period not in values:
            return None, False
        current_profit = values[period]
        prior_profit = values[prior_period]
        turnaround = current_profit > 0.0 and prior_profit <= 0.0
        return _profit_growth(current_profit, prior_profit), turnaround

    current_period = report_dates[-1]
    current_yoy, turnaround = yoy_for(current_period)
    previous_yoy = None
    for period in reversed(report_dates[:-1]):
        candidate_yoy, _ = yoy_for(period)
        if candidate_yoy is not None:
            previous_yoy = candidate_yoy
            break

    confirmed = turnaround
    reason = "loss_to_profit_turnaround" if turnaround else "no_verified_inflection"
    if (
        not confirmed
        and current_yoy is not None
        and previous_yoy is not None
        and current_yoy > 0.0
        and previous_yoy <= 0.0
        and current_yoy - previous_yoy
        >= opportunity_engine_policy.EARNINGS_INFLECTION_MIN_ACCELERATION_PCT
    ):
        confirmed = True
        reason = "profit_growth_sign_change_and_acceleration"

    return {
        "net_profit_yoy": round(current_yoy, 4) if current_yoy is not None else None,
        "previous_net_profit_yoy": round(previous_yoy, 4) if previous_yoy is not None else None,
        "earnings_inflection_confirmed": bool(confirmed),
        "earnings_inflection_reason": reason,
        "earnings_inflection_report_date": current_period.isoformat(),
    }


def _screen_blockers(row: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    hard, soft = _ORIGINAL_SCREEN_BLOCKERS(row)
    if _preliminary_engine(row) in {"STRONG_TREND_RESEARCH", "EARNINGS_INFLECTION"}:
        hard = [item for item in hard if item != "price_position_overheated"]
        soft = [item for item in soft if item != "price_not_low_enough"]
    return sorted(set(hard)), sorted(set(soft))


def _screen_status(row: Mapping[str, Any], hard: list[str], soft: list[str]) -> str:
    status = _ORIGINAL_SCREEN_STATUS(row, hard, soft)
    if hard:
        return status
    if (
        _preliminary_engine(row) in {"STRONG_TREND_RESEARCH", "EARNINGS_INFLECTION"}
        and status == "LOW_PRIORITY"
    ):
        return "SECONDARY_RESEARCH"
    return status


def _build_quant_rows(**kwargs: Any) -> list[dict[str, Any]]:
    rows = _ORIGINAL_BUILD_QUANT_ROWS(**kwargs)
    input_by_code = {str(item.code).zfill(6): item for item in kwargs.get("inputs", [])}
    as_of = kwargs.get("resolved_as_of")
    if not isinstance(as_of, date):
        return rows

    for row in rows:
        item = input_by_code.get(str(row.get("code") or "").zfill(6))
        if item is not None:
            row.update(financial_inflection_metrics(item.financial_df, as_of=as_of))
        hard, soft = _screen_blockers(row)
        row["hard_reject_blockers"] = ";".join(hard)
        row["soft_blockers"] = ";".join(soft)
        row["quant_screen_status"] = _screen_status(row, hard, soft)
        row["preliminary_opportunity_engine"] = _preliminary_engine(row)
    return rows


def _tier_row(row: dict[str, Any]) -> dict[str, Any]:
    """Remove only the duplicated Tier-A price condition for new engines."""

    result = _ORIGINAL_TIER_ROW(row)
    engine = _preliminary_engine(row)
    result["preliminary_opportunity_engine"] = engine
    if engine not in {"STRONG_TREND_RESEARCH", "EARNINGS_INFLECTION"}:
        return result

    failed = [token for token in str(result.get("a_condition_failed") or "").split(";") if token]
    if "price_low_or_reasonable" not in failed:
        return result

    remaining = [token for token in failed if token != "price_low_or_reasonable"]
    result["a_condition_failed"] = ";".join(remaining)
    result["a_condition_fail_count"] = len(remaining)
    result["a_condition_pass_count"] = int(result.get("a_condition_pass_count") or 0) + 1

    hard = str(result.get("hard_blockers") or "").strip()
    if not remaining and not hard and str(row.get("quant_screen_status") or "") in pipeline.RESEARCH_STATUSES:
        result["tier"] = "TIER_A"
        result["research_label"] = pipeline._research_label("TIER_A")
        result["upgrade_conditions"] = pipeline._upgrade_conditions(
            [],
            str(result.get("industry_evidence_status") or ""),
            str(result.get("company_evidence_status") or ""),
        )
    return result


def install() -> None:
    """Install engine-aware research admission; safe to call repeatedly."""

    if pipeline._build_quant_rows is _build_quant_rows:
        return
    pipeline._screen_blockers = _screen_blockers
    pipeline._screen_status = _screen_status
    pipeline._build_quant_rows = _build_quant_rows
    pipeline._tier_row = _tier_row
    for columns in (pipeline.QUANT_COLUMNS, pipeline.OPPORTUNITY_COLUMNS):
        for column in DIAGNOSTIC_COLUMNS:
            if column not in columns:
                columns.append(column)
