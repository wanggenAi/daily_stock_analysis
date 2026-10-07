"""Global market pulse that runs independently of the A-share trading calendar.

This module is research-only. It observes liquid global market proxies, records
explicit coverage/freshness, and derives a bounded cross-market risk pulse.
It never creates or mutates Formal actions, broker orders, or Canonical values.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import pandas as pd

CONTRACT_VERSION = "GEN_GE_GLOBAL_MARKET_PULSE_V1"

DEFAULT_INSTRUMENTS: tuple[dict[str, Any], ...] = (
    {"id": "SP500", "symbol": "^GSPC", "label": "S&P 500", "family": "RISK_EQUITY", "critical": True},
    {"id": "NASDAQ", "symbol": "^IXIC", "label": "Nasdaq Composite", "family": "RISK_EQUITY", "critical": True},
    {"id": "VIX", "symbol": "^VIX", "label": "VIX", "family": "VOLATILITY", "critical": True},
    {"id": "US10Y", "symbol": "^TNX", "label": "US 10Y Treasury Yield", "family": "RATES", "critical": True},
    {"id": "DXY", "symbol": "DX-Y.NYB", "label": "US Dollar Index", "family": "FX", "critical": True},
    {"id": "USDCNH", "symbol": "CNH=X", "label": "USD/CNH", "family": "FX", "critical": False},
    {"id": "COPPER", "symbol": "HG=F", "label": "Copper", "family": "COMMODITY", "critical": True},
    {"id": "GOLD", "symbol": "GC=F", "label": "Gold", "family": "COMMODITY", "critical": False},
    {"id": "WTI", "symbol": "CL=F", "label": "WTI Crude Oil", "family": "COMMODITY", "critical": True},
    {"id": "NIKKEI225", "symbol": "^N225", "label": "Nikkei 225", "family": "GLOBAL_EQUITY", "critical": False},
    {"id": "HANGSENG", "symbol": "^HSI", "label": "Hang Seng", "family": "CHINA_OFFSHORE", "critical": False},
    {"id": "EUROSTOXX50", "symbol": "^STOXX50E", "label": "Euro Stoxx 50", "family": "GLOBAL_EQUITY", "critical": False},
    {"id": "BTC", "symbol": "BTC-USD", "label": "Bitcoin", "family": "CRYPTO_RISK", "critical": False},
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
    try:
        result.index = pd.to_datetime(result.index, utc=True)
    except Exception:
        pass
    return result.sort_index()


def summarize_history(frame: pd.DataFrame) -> dict[str, Any]:
    """Summarize recent hourly observations without assuming any exchange calendar."""
    data = _normalized_frame(frame)
    if len(data) < 2:
        return {
            "status": "INSUFFICIENT_SERIES",
            "latest_at": None,
            "latest": None,
            "change_1h_pct": None,
            "change_24h_pct": None,
            "change_5d_pct": None,
        }

    latest = _finite(data.iloc[-1]["close"])
    previous = _finite(data.iloc[-2]["close"])
    latest_ts = data.index[-1]
    latest_at = latest_ts.isoformat() if hasattr(latest_ts, "isoformat") else str(latest_ts)

    def _anchor(hours: int) -> float | None:
        try:
            cutoff = data.index[-1] - pd.Timedelta(hours=hours)
            eligible = data[data.index <= cutoff]
        except Exception:
            eligible = pd.DataFrame()
        if not eligible.empty:
            return _finite(eligible.iloc[-1]["close"])
        return _finite(data.iloc[0]["close"])

    return {
        "status": "OK",
        "latest_at": latest_at,
        "latest": latest,
        "change_1h_pct": _pct(latest, previous),
        "change_24h_pct": _pct(latest, _anchor(24)),
        "change_5d_pct": _pct(latest, _anchor(24 * 5)),
    }


def fetch_yfinance_history(symbol: str) -> pd.DataFrame:
    """Fetch a compact intraday history. Imported lazily for deterministic tests."""
    import yfinance as yf

    return yf.Ticker(symbol).history(
        period="7d",
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
    if instrument_id in {"SP500", "NASDAQ", "HANGSENG", "NIKKEI225", "EUROSTOXX50", "BTC"}:
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
    for instrument_id in ("SP500", "NASDAQ", "VIX", "US10Y", "DXY", "USDCNH", "HANGSENG", "BTC"):
        summary = series.get(instrument_id) or {}
        if summary.get("status") != "OK":
            continue
        component = _risk_component(instrument_id, summary)
        if component is not None:
            components.append(component)
    if not components:
        return {"status": "UNKNOWN", "score": None, "component_count": 0}
    raw = sum(components) / len(components)
    score = round(50.0 + raw * 20.0, 2)
    status = "RISK_OFF" if score < 38 else "RISK_ON" if score > 62 else "NEUTRAL"
    return {"status": status, "score": max(0.0, min(100.0, score)), "component_count": len(components)}


def build_security_transmission(
    series: Mapping[str, Mapping[str, Any]],
    commodity_config: Mapping[str, Any],
    *,
    security_names: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Map only explicitly configured commodity exposures to securities."""
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
            move = _finite(summary.get("change_24h_pct"))
            if move is None:
                continue
            producer_positive = str(exposure.get("exposure_direction") or "PRODUCER_POSITIVE").upper() == "PRODUCER_POSITIVE"
            favorable = move > 0 if producer_positive else move < 0
            material = abs(move) >= 2.0
            factors.append({
                "factor_id": factor_id,
                "change_24h_pct": move,
                "direction": "FAVORABLE" if favorable else "ADVERSE",
                "material": material,
                "evidence_ref": exposure.get("evidence_ref"),
            })
        if not factors:
            continue
        material_factors = [f for f in factors if f["material"]]
        favorable = sum(f["direction"] == "FAVORABLE" for f in material_factors)
        adverse = sum(f["direction"] == "ADVERSE" for f in material_factors)
        signal = "MIXED"
        if not material_factors:
            signal = "NEUTRAL"
        elif favorable and not adverse:
            signal = "FAVORABLE"
        elif adverse and not favorable:
            signal = "ADVERSE"
        rows.append({
            "code": code,
            "name": names.get(code, ""),
            "signal": signal,
            "factors": factors,
            "authority": "RESEARCH_ONLY",
            "formal_action_mutation_allowed": False,
            "no_auto_trade": True,
        })
    return rows


def build_global_market_pulse(
    *,
    instruments: Sequence[Mapping[str, Any]] = DEFAULT_INSTRUMENTS,
    history_fetcher: Callable[[str], pd.DataFrame] = fetch_yfinance_history,
    commodity_config: Mapping[str, Any] | None = None,
    security_names: Mapping[str, str] | None = None,
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
            summary = summarize_history(history_fetcher(symbol))
        except Exception as exc:
            summary = {
                "status": f"FETCH_ERROR:{type(exc).__name__}",
                "latest_at": None,
                "latest": None,
                "change_1h_pct": None,
                "change_24h_pct": None,
                "change_5d_pct": None,
            }
            failures.append({"id": instrument_id, "error": type(exc).__name__})
        summary.update({
            "symbol": symbol,
            "label": spec.get("label") or instrument_id,
            "family": spec.get("family") or "OTHER",
            "critical": spec.get("critical") is True,
            "provider": "yfinance_public_market",
        })
        series[instrument_id] = summary

    ok_ids = [key for key, value in series.items() if value.get("status") == "OK"]
    critical_ok = [key for key in critical_ids if (series.get(key) or {}).get("status") == "OK"]
    critical_ratio = 0.0 if not critical_ids else len(critical_ok) / len(critical_ids)
    risk_equity_ok = any((series.get(key) or {}).get("status") == "OK" for key in ("SP500", "NASDAQ"))
    commodity_ok = any((series.get(key) or {}).get("status") == "OK" for key in ("COPPER", "WTI", "GOLD"))

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
    return {
        "contract_version": CONTRACT_VERSION,
        "generated_at": now.isoformat(),
        "clock": "GLOBAL_MARKET_INDEPENDENT_OF_A_SHARE_CALENDAR",
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
        "security_transmission": build_security_transmission(
            series,
            commodity_config or {},
            security_names=security_names,
        ),
        "authority": "RESEARCH_ONLY",
        "formal_trading_authority": False,
        "formal_action_mutation_allowed": False,
        "automatic_promotion_allowed": False,
        "no_auto_trade": True,
    }


def _semantic_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    semantic = json.loads(json.dumps(payload))
    semantic.pop("generated_at", None)
    return semantic


def semantic_fingerprint(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(_semantic_payload(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def persist_if_changed(payload: Mapping[str, Any], output_dir: Path) -> dict[str, Any]:
    """Persist latest/history only when market content changes."""
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
