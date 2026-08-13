from __future__ import annotations

from datetime import date

from src.strategies.genge_opportunity_discovery.evidence_collectors import complete_material_event_pagination as pagination


def test_wide_truncation_splits_to_complete_leaf_windows():
    calls = []
    start = date(2024, 8, 13)
    end = date(2026, 8, 13)

    def query(window_start, window_end):
        calls.append((window_start, window_end))
        if window_start == start and window_end == end:
            return [], {
                "pages_fetched": 20,
                "reported_total": 700,
                "query_error": "",
                "truncated": True,
            }
        return [{
            "url": f"{window_start.isoformat()}-{window_end.isoformat()}",
            "publish_date": window_end.isoformat(),
        }], {
            "pages_fetched": 3,
            "reported_total": 50,
            "query_error": "",
            "truncated": False,
        }

    rows, meta = pagination._adaptive_partition_query(
        start_date=start, end_date=end, query_window=query,
    )

    assert len(calls) == 3
    assert len(rows) == 2
    assert meta["truncated"] is False
    assert meta["query_error"] == ""
    assert meta["partition_split_count"] == 1
    assert meta["pages_fetched"] == 26


def test_single_day_truncation_stays_incomplete():
    target = date(2026, 8, 13)

    def query(window_start, window_end):
        assert window_start == window_end == target
        return [{"url": "partial", "publish_date": target.isoformat()}], {
            "pages_fetched": 20,
            "reported_total": 900,
            "query_error": "",
            "truncated": True,
        }

    rows, meta = pagination._adaptive_partition_query(
        start_date=target, end_date=target, query_window=query,
    )

    assert len(rows) == 1
    assert meta["truncated"] is True
    assert "single_day_truncated" in meta["query_error"]


def test_query_error_stays_incomplete_and_is_not_split():
    calls = 0

    def query(window_start, window_end):
        nonlocal calls
        calls += 1
        return [{"url": "partial", "publish_date": window_end.isoformat()}], {
            "pages_fetched": 4,
            "reported_total": 200,
            "query_error": "provider_error",
            "truncated": True,
        }

    rows, meta = pagination._adaptive_partition_query(
        start_date=date(2026, 1, 1),
        end_date=date(2026, 8, 13),
        query_window=query,
    )

    assert calls == 1
    assert len(rows) == 1
    assert meta["truncated"] is True
    assert "query_error" in meta["query_error"]


def test_install_replaces_only_provider_pagination(monkeypatch):
    base = pagination.base
    old_cninfo = base._query_cninfo_material_events
    old_sse = base._query_sse_material_events
    try:
        pagination.install()
        assert base._query_cninfo_material_events is pagination.query_cninfo_material_events_complete
        assert base._query_sse_material_events is pagination.query_sse_material_events_complete
        assert callable(base.collect_company_material_events)
    finally:
        monkeypatch.setattr(base, "_query_cninfo_material_events", old_cninfo)
        monkeypatch.setattr(base, "_query_sse_material_events", old_sse)
