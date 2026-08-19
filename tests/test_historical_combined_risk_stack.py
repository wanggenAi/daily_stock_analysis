from datetime import date

import pandas as pd

from src.strategies.genge_opportunity_discovery.historical_systemic_index_guard import (
    SystemicExposurePolicy,
    apply_systemic_overlay,
)


def test_systemic_leg_changes_exposure_only_next_session():
    days = [date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 4)]
    base = pd.Series([1.0, 0.9, 0.81], index=pd.Index(days, name="date"), dtype=float)
    features = {
        "A": {
            days[0]: {"above_ma60": True, "above_ma120": True, "ret5_pct": 0.0, "ret20_pct": 0.0, "dd60_pct": 0.0},
            days[1]: {"above_ma60": False, "above_ma120": False, "ret5_pct": -8.0, "ret20_pct": -10.0, "dd60_pct": -15.0},
            days[2]: {"above_ma60": False, "above_ma120": False, "ret5_pct": -8.0, "ret20_pct": -10.0, "dd60_pct": -15.0},
        },
        "B": {
            days[0]: {"above_ma60": True, "above_ma120": True, "ret5_pct": 0.0, "ret20_pct": 0.0, "dd60_pct": 0.0},
            days[1]: {"above_ma60": False, "above_ma120": False, "ret5_pct": -8.0, "ret20_pct": -10.0, "dd60_pct": -15.0},
            days[2]: {"above_ma60": False, "above_ma120": False, "ret5_pct": -8.0, "ret20_pct": -10.0, "dd60_pct": -15.0},
        },
    }
    policy = SystemicExposurePolicy(
        "fixture", green_fraction=1.0, yellow_fraction=1.0, red_fraction=0.5,
        unknown_fraction=1.0, rebalance_cost_bps=0.0,
    )
    curve, rows, _ = apply_systemic_overlay(base, feature_maps=features, policy=policy)
    # Day 2's -10% return still uses the GREEN decision from day 1.  Day 2's
    # RED close can affect only day 3, whose -10% base return is reduced to -5%.
    assert round(float(curve.iloc[1]), 6) == 0.9
    assert round(float(curve.iloc[2]), 6) == 0.855
    assert rows[1]["status"] == "RED"
    assert rows[1]["exposure_used"] == 1.0
    assert rows[1]["next_session_target_exposure"] == 0.5
    assert rows[2]["exposure_used"] == 0.5
