"""Multi-horizon industry regime scoring for All-A opportunity discovery.

The legacy industry regime was dominated by one-day breadth and MA20
participation.  This policy keeps those observable safety signals but adds
20/60-session relative strength and MA60 participation so the research funnel
can distinguish a durable leading industry from a one-day bounce.

No vendor-labelled fund-flow field is used and no unavailable institutional or
catalyst metric is fabricated.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from typing import Any

from src.strategies.genge_opportunity_discovery import all_a_full_scan as core
from src.strategies.genge_opportunity_discovery import real_world_signals as base


RULE_VERSION = "industry_regime_v2_multihorizon_rs"
REPORT_COLUMNS = (
    "above_ma60_ratio",
    "median_relative_strength_20d",
    "median_relative_strength_60d",
    "relative_strength_score",
    "rule_version",
)


def _ratio(members: list[Mapping[str, Any]], field: str) -> float:
    if not members:
        return 0.0
    return sum(bool(row.get(field)) for row in members) / len(members)


def build_industry_regimes(
    rows: list[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        industry = str(row.get("industry") or "").strip()
        if industry:
            grouped[industry].append(row)

    result: dict[str, dict[str, Any]] = {}
    for industry, members in grouped.items():
        returns = [base._number(row.get("return_1d_pct")) for row in members]
        returns = [value for value in returns if value is not None]
        count = len(returns)
        advance_ratio = (
            0.5 if not count else sum(value > 0 for value in returns) / count
        )
        median_return = base._median(returns) or 0.0
        above_ma20 = _ratio(members, "above_ma20")
        above_ma60 = _ratio(members, "above_ma60")
        distribution = sum(
            str(row.get("price_volume_state"))
            in {"DISTRIBUTION", "CAPITULATION_RISK"}
            for row in members
        ) / len(members)

        rs20_values = [
            base._number(row.get("relative_strength_20d")) for row in members
        ]
        rs20_values = [value for value in rs20_values if value is not None]
        rs60_values = [
            base._number(row.get("relative_strength_60d")) for row in members
        ]
        rs60_values = [value for value in rs60_values if value is not None]
        median_rs20 = base._median(rs20_values)
        median_rs60 = base._median(rs60_values)

        rs_components: list[tuple[float, float]] = []
        if median_rs20 is not None:
            rs_components.append((base._clamp(50.0 + median_rs20 * 4.0), 0.55))
        if median_rs60 is not None:
            rs_components.append((base._clamp(50.0 + median_rs60 * 2.0), 0.45))
        if rs_components:
            weight_total = sum(weight for _, weight in rs_components)
            rs_score = sum(score * weight for score, weight in rs_components) / weight_total
        else:
            # Missing multi-horizon evidence is neutral, never synthetic strength.
            rs_score = 50.0

        score = (
            advance_ratio * 15.0
            + base._clamp(50.0 + median_return * 12.0) * 0.15
            + above_ma20 * 15.0
            + above_ma60 * 10.0
            + base._clamp(100.0 - distribution * 180.0) * 0.15
            + rs_score * 0.30
        )
        crisis = count >= 5 and (
            (advance_ratio < 0.25 and median_return <= -2.0)
            or distribution >= 0.35
            or (
                median_rs20 is not None
                and median_rs60 is not None
                and median_rs20 <= -8.0
                and median_rs60 <= -12.0
            )
        )
        status = (
            "CRISIS" if crisis
            else "WEAK" if score < 45.0
            else "STRONG" if score >= 62.0
            else "NEUTRAL"
        )
        result[industry] = {
            "industry": industry,
            "status": status,
            "score": round(base._clamp(score), 2),
            "sample_count": count,
            "advance_ratio": round(advance_ratio, 4),
            "median_return_1d_pct": round(median_return, 4),
            "above_ma20_ratio": round(above_ma20, 4),
            "above_ma60_ratio": round(above_ma60, 4),
            "distribution_ratio": round(distribution, 4),
            "median_relative_strength_20d": (
                None if median_rs20 is None else round(median_rs20, 4)
            ),
            "median_relative_strength_60d": (
                None if median_rs60 is None else round(median_rs60, 4)
            ),
            "relative_strength_score": round(rs_score, 2),
            "rule_version": RULE_VERSION,
        }
    return result


def install() -> None:
    """Install the multi-horizon scorer into the already imported scan module."""

    core.build_industry_regimes = build_industry_regimes
    for column in REPORT_COLUMNS:
        if column not in core.INDUSTRY_REGIME_COLUMNS:
            core.INDUSTRY_REGIME_COLUMNS.append(column)
