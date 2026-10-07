from datetime import datetime, timezone

import pandas as pd

from src.era_radar.global_market_pulse import (
    build_global_market_pulse,
    build_security_transmission,
    persist_if_changed,
    summarize_history,
)


def _frame(values):
    index = pd.date_range("2026-10-06T00:00:00Z", periods=len(values), freq="h")
    return pd.DataFrame({"Close": values}, index=index)


def test_global_pulse_does_not_require_a_share_market_open():
    instruments = (
        {"id": "SP500", "symbol": "SP", "family": "RISK_EQUITY", "critical": True},
        {"id": "NASDAQ", "symbol": "NQ", "family": "RISK_EQUITY", "critical": True},
        {"id": "COPPER", "symbol": "CU", "family": "COMMODITY", "critical": True},
    )
    data = {
        "SP": _frame([100, 101, 103]),
        "NQ": _frame([100, 102, 104]),
        "CU": _frame([100, 103, 106]),
    }

    pulse = build_global_market_pulse(
        instruments=instruments,
        history_fetcher=lambda symbol: data[symbol],
        now=datetime(2026, 10, 7, 6, tzinfo=timezone.utc),
    )

    assert pulse["clock"] == "GLOBAL_MARKET_INDEPENDENT_OF_A_SHARE_CALENDAR"
    assert pulse["a_share_market_open_required"] is False
    assert pulse["coverage"]["status"] == "OK"
    assert pulse["formal_trading_authority"] is False
    assert pulse["formal_action_mutation_allowed"] is False
    assert pulse["no_auto_trade"] is True


def test_partial_source_failure_is_explicit_not_silently_promoted():
    instruments = (
        {"id": "SP500", "symbol": "SP", "family": "RISK_EQUITY", "critical": True},
        {"id": "NASDAQ", "symbol": "NQ", "family": "RISK_EQUITY", "critical": True},
        {"id": "COPPER", "symbol": "CU", "family": "COMMODITY", "critical": True},
        {"id": "WTI", "symbol": "OIL", "family": "COMMODITY", "critical": True},
    )

    def fetch(symbol):
        if symbol in {"NQ", "OIL"}:
            raise RuntimeError("provider down")
        return _frame([100, 101, 102])

    pulse = build_global_market_pulse(instruments=instruments, history_fetcher=fetch)
    assert pulse["coverage"]["status"] == "PARTIAL"
    assert pulse["coverage"]["ok_count"] == 2
    assert len(pulse["coverage"]["failures"]) == 2


def test_explicit_commodity_mapping_drives_research_only_transmission():
    series = {
        "COPPER": {"status": "OK", "change_24h_pct": 3.5},
        "GOLD": {"status": "OK", "change_24h_pct": 0.5},
    }
    config = {
        "security_exposures": {
            "603993": [
                {
                    "benchmark_id": "COPPER",
                    "exposure_direction": "PRODUCER_POSITIVE",
                    "evidence_ref": "issuer-primary",
                },
                {
                    "benchmark_id": "GOLD",
                    "exposure_direction": "PRODUCER_POSITIVE",
                    "evidence_ref": "issuer-primary",
                },
            ]
        }
    }
    rows = build_security_transmission(series, config, security_names={"603993": "洛阳钼业"})
    assert rows == [
        {
            "code": "603993",
            "name": "洛阳钼业",
            "signal": "FAVORABLE",
            "factors": [
                {
                    "factor_id": "COPPER",
                    "change_24h_pct": 3.5,
                    "direction": "FAVORABLE",
                    "material": True,
                    "evidence_ref": "issuer-primary",
                },
                {
                    "factor_id": "GOLD",
                    "change_24h_pct": 0.5,
                    "direction": "FAVORABLE",
                    "material": False,
                    "evidence_ref": "issuer-primary",
                },
            ],
            "authority": "RESEARCH_ONLY",
            "formal_action_mutation_allowed": False,
            "no_auto_trade": True,
        }
    ]


def test_semantic_persistence_ignores_generated_at_only_change(tmp_path):
    payload = {
        "generated_at": "2026-10-07T00:00:00+00:00",
        "coverage": {"status": "OK"},
        "no_auto_trade": True,
    }
    first = persist_if_changed(payload, tmp_path)
    later = {**payload, "generated_at": "2026-10-07T01:00:00+00:00"}
    second = persist_if_changed(later, tmp_path)
    assert first["status"] == "UPDATED"
    assert second["status"] == "UNCHANGED"


def test_summarize_history_uses_hourly_and_24h_anchors():
    frame = _frame([100.0] * 24 + [102.0, 103.0])
    summary = summarize_history(frame)
    assert summary["status"] == "OK"
    assert summary["change_1h_pct"] == round((103 / 102 - 1) * 100, 4)
    assert summary["change_24h_pct"] == 3.0
