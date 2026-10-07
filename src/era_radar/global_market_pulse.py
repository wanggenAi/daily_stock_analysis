"""Independent global research clock and pre-open intelligence for A-share investing.

The module observes global risk assets while A shares may be closed, reuses the
existing commodity benchmark collector, computes moves accumulated since the
last valid A-share close, and maps only explicit evidence-backed commodity
exposures to securities. Everything here is RESEARCH_ONLY: no Formal action,
canonical valuation or broker order can be created or mutated.
"""
from __future__ import annotations

from datetime import date, datetime, time, timezone
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import pandas as pd

from src.strategies.genge_opportunity_discovery.commodity_price_evidence_collector import (
    fetch_benchmark_series,
)

CONTRACT_VERSION = "GEN_GE_GLOBAL_MARKET_PULSE_V2"

DEFAULT_INSTRUMENTS: tuple[dict[str, Any], ...] = (
    {"id": "SP500", "symbol": "^GSPC", "label": "S&P 500", "family": "RISK_EQUITY", "critical": True},
    {"id": "NASDAQ", "symbol": "^IXIC", "label": "Nasdaq Composite", "family": "RISK_EQUITY", "critical": True},
    {"id": "NASDAQ100", "symbol": "^NDX", "label": "Nasdaq 100", "family": "RISK_EQUITY", "critical": False},
    {"id": "DOW", "symbol": "^DJI", "label": "Dow Jones", "family": "RISK_EQUITY", "critical": False},
    {"id": "RUSSELL2000", "symbol": "^RUT", "label": "Russell 2000", "family": "RISK_EQUITY", "critical": False},
    {"id": "SOX", "symbol": "^SOX", "label": "PHLX Semiconductor", "family": "TECH_SEMICONDUCTOR", "critical": False},
    {"id": "VIX", "symbol": "^VIX", "label": "VIX", "family": "VOLATILITY", "critical": True},
    {"id": "US10Y", "symbol": "^TNX", "label": "US 10Y Treasury Yield", "family": "RATES", "critical": True},
    {"id": "DXY", "symbol": "DX-Y.NYB", "label": "US Dollar Index", "family": "FX", "critical": True},
    {"id": "USDCNH", "symbol": "CNH=X", "label": "USD/CNH", "family": "FX", "critical": False},
    {"id": "HANGSENG", "symbol": "^HSI", "label": "Hang Seng", "family": "CHINA_OFFSHORE", "critical": False},
    {"id": "HANGSENGTECH", "symbol": "^HSTECH", "label": "Hang Seng Tech", "family": "CHINA_OFFSHORE", "critical": False},
    {"id": "NIKKEI225", "symbol": "^N225", "label": "Nikkei 225", "family": "GLOBAL_EQUITY", "critical": False},
    {"id": "DAX", "symbol": "^GDAXI", "label": "DAX", "family": "GLOBAL_EQUITY", "critical": False},
    {"id": "EUROSTOXX50", "symbol": "^STOXX50E", "label": "Euro Stoxx 50", "family": "GLOBAL_EQUITY", "critical": False},
    {"id": "BTC", "symbol": "BTC-USD", "label": "Bitcoin", "family": "RISK_APPETITE_PROXY", "critical": False},
    {"id": "ETH", "symbol": "ETH-USD", "label": "Ethereum", "family": "RISK_APPETITE_PROXY", "critical": False},
)

UNAVAILABLE_MACRO = (
    {"id": "US2Y", "label": "US 2Y Treasury Yield", "family": "RATES", "reason": "NO_RELIABLE_FREE_SOURCE_WIRED"},
    {"id": "CURVE_2S10S", "label": "US 2Y-10Y Curve", "family": "RATES", "reason": "US2Y_UNAVAILABLE"},
)


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _pct(latest: float | None, base: float | None) -> float | None:
    if latest is None or base in (None, 0.0):
        return None
    return round((latest / base - 1.0) * 100.0, 4)


def _parse_trade_date(value: Any) -> date | None:
    text = str(value or "").strip()[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _a_share_close_utc(trade_date: Any) -> datetime | None:
    day = _parse_trade_date(trade_date)
    if day is None:
        return None
    # 15:00 Asia/Shanghai == 07:00 UTC (China has no DST).
    return datetime.combine(day, time(7, 0), tzinfo=timezone.utc)


def _freshness(latest_at: datetime | None, now: datetime) -> tuple[str, float | None]:
    if latest_at is None:
        return "UNAVAILABLE", None
    age_hours = max(0.0, (now - latest_at).total_seconds() / 3600.0)
    if age_hours <= 8:
        return "FRESH", round(age_hours, 2)
    if age_hours <= 72:
        return "LAST_VALID_MARKET_OBSERVATION", round(age_hours, 2)
    return "STALE", round(age_hours, 2)


def _normalized_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame(columns=["close"])
    result = frame.copy()
    result.columns = [str(c).lower() for c in result.columns]
    if "close" not in result.columns:
        return pd.DataFrame(columns=["close"])
    result = result[["close"]].copy()
    result["close"] = pd.to_numeric(result["close"], errors="coerce")
    result = result.dropna(subset=["close"])
    if result.empty:
        return result
    result.index = pd.to_datetime(result.index, utc=True, errors="coerce")
    result = result[~result.index.isna()]
    return result.sort_index()


def summarize_history(
    frame: pd.DataFrame,
    *,
    a_share_last_trade_date: Any = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Summarize an intraday series without coupling freshness to the A-share clock."""
    now = now or datetime.now(timezone.utc)
    data = _normalized_frame(frame)
    if len(data) < 2:
        return {
            "status": "INSUFFICIENT_SERIES",
            "observed_at": now.isoformat(),
            "market_date": None,
            "latest_at": None,
            "latest": None,
            "age_hours": None,
            "freshness": "UNAVAILABLE",
            "change_1h_pct": None,
            "change_24h_pct": None,
            "change_5d_pct": None,
            "since_last_a_share_close_pct": None,
        }

    latest = _finite(data.iloc[-1]["close"])
    previous = _finite(data.iloc[-2]["close"])
    latest_ts = data.index[-1].to_pydatetime()

    def _anchor(hours: int) -> float | None:
        cutoff = data.index[-1] - pd.Timedelta(hours=hours)
        eligible = data[data.index <= cutoff]
        return _finite(eligible.iloc[-1]["close"]) if not eligible.empty else None

    holiday_anchor = None
    close_utc = _a_share_close_utc(a_share_last_trade_date)
    if close_utc is not None:
        eligible = data[data.index <= pd.Timestamp(close_utc)]
        if not eligible.empty:
            holiday_anchor = _finite(eligible.iloc[-1]["close"])

    freshness, age_hours = _freshness(latest_ts, now)
    return {
        "status": "OK",
        "observed_at": now.isoformat(),
        "market_date": latest_ts.date().isoformat(),
        "latest_at": latest_ts.isoformat(),
        "latest": latest,
        "age_hours": age_hours,
        "freshness": freshness,
        "change_1h_pct": _pct(latest, previous),
        "change_24h_pct": _pct(latest, _anchor(24)),
        "change_5d_pct": _pct(latest, _anchor(24 * 5)),
        "since_last_a_share_close_pct": _pct(latest, holiday_anchor),
        "a_share_anchor_trade_date": _parse_trade_date(a_share_last_trade_date).isoformat()
        if _parse_trade_date(a_share_last_trade_date)
        else None,
    }


def summarize_commodity_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    provider: str,
    a_share_last_trade_date: Any = None,
    now: datetime | None = None,
    source_errors: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Normalize the shared commodity collector's daily series into pulse fields."""
    now = now or datetime.now(timezone.utc)
    normalized: list[tuple[date, float]] = []
    for row in rows:
        day = _parse_trade_date(row.get("date"))
        close = _finite(row.get("close"))
        if day is not None and close is not None:
            normalized.append((day, close))
    normalized.sort(key=lambda item: item[0])
    if len(normalized) < 2:
        return {
            "status": "INSUFFICIENT_SERIES",
            "observed_at": now.isoformat(),
            "market_date": None,
            "latest_at": None,
            "latest": None,
            "age_hours": None,
            "freshness": "UNAVAILABLE",
            "change_1h_pct": None,
            "change_24h_pct": None,
            "change_1d_pct": None,
            "change_5d_pct": None,
            "since_last_a_share_close_pct": None,
            "provider": provider,
            "source_errors": list(source_errors or []),
        }
    latest_day, latest = normalized[-1]
    previous = normalized[-2][1]
    five_anchor = normalized[max(0, len(normalized) - 6)][1]
    anchor_day = _parse_trade_date(a_share_last_trade_date)
    holiday_anchor = None
    if anchor_day is not None:
        eligible = [close for day, close in normalized if day <= anchor_day]
        if eligible:
            holiday_anchor = eligible[-1]
    latest_dt = datetime.combine(latest_day, time(23, 59), tzinfo=timezone.utc)
    freshness, age_hours = _freshness(latest_dt, now)
    return {
        "status": "OK",
        "observed_at": now.isoformat(),
        "market_date": latest_day.isoformat(),
        "latest_at": latest_dt.isoformat(),
        "latest": latest,
        "age_hours": age_hours,
        "freshness": freshness,
        "change_1h_pct": None,
        "change_24h_pct": _pct(latest, previous),
        "change_1d_pct": _pct(latest, previous),
        "change_5d_pct": _pct(latest, five_anchor),
        "since_last_a_share_close_pct": _pct(latest, holiday_anchor),
        "a_share_anchor_trade_date": anchor_day.isoformat() if anchor_day else None,
        "provider": provider,
        "source_errors": list(source_errors or []),
    }


def fetch_yfinance_history(symbol: str) -> pd.DataFrame:
    import yfinance as yf

    return yf.Ticker(symbol).history(
        period="1mo",
        interval="1h",
        auto_adjust=False,
        actions=False,
        prepost=False,
        timeout=12,
    )


def _risk_component(instrument_id: str, summary: Mapping[str, Any]) -> float | None:
    move = _finite(summary.get("change_24h_pct"))
    if move is None:
        return None
    if instrument_id in {"SP500", "NASDAQ", "NASDAQ100", "RUSSELL2000", "HANGSENG", "HANGSENGTECH", "BTC", "ETH"}:
        return max(-2.0, min(2.0, move / 2.0))
    if instrument_id == "VIX":
        return max(-2.0, min(2.0, -move / 6.0))
    if instrument_id == "USDCNH":
        return max(-2.0, min(2.0, -move / 1.0))
    if instrument_id == "DXY":
        return max(-2.0, min(2.0, -move / 1.5))
    if instrument_id == "US10Y":
        return max(-1.5, min(1.5, -move / 4.0))
    return None


def _market_regime(series: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    components: list[float] = []
    for instrument_id in (
        "SP500", "NASDAQ", "NASDAQ100", "VIX", "US10Y", "DXY", "USDCNH",
        "HANGSENG", "HANGSENGTECH", "BTC", "ETH",
    ):
        summary = series.get(instrument_id) or {}
        if summary.get("status") != "OK" or summary.get("freshness") == "STALE":
            continue
        component = _risk_component(instrument_id, summary)
        if component is not None:
            components.append(component)
    if not components:
        return {"status": "UNKNOWN", "score": None, "component_count": 0}
    raw = sum(components) / len(components)
    score = max(0.0, min(100.0, round(50.0 + raw * 20.0, 2)))
    status = "RISK_OFF" if score < 38 else "RISK_ON" if score > 62 else "NEUTRAL"
    return {"status": status, "score": score, "component_count": len(components)}


def _context_row(name: str, factor_ids: Sequence[str], series: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    factors = []
    for factor_id in factor_ids:
        row = series.get(factor_id) or {}
        if row.get("status") == "OK":
            factors.append(
                {
                    "factor_id": factor_id,
                    "since_last_a_share_close_pct": row.get("since_last_a_share_close_pct"),
                    "change_24h_pct": row.get("change_24h_pct"),
                    "freshness": row.get("freshness"),
                }
            )
    return {"context": name, "factors": factors, "authority": "GLOBAL_MACRO_CONTEXT", "formal_action_eligible": False}


def build_global_context(series: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        _context_row("AI_SEMICONDUCTOR_RISK_APPETITE", ("SOX", "NASDAQ100", "NASDAQ"), series),
        _context_row("GROWTH_DURATION_FINANCIAL_CONDITIONS", ("US10Y", "DXY", "VIX"), series),
        _context_row("CHINA_OFFSHORE_RISK_APPETITE", ("HANGSENG", "HANGSENGTECH", "USDCNH"), series),
        _context_row("GLOBAL_RESOURCE_COMPLEX", ("COPPER", "GOLD", "SILVER", "CRUDE_OIL"), series),
        _context_row("LIQUIDITY_RISK_APPETITE_PROXY", ("BTC", "ETH"), series),
    ]


def _transmission_move(summary: Mapping[str, Any]) -> float | None:
    move = _finite(summary.get("since_last_a_share_close_pct"))
    return move if move is not None else _finite(summary.get("change_5d_pct"))


def build_security_transmission(
    series: Mapping[str, Mapping[str, Any]],
    commodity_config: Mapping[str, Any],
    *,
    security_names: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Map only explicit evidence-backed commodity exposures to securities."""
    names = dict(security_names or {})
    rows: list[dict[str, Any]] = []
    for raw_code, exposures in (commodity_config.get("security_exposures") or {}).items():
        code = str(raw_code).zfill(6)
        if not isinstance(exposures, list):
            continue
        factors: list[dict[str, Any]] = []
        for exposure in exposures:
            if not isinstance(exposure, Mapping):
                continue
            factor_id = str(exposure.get("benchmark_id") or "")
            summary = series.get(factor_id) or {}
            if summary.get("status") != "OK":
                continue
            move = _transmission_move(summary)
            if move is None:
                continue
            producer_positive = str(exposure.get("exposure_direction") or "PRODUCER_POSITIVE").upper() == "PRODUCER_POSITIVE"
            favorable = move > 0 if producer_positive else move < 0
            abs_move = abs(move)
            material = abs_move >= 2.0
            direction = "STRENGTHENING" if favorable and material else "WEAKENING" if material else "NEUTRAL"
            factors.append(
                {
                    "factor_id": factor_id,
                    "change_24h_pct": summary.get("change_24h_pct"),
                    "change_5d_pct": summary.get("change_5d_pct"),
                    "since_last_a_share_close_pct": summary.get("since_last_a_share_close_pct"),
                    "direction": direction,
                    "legacy_direction": "FAVORABLE" if favorable else "ADVERSE",
                    "material": material,
                    "magnitude": "HIGH" if abs_move >= 5 else "MEDIUM" if material else "LOW",
                    "freshness": summary.get("freshness"),
                    "market_date": summary.get("market_date"),
                    "provider": summary.get("provider"),
                    "evidence_ref": exposure.get("evidence_ref"),
                    "exposure_direction": exposure.get("exposure_direction") or "PRODUCER_POSITIVE",
                }
            )
        if not factors:
            continue
        strengthening = sum(f["direction"] == "STRENGTHENING" for f in factors)
        weakening = sum(f["direction"] == "WEAKENING" for f in factors)
        if strengthening and not weakening:
            direction = "STRENGTHENING"
            signal = "FAVORABLE"
        elif weakening and not strengthening:
            direction = "WEAKENING"
            signal = "ADVERSE"
        elif strengthening or weakening:
            direction = "MIXED"
            signal = "MIXED"
        else:
            direction = "NEUTRAL"
            signal = "NEUTRAL"
        material_count = strengthening + weakening
        rows.append(
            {
                "code": code,
                "name": names.get(code, ""),
                "signal": signal,
                "direction": direction,
                "magnitude": "HIGH" if any(f["magnitude"] == "HIGH" for f in factors) else "MEDIUM" if material_count else "LOW",
                "freshness": "STALE" if any(f["freshness"] == "STALE" for f in factors) else "CURRENT_OR_LAST_VALID",
                "confidence": "PUBLIC_MARKET_PLUS_EXPLICIT_EXPOSURE",
                "relevant_global_factors": [f["factor_id"] for f in factors],
                "factors": factors,
                "transmission_reason": "Only explicit issuer/evidence-backed commodity exposure mappings are applied; global index moves remain context, not company fundamentals.",
                "evidence_refs": sorted({str(f["evidence_ref"]) for f in factors if f.get("evidence_ref")}),
                "research_implication": "REASSESS_VALUATION_AND_DEEP_REVIEW" if material_count else "MONITOR_EXTERNAL_CONTEXT",
                "authority": "RESEARCH_ONLY",
                "formal_action_eligible": False,
                "formal_action_mutation_allowed": False,
                "automatic_promotion_allowed": False,
                "no_auto_trade": True,
            }
        )
    return rows


def build_pre_open_intelligence(
    series: Mapping[str, Mapping[str, Any]],
    *,
    a_share_last_trade_date: Any,
) -> dict[str, Any]:
    anchor = _parse_trade_date(a_share_last_trade_date)
    factor_ids = (
        "SP500", "NASDAQ", "SOX", "VIX", "US10Y", "DXY", "USDCNH",
        "HANGSENG", "HANGSENGTECH", "COPPER", "GOLD", "CRUDE_OIL", "BTC", "ETH",
    )
    accumulated = []
    moves: dict[str, float] = {}
    for factor_id in factor_ids:
        row = series.get(factor_id) or {}
        move = _finite(row.get("since_last_a_share_close_pct"))
        if row.get("status") != "OK":
            continue
        accumulated.append(
            {
                "factor_id": factor_id,
                "since_last_a_share_close_pct": move,
                "latest_1d_pct": row.get("change_24h_pct"),
                "5d_pct": row.get("change_5d_pct"),
                "market_date": row.get("market_date"),
                "freshness": row.get("freshness"),
            }
        )
        if move is not None:
            moves[factor_id] = move

    risk_flags: list[str] = []
    if min(moves.get("SP500", 0.0), moves.get("NASDAQ", 0.0)) <= -2.0:
        risk_flags.append("US_EQUITY_DRAWDOWN")
    if moves.get("VIX", 0.0) >= 15.0:
        risk_flags.append("VOLATILITY_SPIKE")
    if moves.get("US10Y", 0.0) >= 5.0:
        risk_flags.append("US_YIELD_SHOCK")
    if moves.get("DXY", 0.0) >= 1.5:
        risk_flags.append("USD_STRENGTH_PRESSURE")
    if moves.get("USDCNH", 0.0) >= 1.0:
        risk_flags.append("RMB_DEPRECIATION_PRESSURE")
    if moves.get("CRUDE_OIL", 0.0) >= 5.0 or moves.get("CRUDE_OIL", 0.0) <= -5.0:
        risk_flags.append("OIL_PRICE_SHOCK")

    opportunity_flags: list[str] = []
    if moves.get("COPPER", 0.0) >= 2.0:
        opportunity_flags.append("COPPER_POSITIVE_ACCUMULATION")
    if moves.get("GOLD", 0.0) >= 2.0:
        opportunity_flags.append("GOLD_POSITIVE_ACCUMULATION")
    if moves.get("SOX", 0.0) >= 3.0 and moves.get("NASDAQ", 0.0) >= 2.0:
        opportunity_flags.append("GLOBAL_SEMICONDUCTOR_RISK_ON")
    if moves.get("HANGSENGTECH", 0.0) >= 3.0:
        opportunity_flags.append("CHINA_OFFSHORE_TECH_RISK_ON")

    gap_risk = "HIGH" if len(risk_flags) >= 2 else "ELEVATED" if risk_flags else "NORMAL"
    positive = "MATERIAL" if opportunity_flags else "NONE_IDENTIFIED"
    watch = []
    if gap_risk != "NORMAL":
        watch.append("Open with reduced risk appetite until A-share price discovery confirms external gap absorption.")
    if any(flag.startswith("COPPER") or flag.startswith("GOLD") for flag in opportunity_flags):
        watch.append("Re-evaluate explicitly mapped resource producers against current valuation and entry-price gates.")
    if "GLOBAL_SEMICONDUCTOR_RISK_ON" in opportunity_flags:
        watch.append("Prioritize semiconductor/AI candidates for research refresh; do not substitute index strength for company evidence.")
    if not watch:
        watch.append("No material holiday gap signal; use global pulse as context and keep company-level gates authoritative.")

    return {
        "status": "AVAILABLE" if anchor and accumulated else "PARTIAL" if accumulated else "UNAVAILABLE",
        "a_share_last_trade_date": anchor.isoformat() if anchor else None,
        "calculation_basis": "ACCUMULATED_SINCE_LAST_A_SHARE_CLOSE",
        "accumulated_holiday_moves": accumulated,
        "holiday_gap_risk": gap_risk,
        "holiday_gap_risk_flags": risk_flags,
        "holiday_positive_accumulation": positive,
        "holiday_positive_flags": opportunity_flags,
        "next_a_share_open_watch": watch,
        "authority": "RESEARCH_ONLY",
        "formal_action_eligible": False,
        "automatic_promotion_allowed": False,
        "no_auto_trade": True,
    }


def build_global_market_pulse(
    *,
    instruments: Sequence[Mapping[str, Any]] = DEFAULT_INSTRUMENTS,
    history_fetcher: Callable[[str], pd.DataFrame] = fetch_yfinance_history,
    commodity_config: Mapping[str, Any] | None = None,
    commodity_series_fetcher: Callable[[str, str], tuple[list[dict[str, Any]], str, list[str]]] | None = None,
    security_names: Mapping[str, str] | None = None,
    a_share_last_trade_date: Any = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    series: dict[str, dict[str, Any]] = {}
    failures: list[dict[str, str]] = []
    critical_ids: list[str] = []

    for spec in instruments:
        instrument_id = str(spec.get("id") or "")
        symbol = str(spec.get("symbol") or "")
        if not instrument_id or not symbol:
            continue
        if spec.get("critical") is True:
            critical_ids.append(instrument_id)
        try:
            summary = summarize_history(
                history_fetcher(symbol),
                a_share_last_trade_date=a_share_last_trade_date,
                now=now,
            )
        except Exception as exc:
            summary = {
                "status": f"FETCH_ERROR:{type(exc).__name__}",
                "observed_at": now.isoformat(),
                "market_date": None,
                "latest_at": None,
                "latest": None,
                "age_hours": None,
                "freshness": "UNAVAILABLE",
                "change_1h_pct": None,
                "change_24h_pct": None,
                "change_5d_pct": None,
                "since_last_a_share_close_pct": None,
            }
            failures.append({"id": instrument_id, "error": type(exc).__name__})
        summary.update(
            {
                "symbol": symbol,
                "label": spec.get("label") or instrument_id,
                "family": spec.get("family") or "OTHER",
                "critical": spec.get("critical") is True,
                "provider": "yfinance_public_market",
            }
        )
        if summary.get("status") != "OK" and not any(row["id"] == instrument_id for row in failures):
            failures.append({"id": instrument_id, "error": str(summary.get("status") or "UNKNOWN")})
        series[instrument_id] = summary

    config = dict(commodity_config or {})
    for benchmark_id, spec in (config.get("benchmarks") or {}).items():
        if not isinstance(spec, Mapping):
            continue
        stooq_symbol = str(spec.get("symbol") or "")
        try:
            if commodity_series_fetcher is None:
                rows, provider, source_errors = fetch_benchmark_series(str(benchmark_id), stooq_symbol)
            else:
                rows, provider, source_errors = commodity_series_fetcher(str(benchmark_id), stooq_symbol)
            summary = summarize_commodity_rows(
                rows,
                provider=provider,
                a_share_last_trade_date=a_share_last_trade_date,
                now=now,
                source_errors=source_errors,
            )
        except Exception as exc:
            summary = summarize_commodity_rows(
                [],
                provider="commodity_collector_error",
                a_share_last_trade_date=a_share_last_trade_date,
                now=now,
                source_errors=[type(exc).__name__],
            )
        summary.update(
            {
                "symbol": stooq_symbol,
                "label": spec.get("label") or benchmark_id,
                "family": "COMMODITY",
                "critical": str(benchmark_id) in {"COPPER", "CRUDE_OIL"},
            }
        )
        if summary["critical"]:
            critical_ids.append(str(benchmark_id))
        if summary.get("status") != "OK":
            failures.append({"id": str(benchmark_id), "error": str(summary.get("status") or "UNKNOWN")})
        series[str(benchmark_id)] = summary

    for spec in UNAVAILABLE_MACRO:
        series[spec["id"]] = {
            "status": "UNAVAILABLE",
            "observed_at": now.isoformat(),
            "market_date": None,
            "latest_at": None,
            "latest": None,
            "age_hours": None,
            "freshness": "UNAVAILABLE",
            "change_1h_pct": None,
            "change_24h_pct": None,
            "change_5d_pct": None,
            "since_last_a_share_close_pct": None,
            "label": spec["label"],
            "family": spec["family"],
            "critical": False,
            "provider": None,
            "unavailable_reason": spec["reason"],
        }

    ok_ids = [key for key, value in series.items() if value.get("status") == "OK"]
    critical_ok = [key for key in critical_ids if (series.get(key) or {}).get("status") == "OK"]
    critical_ratio = 0.0 if not critical_ids else len(critical_ok) / len(critical_ids)
    risk_equity_ok = any((series.get(key) or {}).get("status") == "OK" for key in ("SP500", "NASDAQ"))
    commodity_ok = any((series.get(key) or {}).get("status") == "OK" for key in ("COPPER", "CRUDE_OIL", "GOLD"))
    if not ok_ids:
        coverage_status = "UNAVAILABLE"
    elif critical_ratio >= 0.70 and risk_equity_ok and commodity_ok:
        coverage_status = "OK"
    else:
        coverage_status = "PARTIAL"

    latest_times = [
        str(value.get("latest_at"))
        for value in series.values()
        if value.get("status") == "OK" and value.get("latest_at")
    ]
    transmission = build_security_transmission(series, config, security_names=security_names)
    pre_open = build_pre_open_intelligence(series, a_share_last_trade_date=a_share_last_trade_date)
    return {
        "contract_version": CONTRACT_VERSION,
        "generated_at": now.isoformat(),
        "clock": "GLOBAL_MARKET_INDEPENDENT_OF_A_SHARE_CALENDAR",
        "a_share_market_clock": {"last_valid_trade_date": _parse_trade_date(a_share_last_trade_date).isoformat() if _parse_trade_date(a_share_last_trade_date) else None},
        "global_research_clock": {"observed_at": now.isoformat(), "continues_during_a_share_holidays": True},
        "a_share_market_open_required": False,
        "coverage": {
            "status": coverage_status,
            "instrument_count": len(series),
            "ok_count": len(ok_ids),
            "critical_count": len(critical_ids),
            "critical_ok_count": len(critical_ok),
            "critical_coverage_ratio": round(critical_ratio, 4),
            "latest_observation_at": max(latest_times) if latest_times else None,
            "failures": failures,
        },
        "risk_regime": _market_regime(series),
        "series": series,
        "global_context": build_global_context(series),
        "security_transmission": transmission,
        "pre_open_intelligence": pre_open,
        "authority": "RESEARCH_ONLY",
        "formal_trading_authority": False,
        "formal_action_eligible": False,
        "formal_action_mutation_allowed": False,
        "automatic_promotion_allowed": False,
        "unknown_is_pass": False,
        "no_auto_trade": True,
    }


def _semantic_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    semantic = json.loads(json.dumps(payload))
    semantic.pop("generated_at", None)
    if isinstance(semantic.get("global_research_clock"), dict):
        semantic["global_research_clock"].pop("observed_at", None)
    for row in (semantic.get("series") or {}).values():
        if isinstance(row, dict):
            row.pop("observed_at", None)
            row.pop("age_hours", None)
    return semantic


def semantic_fingerprint(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(_semantic_payload(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def persist_if_changed(payload: Mapping[str, Any], output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    latest_path = output_dir / "latest.json"
    new_fp = semantic_fingerprint(payload)
    if latest_path.exists():
        try:
            old = json.loads(latest_path.read_text(encoding="utf-8"))
            if semantic_fingerprint(old) == new_fp:
                return {"status": "UNCHANGED", "path": str(latest_path), "fingerprint": new_fp}
        except Exception:
            pass
    latest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    stamp = str(payload.get("generated_at") or "").replace(":", "").replace("-", "")
    history_dir = output_dir / "history"
    history_dir.mkdir(parents=True, exist_ok=True)
    history_path = history_dir / f"{stamp or new_fp[:16]}.json"
    history_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"status": "UPDATED", "path": str(latest_path), "history_path": str(history_path), "fingerprint": new_fp}
