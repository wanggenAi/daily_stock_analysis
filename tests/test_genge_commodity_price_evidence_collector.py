from src.strategies.genge_opportunity_discovery.commodity_price_evidence_collector import collect, summarize_series


def test_series_summary_computes_one_and_five_day_moves():
    rows = [
        {"date": "2026-08-20", "close": 100.0},
        {"date": "2026-08-21", "close": 101.0},
        {"date": "2026-08-24", "close": 102.0},
        {"date": "2026-08-25", "close": 103.0},
        {"date": "2026-08-26", "close": 104.0},
        {"date": "2026-08-27", "close": 106.0},
    ]
    summary = summarize_series(rows)
    assert summary["status"] == "OK"
    assert summary["latest_close"] == 106.0
    assert summary["change_1d_pct"] == round((106.0 / 104.0 - 1.0) * 100, 4)
    assert summary["change_5d_pct"] == 6.0


def test_connected_benchmark_without_exposure_does_not_invent_stock_evidence():
    overlay = {"rows": [{"code": "601899", "name": "紫金矿业", "formal_action": "WAIT"}]}
    config = {
        "benchmarks": {"COPPER": {"label": "Copper", "symbol": "hg.f"}},
        "security_exposures": {},
    }
    fixture = [
        {"date": "2026-08-26", "close": 100.0},
        {"date": "2026-08-27", "close": 105.0},
    ]
    events, status = collect(overlay, config, series_fetcher=lambda symbol: fixture)
    assert events == []
    assert status["status"] == "CONNECTED"
    assert status["mapping_status"] == "CONNECTED_NO_EVIDENCE_BACKED_SECURITY_EXPOSURES"
    assert status["formal_action_eligible"] is False
    assert status["no_auto_trade"] is True


def test_explicit_exposure_mapping_can_emit_research_only_event():
    overlay = {"rows": [{"code": "600001", "name": "fixture resource", "formal_action": "WAIT"}]}
    config = {
        "benchmarks": {"COPPER": {"label": "Copper", "symbol": "hg.f"}},
        "security_exposures": {
            "600001": [{"benchmark_id": "COPPER", "exposure_direction": "PRODUCER_POSITIVE"}]
        },
    }
    fixture = [
        {"date": "2026-08-21", "close": 100.0},
        {"date": "2026-08-27", "close": 106.0},
    ]
    events, status = collect(overlay, config, series_fetcher=lambda symbol: fixture)
    assert status["mapped_workset_security_count"] == 1
    assert len(events) == 1
    assert events[0]["direction"] == "STRENGTHENING"
    assert events[0]["materiality"] == "MEDIUM"
    assert events[0]["sell_relevance"] == "RESEARCH_ONLY"
