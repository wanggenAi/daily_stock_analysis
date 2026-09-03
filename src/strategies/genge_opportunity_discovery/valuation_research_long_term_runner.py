"""Run reverse valuation with long-term second-pass names prioritized for deep financial review.

This wrapper does not change valuation formulas. It preserves the source channel
and gives candidates explicitly routed from LONG_TERM_SECOND_PASS first claim on
the bounded financial-review budget. Crucially, long-term names receive financial
review even when the generic PE diagnostic is not applicable, because a
specialized/non-PE model still needs point-in-time financial evidence.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Iterable, Mapping

import pandas as pd

from src.strategies.genge_opportunity_discovery import valuation_research_report as base
from src.strategies.genge_opportunity_discovery.fundamental_valuation import ValuationPolicy


_ORIGINAL_BASE_ROW = base._base_row
_ORIGINAL_RANK_KEY = base._rank_key
_ORIGINAL_ADD_FINANCIAL_REVIEW = base._add_financial_review
_CASH_POLICY = ValuationPolicy()


def _source_priority(row: Mapping[str, Any]) -> int:
    channel = str(row.get("valuation_source_channel") or "")
    return 0 if "LONG_TERM_SECOND_PASS" in channel else 1


def _base_row(source, pe_diag):
    row = _ORIGINAL_BASE_ROW(source, pe_diag)
    row["valuation_source_channel"] = source.get("valuation_source_channel") or ""
    row["long_term_second_pass_status"] = source.get("long_term_second_pass_status") or ""
    row["medium_horizon_exit_profile_limitation"] = source.get(
        "medium_horizon_exit_profile_limitation"
    ) or False
    row["cash_conversion_ratio_basis"] = ""
    return row


def _rank_key(row: Mapping[str, Any]):
    return (_source_priority(row),) + tuple(_ORIGINAL_RANK_KEY(row))


def _cash_quality_contribution(ratio: float) -> float:
    if ratio >= _CASH_POLICY.high_cash_conversion:
        return 15.0
    if ratio >= _CASH_POLICY.medium_cash_conversion:
        return 7.0
    if ratio < 0:
        return -20.0
    return -8.0


def _statutory_latest_disclosure_date(report_date: Any) -> date | None:
    """Conservative latest lawful publication date for standard A-share periods.

    This is used only when the provider has no actual disclosure timestamp. It
    intentionally does not assume that a period-end row was public immediately.
    Under the current SSE timetable, annual reports are due within four months,
    half-year reports within two months, and Q1/Q3 reports within one month.
    """
    rd = base._coerce_date(report_date)
    if rd is None:
        return None
    if (rd.month, rd.day) == (12, 31):
        return date(rd.year + 1, 4, 30)
    if (rd.month, rd.day) == (3, 31):
        return date(rd.year, 4, 30)
    if (rd.month, rd.day) == (6, 30):
        return date(rd.year, 8, 31)
    if (rd.month, rd.day) == (9, 30):
        return date(rd.year, 10, 31)
    return None


def _pit_safe_financial_frame(financial_frame, *, as_of: date):
    """Remove undated report periods not yet guaranteed public by ``as_of``.

    If real disclosure dates exist, leave the frame intact and let the base PIT
    selector use them. If all disclosure dates are missing, only periods whose
    statutory latest disclosure date has passed are eligible. This is deliberately
    fail-closed: an early half-year filing without a captured disclosure timestamp
    is not used until publication can be proven by another source or the deadline.
    """
    if financial_frame is None or financial_frame.empty:
        return financial_frame, False
    if "disclosure_date" in financial_frame.columns:
        known = pd.to_datetime(financial_frame["disclosure_date"], errors="coerce").notna()
        if bool(known.any()):
            return financial_frame, False
    if "report_date" not in financial_frame.columns:
        return financial_frame, False

    local = financial_frame.copy()
    local["_statutory_latest_disclosure_date"] = local["report_date"].map(
        _statutory_latest_disclosure_date
    )
    eligible = local["_statutory_latest_disclosure_date"].map(
        lambda value: value is not None and value <= as_of
    )
    local = local[eligible].drop(columns=["_statutory_latest_disclosure_date"])
    return local, True


def _add_financial_review(row, financial_frame, *, as_of: date):
    """Use unit-safe cash evidence and point-in-time-safe financial periods."""
    safe_frame, statutory_filter_used = _pit_safe_financial_frame(
        financial_frame, as_of=as_of
    )
    reviewed = _ORIGINAL_ADD_FINANCIAL_REVIEW(row, safe_frame, as_of=as_of)
    financial_row, pit_method = base._financial_pit_row(safe_frame, as_of=as_of)
    if statutory_filter_used and financial_row and pit_method == "REPORT_DATE_FALLBACK":
        reviewed["earnings_point_in_time_method"] = "STATUTORY_DEADLINE_FALLBACK"

    direct_ratio = base._finite(financial_row.get("cash_conversion_ratio"))
    if direct_ratio is None:
        return reviewed

    cashless = base.normalize_core_earnings(
        net_profit=financial_row.get("net_profit"),
        recurring_profit=financial_row.get("recurring_profit"),
        investment_income=financial_row.get("investment_income"),
        fair_value_change_gain=financial_row.get("fair_value_change_gain"),
        operating_cash_flow=None,
    )
    score = max(
        0.0,
        min(100.0, cashless.earnings_quality_score + _cash_quality_contribution(direct_ratio)),
    )

    reviewed["cash_conversion_ratio"] = direct_ratio
    reviewed["cash_conversion_ratio_basis"] = (
        financial_row.get("cash_conversion_ratio_basis")
        or "PROVIDER_OCF_TO_NET_PROFIT_RATIO"
    )
    reviewed["earnings_quality_score"] = round(score, 2)
    # normalize_core_earnings lowers HIGH -> MEDIUM only because raw total OCF
    # is absent. A verified provider ratio supplies the missing cash evidence.
    if (
        cashless.normalization_method == "REPORTED_RECURRING_PROFIT"
        and cashless.normalized_core_operating_profit is not None
    ):
        reviewed["earnings_quality_confidence"] = "HIGH"
    else:
        reviewed["earnings_quality_confidence"] = cashless.earnings_quality_confidence
    return reviewed


def _build_valuation_research_rows(
    source_rows: Iterable[Mapping[str, Any]],
    *,
    as_of: date,
    loader,
    research_limit: int = base.DEFAULT_RESEARCH_LIMIT,
    relaxed_reserve: int = base.DEFAULT_RELAXED_RESERVE,
    financial_review_limit: int = base.DEFAULT_FINANCIAL_REVIEW_LIMIT,
    minimum_pe_samples: int = 1,
    years: int = 5,
    max_workers: int = 1,
) -> list[dict[str, Any]]:
    """Base valuation flow with long-term-first financial review semantics.

    Normal rows keep the legacy rule: only a ready generic PE diagnostic is
    eligible for bounded financial review. Long-term second-pass rows are the
    exception: they are reviewed first even if PE is non-applicable/incomplete,
    because that status may be exactly why a non-PE specialized model is needed.
    """
    selected = base.select_wide_recall_rows(
        source_rows,
        research_limit=research_limit,
        relaxed_reserve=relaxed_reserve,
    )

    valuation_results = base._load_many(
        loader,
        [row.get("code") for row in selected],
        years=years,
        fetch_valuation=True,
        fetch_financial=False,
        max_workers=max_workers,
    )
    provisional: list[dict[str, Any]] = []
    for source in selected:
        code = base._normalize_code(source.get("code"))
        fetched = valuation_results.get(code)
        valuation_frame = (
            None if isinstance(fetched, Exception) or fetched is None else fetched.valuation_df
        )
        pe_diag = base.build_pe_reference_diagnostic(
            valuation_frame,
            as_of=as_of,
            minimum_history_samples=minimum_pe_samples,
        )
        base_row = _base_row(source, pe_diag)
        if fetched is not None and not isinstance(fetched, Exception):
            base_row["valuation_provider"] = getattr(
                fetched, "valuation_provider", "none"
            )
            provider_errors = getattr(fetched, "provider_errors", {}) or {}
            base_row["valuation_provider_errors"] = ";".join(
                provider_errors.get("valuation", [])
            )
        provisional.append(base_row)

    provisional.sort(key=_rank_key)
    budget = max(0, int(financial_review_limit))

    long_term_codes = [
        row["code"]
        for row in provisional
        if "LONG_TERM_SECOND_PASS" in str(row.get("valuation_source_channel") or "")
    ]
    normal_ready_codes = [
        row["code"]
        for row in provisional
        if "LONG_TERM_SECOND_PASS" not in str(row.get("valuation_source_channel") or "")
        and row.get("valuation_diagnostic_status") == "OK"
    ]
    financial_codes = list(dict.fromkeys(long_term_codes + normal_ready_codes))[:budget]

    financial_results = base._load_many(
        loader,
        financial_codes,
        years=years,
        fetch_valuation=False,
        fetch_financial=True,
        max_workers=max_workers,
    )

    reviewed: list[dict[str, Any]] = []
    financial_code_set = set(financial_codes)
    for row in provisional:
        code = base._normalize_code(row.get("code"))
        if code not in financial_code_set:
            reviewed.append(dict(row))
            continue
        fetched = financial_results.get(code)
        financial_frame = (
            None if isinstance(fetched, Exception) or fetched is None else fetched.financial_df
        )
        reviewed_row = _add_financial_review(row, financial_frame, as_of=as_of)
        if fetched is not None and not isinstance(fetched, Exception):
            reviewed_row["financial_provider"] = getattr(
                fetched, "financial_provider", "none"
            )
            provider_errors = getattr(fetched, "provider_errors", {}) or {}
            reviewed_row["financial_provider_errors"] = ";".join(
                provider_errors.get("financial", [])
            )
        reviewed.append(reviewed_row)

    reviewed.sort(key=_rank_key)
    for rank, row in enumerate(reviewed, 1):
        row["valuation_research_rank"] = rank
    return reviewed


def install_long_term_priority() -> None:
    base._base_row = _base_row
    base._rank_key = _rank_key
    base._add_financial_review = _add_financial_review
    base.build_valuation_research_rows = _build_valuation_research_rows
    for field in (
        "valuation_source_channel",
        "long_term_second_pass_status",
        "medium_horizon_exit_profile_limitation",
        "cash_conversion_ratio_basis",
    ):
        if field not in base.OUTPUT_COLUMNS:
            insert_at = base.OUTPUT_COLUMNS.index("wide_recall_reason") + 1
            base.OUTPUT_COLUMNS.insert(insert_at, field)


def main(argv: list[str] | None = None) -> int:
    install_long_term_priority()
    print("[VALUATION][LONG_TERM_PRIORITY] enabled", flush=True)
    return base.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
