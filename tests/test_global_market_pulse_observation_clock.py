from datetime import datetime, timezone

from tools.run_global_market_pulse import _normalize_daily_commodity_observation_times


def test_date_only_commodity_bar_never_claims_future_observation_and_cannot_dominate_coverage_clock():
    now = datetime(2026, 10, 12, 20, 17, tzinfo=timezone.utc)
    pulse = {
        "series": {
            "COPPER": {
                "status": "OK",
                "family": "COMMODITY",
                "market_date": "2026-10-12",
                "latest_at": "2026-10-12T23:59:00+00:00",
                "age_hours": 0.0,
                "freshness": "FRESH",
            },
            "BTC": {
                "status": "OK",
                "family": "RISK_APPETITE_PROXY",
                "market_date": "2026-10-12",
                "latest_at": "2026-10-12T20:00:00+00:00",
                "age_hours": 0.28,
                "freshness": "FRESH",
            },
        },
        "coverage": {
            "status": "OK",
            "latest_observation_at": "2026-10-12T23:59:00+00:00",
        },
    }

    normalized = _normalize_daily_commodity_observation_times(pulse, now=now)

    copper = normalized["series"]["COPPER"]
    assert copper["latest_at"] == "2026-10-12T00:00:00+00:00"
    assert copper["timestamp_precision"] == "DATE_ONLY_CONSERVATIVE_UTC_START"
    assert copper["freshness"] == "LAST_VALID_MARKET_OBSERVATION"
    assert normalized["coverage"]["latest_observation_at"] == "2026-10-12T20:00:00+00:00"
    assert normalized["coverage"]["observation_clock_invariant"] == "NO_FUTURE_OBSERVATION"
    assert datetime.fromisoformat(normalized["coverage"]["latest_observation_at"]) <= now
