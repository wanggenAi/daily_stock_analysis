"""Quality-preserving runtime optimization for GenGe V3.1 deep gap closure.

This module deliberately reuses the canonical gap-closing rules from
``v31_deep_gap_closure`` and changes only collection scheduling:

1. the first automatic evidence pass still sees the complete requested workset;
2. the second bounded retry is restricted to targets implicated by FAILED audit
   rows (falling back to the complete workset when failure scope is ambiguous);
3. expensive multi-year official-report predictability collection is sharded
   across a bounded thread pool.  Each shard executes the original collector,
   with the same sources, timeouts, report-depth rules and classification logic.

No threshold, authority rule, evidence requirement or UNKNOWN/PASS semantics are
changed.  Any worker exception fails the run instead of manufacturing evidence.
"""
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping

from . import v31_deep_gap_closure as core
from .evidence_collectors import collect_auto_evidence as _original_auto_evidence
from .evidence_collectors.multi_year_predictability import (
    collect_multi_year_predictability_evidence as _original_predictability,
)

DEFAULT_WORKERS = 4
MAX_WORKERS = 6


def _worker_count(requested: int) -> int:
    if requested <= 1:
        return 1
    raw = os.environ.get("GEN_GE_DEEP_EVIDENCE_WORKERS", str(DEFAULT_WORKERS))
    try:
        configured = int(raw)
    except (TypeError, ValueError):
        configured = DEFAULT_WORKERS
    return max(1, min(MAX_WORKERS, requested, configured))


def _failure_scope(
    audit_rows: Iterable[Mapping[str, Any]],
    selected: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Return only targets implicated by FAILED audit rows.

    A failure that cannot be mapped safely to a stock/industry returns the whole
    workset.  That fallback is intentional: optimization must never reduce
    evidence coverage.
    """
    rows = [dict(row) for row in selected]
    failed = [
        dict(row)
        for row in audit_rows
        if str(row.get("status") or "").upper() == "FAILED"
    ]
    if not failed:
        return []

    failed_codes = {core._code(row.get("code")) for row in failed if core._code(row.get("code"))}
    failed_industries = {
        str(row.get("industry") or "").strip()
        for row in failed
        if str(row.get("industry") or "").strip()
    }
    if not failed_codes and not failed_industries:
        return rows

    scoped: list[dict[str, Any]] = []
    for row in rows:
        code = core._code(row.get("code"))
        industry = str(row.get("normalized_industry") or row.get("industry") or "").strip()
        if code in failed_codes or industry in failed_industries:
            scoped.append(row)

    # If audit identifiers do not map back to the workset, preserve the old
    # all-target retry rather than risk losing evidence.
    return scoped or rows


def collect_with_selective_retry(
    *,
    selected: list[Mapping[str, Any]],
    as_of: date,
    cache_dir: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Same two-attempt contract as core, but retry only failed target scope."""
    all_industry: list[dict[str, Any]] = []
    all_company: list[dict[str, Any]] = []
    all_audit: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []

    attempt_rows = [dict(row) for row in selected]
    for attempt in range(1, core.MAX_COLLECTION_ATTEMPTS + 1):
        if not attempt_rows:
            break
        industry, company, audit, summary = _original_auto_evidence(
            priority_rows=attempt_rows,
            as_of=as_of,
            cache_dir=cache_dir / f"attempt-{attempt}",
            max_companies=max(1, len(attempt_rows)),
        )
        all_industry.extend(industry)
        all_company.extend(company)
        all_audit.extend(audit)
        enriched = dict(summary)
        enriched["requested_target_count"] = len(attempt_rows)
        summaries.append(enriched)
        if int(summary.get("failed_count") or 0) == 0:
            break
        attempt_rows = _failure_scope(audit, selected)

    industry_unique = core._dedupe(all_industry)
    company_unique = core._dedupe(all_company)
    last = summaries[-1] if summaries else {}
    final_summary = {
        "collection_attempt_count": len(summaries),
        "max_collection_attempts": core.MAX_COLLECTION_ATTEMPTS,
        "attempts": summaries,
        "unique_industry_evidence_count": len(industry_unique),
        "unique_company_evidence_count": len(company_unique),
        "unique_evidence_count": len(industry_unique) + len(company_unique),
        "final_failed_count": int(last.get("failed_count") or 0),
        "final_missing_count": int(last.get("missing_count") or 0),
        "bounded_retry_exhausted": bool(
            len(summaries) == core.MAX_COLLECTION_ATTEMPTS
            and int(last.get("failed_count") or 0) > 0
        ),
        "retry_scope_optimized": True,
        "quality_contract_unchanged": True,
    }
    return industry_unique, company_unique, all_audit, final_summary


def _shards(rows: list[dict[str, Any]], workers: int) -> list[list[dict[str, Any]]]:
    result: list[list[dict[str, Any]]] = [[] for _ in range(workers)]
    for index, row in enumerate(rows):
        result[index % workers].append(row)
    return [chunk for chunk in result if chunk]


def collect_predictability_parallel(
    *,
    priority_rows: Iterable[Mapping[str, Any]],
    as_of: date,
    timeout: int = 20,
) -> list[dict[str, Any]]:
    """Run the unchanged strict collector in independent bounded shards."""
    selected = [dict(row) for row in priority_rows if core._code(row.get("code"))]
    workers = _worker_count(len(selected))
    if workers <= 1:
        return _original_predictability(priority_rows=selected, as_of=as_of, timeout=timeout)

    chunks = _shards(selected, workers)
    outputs: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="genge-predictability") as pool:
        futures = {
            pool.submit(
                _original_predictability,
                priority_rows=chunk,
                as_of=as_of,
                timeout=timeout,
            ): tuple(core._code(row.get("code")) for row in chunk)
            for chunk in chunks
        }
        for future in as_completed(futures):
            # Deliberately let exceptions propagate.  Fail-closed is safer than
            # silently converting a collector failure into fabricated context.
            outputs.extend(future.result())

    order = {core._code(row.get("code")): i for i, row in enumerate(selected)}
    outputs.sort(key=lambda row: (order.get(core._code(row.get("code")), 10**9), core._code(row.get("code"))))
    return outputs


def install_runtime_optimizations() -> None:
    """Patch collection scheduling only; all gate logic stays in core."""
    core._collect_with_bounded_retry = collect_with_selective_retry
    core.collect_multi_year_predictability_evidence = collect_predictability_parallel


def main() -> int:
    """Install scheduling optimizations, then delegate CLI parsing to core."""
    install_runtime_optimizations()
    return core.main()


if __name__ == "__main__":
    raise SystemExit(main())
