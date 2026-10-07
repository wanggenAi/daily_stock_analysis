from src.strategies.genge_opportunity_discovery.commodity_price_evidence_collector import (
    FALLBACK_PROVIDER,
    fetch_benchmark_series,
    collect,
)


def test_existing_commodity_collector_uses_explicit_fallback_when_stooq_is_insufficient():
    rows, provider, errors = fetch_benchmark_series(
        "COPPER",
        "hg.f",
        stooq_fetcher=lambda _symbol: [{"date": "2026-10-07", "close": 100.0}],
        fallback_fetcher=lambda symbol: [
            {"date": "2026-10-06", "close": 100.0},
            {"date": "2026-10-07", "close": 103.0},
        ],
    )
    assert provider == FALLBACK_PROVIDER
    assert rows[-1]["close"] == 103.0
    assert "STOOQ_INSUFFICIENT_SERIES" in errors


def test_collector_preserves_explicit_mapping_and_research_only_authority():
    overlay = {"rows": [{"code": "603993", "name": "洛阳钼业"}, {"code": "600000", "name": "无映射"}]}
    config = {
        "benchmarks": {"COPPER": {"label": "Copper", "symbol": "hg.f"}},
        "security_exposures": {
            "603993": [
                {"benchmark_id": "COPPER", "exposure_direction": "PRODUCER_POSITIVE", "evidence_ref": "issuer-primary"}
            ]
        },
    }
    events, status = collect(
        overlay,
        config,
        series_fetcher=lambda _symbol: [
            {"date": "2026-10-01", "close": 100.0},
            {"date": "2026-10-07", "close": 104.0},
        ],
    )
    assert status["status"] == "CONNECTED"
    assert status["benchmark_ok_count"] == 1
    assert status["formal_action_eligible"] is False
    assert status["automatic_promotion_allowed"] is False
    assert status["no_auto_trade"] is True
    assert [row["code"] for row in events] == ["603993"]
