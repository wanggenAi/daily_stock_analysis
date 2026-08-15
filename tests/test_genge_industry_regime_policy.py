from __future__ import annotations

from src.strategies.genge_opportunity_discovery import industry_regime_policy


def _member(
    *,
    industry: str,
    return_1d: float,
    rs20: float,
    rs60: float,
    above_ma20: bool = True,
    above_ma60: bool = True,
    state: str = "NEUTRAL",
) -> dict[str, object]:
    return {
        "industry": industry,
        "return_1d_pct": return_1d,
        "relative_strength_20d": rs20,
        "relative_strength_60d": rs60,
        "above_ma20": above_ma20,
        "above_ma60": above_ma60,
        "price_volume_state": state,
    }


def test_durable_relative_strength_can_make_industry_strong() -> None:
    rows = [
        _member(industry="LEADER", return_1d=0.5, rs20=8.0, rs60=15.0)
        for _ in range(10)
    ]

    regime = industry_regime_policy.build_industry_regimes(rows)["LEADER"]

    assert regime["status"] == "STRONG"
    assert regime["median_relative_strength_20d"] == 8.0
    assert regime["median_relative_strength_60d"] == 15.0
    assert regime["above_ma60_ratio"] == 1.0
    assert regime["rule_version"] == industry_regime_policy.RULE_VERSION


def test_one_day_bounce_does_not_hide_weak_multi_horizon_structure() -> None:
    rows = [
        _member(
            industry="LAGGARD",
            return_1d=1.0,
            rs20=-10.0,
            rs60=-15.0,
            above_ma20=False,
            above_ma60=False,
        )
        for _ in range(10)
    ]

    regime = industry_regime_policy.build_industry_regimes(rows)["LAGGARD"]

    assert regime["status"] in {"WEAK", "CRISIS"}
    assert regime["relative_strength_score"] < 30.0


def test_missing_relative_strength_is_neutral_not_synthetic_strength() -> None:
    rows = [
        {
            "industry": "NO_RS",
            "return_1d_pct": 0.0,
            "above_ma20": False,
            "above_ma60": False,
            "price_volume_state": "NEUTRAL",
        }
        for _ in range(10)
    ]

    regime = industry_regime_policy.build_industry_regimes(rows)["NO_RS"]

    assert regime["relative_strength_score"] == 50.0
    assert regime["status"] != "STRONG"
