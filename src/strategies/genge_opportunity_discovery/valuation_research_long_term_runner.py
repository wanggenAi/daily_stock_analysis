"""Run reverse valuation with long-term second-pass names prioritized for deep financial review.

This wrapper does not change valuation formulas. It only preserves the source
channel and gives candidates explicitly routed from LONG_TERM_SECOND_PASS first
claim on the bounded financial-review budget so they cannot be re-erased by a
secondary ranking cap.
"""
from __future__ import annotations

from typing import Any, Mapping

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


def install_long_term_priority() -> None:
    base._base_row = _base_row
    base._rank_key = _rank_key
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
