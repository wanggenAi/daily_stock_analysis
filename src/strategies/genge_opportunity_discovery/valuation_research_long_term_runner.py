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

from src.strategies.genge_opportunity_discovery import valuation_research_report as base


_ORIGINAL_BASE_ROW = base._base_row
_ORIGINAL_RANK_KEY = base._rank_key


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
    return row


def _rank_key(row: Mapping[str, Any]):
    return (_source_priority(row),) + tuple(_ORIGINAL_RANK_KEY(row))


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
        provisional.append(_base_row(source, pe_diag))

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
        reviewed.append(base._add_financial_review(row, financial_frame, as_of=as_of))

    reviewed.sort(key=_rank_key)
    for rank, row in enumerate(reviewed, 1):
        row["valuation_research_rank"] = rank
    return reviewed


def install_long_term_priority() -> None:
    base._base_row = _base_row
    base._rank_key = _rank_key
    base.build_valuation_research_rows = _build_valuation_research_rows
    for field in (
        "valuation_source_channel",
        "long_term_second_pass_status",
        "medium_horizon_exit_profile_limitation",
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
