from __future__ import annotations

from datetime import date

from src.strategies.genge_opportunity_discovery import v31_deep_gap_closure_optimized as opt


def _row(code: str, industry: str = "I1") -> dict[str, str]:
    return {"code": code, "industry": industry, "normalized_industry": industry}


def test_selective_retry_retries_only_failed_scope(monkeypatch, tmp_path):
    calls = []

    def fake_collect(*, priority_rows, as_of, cache_dir, max_companies):
        codes = [row["code"] for row in priority_rows]
        calls.append(codes)
        if len(calls) == 1:
            return (
                [{"industry": "I1", "content_hash": "i1"}],
                [{"code": "000001", "content_hash": "c1"}],
                [
                    {"status": "OK", "code": "000001"},
                    {"status": "FAILED", "code": "000002"},
                ],
                {"failed_count": 1, "missing_count": 0},
            )
        return (
            [],
            [{"code": "000002", "content_hash": "c2"}],
            [{"status": "OK", "code": "000002"}],
            {"failed_count": 0, "missing_count": 0},
        )

    monkeypatch.setattr(opt, "_original_auto_evidence", fake_collect)
    industry, company, audit, summary = opt.collect_with_selective_retry(
        selected=[_row("000001"), _row("000002")],
        as_of=date(2026, 9, 11),
        cache_dir=tmp_path,
    )

    assert calls == [["000001", "000002"], ["000002"]]
    assert {row.get("code") for row in company} == {"000001", "000002"}
    assert len(industry) == 1
    assert len(audit) == 3
    assert summary["collection_attempt_count"] == 2
    assert summary["final_failed_count"] == 0
    assert summary["retry_scope_optimized"] is True
    assert summary["quality_contract_unchanged"] is True


def test_ambiguous_failure_scope_falls_back_to_full_retry(monkeypatch, tmp_path):
    calls = []

    def fake_collect(*, priority_rows, as_of, cache_dir, max_companies):
        codes = [row["code"] for row in priority_rows]
        calls.append(codes)
        if len(calls) == 1:
            return [], [], [{"status": "FAILED", "source": "unscoped"}], {"failed_count": 1}
        return [], [], [], {"failed_count": 0}

    monkeypatch.setattr(opt, "_original_auto_evidence", fake_collect)
    opt.collect_with_selective_retry(
        selected=[_row("000001"), _row("000002")],
        as_of=date(2026, 9, 11),
        cache_dir=tmp_path,
    )
    assert calls == [["000001", "000002"], ["000001", "000002"]]


def test_predictability_parallel_uses_same_original_collector_and_is_deterministic(monkeypatch):
    calls = []

    def fake_predictability(*, priority_rows, as_of, timeout=20):
        codes = [row["code"] for row in priority_rows]
        calls.append(codes)
        return [
            {
                "code": code,
                "predictability_classification": "UNKNOWN",
                "reason_code": "TEST_UNRESOLVED",
                "adopted_for_gate": False,
            }
            for code in reversed(codes)
        ]

    monkeypatch.setattr(opt, "_original_predictability", fake_predictability)
    monkeypatch.setenv("GEN_GE_DEEP_EVIDENCE_WORKERS", "3")
    rows = [_row("000003"), _row("000001"), _row("000004"), _row("000002")]
    result = opt.collect_predictability_parallel(
        priority_rows=rows,
        as_of=date(2026, 9, 11),
        timeout=17,
    )

    assert sorted(code for chunk in calls for code in chunk) == sorted(row["code"] for row in rows)
    assert [row["code"] for row in result] == [row["code"] for row in rows]
    assert all(row["predictability_classification"] == "UNKNOWN" for row in result)


def test_install_runtime_optimizations_changes_scheduling_not_contract(monkeypatch):
    original_retry = opt.core._collect_with_bounded_retry
    original_predictability = opt.core.collect_multi_year_predictability_evidence
    try:
        opt.install_runtime_optimizations()
        assert opt.core._collect_with_bounded_retry is opt.collect_with_selective_retry
        assert opt.core.collect_multi_year_predictability_evidence is opt.collect_predictability_parallel
        assert opt.core.MAX_COLLECTION_ATTEMPTS == 2
        assert opt.core.CONTRACT == "GEN_GE_V31_DEEP_GAP_CLOSURE_V1"
        assert set(opt.core.GATES) == {
            "predictability",
            "long_term_demand",
            "moat",
            "financial_safety",
            "earnings_authenticity",
        }
    finally:
        monkeypatch.setattr(opt.core, "_collect_with_bounded_retry", original_retry)
        monkeypatch.setattr(opt.core, "collect_multi_year_predictability_evidence", original_predictability)
