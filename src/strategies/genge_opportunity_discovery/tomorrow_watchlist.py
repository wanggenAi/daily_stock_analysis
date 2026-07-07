"""Generate next-trading-day watchlist and conditional price plan."""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, Mapping

import pandas as pd
import requests

from src.strategies.genge_cycle_bottom.features import coerce_date, prepare_price_frame


DISCLAIMER = "仅用于公开数据研究观察和人工复核，不构成买入建议，不应自动交易。"
PLAN_COLUMNS = [
    "rank",
    "code",
    "stock_name",
    "industry",
    "tier",
    "tomorrow_status",
    "latest_trade_date",
    "latest_close",
    "atr14",
    "ma20",
    "ma60",
    "support_20d",
    "support_60d",
    "resistance_20d",
    "resistance_60d",
    "initial_entry_low",
    "initial_entry_high",
    "breakout_trigger_price",
    "required_breakout_volume",
    "max_chase_price",
    "add_position_low",
    "add_position_high",
    "technical_stop_price",
    "logic_invalidation_price",
    "target_1_price",
    "target_2_price",
    "trailing_exit_rule",
    "reward_risk_ratio",
    "initial_position_pct",
    "max_position_pct",
    "main_logic",
    "top_risks",
    "buy_conditions",
    "cancel_conditions",
    "industry_evidence_status",
    "company_evidence_status",
    "exit_profile_status",
    "evidence_urls",
    "data_warnings",
]


@dataclass
class PriceContext:
    latest_trade_date: date
    latest_close: float
    atr14: float
    ma20: float
    ma60: float
    support_20d: float
    support_60d: float
    resistance_20d: float
    resistance_60d: float
    local_low: float
    local_high: float
    avg_volume_20d: float
    latest_volume: float


def _normalize_code(value: Any) -> str:
    text = str(value or "").strip()
    return text.zfill(6) if text.isdigit() else text


def _round_price(value: Any) -> float:
    number = float(value)
    return round(max(0.01, number), 2)


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _tencent_symbol(code: str) -> str:
    normalized = _normalize_code(code)
    if normalized.startswith(("6", "5", "9")):
        return f"sh{normalized}"
    if normalized.startswith(("0", "2", "3")):
        return f"sz{normalized}"
    return normalized


def fetch_unadjusted_history(code: str, *, end_date: date, lookback_days: int = 180, timeout: int = 10) -> pd.DataFrame:
    """Fetch unadjusted daily K-line from Tencent. Latest prices are tradable cash prices."""

    start = end_date - timedelta(days=lookback_days)
    symbol = _tencent_symbol(code)
    response = requests.get(
        "https://web.ifzq.gtimg.cn/appstock/app/kline/kline",
        params={"param": f"{symbol},day,{start:%Y-%m-%d},{end_date:%Y-%m-%d},260"},
        headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json,text/plain,*/*"},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    rows = (((payload.get("data") or {}).get(symbol) or {}).get("day") or [])
    parsed = []
    for row in rows:
        if len(row) < 6:
            continue
        parsed.append(
            {
                "date": row[0],
                "open": float(row[1]),
                "close": float(row[2]),
                "high": float(row[3]),
                "low": float(row[4]),
                "volume": float(row[5]),
            }
        )
    frame = pd.DataFrame(parsed)
    if frame.empty:
        return frame
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    return frame.sort_values("date").reset_index(drop=True)


def build_price_context(history: pd.DataFrame, *, as_of: date) -> PriceContext:
    frame = prepare_price_frame(history)
    frame = frame[frame["date"] <= as_of].copy().reset_index(drop=True)
    if len(frame) < 70:
        raise ValueError("insufficient_unadjusted_history")
    for column in ("open", "high", "low", "close", "volume"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["high", "low", "close"]).reset_index(drop=True)
    if len(frame) < 70:
        raise ValueError("insufficient_valid_unadjusted_history")
    previous_close = frame["close"].shift(1)
    true_range = pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - previous_close).abs(),
            (frame["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr14 = float(true_range.tail(14).mean())
    if atr14 <= 0:
        raise ValueError("invalid_atr14")
    latest = frame.iloc[-1]
    last20 = frame.tail(20)
    last60 = frame.tail(60)
    return PriceContext(
        latest_trade_date=coerce_date(latest["date"]),
        latest_close=float(latest["close"]),
        atr14=atr14,
        ma20=float(frame["close"].tail(20).mean()),
        ma60=float(frame["close"].tail(60).mean()),
        support_20d=float(last20["low"].min()),
        support_60d=float(last60["low"].min()),
        resistance_20d=float(last20["high"].max()),
        resistance_60d=float(last60["high"].max()),
        local_low=float(frame.tail(12)["low"].min()),
        local_high=float(frame.tail(12)["high"].max()),
        avg_volume_20d=float(last20["volume"].mean()),
        latest_volume=float(latest.get("volume") or 0),
    )


def _status_rank(row: Mapping[str, Any]) -> tuple[int, int, float]:
    tier_rank = {"TIER_A": 0, "TIER_B": 1, "TIER_C": 2}.get(str(row.get("tier")), 9)
    proximity = int(float(row.get("opportunity_proximity_rank") or 999))
    quality = -(float(row.get("opportunity_quality_score") or 0))
    return tier_rank, proximity, quality


def _evidence_urls(evidence_rows: Iterable[Mapping[str, Any]], row: Mapping[str, Any]) -> list[str]:
    code = _normalize_code(row.get("code"))
    industry = str(row.get("normalized_industry") or "")
    urls: list[str] = []
    for evidence in evidence_rows:
        scope = str(evidence.get("scope") or "")
        evidence_code = _normalize_code(evidence.get("code")) if evidence.get("code") else ""
        evidence_industry = str(evidence.get("industry") or "")
        if (scope == "company" and evidence_code == code) or (scope == "industry" and evidence_industry == industry):
            url = str(evidence.get("original_url") or evidence.get("source") or "").strip()
            if url.startswith(("http://", "https://")):
                urls.append(url)
    return list(dict.fromkeys(urls))


def _plan_prices(row: Mapping[str, Any], ctx: PriceContext, evidence_urls: list[str]) -> dict[str, Any]:
    close = ctx.latest_close
    supports = [ctx.support_20d, ctx.support_60d, ctx.local_low, ctx.ma20, ctx.ma60]
    supports = [value for value in supports if value > 0 and value <= close * 1.01]
    support_center = min(supports, key=lambda value: abs(close - value)) if supports else min(ctx.support_20d, ctx.support_60d)
    entry_low = _round_price(support_center - 0.30 * ctx.atr14)
    entry_high = _round_price(min(close, support_center + 0.20 * ctx.atr14))
    if entry_high < entry_low:
        entry_low = _round_price(entry_high - 0.20 * ctx.atr14)
    breakout = _round_price(ctx.resistance_20d + 0.10 * ctx.atr14)
    max_chase = _round_price(breakout * 1.015)
    add_center = min(ctx.support_60d, ctx.local_low)
    add_low = _round_price(add_center - 0.30 * ctx.atr14)
    add_high = _round_price(min(entry_low, add_center + 0.20 * ctx.atr14))
    technical_stop = _round_price(min(entry_low - 0.01, max(support_center - 0.70 * ctx.atr14, ctx.local_low - 0.30 * ctx.atr14)))
    logic_invalid = _round_price(min(technical_stop, ctx.local_low - 0.10 * ctx.atr14))
    if close <= entry_high * 1.02:
        tentative_status = "WAIT_FOR_PULLBACK"
    elif close < breakout:
        tentative_status = "WAIT_FOR_BREAKOUT"
    else:
        tentative_status = "WATCH_ONLY"
    plan_entry = breakout if tentative_status == "WAIT_FOR_BREAKOUT" else entry_high
    risk = max(0.01, plan_entry - technical_stop)
    target1 = _round_price(plan_entry + 1.50 * risk)
    target2 = _round_price(plan_entry + 2.50 * risk)
    rr = round((target2 - plan_entry) / risk, 2)
    hard_blockers = str(row.get("hard_blockers") or row.get("hard_reject_blockers") or "").strip()
    industry_status = str(row.get("industry_evidence_status") or "")
    company_status = str(row.get("company_evidence_status") or "")
    hard_logic = str(row.get("hard_logic_level") or "")
    exit_profile = str(row.get("balanced_exit_historical_profile") or "")
    failed = set(str(row.get("a_condition_failed") or "").split(";"))
    buy_ready = (
        not hard_blockers
        and row.get("tier") == "TIER_A"
        and industry_status in {"VERIFIED", "PARTIALLY_VERIFIED"}
        and company_status in {"VERIFIED", "PARTIALLY_VERIFIED"}
        and hard_logic in {"MEDIUM", "STRONG"}
        and exit_profile == "PASSED"
        and rr >= 1.8
        and bool(evidence_urls)
    )
    if buy_ready:
        status = "BUY_READY"
    else:
        status = tentative_status
    if {"trend_medium", "hard_logic_medium", "company_evidence_medium", "industry_evidence_medium"} & failed and status == "WAIT_FOR_PULLBACK":
        status = "WATCH_ONLY"
    cancel_conditions = [
        "高开超过买入区间上沿2%",
        "高开超过最高追价",
        "低开并直接跌破技术止损价",
        "集合竞价异常或流动性异常",
        "新增重大负面公告",
        "行业或公司证据被证伪",
        "停牌、涨停无法成交或价格数据不一致",
    ]
    buy_conditions = [
        "开盘价位于回踩买入区间且未跌破逻辑失效价",
        f"突破买入需价格突破 {breakout:.2f} 且成交量不低于 {ctx.avg_volume_20d * 1.2:.0f}",
        "行业和公司证据未恶化",
        "不得无条件市价追单",
    ]
    return {
        "tomorrow_status": status,
        "initial_entry_low": entry_low,
        "initial_entry_high": entry_high,
        "breakout_trigger_price": breakout,
        "required_breakout_volume": round(ctx.avg_volume_20d * 1.2, 0),
        "max_chase_price": max_chase,
        "add_position_low": add_low,
        "add_position_high": add_high,
        "technical_stop_price": technical_stop,
        "logic_invalidation_price": logic_invalid,
        "target_1_price": target1,
        "target_2_price": target2,
        "reward_risk_ratio": rr,
        "trailing_exit_rule": "达到第一止盈后保护位不低于成本价；后续取 MA20 与最高价-2*ATR14 中较高者作为移动保护。",
        "initial_position_pct": 2.0 if status == "BUY_READY" else 0.0,
        "max_position_pct": 5.0 if status == "BUY_READY" else 0.0,
        "buy_conditions": "；".join(buy_conditions),
        "cancel_conditions": "；".join(cancel_conditions),
    }


def _validate_price_plan(plan: Mapping[str, Any]) -> list[str]:
    warnings: list[str] = []
    entry = _finite(plan.get("initial_entry_high"))
    stop = _finite(plan.get("technical_stop_price"))
    target1 = _finite(plan.get("target_1_price"))
    target2 = _finite(plan.get("target_2_price"))
    breakout = _finite(plan.get("breakout_trigger_price"))
    rr = _finite(plan.get("reward_risk_ratio"))
    planned_entry = breakout if str(plan.get("tomorrow_status") or "") == "WAIT_FOR_BREAKOUT" and breakout is not None else entry
    for field in ("latest_close", "atr14", "ma20", "ma60", "initial_entry_low", "initial_entry_high", "technical_stop_price", "target_1_price", "target_2_price"):
        value = _finite(plan.get(field))
        if value is None or value <= 0:
            warnings.append(f"{field}_invalid")
    if entry is not None and stop is not None and stop >= entry:
        warnings.append("stop_not_below_entry")
    if entry is not None and target1 is not None and target1 <= entry:
        warnings.append("target1_not_above_entry")
    if target1 is not None and target2 is not None and target2 <= target1:
        warnings.append("target2_not_above_target1")
    if str(plan.get("tomorrow_status") or "") == "WAIT_FOR_BREAKOUT" and breakout is not None and target1 is not None and target1 <= breakout:
        warnings.append("breakout_target_not_above_trigger")
    if planned_entry is not None and stop is not None and target2 is not None:
        expected = round((target2 - planned_entry) / max(0.01, planned_entry - stop), 2)
        if rr is None or abs(rr - expected) > 0.02:
            warnings.append("reward_risk_mismatch")
    return warnings


def generate_tomorrow_watchlist(
    *,
    opportunity_report_dir: str | Path,
    output_dir: str | Path = "reports/tomorrow_watchlist/20260708",
    as_of: str | date = "2026-07-07",
    tomorrow: str | date = "2026-07-08",
    max_watchlist: int = 3,
    max_buy_ready: int = 2,
) -> tuple[Path, dict[str, Any]]:
    report_dir = Path(opportunity_report_dir)
    as_of_date = coerce_date(as_of)
    tomorrow_date = coerce_date(tomorrow)
    payload = json.loads((report_dir / "daily_opportunity_report.json").read_text(encoding="utf-8"))
    summary = payload.get("summary") or {}
    opportunities = payload.get("all_opportunities") or []
    evidence_rows = list(csv.DictReader((report_dir / "evidence_inventory.csv").open(encoding="utf-8"))) if (report_dir / "evidence_inventory.csv").exists() else []
    candidates = [
        row
        for row in opportunities
        if str(row.get("tier")) in {"TIER_A", "TIER_B", "TIER_C"}
        and not str(row.get("hard_blockers") or row.get("hard_reject_blockers") or "").strip()
    ]
    candidates = sorted(candidates, key=_status_rank)
    plan_rows: list[dict[str, Any]] = []
    quality_rows: list[dict[str, Any]] = []
    buy_ready_count = 0
    for row in candidates:
        if len(plan_rows) >= max_watchlist:
            break
        code = _normalize_code(row.get("code"))
        try:
            history = fetch_unadjusted_history(code, end_date=as_of_date)
            ctx = build_price_context(history, as_of=as_of_date)
        except Exception as exc:
            quality_rows.append({"code": code, "stock_name": row.get("stock_name"), "status": "FAILED", "issue": "unadjusted_price_fetch_failed", "detail": f"{type(exc).__name__}: {exc}"})
            continue
        urls = _evidence_urls(evidence_rows, row)
        price_plan = _plan_prices(row, ctx, urls)
        if price_plan["tomorrow_status"] == "BUY_READY":
            if buy_ready_count >= max_buy_ready:
                price_plan["tomorrow_status"] = "WATCH_ONLY"
            else:
                buy_ready_count += 1
        plan = {
            "rank": len(plan_rows) + 1,
            "code": code,
            "stock_name": row.get("stock_name"),
            "industry": row.get("normalized_industry") or row.get("raw_industry"),
            "tier": row.get("tier"),
            "latest_trade_date": ctx.latest_trade_date.isoformat(),
            "latest_close": _round_price(ctx.latest_close),
            "atr14": _round_price(ctx.atr14),
            "ma20": _round_price(ctx.ma20),
            "ma60": _round_price(ctx.ma60),
            "support_20d": _round_price(ctx.support_20d),
            "support_60d": _round_price(ctx.support_60d),
            "resistance_20d": _round_price(ctx.resistance_20d),
            "resistance_60d": _round_price(ctx.resistance_60d),
            "main_logic": row.get("opportunity_logic"),
            "top_risks": row.get("top_risks"),
            "industry_evidence_status": row.get("industry_evidence_status"),
            "company_evidence_status": row.get("company_evidence_status"),
            "exit_profile_status": row.get("balanced_exit_historical_profile"),
            "evidence_urls": ";".join(urls),
            **price_plan,
        }
        warnings = _validate_price_plan(plan)
        if ctx.latest_trade_date > as_of_date:
            warnings.append("future_price_date")
        if ctx.latest_trade_date < as_of_date:
            warnings.append("latest_trade_date_before_as_of")
        plan["data_warnings"] = ";".join(warnings)
        if warnings:
            quality_rows.append({"code": code, "stock_name": row.get("stock_name"), "status": "DEGRADED", "issue": "price_plan_warning", "detail": ";".join(warnings)})
        plan_rows.append(plan)

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    _write_csv(output_path / "buy_sell_price_plan.csv", plan_rows, PLAN_COLUMNS)
    _write_csv(output_path / "tomorrow_watchlist.csv", plan_rows, PLAN_COLUMNS)
    _write_csv(output_path / "data_quality_audit.csv", quality_rows, ["code", "stock_name", "status", "issue", "detail"])
    plan_json = {"disclaimer": DISCLAIMER, "as_of_date": as_of_date.isoformat(), "tomorrow": tomorrow_date.isoformat(), "plans": plan_rows}
    (output_path / "buy_sell_price_plan.json").write_text(json.dumps(plan_json, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_path / "tomorrow_watchlist.md").write_text(_markdown(plan_rows, as_of_date, tomorrow_date), encoding="utf-8")
    (output_path / "evidence_review.md").write_text(_evidence_markdown(plan_rows), encoding="utf-8")
    run_summary = {
        "disclaimer": DISCLAIMER,
        "as_of_date": as_of_date.isoformat(),
        "tomorrow": tomorrow_date.isoformat(),
        "source_report_dir": str(report_dir),
        "opportunity_acceptance_enum": summary.get("acceptance_enum"),
        "watchlist_count": len(plan_rows),
        "buy_ready_count": sum(1 for row in plan_rows if row.get("tomorrow_status") == "BUY_READY"),
        "actual_latest_trade_dates": sorted({row.get("latest_trade_date") for row in plan_rows}),
        "price_adjustment": "unadjusted/tencent_kline",
        "no_auto_trade": True,
        "no_broker_integration": True,
    }
    (output_path / "run_summary.json").write_text(json.dumps(run_summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path, run_summary


def _write_csv(path: Path, rows: list[Mapping[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _markdown(rows: list[Mapping[str, Any]], as_of: date, tomorrow: date) -> str:
    lines = [
        f"# {tomorrow.isoformat()} Tomorrow Watchlist",
        "",
        DISCLAIMER,
        "",
        f"- source_as_of_date: {as_of.isoformat()}",
        f"- price_adjustment: unadjusted/tencent_kline",
        "",
        "| 排名 | 代码 | 股票 | 状态 | 最新收盘 | 回踩买入区间 | 突破买入价 | 最高追价 | 止损价 | 逻辑失效价 | 第一止盈 | 第二止盈 | 收益风险比 |",
        "| -- | -- | -- | -- | ---: | -----: | ----: | ---: | --: | ----: | ---: | ---: | ----: |",
    ]
    for row in rows:
        lines.append(
            f"| {row.get('rank')} | {row.get('code')} | {row.get('stock_name')} | {row.get('tomorrow_status')} | {row.get('latest_close')} | "
            f"{row.get('initial_entry_low')}-{row.get('initial_entry_high')} | {row.get('breakout_trigger_price')} | {row.get('max_chase_price')} | "
            f"{row.get('technical_stop_price')} | {row.get('logic_invalidation_price')} | {row.get('target_1_price')} | {row.get('target_2_price')} | {row.get('reward_risk_ratio')} |"
        )
    lines.append("")
    if not any(row.get("tomorrow_status") == "BUY_READY" for row in rows):
        lines.append("2026年7月8日暂不买入；明日没有达到正式买入标准的股票。")
    return "\n".join(lines) + "\n"


def _evidence_markdown(rows: list[Mapping[str, Any]]) -> str:
    lines = ["# Evidence Review", "", DISCLAIMER, ""]
    for row in rows:
        lines.extend(
            [
                f"## {row.get('stock_name')} ({row.get('code')})",
                "",
                f"- industry_evidence_status: {row.get('industry_evidence_status')}",
                f"- company_evidence_status: {row.get('company_evidence_status')}",
                f"- exit_profile_status: {row.get('exit_profile_status')}",
                f"- evidence_urls: {row.get('evidence_urls') or '无可核验 URL，不能标记 BUY_READY'}",
                f"- data_warnings: {row.get('data_warnings') or '无'}",
                "",
            ]
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate 2026-07-08 watchlist and conditional price plan.")
    parser.add_argument("--opportunity-report-dir", required=True)
    parser.add_argument("--output-dir", default="reports/tomorrow_watchlist/20260708")
    parser.add_argument("--as-of-date", default="2026-07-07")
    parser.add_argument("--tomorrow", default="2026-07-08")
    args = parser.parse_args(argv)
    output_dir, summary = generate_tomorrow_watchlist(
        opportunity_report_dir=args.opportunity_report_dir,
        output_dir=args.output_dir,
        as_of=args.as_of_date,
        tomorrow=args.tomorrow,
    )
    print(f"tomorrow_watchlist_dir={output_dir}")
    print(f"watchlist_count={summary['watchlist_count']}")
    print(f"buy_ready_count={summary['buy_ready_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
