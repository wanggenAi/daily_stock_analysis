from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys

import pandas as pd

from src.era_radar.global_market_pulse import (
    build_global_market_pulse,
    build_pre_open_intelligence,
    build_security_transmission,
    persist_if_changed,
    summarize_history,
)


ROOT = Path(__file__).resolve().parents[1]


def _frame(values, start="2026-10-06T00:00:00Z"):
    index = pd.date_range(start, periods=len(values), freq="h")
    return pd.DataFrame({"Close": values}, index=index)


def _holiday_frame():
    index = pd.to_datetime(
        [
            "2026-09-30T06:00:00Z",
            "2026-09-30T07:00:00Z",
            "2026-10-01T07:00:00Z",
            "2026-10-05T07:00:00Z",
            "2026-10-07T06:00:00Z",
        ],
        utc=True,
    )
    return pd.DataFrame({"Close": [100.0, 100.0, 101.0, 103.0, 104.0]}, index=index)


def _commodity_config():
    return {
        "benchmarks": {
            "COPPER": {"label": "Copper", "symbol": "hg.f"},
            "GOLD": {"label": "Gold", "symbol": "gc.f"},
        },
        "security_exposures": {
            "603993": [
                {"benchmark_id": "COPPER", "exposure_direction": "PRODUCER_POSITIVE", "evidence_ref": "issuer-primary"},
                {"benchmark_id": "GOLD", "exposure_direction": "PRODUCER_POSITIVE", "evidence_ref": "issuer-primary"},
            ]
        },
    }


def _commodity_fetcher(benchmark_id, _symbol):
    rows = [
        {"date": "2026-09-29", "close": 99.0},
        {"date": "2026-09-30", "close": 100.0},
        {"date": "2026-10-05", "close": 101.0},
        {"date": "2026-10-06", "close": 102.0},
        {"date": "2026-10-07", "close": 104.0 if benchmark_id == "COPPER" else 97.0},
    ]
    return rows, "shared_commodity_collector_test", []


def test_global_pulse_runner_imports_from_tools_entrypoint():
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "run_global_market_pulse.py"), "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "global market pulse" in result.stdout.lower()


def test_global_pulse_does_not_require_a_share_market_open_and_keeps_independent_dates():
    instruments = (
        {"id": "SP500", "symbol": "SP", "family": "RISK_EQUITY", "critical": True},
        {"id": "NASDAQ", "symbol": "NQ", "family": "RISK_EQUITY", "critical": True},
    )
    data = {"SP": _holiday_frame(), "NQ": _holiday_frame()}
    pulse = build_global_market_pulse(
        instruments=instruments,
        history_fetcher=lambda symbol: data[symbol],
        commodity_config=_commodity_config(),
        commodity_series_fetcher=_commodity_fetcher,
        a_share_last_trade_date="2026-09-30",
        now=datetime(2026, 10, 7, 8, tzinfo=timezone.utc),
    )
    assert pulse["clock"] == "GLOBAL_MARKET_INDEPENDENT_OF_A_SHARE_CALENDAR"
    assert pulse["a_share_market_clock"]["last_valid_trade_date"] == "2026-09-30"
    assert pulse["global_research_clock"]["continues_during_a_share_holidays"] is True
    assert pulse["series"]["SP500"]["market_date"] == "2026-10-07"
    assert pulse["series"]["SP500"]["since_last_a_share_close_pct"] == 4.0
    assert pulse["coverage"]["status"] == "OK"
    assert pulse["formal_trading_authority"] is False
    assert pulse["formal_action_eligible"] is False
    assert pulse["unknown_is_pass"] is False
    assert pulse["no_auto_trade"] is True


def test_partial_source_failure_is_explicit_not_silently_promoted():
    instruments = (
        {"id": "SP500", "symbol": "SP", "family": "RISK_EQUITY", "critical": True},
        {"id": "NASDAQ", "symbol": "NQ", "family": "RISK_EQUITY", "critical": True},
    )

    def fetch(symbol):
        if symbol == "NQ":
            raise RuntimeError("provider down")
        return _holiday_frame()

    pulse = build_global_market_pulse(
        instruments=instruments,
        history_fetcher=fetch,
        commodity_config=_commodity_config(),
        commodity_series_fetcher=_commodity_fetcher,
        a_share_last_trade_date="2026-09-30",
        now=datetime(2026, 10, 7, 8, tzinfo=timezone.utc),
    )
    assert pulse["coverage"]["status"] == "PARTIAL"
    assert pulse["series"]["NASDAQ"]["status"].startswith("FETCH_ERROR")
    assert pulse["series"]["NASDAQ"]["freshness"] == "UNAVAILABLE"


def test_603993_receives_only_explicit_copper_gold_transmission_and_unmapped_security_does_not():
    series = {
        "COPPER": {"status": "OK", "since_last_a_share_close_pct": 4.0, "change_24h_pct": 2.0, "change_5d_pct": 4.0, "freshness": "FRESH", "market_date": "2026-10-07", "provider": "shared"},
        "GOLD": {"status": "OK", "since_last_a_share_close_pct": -3.0, "change_24h_pct": -1.0, "change_5d_pct": -3.0, "freshness": "FRESH", "market_date": "2026-10-07", "provider": "shared"},
    }
    rows = build_security_transmission(series, _commodity_config(), security_names={"603993": "洛阳钼业", "600000": "不相关"})
    assert len(rows) == 1
    row = rows[0]
    assert row["code"] == "603993"
    assert row["name"] == "洛阳钼业"
    assert row["direction"] == "MIXED"
    assert row["relevant_global_factors"] == ["COPPER", "GOLD"]
    assert row["formal_action_eligible"] is False
    assert row["automatic_promotion_allowed"] is False
    assert row["no_auto_trade"] is True
    assert all(item["evidence_ref"] == "issuer-primary" for item in row["factors"])


def test_pre_open_intelligence_accumulates_since_last_a_share_close():
    series = {
        "SP500": {"status": "OK", "since_last_a_share_close_pct": -2.5, "change_24h_pct": -0.5, "change_5d_pct": -2.5, "market_date": "2026-10-07", "freshness": "LAST_VALID_MARKET_OBSERVATION"},
        "NASDAQ": {"status": "OK", "since_last_a_share_close_pct": -3.0, "change_24h_pct": -0.7, "change_5d_pct": -3.0, "market_date": "2026-10-07", "freshness": "LAST_VALID_MARKET_OBSERVATION"},
        "VIX": {"status": "OK", "since_last_a_share_close_pct": 18.0, "change_24h_pct": 4.0, "change_5d_pct": 18.0, "market_date": "2026-10-07", "freshness": "FRESH"},
        "COPPER": {"status": "OK", "since_last_a_share_close_pct": 3.2, "change_24h_pct": 0.3, "change_5d_pct": 3.2, "market_date": "2026-10-07", "freshness": "FRESH"},
    }
    pre = build_pre_open_intelligence(series, a_share_last_trade_date="2026-09-30")
    assert pre["status"] == "AVAILABLE"
    assert pre["holiday_gap_risk"] == "HIGH"
    assert "US_EQUITY_DRAWDOWN" in pre["holiday_gap_risk_flags"]
    assert "VOLATILITY_SPIKE" in pre["holiday_gap_risk_flags"]
    assert "COPPER_POSITIVE_ACCUMULATION" in pre["holiday_positive_flags"]
    assert pre["formal_action_eligible"] is False


def test_unavailable_macro_is_explicit_not_fabricated():
    pulse = build_global_market_pulse(
        instruments=(
            {"id": "SP500", "symbol": "SP", "family": "RISK_EQUITY", "critical": True},
            {"id": "NASDAQ", "symbol": "NQ", "family": "RISK_EQUITY", "critical": True},
        ),
        history_fetcher=lambda _symbol: _holiday_frame(),
        commodity_config=_commodity_config(),
        commodity_series_fetcher=_commodity_fetcher,
        a_share_last_trade_date="2026-09-30",
        now=datetime(2026, 10, 7, 8, tzinfo=timezone.utc),
    )
    assert pulse["series"]["US2Y"]["status"] == "UNAVAILABLE"
    assert pulse["series"]["US2Y"]["latest"] is None
    assert pulse["series"]["CURVE_2S10S"]["status"] == "UNAVAILABLE"


def test_semantic_persistence_ignores_observation_clock_only_change(tmp_path):
    payload = {
        "generated_at": "2026-10-07T00:00:00+00:00",
        "global_research_clock": {"observed_at": "2026-10-07T00:00:00+00:00"},
        "series": {"SP500": {"observed_at": "2026-10-07T00:00:00+00:00", "age_hours": 1.0, "latest": 100.0}},
        "coverage": {"status": "OK"},
        "no_auto_trade": True,
    }
    first = persist_if_changed(payload, tmp_path)
    later = json_clone(payload)
    later["generated_at"] = "2026-10-07T01:00:00+00:00"
    later["global_research_clock"]["observed_at"] = "2026-10-07T01:00:00+00:00"
    later["series"]["SP500"]["observed_at"] = "2026-10-07T01:00:00+00:00"
    later["series"]["SP500"]["age_hours"] = 2.0
    second = persist_if_changed(later, tmp_path)
    assert first["status"] == "UPDATED"
    assert second["status"] == "UNCHANGED"


def json_clone(value):
    import json
    return json.loads(json.dumps(value))


def test_summarize_history_uses_real_holiday_anchor_not_first_available_row():
    summary = summarize_history(
        _holiday_frame(),
        a_share_last_trade_date="2026-09-30",
        now=datetime(2026, 10, 7, 8, tzinfo=timezone.utc),
    )
    assert summary["status"] == "OK"
    assert summary["since_last_a_share_close_pct"] == 4.0
    assert summary["market_date"] == "2026-10-07"
    assert summary["freshness"] == "FRESH"
