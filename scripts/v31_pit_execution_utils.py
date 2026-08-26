from __future__ import annotations

"""Execution-only utilities shared by PIT backtest audits.

These helpers deliberately do not change any GenGe valuation, BUY, SELL, or
confidence thresholds.  They only define how sparse per-symbol trading dates
are aligned onto a union calendar.
"""

from collections.abc import Iterable

import pandas as pd


def align_execution_panel(
    panels: dict[str, pd.DataFrame],
    codes: Iterable[str],
    fields: list[str],
    *,
    start: pd.Timestamp | None = None,
    end: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Align sparse symbol panels without manufacturing returns or trades.

    Contract:
    - state/information fields may be forward-filled for marking/research;
    - ``ret`` is never forward-filled: a missing quote day contributes 0;
    - ``tradable_today`` is true only when that symbol has an observed, valid
      close in its original panel on that exact date.

    Source ``ret`` is assumed to have been calculated between consecutive
    *observed* closes.  Therefore the first quote after a suspension carries
    the cumulative move exactly once.
    """

    codes = list(codes)
    frames: list[pd.DataFrame] = []
    for code in codes:
        source = panels[code].copy()
        source["date"] = pd.to_datetime(source["date"])
        source = source.sort_values("date").drop_duplicates("date", keep="last").set_index("date")
        missing = [field for field in fields if field not in source.columns]
        if missing:
            raise KeyError(f"{code} missing execution fields: {missing}")

        frame = source[fields].copy()
        frame["tradable_today"] = pd.to_numeric(source["close"], errors="coerce").notna()
        frame.columns = pd.MultiIndex.from_product([[code], frame.columns])
        frames.append(frame)

    if not frames:
        return pd.DataFrame()

    aligned = pd.concat(frames, axis=1).sort_index()
    if start is not None:
        aligned = aligned[aligned.index >= pd.Timestamp(start)]
    if end is not None:
        aligned = aligned[aligned.index <= pd.Timestamp(end)]

    for code in codes:
        # Preserve exact-day observability before filling state fields.
        tradable = aligned[(code, "tradable_today")].fillna(False).astype(bool)
        for field in fields:
            column = (code, field)
            if field == "ret":
                aligned[column] = pd.to_numeric(aligned[column], errors="coerce").fillna(0.0)
            else:
                aligned[column] = aligned[column].ffill()
        aligned[(code, "tradable_today")] = tradable

    return aligned


def cash_constrained_targets(
    weights: dict[str, float],
    raw_targets: dict[str, float],
    tradable: dict[str, bool],
) -> dict[str, float]:
    """Execute sells first, then scale only tradable positive buy requests.

    A non-tradable symbol's weight is preserved exactly.  This prevents a
    stale month-end quote from creating a synthetic buy or sell.
    """

    targets = dict(weights)

    # Explicit executable sells first.
    for code, current in weights.items():
        if tradable.get(code, False) and raw_targets.get(code, current) < current:
            targets[code] = raw_targets[code]

    available_cash = max(0.0, 1.0 - sum(targets.values()))
    requests = {
        code: max(0.0, raw_targets.get(code, current) - targets[code])
        if tradable.get(code, False)
        else 0.0
        for code, current in weights.items()
    }
    total_requested = sum(requests.values())
    scale = min(1.0, available_cash / total_requested) if total_requested > 0 else 0.0
    for code in targets:
        targets[code] += requests[code] * scale

    return targets
