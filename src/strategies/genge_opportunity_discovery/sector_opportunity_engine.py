"""Industry-first market opportunity discovery for the All-A universe.

This module turns stock-level point-in-time price/breadth features already
produced by the All-A scan into one auditable row per industry.  It is a
*discovery and research-priority* layer only:

* a strong or emerging industry is researched earlier;
* a weak industry remains visible instead of being deleted;
* an overheated industry is explicitly marked WATCH_AVOID_CHASE;
* sector strength can never create HARD_LOGIC_PASS, fair value, or a buy signal.

Structural industry logic and company-specific hard logic are verified later by
the evidence-first research engine.  This separation is deliberate: price
strength helps us avoid missing what the market is currently repricing, while
fundamental evidence prevents momentum from masquerading as investment logic.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

from .industry_coverage import UNKNOWN_INDUSTRY, find_latest_report


STATE_PRIORITY = {
    "EMERGING": 0,
    "LEADING": 1,
    "OVERHEATED": 2,
    "HEALTHY": 3,
    "NEUTRAL": 4,
    "WEAK": 5,
    "RISK_OFF": 6,
    "DATA_THIN": 7,
}

STATE_ACTION = {
    "EMERGING": "PRIORITY_RESEARCH",
    "LEADING": "PRIORITY_RESEARCH",
    "OVERHEATED": "WATCH_AVOID_CHASE",
    "HEALTHY": "RESEARCH",
    "NEUTRAL": "RESEARCH",
    "WEAK": "LOW_PRIORITY_RESEARCH",
    "RISK_OFF": "RISK_REVIEW",
    "DATA_THIN": "DATA_REVIEW",
}

OUTPUT_COLUMNS = [
    "sector_rank",
    "industry",
    "sector_opportunity_state",
    "sector_research_action",
    "sector_opportunity_score",
    "sample_count",
    "advance_ratio",
    "strong_advance_ratio",
    "median_return_1d_pct",
    "market_median_return_1d_pct",
    "excess_return_1d_pct",
    "median_return_5d_pct",
    "market_median_return_5d_pct",
    "excess_return_5d_pct",
    "median_return_10d_pct",
    "above_ma20_ratio",
    "above_ma60_ratio",
    "expanding_activity_ratio",
    "median_activity_ratio_20",
    "accumulation_ratio",
    "distribution_ratio",
    "limit_up_count",
    "limit_up_ratio",
    "sector_overheated",
    "sector_risk_off",
    "sector_strength_is_hard_logic",
    "formal_signal_eligible",
    "automatic_promotion_allowed",
    "no_auto_trade",
]


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def _median(values: Iterable[float | None], default: float = 0.0) -> float:
    clean = [float(value) for value in values if value is not None and math.isfinite(float(value))]
    return float(statistics.median(clean)) if clean else float(default)


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, float(value)))


def _industry(row: Mapping[str, Any]) -> str:
    return str(
        row.get("industry")
        or row.get("normalized_industry")
        or row.get("raw_industry")
        or UNKNOWN_INDUSTRY
    ).strip() or UNKNOWN_INDUSTRY


def _activity(row: Mapping[str, Any]) -> float | None:
    volume = _finite(row.get("volume_ratio_20"))
    amount = _finite(row.get("amount_ratio_20"))
    values = [value for value in (volume, amount) if value is not None]
    return max(values) if values else None


def _board_limit_threshold(row: Mapping[str, Any]) -> float:
    return 19.0 if str(row.get("board") or "").strip().upper() in {"STAR", "CHINEXT"} else 9.5


def _effective_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate by code while retaining blocked-but-trading names for breadth.

    Company hard blockers are intentionally irrelevant to sector breadth.  Rows
    explicitly excluded from the tradable universe (for example future listing
    or unresolved security type) do not participate in breadth calculations.
    """
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in rows:
        code = str(raw.get("code") or "").strip()
        if not code or code in seen:
            continue
        if str(raw.get("exclusion_reason") or "").strip():
            continue
        row = dict(raw)
        row["industry"] = _industry(row)
        result.append(row)
        seen.add(code)
    return result


def build_sector_opportunities(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    effective = _effective_rows(rows)
    if not effective:
        return []

    market_median_1d = _median(_finite(row.get("return_1d_pct")) for row in effective)
    market_median_5d = _median(_finite(row.get("return_5d_pct")) for row in effective)

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in effective:
        grouped[row["industry"]].append(row)

    output: list[dict[str, Any]] = []
    for industry, members in grouped.items():
        returns_1d = [_finite(row.get("return_1d_pct")) for row in members]
        valid_1d = [value for value in returns_1d if value is not None]
        returns_5d = [_finite(row.get("return_5d_pct")) for row in members]
        valid_5d = [value for value in returns_5d if value is not None]
        returns_10d = [_finite(row.get("return_10d_pct")) for row in members]
        valid_10d = [value for value in returns_10d if value is not None]

        count = len(valid_1d)
        denominator = max(1, count)
        advance_ratio = sum(value > 0 for value in valid_1d) / denominator
        strong_advance_ratio = sum(value >= 2.0 for value in valid_1d) / denominator
        median_1d = _median(valid_1d)
        median_5d = _median(valid_5d)
        median_10d = _median(valid_10d)
        excess_1d = median_1d - market_median_1d
        excess_5d = median_5d - market_median_5d

        above_ma20_ratio = sum(_truthy(row.get("above_ma20")) for row in members) / len(members)
        above_ma60_ratio = sum(_truthy(row.get("above_ma60")) for row in members) / len(members)

        activities = [_activity(row) for row in members]
        valid_activity = [value for value in activities if value is not None]
        expanding_activity_ratio = (
            sum(value >= 1.15 for value in valid_activity) / len(valid_activity)
            if valid_activity
            else 0.0
        )
        median_activity = _median(valid_activity, default=1.0)

        states = [str(row.get("price_volume_state") or "").strip().upper() for row in members]
        accumulation_ratio = sum(state == "ACCUMULATION" for state in states) / len(members)
        distribution_ratio = sum(
            state in {"DISTRIBUTION", "CAPITULATION_RISK"} for state in states
        ) / len(members)

        limit_up_count = 0
        for row in members:
            daily = _finite(row.get("return_1d_pct"))
            if daily is not None and daily >= _board_limit_threshold(row):
                limit_up_count += 1
        limit_up_ratio = limit_up_count / denominator

        breadth_score = advance_ratio * 100.0
        relative_1d_score = _clamp(50.0 + excess_1d * 12.0)
        relative_5d_score = _clamp(50.0 + excess_5d * 4.0)
        trend_score = (above_ma20_ratio + above_ma60_ratio) * 50.0
        activity_score = _clamp(50.0 + (median_activity - 1.0) * 50.0)
        participation_score = _clamp(
            65.0 + accumulation_ratio * 50.0 - distribution_ratio * 120.0
        )
        score = (
            breadth_score * 0.24
            + relative_1d_score * 0.16
            + relative_5d_score * 0.15
            + trend_score * 0.22
            + activity_score * 0.10
            + participation_score * 0.13
        )
        if count < 5:
            score -= 5.0
        score = _clamp(score)

        risk_off = count >= 5 and (
            (advance_ratio < 0.30 and median_1d <= -1.5)
            or distribution_ratio >= 0.35
        )
        overheated = count >= 3 and (
            median_5d >= 12.0
            or median_10d >= 20.0
            or limit_up_ratio >= 0.15
        )
        emerging = (
            count >= 3
            and score >= 58.0
            and excess_1d >= 0.80
            and expanding_activity_ratio >= 0.35
            and median_5d < 8.0
        )
        leading = (
            count >= 3
            and score >= 68.0
            and advance_ratio >= 0.60
            and excess_5d >= 0.0
        )

        if count < 3:
            state = "DATA_THIN"
        elif risk_off:
            state = "RISK_OFF"
        elif overheated and score >= 58.0:
            state = "OVERHEATED"
        elif emerging:
            state = "EMERGING"
        elif leading:
            state = "LEADING"
        elif score >= 55.0:
            state = "HEALTHY"
        elif score < 42.0:
            state = "WEAK"
        else:
            state = "NEUTRAL"

        output.append(
            {
                "sector_rank": 0,
                "industry": industry,
                "sector_opportunity_state": state,
                "sector_research_action": STATE_ACTION[state],
                "sector_opportunity_score": round(score, 2),
                "sample_count": count,
                "advance_ratio": round(advance_ratio, 4),
                "strong_advance_ratio": round(strong_advance_ratio, 4),
                "median_return_1d_pct": round(median_1d, 4),
                "market_median_return_1d_pct": round(market_median_1d, 4),
                "excess_return_1d_pct": round(excess_1d, 4),
                "median_return_5d_pct": round(median_5d, 4),
                "market_median_return_5d_pct": round(market_median_5d, 4),
                "excess_return_5d_pct": round(excess_5d, 4),
                "median_return_10d_pct": round(median_10d, 4),
                "above_ma20_ratio": round(above_ma20_ratio, 4),
                "above_ma60_ratio": round(above_ma60_ratio, 4),
                "expanding_activity_ratio": round(expanding_activity_ratio, 4),
                "median_activity_ratio_20": round(median_activity, 4),
                "accumulation_ratio": round(accumulation_ratio, 4),
                "distribution_ratio": round(distribution_ratio, 4),
                "limit_up_count": limit_up_count,
                "limit_up_ratio": round(limit_up_ratio, 4),
                "sector_overheated": bool(overheated),
                "sector_risk_off": bool(risk_off),
                "sector_strength_is_hard_logic": False,
                "formal_signal_eligible": False,
                "automatic_promotion_allowed": False,
                "no_auto_trade": True,
            }
        )

    output.sort(
        key=lambda row: (
            STATE_PRIORITY.get(str(row.get("sector_opportunity_state")), 99),
            -float(row.get("sector_opportunity_score") or 0.0),
            str(row.get("industry") or ""),
        )
    )
    for rank, row in enumerate(output, 1):
        row["sector_rank"] = rank
    return output


def _read_source(report_dir: Path) -> list[dict[str, Any]]:
    for name in ("all_a_quant_screen.csv", "quant_screen_all.csv", "top80_evidence_queue.csv"):
        path = report_dir / name
        if path.exists():
            with path.open(encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            if rows:
                return rows
    raise FileNotFoundError(f"no All-A source under {report_dir}")


def write_sector_opportunity(
    report_dir: Path,
    output_dir: Path,
) -> list[dict[str, Any]]:
    rows = build_sector_opportunities(_read_source(report_dir))
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "sector_opportunity.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=OUTPUT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    state_counts: dict[str, int] = defaultdict(int)
    for row in rows:
        state_counts[str(row["sector_opportunity_state"])] += 1
    summary = {
        "industry_count": len(rows),
        "state_counts": dict(sorted(state_counts.items())),
        "priority_research_industries": [
            row["industry"]
            for row in rows
            if row["sector_research_action"] == "PRIORITY_RESEARCH"
        ],
        "overheated_industries": [
            row["industry"]
            for row in rows
            if row["sector_opportunity_state"] == "OVERHEATED"
        ],
        "industry_first_discovery": True,
        "sector_strength_is_hard_logic": False,
        "sector_strength_can_create_buy": False,
        "all_industries_remain_visible": True,
        "formal_signal_eligible": False,
        "automatic_promotion_allowed": False,
        "no_auto_trade": True,
    }
    (output_dir / "sector_opportunity_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines = [
        "# All-A Sector Opportunity Map",
        "",
        "Industry strength is a discovery/research-priority signal only. It cannot substitute for structural hard logic or valuation.",
        "",
    ]
    for row in rows:
        lines.append(
            f"- #{row['sector_rank']} {row['industry']} | {row['sector_opportunity_state']} | "
            f"score={row['sector_opportunity_score']} | breadth={row['advance_ratio']} | "
            f"1d={row['median_return_1d_pct']}% (excess {row['excess_return_1d_pct']}%) | "
            f"5d={row['median_return_5d_pct']}% (excess {row['excess_return_5d_pct']}%) | "
            f"activity={row['median_activity_ratio_20']} | action={row['sector_research_action']}"
        )
    (output_dir / "sector_opportunity.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    report_dir = find_latest_report(args.report_root)
    rows = write_sector_opportunity(report_dir, args.output_dir)
    print(f"sector_opportunity={args.output_dir};industries={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
