"""Point-in-time walk-forward test for hard logic + reverse valuation.

Signals use only information visible at each historical date. A signal is
computed after the close and executes at the next supplied session open. Named
famous stocks are an ex-post capture audit, not an unbiased all-market return
estimate.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Mapping

import pandas as pd

from src.strategies.genge_cycle_bottom.features import prepare_price_frame
from src.strategies.genge_cycle_bottom.fundamentals import PublicFundamentalLoader
from src.strategies.genge_opportunity_discovery.exit_profile import fetch_extended_adjusted_histories
from src.strategies.genge_opportunity_discovery.hard_logic_price_map import build_price_expectation_row

RULE_VERSION = "hard_logic_reverse_valuation_walk_forward_v1"
DISCLAIMER = "仅用于公开历史数据研究回放，不构成买入或卖出建议，不应自动交易。"
MIN_PRIOR_PE_OBSERVATIONS = 120
PE_LOOKBACK = 1260
DEFAULT_STRIDE = 5
MAX_ENTRY_PE_PERCENTILE = 50.0
MIN_EXIT_PE_PERCENTILE = 70.0
BUY_DECISIONS = {"BUY_DEEP_VALUE", "BUYABLE", "BUYABLE_WITH_SUPPORTED_GROWTH"}


@dataclass(frozen=True)
class FamousCase:
    code: str
    stock_name: str
    note: str = ""


@dataclass
class HistoricalCompanyData:
    code: str
    stock_name: str
    price_df: pd.DataFrame
    valuation_df: pd.DataFrame
    financial_df: pd.DataFrame
    warnings: list[str]


def _finite(value: Any) -> float | None:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _parse_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value or "")[:10])
    except ValueError:
        return None


def _code(value: Any) -> str:
    text = str(value or "").strip().upper()
    if "." in text:
        text = text.split(".", 1)[0]
    for prefix in ("SH", "SZ", "BJ"):
        if text.startswith(prefix) and text[len(prefix):].isdigit():
            text = text[len(prefix):]
    return text.zfill(6) if text.isdigit() else text


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _growth(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None or previous == 0:
        return None
    return (current / previous - 1.0) * 100.0


def _fallback_disclosure(report_date: date) -> date:
    # Conservative lags prevent report_date itself from becoming a look-ahead.
    md = (report_date.month, report_date.day)
    lag = 130 if md >= (12, 1) else 50 if md >= (9, 1) else 70 if md >= (6, 1) else 50
    return report_date + timedelta(days=lag)


def normalize_financial_point_in_time(financial_df: pd.DataFrame | None) -> pd.DataFrame:
    if financial_df is None or financial_df.empty or "report_date" not in financial_df.columns:
        return pd.DataFrame()
    local = financial_df.copy()
    local["report_date"] = local["report_date"].map(_parse_date)
    if "disclosure_date" not in local.columns:
        local["disclosure_date"] = None
    local["disclosure_date"] = local["disclosure_date"].map(_parse_date)
    local["effective_disclosure_date"] = [
        disclosure if disclosure is not None else (_fallback_disclosure(report) if report is not None else None)
        for report, disclosure in zip(local["report_date"], local["disclosure_date"])
    ]
    return (
        local.dropna(subset=["report_date", "effective_disclosure_date"])
        .sort_values(["effective_disclosure_date", "report_date"])
        .reset_index(drop=True)
    )


def financials_visible_as_of(financial_df: pd.DataFrame, as_of: date) -> pd.DataFrame:
    if financial_df.empty:
        return financial_df.copy()
    return financial_df[financial_df["effective_disclosure_date"] <= as_of].copy()


def _profit(row: Mapping[str, Any]) -> float | None:
    value = _finite(row.get("recurring_profit"))
    return value if value is not None else _finite(row.get("net_profit"))


def _prior_same_period(rows: pd.DataFrame, report_date: date) -> Mapping[str, Any] | None:
    old = rows[rows["report_date"] < report_date]
    if old.empty:
        return None
    same = old[old["report_date"].map(lambda d: d.month == report_date.month)]
    if same.empty:
        return None
    last_year = same[same["report_date"].map(lambda d: d.year == report_date.year - 1)]
    selected = last_year if not last_year.empty else same
    return selected.sort_values("report_date").iloc[-1].to_dict()


def point_in_time_hard_logic(financial_df: pd.DataFrame, as_of: date) -> dict[str, Any]:
    visible = financials_visible_as_of(financial_df, as_of)
    if visible.empty:
        return {"state": "REVIEW", "score": 0.0, "reasons": ["no_visible_financial_statement"]}
    latest = visible.sort_values(["report_date", "effective_disclosure_date"]).iloc[-1].to_dict()
    core_profit = _profit(latest)
    if core_profit is not None and core_profit <= 0:
        return {"state": "BLOCKED", "score": 0.0, "reasons": ["latest_visible_core_profit_non_positive"]}

    score = 40.0 if core_profit is not None and core_profit > 0 else 0.0
    reasons = ["positive_core_profit"] if score else []
    prior = _prior_same_period(visible, latest["report_date"])
    yoy = _growth(core_profit, _profit(prior) if prior else None)
    if yoy is not None:
        if yoy >= 15:
            score += 20
            reasons.append("profit_growth_strong")
        elif yoy >= 0:
            score += 16
            reasons.append("profit_growth_positive")
        elif yoy >= -10:
            score += 8
            reasons.append("profit_growth_resilient")
        elif yoy < -30:
            reasons.append("profit_growth_sharp_decline")

    cash_ratio = _finite(latest.get("cash_conversion_ratio"))
    ocf = _finite(latest.get("operating_cash_flow"))
    if cash_ratio is not None:
        if cash_ratio >= 0.8:
            score += 15
            reasons.append("cash_conversion_good")
        elif cash_ratio >= 0.4:
            score += 8
    elif ocf is not None and ocf > 0:
        score += 8
        reasons.append("operating_cash_positive")

    roe = _finite(latest.get("roe"))
    if roe is not None:
        score += 15 if roe >= 12 else 10 if roe >= 7 else 5 if roe >= 4 else 0
    debt = _finite(latest.get("debt_ratio"))
    if debt is not None:
        score += 10 if debt <= 60 else 5 if debt <= 75 else 0

    observations: list[float] = []
    for _, row in visible.sort_values("report_date").tail(12).iterrows():
        item = row.to_dict()
        previous = _prior_same_period(visible, item["report_date"])
        g = _growth(_profit(item), _profit(previous) if previous else None)
        if g is not None:
            observations.append(_clip(g, -50.0, 80.0))
    observations = observations[-4:]
    base = _clip(float(median(observations)), -30.0, 60.0) if observations else None
    spread = 15.0 if len(observations) < 3 else 10.0
    low = _clip(base - spread, -50.0, 60.0) if base is not None else None
    high = _clip(base + spread, -30.0, 80.0) if base is not None else None
    if base is not None:
        reasons.append("point_in_time_growth_support_available")

    if core_profit is None:
        state = "REVIEW"
    elif score >= 60:
        state = "PASS"
    elif score < 45:
        state = "BLOCKED"
        reasons.append("hard_logic_quality_deteriorated")
    else:
        state = "REVIEW"
        reasons.append("hard_logic_quality_not_confirmed")
    return {
        "state": state,
        "score": round(score, 2),
        "reasons": reasons,
        "supported_growth_low_pct": round(low, 4) if low is not None else None,
        "supported_growth_base_pct": round(base, 4) if base is not None else None,
        "supported_growth_high_pct": round(high, 4) if high is not None else None,
        "latest_report_date": latest.get("report_date"),
        "latest_effective_disclosure_date": latest.get("effective_disclosure_date"),
    }


def point_in_time_valuation(valuation_df: pd.DataFrame, as_of: date) -> dict[str, Any] | None:
    if valuation_df is None or valuation_df.empty or "date" not in valuation_df.columns:
        return None
    local = valuation_df.copy()
    local["date"] = local["date"].map(_parse_date)
    local["pe"] = pd.to_numeric(local.get("pe"), errors="coerce")
    local = local.dropna(subset=["date", "pe"])
    local = local[local["pe"] > 0].sort_values("date")
    current_rows = local[local["date"] <= as_of]
    if current_rows.empty:
        return None
    current = current_rows.iloc[-1]
    current_pe = _finite(current["pe"])
    prior = local[local["date"] < current["date"]].tail(PE_LOOKBACK)
    values = [float(x) for x in prior["pe"].tolist() if _finite(x) is not None and float(x) > 0]
    if current_pe is None or len(values) < MIN_PRIOR_PE_OBSERVATIONS:
        return None
    reference = float(median(values))
    return {
        "valuation_date": current["date"],
        "current_pe": current_pe,
        "historical_reference_pe": reference,
        "historical_pe_percentile": sum(x <= current_pe for x in values) / len(values) * 100.0,
        "required_profit_growth_pct": (current_pe / reference - 1.0) * 100.0,
    }


def _price_percentile(history: pd.DataFrame, price: float, sessions: int = 500) -> float | None:
    closes = pd.to_numeric(history.tail(sessions)["close"], errors="coerce").dropna()
    closes = closes[closes > 0]
    return float((closes <= price).sum()) / len(closes) * 100.0 if len(closes) else None


def _max_drawdown(values: Iterable[float]) -> float:
    peak = None
    worst = 0.0
    for raw in values:
        value = _finite(raw)
        if value is None or value <= 0:
            continue
        peak = value if peak is None else max(peak, value)
        worst = min(worst, (value / peak - 1.0) * 100.0)
    return round(worst, 4)


def _price_map(
    data: HistoricalCompanyData,
    as_of: date,
    close: float,
    valuation: Mapping[str, Any],
    logic: Mapping[str, Any],
) -> dict[str, Any]:
    return build_price_expectation_row(
        {
            "code": data.code,
            "stock_name": data.stock_name,
            "hard_logic_state": logic["state"],
            "normalized_core_operating_profit": 1 if logic["state"] != "BLOCKED" else -1,
            "current_price": close,
            "current_pe": valuation["current_pe"],
            "historical_median_pe_reference": valuation["historical_reference_pe"],
            "historical_pe_percentile": valuation["historical_pe_percentile"],
            "required_profit_growth_pct": valuation["required_profit_growth_pct"],
            "hard_logic_supported_profit_growth_low_pct": logic.get("supported_growth_low_pct"),
            "hard_logic_supported_profit_growth_base_pct": logic.get("supported_growth_base_pct"),
            "hard_logic_supported_profit_growth_high_pct": logic.get("supported_growth_high_pct"),
        }
    )


def _sell_reason(price_map: Mapping[str, Any], logic: Mapping[str, Any]) -> str | None:
    if logic.get("state") == "BLOCKED":
        return "SELL_HARD_LOGIC_INVALIDATED"
    required = _finite(price_map.get("required_profit_growth_pct"))
    base = _finite(price_map.get("supported_profit_growth_base_pct"))
    percentile = _finite(price_map.get("historical_pe_percentile"))
    if required is None or percentile is None:
        return None
    high_valuation_zone = percentile >= MIN_EXIT_PE_PERCENTILE
    if base is not None and required >= base and high_valuation_zone:
        return "SELL_EXPECTATIONS_FULL_HIGH_VALUATION"
    if base is None and required >= 20 and high_valuation_zone:
        return "SELL_HISTORICAL_REFERENCE_PLUS20_HIGH_VALUATION"
    return None


def _signal(
    data: HistoricalCompanyData,
    day: date,
    action: str,
    reason: str,
    logic: Mapping[str, Any],
    valuation: Mapping[str, Any],
    price_map: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "code": data.code,
        "stock_name": data.stock_name,
        "signal_date": day,
        "signal_action": action,
        "reason": reason,
        "hard_logic_state": logic.get("state"),
        "hard_logic_score": logic.get("score"),
        "current_price": price_map.get("current_price"),
        "current_pe": valuation.get("current_pe"),
        "historical_reference_pe": valuation.get("historical_reference_pe"),
        "historical_pe_percentile": valuation.get("historical_pe_percentile"),
        "required_profit_growth_pct": price_map.get("required_profit_growth_pct"),
        "supported_growth_base_pct": price_map.get("supported_profit_growth_base_pct"),
        "expectation_headroom_pct": price_map.get("expectation_headroom_pct"),
        "buyable_price_ceiling": price_map.get("buyable_price_ceiling"),
        "deep_value_price_ceiling": price_map.get("deep_value_price_ceiling"),
    }


def simulate_company(
    data: HistoricalCompanyData,
    *,
    start_date: date,
    end_date: date,
    evaluation_stride: int = DEFAULT_STRIDE,
    cost_bps_per_side: float = 15.0,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    price = prepare_price_frame(data.price_df)
    price = price[(price["date"] >= start_date) & (price["date"] <= end_date)].reset_index(drop=True)
    financial = normalize_financial_point_in_time(data.financial_df)
    if len(price) < MIN_PRIOR_PE_OBSERVATIONS + 2:
        return [], [], {
            "code": data.code,
            "stock_name": data.stock_name,
            "status": "INSUFFICIENT_PRICE_HISTORY",
            "trade_count": 0,
            "data_warnings": ";".join(data.warnings),
        }

    trades: list[dict[str, Any]] = []
    signals: list[dict[str, Any]] = []
    cash = 1.0
    shares = 0.0
    position = None
    pending = None
    equity: list[float] = []
    first_close = _finite(price.iloc[0].get("close"))
    last_close = _finite(price.iloc[-1].get("close"))

    for i, bar in price.iterrows():
        day = bar["date"]
        open_price = _finite(bar.get("open"))
        close = _finite(bar.get("close"))
        if pending and pending["execute_index"] == i and open_price and open_price > 0:
            if pending["action"] == "BUY" and position is None:
                ceiling = _finite(pending.get("buyable_price_ceiling"))
                if ceiling is None or open_price <= ceiling:
                    entry = open_price * (1 + cost_bps_per_side / 10000.0)
                    shares = cash / entry
                    cash = 0.0
                    position = {**pending, "entry_date": day, "entry_price": entry, "entry_index": i}
            elif pending["action"] == "SELL" and position is not None:
                exit_price = open_price * (1 - cost_bps_per_side / 10000.0)
                cash = shares * exit_price
                shares = 0.0
                window = price.iloc[position["entry_index"] : i + 1]
                gross = (exit_price / position["entry_price"] - 1) * 100.0
                highs = pd.to_numeric(window["high"], errors="coerce").dropna().tolist()
                max_runup = ((max(highs) / position["entry_price"] - 1) * 100.0) if highs else gross
                exit_pct = _price_percentile(price.iloc[: i + 1], exit_price)
                trade = {
                    "code": data.code,
                    "stock_name": data.stock_name,
                    "entry_signal_date": position["signal_date"],
                    "entry_date": position["entry_date"],
                    "entry_price": round(position["entry_price"], 4),
                    "entry_decision": position["entry_decision"],
                    "entry_required_profit_growth_pct": position.get("required_profit_growth_pct"),
                    "entry_supported_growth_base_pct": position.get("supported_growth_base_pct"),
                    "entry_expectation_headroom_pct": position.get("expectation_headroom_pct"),
                    "entry_buyable_price_ceiling": position.get("buyable_price_ceiling"),
                    "entry_deep_value_price_ceiling": position.get("deep_value_price_ceiling"),
                    "entry_pe": position.get("current_pe"),
                    "entry_reference_pe": position.get("historical_reference_pe"),
                    "entry_pe_percentile": position.get("historical_pe_percentile"),
                    "entry_price_percentile_2y": position.get("entry_price_percentile_2y"),
                    "exit_signal_date": pending["signal_date"],
                    "exit_date": day,
                    "exit_price": round(exit_price, 4),
                    "exit_reason": pending["reason"],
                    "exit_required_profit_growth_pct": pending.get("required_profit_growth_pct"),
                    "exit_supported_growth_base_pct": pending.get("supported_growth_base_pct"),
                    "exit_pe_percentile": pending.get("historical_pe_percentile"),
                    "exit_price_percentile_2y": exit_pct,
                    "gross_return_pct": round(gross, 4),
                    "net_return_pct": round(gross, 4),
                    "max_runup_pct": round(max_runup, 4),
                    "max_drawdown_pct": _max_drawdown(
                        [position["entry_price"], *pd.to_numeric(window["close"], errors="coerce").dropna().tolist()]
                    ),
                    "capture_ratio_pct": round(gross / max_runup * 100.0, 4) if max_runup > 0 else None,
                    "holding_sessions": len(window),
                    "low_buy_high_sell": bool(
                        (_finite(position.get("entry_price_percentile_2y")) or 101) <= 40
                        and (_finite(exit_pct) or -1) >= 60
                        and gross > 0
                    ),
                }
                trades.append(trade)
                position = None
            pending = None

        if close and close > 0:
            equity.append(cash if position is None else shares * close)
        if i >= len(price) - 1 or i % max(1, evaluation_stride) != 0 or pending is not None or not close:
            continue

        valuation = point_in_time_valuation(data.valuation_df, day)
        logic = point_in_time_hard_logic(financial, day)
        if valuation is None:
            continue
        pmap = _price_map(data, day, close, valuation, logic)
        decision = str(pmap.get("price_decision") or "")
        pe_percentile = _finite(valuation.get("historical_pe_percentile"))
        low_zone_ok = bool(
            decision == "BUY_DEEP_VALUE"
            or (pe_percentile is not None and pe_percentile <= MAX_ENTRY_PE_PERCENTILE)
        )
        if position is None and logic["state"] == "PASS" and decision in BUY_DECISIONS and low_zone_ok:
            ceiling = _finite(pmap.get("buyable_price_ceiling"))
            if ceiling is not None and close <= ceiling:
                pending = {
                    "action": "BUY",
                    "execute_index": i + 1,
                    "signal_date": day,
                    "entry_decision": pmap["price_decision"],
                    "required_profit_growth_pct": pmap.get("required_profit_growth_pct"),
                    "supported_growth_base_pct": pmap.get("supported_profit_growth_base_pct"),
                    "expectation_headroom_pct": pmap.get("expectation_headroom_pct"),
                    "buyable_price_ceiling": ceiling,
                    "deep_value_price_ceiling": pmap.get("deep_value_price_ceiling"),
                    "current_pe": valuation["current_pe"],
                    "historical_reference_pe": valuation["historical_reference_pe"],
                    "historical_pe_percentile": valuation["historical_pe_percentile"],
                    "entry_price_percentile_2y": _price_percentile(price.iloc[: i + 1], close),
                }
                signals.append(_signal(data, day, "BUY", pmap["price_decision"], logic, valuation, pmap))
        elif position is not None:
            reason = _sell_reason(pmap, logic)
            if reason:
                pending = {
                    "action": "SELL",
                    "execute_index": i + 1,
                    "signal_date": day,
                    "reason": reason,
                    "required_profit_growth_pct": pmap.get("required_profit_growth_pct"),
                    "supported_growth_base_pct": pmap.get("supported_profit_growth_base_pct"),
                    "historical_pe_percentile": valuation["historical_pe_percentile"],
                }
                signals.append(_signal(data, day, "SELL", reason, logic, valuation, pmap))

    if position is not None and last_close and last_close > 0:
        exit_price = last_close * (1 - cost_bps_per_side / 10000.0)
        window = price.iloc[position["entry_index"] :]
        gross = (exit_price / position["entry_price"] - 1) * 100.0
        highs = pd.to_numeric(window["high"], errors="coerce").dropna().tolist()
        max_runup = ((max(highs) / position["entry_price"] - 1) * 100.0) if highs else gross
        trades.append(
            {
                "code": data.code,
                "stock_name": data.stock_name,
                "entry_signal_date": position["signal_date"],
                "entry_date": position["entry_date"],
                "entry_price": round(position["entry_price"], 4),
                "entry_decision": position["entry_decision"],
                "entry_required_profit_growth_pct": position.get("required_profit_growth_pct"),
                "entry_supported_growth_base_pct": position.get("supported_growth_base_pct"),
                "entry_expectation_headroom_pct": position.get("expectation_headroom_pct"),
                "entry_buyable_price_ceiling": position.get("buyable_price_ceiling"),
                "entry_deep_value_price_ceiling": position.get("deep_value_price_ceiling"),
                "entry_pe": position.get("current_pe"),
                "entry_reference_pe": position.get("historical_reference_pe"),
                "entry_pe_percentile": position.get("historical_pe_percentile"),
                "entry_price_percentile_2y": position.get("entry_price_percentile_2y"),
                "exit_signal_date": price.iloc[-1]["date"],
                "exit_date": price.iloc[-1]["date"],
                "exit_price": round(exit_price, 4),
                "exit_reason": "END_OF_TEST_MARK_TO_MARKET",
                "gross_return_pct": round(gross, 4),
                "net_return_pct": round(gross, 4),
                "max_runup_pct": round(max_runup, 4),
                "max_drawdown_pct": _max_drawdown(
                    [position["entry_price"], *pd.to_numeric(window["close"], errors="coerce").dropna().tolist()]
                ),
                "capture_ratio_pct": round(gross / max_runup * 100.0, 4) if max_runup > 0 else None,
                "holding_sessions": len(window),
                "exit_price_percentile_2y": _price_percentile(price, exit_price),
                "low_buy_high_sell": False,
            }
        )
        cash = shares * exit_price
        equity.append(cash)

    strategy = (cash - 1) * 100.0
    buy_hold = (last_close / first_close - 1) * 100.0 if first_close and last_close else None
    best = max(trades, key=lambda x: float(x["net_return_pct"])) if trades else None
    case = {
        "code": data.code,
        "stock_name": data.stock_name,
        "status": "OK" if trades else "NO_TRADE",
        "trade_count": len(trades),
        "win_rate_pct": round(sum(float(t["net_return_pct"]) > 0 for t in trades) / len(trades) * 100, 4) if trades else 0.0,
        "compounded_strategy_return_pct": round(strategy, 4),
        "buy_hold_return_pct": round(buy_hold, 4) if buy_hold is not None else None,
        "excess_return_pct": round(strategy - buy_hold, 4) if buy_hold is not None else None,
        "max_strategy_drawdown_pct": _max_drawdown(equity),
        "best_trade_return_pct": best["net_return_pct"] if best else None,
        "best_trade_entry_date": best["entry_date"] if best else None,
        "best_trade_exit_date": best["exit_date"] if best else None,
        "low_buy_high_sell_count": sum(bool(t.get("low_buy_high_sell")) for t in trades),
        "first_buy_price": trades[0]["entry_price"] if trades else None,
        "first_buyable_price_ceiling": trades[0].get("entry_buyable_price_ceiling") if trades else None,
        "capture_note": "ex-post named-case audit; not an unbiased expected-return estimate",
        "data_warnings": ";".join(data.warnings),
    }
    return trades, signals, case


def load_cases(path: Path) -> list[FamousCase]:
    return [
        FamousCase(_code(r.get("code")), str(r.get("stock_name") or r.get("code")), str(r.get("note") or ""))
        for r in csv.DictReader(path.open(encoding="utf-8"))
        if _code(r.get("code"))
    ]


def fetch_case_data(
    cases: list[FamousCase],
    *,
    as_of: date,
    years: int,
    cache_dir: Path,
) -> tuple[list[HistoricalCompanyData], list[dict[str, Any]]]:
    histories, audit = fetch_extended_adjusted_histories(
        candidates=[{"code": c.code, "stock_name": c.stock_name} for c in cases],
        as_of=as_of,
        cache_dir=cache_dir / "prices",
    )
    loader = PublicFundamentalLoader(cache_dir / "fundamentals")
    ready: list[HistoricalCompanyData] = []
    failures: list[dict[str, Any]] = []
    for case in cases:
        price = histories.get(case.code)
        if price is None or price.empty:
            failures.append({"code": case.code, "stock_name": case.stock_name, "reason": "price_history_unavailable"})
            continue
        fetched = loader.load(case.code, years=years, fetch_valuation=True, fetch_financial=True)
        if fetched.valuation_df is None or fetched.valuation_df.empty:
            failures.append({"code": case.code, "stock_name": case.stock_name, "reason": "valuation_history_unavailable"})
            continue
        if fetched.financial_df is None or fetched.financial_df.empty:
            failures.append({"code": case.code, "stock_name": case.stock_name, "reason": "financial_history_unavailable"})
            continue
        warnings = [json.dumps(fetched.provider_errors, ensure_ascii=False, sort_keys=True)] if fetched.provider_errors else []
        ready.append(HistoricalCompanyData(case.code, case.stock_name, price, fetched.valuation_df, fetched.financial_df, warnings))
    if isinstance(audit, Mapping) and audit.get("failed_codes"):
        failures.append(
            {
                "code": "__history_audit__",
                "stock_name": "",
                "reason": json.dumps(audit.get("failed_codes"), ensure_ascii=False),
            }
        )
    return ready, failures


def _write_csv(path: Path, rows: list[dict[str, Any]], fallback_fields: list[str]) -> None:
    fields = sorted({key for row in rows for key in row}) if rows else fallback_fields
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def run_suite(
    cases: list[FamousCase],
    *,
    start_date: date,
    end_date: date,
    output_dir: Path,
    cache_dir: Path,
    evaluation_stride: int = DEFAULT_STRIDE,
    cost_bps_per_side: float = 15.0,
) -> dict[str, Any]:
    years = max(3, int((end_date - start_date).days / 365.25) + 2)
    ready, failures = fetch_case_data(cases, as_of=end_date, years=years, cache_dir=cache_dir)
    trades: list[dict[str, Any]] = []
    signals: list[dict[str, Any]] = []
    case_rows: list[dict[str, Any]] = []
    for data in ready:
        t, s, c = simulate_company(
            data,
            start_date=start_date,
            end_date=end_date,
            evaluation_stride=evaluation_stride,
            cost_bps_per_side=cost_bps_per_side,
        )
        trades += t
        signals += s
        case_rows.append(c)
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "historical_trades.csv", trades, ["code", "stock_name"])
    _write_csv(output_dir / "historical_signals.csv", signals, ["code", "stock_name"])
    _write_csv(output_dir / "famous_case_results.csv", case_rows, ["code", "stock_name", "status"])
    _write_csv(output_dir / "data_failures.csv", failures, ["code", "stock_name", "reason"])
    trade_returns = [float(t["net_return_pct"]) for t in trades]
    summary = {
        "rule_version": RULE_VERSION,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "requested_case_count": len(cases),
        "data_ready_case_count": len(ready),
        "failed_case_count": len(failures),
        "case_with_trade_count": sum(int(c.get("trade_count") or 0) > 0 for c in case_rows),
        "trade_count": len(trades),
        "trade_win_rate_pct": round(sum(x > 0 for x in trade_returns) / len(trade_returns) * 100, 4) if trade_returns else 0.0,
        "median_trade_return_pct": round(float(median(trade_returns)), 4) if trade_returns else None,
        "mean_trade_return_pct": round(sum(trade_returns) / len(trade_returns), 4) if trade_returns else None,
        "low_buy_high_sell_trade_count": sum(bool(t.get("low_buy_high_sell")) for t in trades),
        "evaluation_stride_sessions": evaluation_stride,
        "cost_bps_per_side": cost_bps_per_side,
        "valuation_low_zone_entry_required": True,
        "max_entry_pe_percentile": MAX_ENTRY_PE_PERCENTILE,
        "deep_value_bypasses_pe_percentile_gate": True,
        "high_valuation_exit_required": True,
        "min_exit_pe_percentile": MIN_EXIT_PE_PERCENTILE,
        "point_in_time_financials": True,
        "next_open_execution": True,
        "famous_case_selection_bias_warning": True,
        "headline_expected_return_allowed": False,
        "no_auto_trade": True,
        "disclaimer": DISCLAIMER,
    }
    (output_dir / "historical_backtest_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    lines = [
        "# Hard Logic × Reverse Valuation Historical Backtest",
        "",
        f"- period: {start_date} to {end_date}",
        f"- data-ready cases: {len(ready)}/{len(cases)}",
        f"- cases with trades: {summary['case_with_trade_count']}",
        f"- trades: {len(trades)}",
        f"- win rate: {summary['trade_win_rate_pct']}%",
        f"- median trade return: {summary['median_trade_return_pct']}%",
        "",
        "> Named famous stocks are an ex-post capture audit; do not treat this panel return as unbiased expected return.",
        "",
        "## Cases",
    ]
    for row in sorted(case_rows, key=lambda x: float(x.get("compounded_strategy_return_pct") or -1e9), reverse=True):
        lines.append(
            f"- {row['code']} {row['stock_name']} | trades={row['trade_count']} | "
            f"strategy={row.get('compounded_strategy_return_pct')}% | buy_hold={row.get('buy_hold_return_pct')}% | "
            f"maxDD={row.get('max_strategy_drawdown_pct')}% | best={row.get('best_trade_return_pct')}% | "
            f"low/high={row.get('low_buy_high_sell_count')}"
        )
    if failures:
        lines += ["", "## Data failures"] + [
            f"- {r['code']} {r['stock_name']} | {r['reason']}" for r in failures
        ]
    (output_dir / "historical_backtest.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases-file", type=Path, required=True)
    parser.add_argument("--start-date", type=date.fromisoformat, default=date(2017, 1, 1))
    parser.add_argument("--end-date", type=date.fromisoformat, default=date.today())
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, default=Path("data/cache/hard_logic_history_backtest"))
    parser.add_argument("--evaluation-stride", type=int, default=DEFAULT_STRIDE)
    parser.add_argument("--cost-bps-per-side", type=float, default=15.0)
    args = parser.parse_args(argv)
    summary = run_suite(
        load_cases(args.cases_file),
        start_date=args.start_date,
        end_date=args.end_date,
        output_dir=args.output_dir,
        cache_dir=args.cache_dir,
        evaluation_stride=max(1, args.evaluation_stride),
        cost_bps_per_side=max(0.0, args.cost_bps_per_side),
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["data_ready_case_count"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
