from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from v31_pit_execution_utils import align_execution_panel, cash_constrained_targets


def _panel(dates: list[str], closes: list[float], rets: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.to_datetime(dates),
            "close": closes,
            "ret": rets,
            "ratio": [0.8] * len(dates),
        }
    )


def test_missing_union_date_has_zero_return_and_is_not_tradable() -> None:
    panels = {
        "A": _panel(
            ["2024-01-02", "2024-01-03", "2024-01-05"],
            [10.0, 11.0, 13.2],
            [0.0, 0.10, 0.20],
        ),
        "B": _panel(
            ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"],
            [20.0, 20.0, 20.0, 20.0],
            [0.0, 0.0, 0.0, 0.0],
        ),
    }

    aligned = align_execution_panel(panels, ["A", "B"], ["ret", "close", "ratio"])

    missing_day = pd.Timestamp("2024-01-04")
    resume_day = pd.Timestamp("2024-01-05")
    assert aligned.loc[missing_day, ("A", "ret")] == 0.0
    assert bool(aligned.loc[missing_day, ("A", "tradable_today")]) is False
    # Stateful close can be carried for marking, but cannot manufacture a trade.
    assert aligned.loc[missing_day, ("A", "close")] == 11.0
    # The cumulative move from the previous real quote is applied exactly once.
    assert aligned.loc[resume_day, ("A", "ret")] == 0.20
    assert bool(aligned.loc[resume_day, ("A", "tradable_today")]) is True


def test_nontradable_symbol_cannot_trade_on_stale_month_end() -> None:
    weights = {"A": 0.50, "B": 0.25}
    raw_targets = {"A": 0.00, "B": 0.50}
    tradable = {"A": False, "B": True}

    targets = cash_constrained_targets(weights, raw_targets, tradable)

    assert targets["A"] == 0.50
    assert targets["B"] == 0.50


def test_cash_scaling_never_turns_unrelated_position_into_a_sell() -> None:
    weights = {"A": 0.40, "B": 0.40, "C": 0.10}
    raw_targets = {"A": 0.40, "B": 0.70, "C": 0.30}
    tradable = {"A": True, "B": True, "C": True}

    targets = cash_constrained_targets(weights, raw_targets, tradable)

    assert targets["A"] == 0.40
    assert targets["B"] >= weights["B"]
    assert targets["C"] >= weights["C"]
    assert abs(sum(targets.values()) - 1.0) < 1e-12
