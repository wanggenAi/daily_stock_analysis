"""Lightweight intraday Shanghai/Shenzhen sector opportunity refresh.

The expensive structural-research and valuation stack should not be re-run every
few hours just to learn that a different industry has become today's market
leader.  This module overlays live Shanghai/Shenzhen A-share quotes onto the
latest completed All-A research snapshot, reuses the snapshot's stable industry
mapping / multi-day context, and rebuilds only the sector-opportunity layer.

Fresh intraday fields:
- latest price / previous close / open / high / low;
- current-day return;
- vendor intraday volume ratio;
- turnover / amount;
- price-volume participation state derived from the fresh quote.

Stable baseline fields such as industry membership and prior multi-day trend are
retained from the most recent complete All-A scan.  Intraday data is explicitly
marked non-PIT for historical backtests and can never create HARD_LOGIC_PASS,
fair value, or a buy signal.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping
from zoneinfo import ZoneInfo

import pandas as pd

from .real_world_signals import price_volume_state
from .sector_opportunity_engine import (
    OUTPUT_COLUMNS as BASE_SECTOR_COLUMNS,
    UNKNOWN_INDUSTRY,
    build_sector_opportunities,
)

SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
PROVIDER = "efinance.stock.get_realtime_quotes:沪A+深A"
SNAPSHOT_TYPE = "INTRADAY_REALTIME_OVERLAY"
MIN_REALTIME_MATCH_RATIO = 0.85
MIN_INDUSTRY_COVERAGE_RATIO = 0.90

INTRADAY_SECTOR_COLUMNS = list(BASE_SECTOR_COLUMNS) + [
    "snapshot_as_of",
    "snapshot_type",
    "realtime_provider",
    "realtime_match_ratio",
    "industry_mapping_coverage_ratio",
    "baseline_trade_date",
    "fresh_field_basis",
    "baseline_field_basis",
    "historical_backtest_eligible",
]

STOCK_SNAPSHOT_COLUMNS = [
    "code",
    "stock_name",
    "industry",
    "market_type",
    "board",
    "snapshot_as_of",
    "baseline_trade_date",
    "intraday_latest_price",
    "intraday_previous_close",
    "intraday_return_1d_pct",
    "intraday_open",
    "intraday_high",
    "intraday_low",
    "intraday_turnover_rate_pct",
    "intraday_volume_ratio",
    "intraday_amount",
    "return_1d_pct",
    "return_5d_pct",
    "return_10d_pct",
    "above_ma20",
    "above_ma60",
    "price_volume_state",
    "price_volume_score",
    "price_volume_reasons",
]


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _normalize_code(value: Any) -> str:
    text = str(value or "").strip().upper()
    if "." in text:
        base, suffix = text.rsplit(".", 1)
        if suffix in {"SH", "SZ", "BJ"} and base.isdigit():
            text = base
    for prefix in ("SH", "SZ", "BJ"):
        if text.startswith(prefix) and text[len(prefix):].isdigit():
            text = text[len(prefix):]
            break
    return text.zfill(6) if text.isdigit() else text


def _read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _first(row: Mapping[str, Any], *fields: str) -> Any:
    for field in fields:
        value = row.get(field)
        if value not in (None, ""):
            return value
    return ""


def _baseline_trade_date(rows: Iterable[Mapping[str, Any]]) -> str:
    values = sorted(
        {
            str(_first(row, "trade_date", "as_of_date", "snapshot_date") or "").strip()
            for row in rows
            if str(_first(row, "trade_date", "as_of_date", "snapshot_date") or "").strip()
        }
    )
    return values[-1] if values else ""


def normalize_realtime_rows(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """Normalize efinance Chinese quote columns without depending on column order."""
    if frame is None or frame.empty:
        return []
    rows: list[dict[str, Any]] = []
    for raw in frame.to_dict("records"):
        code = _normalize_code(_first(raw, "股票代码", "代码", "code"))
        market_type = str(_first(raw, "市场类型", "market_type") or "").strip()
        if not code or market_type not in {"沪A", "深A"}:
            continue
        rows.append(
            {
                "code": code,
                "stock_name": str(_first(raw, "股票名称", "名称", "name") or "").strip(),
                "market_type": market_type,
                "latest_price": _finite(_first(raw, "最新价", "最新", "price")),
                "previous_close": _finite(_first(raw, "昨日收盘", "昨收", "previous_close")),
                "return_1d_pct": _finite(_first(raw, "涨跌幅", "change_pct", "return_1d_pct")),
                "open": _finite(_first(raw, "今开", "开盘", "open")),
                "high": _finite(_first(raw, "最高", "high")),
                "low": _finite(_first(raw, "最低", "low")),
                "turnover_rate_pct": _finite(_first(raw, "换手率", "turnover_rate")),
                "volume_ratio": _finite(_first(raw, "量比", "volume_ratio")),
                "amount": _finite(_first(raw, "成交额", "amount")),
            }
        )
    return rows


def fetch_realtime_quotes() -> pd.DataFrame:
    """Fetch the full Shanghai/Shenzhen A-share market from efinance."""
    import efinance as ef

    return ef.stock.get_realtime_quotes(["沪A", "深A"])


def overlay_intraday_quotes(
    baseline_rows: Iterable[Mapping[str, Any]],
    realtime_rows: Iterable[Mapping[str, Any]],
    *,
    snapshot_as_of: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    baseline = [dict(row) for row in baseline_rows]
    baseline_by_code = {
        _normalize_code(row.get("code")): row
        for row in baseline
        if _normalize_code(row.get("code"))
    }
    base_trade_date = _baseline_trade_date(baseline)

    live = [dict(row) for row in realtime_rows if _normalize_code(row.get("code"))]
    matched: list[dict[str, Any]] = []
    industry_mapped = 0
    for quote in live:
        code = _normalize_code(quote.get("code"))
        base = baseline_by_code.get(code)
        if base is None:
            continue
        industry = str(
            base.get("industry")
            or base.get("normalized_industry")
            or base.get("raw_industry")
            or UNKNOWN_INDUSTRY
        ).strip() or UNKNOWN_INDUSTRY
        if industry != UNKNOWN_INDUSTRY:
            industry_mapped += 1

        row = dict(base)
        row.update(
            {
                "code": code,
                "stock_name": quote.get("stock_name") or base.get("stock_name") or base.get("name") or "",
                "industry": industry,
                "market_type": quote.get("market_type") or base.get("market_type") or "",
                "snapshot_as_of": snapshot_as_of,
                "baseline_trade_date": base_trade_date,
                "intraday_latest_price": quote.get("latest_price"),
                "intraday_previous_close": quote.get("previous_close"),
                "intraday_return_1d_pct": quote.get("return_1d_pct"),
                "intraday_open": quote.get("open"),
                "intraday_high": quote.get("high"),
                "intraday_low": quote.get("low"),
                "intraday_turnover_rate_pct": quote.get("turnover_rate_pct"),
                "intraday_volume_ratio": quote.get("volume_ratio"),
                "intraday_amount": quote.get("amount"),
                # Sector breadth must use the fresh current-day quote.
                "return_1d_pct": quote.get("return_1d_pct"),
                "raw_latest_close": quote.get("latest_price"),
            }
        )

        previous_close = _finite(quote.get("previous_close"))
        open_price = _finite(quote.get("open"))
        high = _finite(quote.get("high"))
        low = _finite(quote.get("low"))
        price = _finite(quote.get("latest_price"))
        if previous_close not in (None, 0.0) and open_price is not None:
            row["gap_open_pct"] = round((open_price / previous_close - 1.0) * 100.0, 4)
        if price is not None and high is not None and low is not None and high > low:
            row["close_location"] = round((price - low) / (high - low), 4)

        # Existing price_volume_state expects a volume/amount activity ratio.
        # Feed the live vendor intraday ratio into a temporary copy without
        # pretending it is a historical 20-day end-of-day volume ratio.
        state_input = dict(row)
        live_ratio = _finite(quote.get("volume_ratio"))
        if live_ratio is not None:
            state_input["volume_ratio_20"] = live_ratio
            state_input["amount_ratio_20"] = live_ratio
        row.update(price_volume_state(state_input))
        matched.append(row)

    live_count = len(live)
    matched_count = len(matched)
    match_ratio = matched_count / live_count if live_count else 0.0
    industry_ratio = industry_mapped / matched_count if matched_count else 0.0
    stats = {
        "snapshot_as_of": snapshot_as_of,
        "snapshot_type": SNAPSHOT_TYPE,
        "realtime_provider": PROVIDER,
        "realtime_row_count": live_count,
        "matched_row_count": matched_count,
        "realtime_match_ratio": match_ratio,
        "industry_mapping_coverage_ratio": industry_ratio,
        "baseline_row_count": len(baseline_by_code),
        "baseline_trade_date": base_trade_date,
    }
    return matched, stats


def build_intraday_sector_snapshot(
    baseline_rows: Iterable[Mapping[str, Any]],
    realtime_frame: pd.DataFrame,
    *,
    snapshot_as_of: str,
    min_match_ratio: float = MIN_REALTIME_MATCH_RATIO,
    min_industry_coverage_ratio: float = MIN_INDUSTRY_COVERAGE_RATIO,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    realtime_rows = normalize_realtime_rows(realtime_frame)
    stock_rows, stats = overlay_intraday_quotes(
        baseline_rows,
        realtime_rows,
        snapshot_as_of=snapshot_as_of,
    )
    if stats["realtime_match_ratio"] < float(min_match_ratio):
        raise RuntimeError(
            f"intraday baseline match ratio too low: {stats['realtime_match_ratio']:.3f}"
        )
    if stats["industry_mapping_coverage_ratio"] < float(min_industry_coverage_ratio):
        raise RuntimeError(
            "intraday industry mapping coverage too low: "
            f"{stats['industry_mapping_coverage_ratio']:.3f}"
        )

    # Make current vendor volume ratio available to the sector activity helper.
    sector_input: list[dict[str, Any]] = []
    for raw in stock_rows:
        row = dict(raw)
        if _finite(row.get("intraday_volume_ratio")) is not None:
            row["volume_ratio_20"] = row["intraday_volume_ratio"]
        sector_input.append(row)
    sectors = build_sector_opportunities(sector_input)

    base_trade_date = str(stats.get("baseline_trade_date") or "")
    for row in sectors:
        row.update(
            {
                "snapshot_as_of": snapshot_as_of,
                "snapshot_type": SNAPSHOT_TYPE,
                "realtime_provider": PROVIDER,
                "realtime_match_ratio": round(float(stats["realtime_match_ratio"]), 4),
                "industry_mapping_coverage_ratio": round(
                    float(stats["industry_mapping_coverage_ratio"]), 4
                ),
                "baseline_trade_date": base_trade_date,
                "fresh_field_basis": (
                    "latest_price;return_1d;open;high;low;turnover;amount;vendor_intraday_volume_ratio"
                ),
                "baseline_field_basis": (
                    "industry_mapping;return_5d;return_10d;ma20_ma60_context_from_latest_complete_all_a"
                ),
                "historical_backtest_eligible": False,
            }
        )

    summary = {
        **stats,
        "industry_count": len(sectors),
        "industry_first_discovery": True,
        "intraday_refresh_only": True,
        "structural_research_reused_not_rerun": True,
        "valuation_reused_not_rerun": True,
        "sector_strength_is_hard_logic": False,
        "sector_strength_can_create_buy": False,
        "historical_backtest_eligible": False,
        "formal_signal_eligible": False,
        "automatic_promotion_allowed": False,
        "no_auto_trade": True,
    }
    return stock_rows, sectors, summary


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_intraday_sector_snapshot(
    baseline_all_a_csv: Path,
    output_dir: Path,
    *,
    quote_fetcher: Callable[[], pd.DataFrame] = fetch_realtime_quotes,
    snapshot_as_of: str | None = None,
    min_match_ratio: float = MIN_REALTIME_MATCH_RATIO,
    min_industry_coverage_ratio: float = MIN_INDUSTRY_COVERAGE_RATIO,
) -> dict[str, Any]:
    baseline_rows = _read_csv(baseline_all_a_csv)
    now_text = snapshot_as_of or datetime.now(SHANGHAI_TZ).isoformat(timespec="seconds")
    frame = quote_fetcher()
    stock_rows, sectors, summary = build_intraday_sector_snapshot(
        baseline_rows,
        frame,
        snapshot_as_of=now_text,
        min_match_ratio=min_match_ratio,
        min_industry_coverage_ratio=min_industry_coverage_ratio,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "intraday_stock_snapshot.csv", stock_rows, STOCK_SNAPSHOT_COLUMNS)
    _write_csv(output_dir / "sector_opportunity_intraday.csv", sectors, INTRADAY_SECTOR_COLUMNS)
    (output_dir / "sector_opportunity_intraday_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines = [
        "# Intraday Shanghai/Shenzhen Sector Opportunity Map",
        "",
        f"- snapshot_as_of: {summary['snapshot_as_of']}",
        f"- baseline_trade_date: {summary['baseline_trade_date'] or 'UNKNOWN'}",
        f"- realtime match: {summary['matched_row_count']}/{summary['realtime_row_count']} "
        f"({summary['realtime_match_ratio']:.1%})",
        f"- industry mapping coverage: {summary['industry_mapping_coverage_ratio']:.1%}",
        "- policy: discovery/priority only; never substitutes for structural hard logic or valuation",
        "",
        "## Current industry ranking",
    ]
    for row in sectors:
        lines.append(
            f"- #{row['sector_rank']} {row['industry']} | {row['sector_opportunity_state']} | "
            f"score={row['sector_opportunity_score']} | breadth={row['advance_ratio']} | "
            f"1d={row['median_return_1d_pct']}% (excess {row['excess_return_1d_pct']}%) | "
            f"activity={row['median_activity_ratio_20']} | action={row['sector_research_action']}"
        )
    (output_dir / "sector_opportunity_intraday.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-all-a-csv", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--min-match-ratio", type=float, default=MIN_REALTIME_MATCH_RATIO)
    parser.add_argument(
        "--min-industry-coverage-ratio",
        type=float,
        default=MIN_INDUSTRY_COVERAGE_RATIO,
    )
    args = parser.parse_args(argv)
    summary = write_intraday_sector_snapshot(
        args.baseline_all_a_csv,
        args.output_dir,
        min_match_ratio=args.min_match_ratio,
        min_industry_coverage_ratio=args.min_industry_coverage_ratio,
    )
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
