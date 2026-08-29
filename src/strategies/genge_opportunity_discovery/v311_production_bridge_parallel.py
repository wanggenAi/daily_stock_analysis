"""Parallel runtime wrapper for the frozen V3.1.1 production bridge.

This module changes only orchestration.  The per-security strict-PIT extraction,
price provenance checks, fail-closed behavior and production policy remain in
the existing V3.1.1 modules.  Network-bound per-security refreshes are executed
concurrently so one slow provider request cannot serialize the whole candidate
set for hours.
"""
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Iterable, Mapping

from . import v311_current_expectation_inputs as expectation_inputs
from . import v311_production_bridge as production_bridge


_ORIGINAL_BUILD = expectation_inputs.build_current_expectation_rows
DEFAULT_MAX_WORKERS = 12
MAX_MAX_WORKERS = 16


def _worker_count(item_count: int) -> int:
    raw = os.getenv("GENGE_V311_PIT_WORKERS", str(DEFAULT_MAX_WORKERS)).strip()
    try:
        requested = int(raw)
    except ValueError:
        requested = DEFAULT_MAX_WORKERS
    requested = max(1, min(requested, MAX_MAX_WORKERS))
    return min(requested, max(1, item_count))


def build_current_expectation_rows_parallel(
    codes: Iterable[str],
    *,
    source_rows: Iterable[Mapping[str, Any]] = (),
    as_of,
    financial_loader=expectation_inputs.fetch_financial_panel,
    price_loader=expectation_inputs.fetch_latest_close,
) -> list[dict[str, Any]]:
    """Run the unchanged strict-PIT single-security contract concurrently.

    Result ordering is deterministic and identical to the input's first-seen
    normalized-code order.  Exceptions remain fail-closed inside the original
    extractor; this wrapper does not manufacture fallback values.
    """
    source_rows = list(source_rows)
    ordered_codes = list(
        dict.fromkeys(
            expectation_inputs._normalize_code(value)
            for value in codes
            if expectation_inputs._normalize_code(value)
        )
    )
    if not ordered_codes:
        return []

    workers = _worker_count(len(ordered_codes))
    if workers <= 1:
        return _ORIGINAL_BUILD(
            ordered_codes,
            source_rows=source_rows,
            as_of=as_of,
            financial_loader=financial_loader,
            price_loader=price_loader,
        )

    def run_one(code: str) -> dict[str, Any]:
        rows = _ORIGINAL_BUILD(
            [code],
            source_rows=source_rows,
            as_of=as_of,
            financial_loader=financial_loader,
            price_loader=price_loader,
        )
        if rows:
            return rows[0]
        return expectation_inputs._invalid_row(
            code,
            None,
            as_of,
            "",
            "PARALLEL_REFRESH_EMPTY_RESULT",
        )

    by_code: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="v311-pit") as pool:
        futures = {pool.submit(run_one, code): code for code in ordered_codes}
        for future in as_completed(futures):
            code = futures[future]
            try:
                by_code[code] = future.result()
            except Exception as exc:
                # Preserve the production fail-closed contract even if an
                # unexpected wrapper-level exception escapes a worker.
                by_code[code] = expectation_inputs._invalid_row(
                    code,
                    None,
                    as_of,
                    "",
                    f"PARALLEL_REFRESH_ERROR:{type(exc).__name__}:{exc}",
                )

    return [by_code[code] for code in ordered_codes]


def main(argv: list[str] | None = None) -> int:
    expectation_inputs.build_current_expectation_rows = build_current_expectation_rows_parallel
    return production_bridge.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
