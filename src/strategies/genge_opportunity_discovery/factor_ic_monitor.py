"""Point-in-time factor effectiveness monitor for the All-A opportunity scan.

The monitor persists daily cross-sectional factor observations and only scores a
factor after the corresponding forward return has become observable.  It never
uses future prices at formation time and it deliberately reports UNKNOWN until
there are enough completed cohorts.

The output is research metadata.  It can invalidate the matching opportunity
engine when there is sufficiently negative out-of-sample evidence, but it does
not bypass any company, event, valuation, execution, reward/risk or exit gate.
"""

from __future__ import annotations

import json
import math
import os
from collections.abc import Iterable, Mapping, MutableMapping
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from src.strategies.genge_cycle_bottom.backtest import BacktestInput
from src.strategies.genge_cycle_bottom.features import prepare_price_frame
from src.strategies.genge_opportunity_discovery import pipeline


RULE_VERSION = "factor_ic_monitor_v1_point_in_time"
DEFAULT_STATE_PATH = Path(
    os.environ.get(
        "GENGE_FACTOR_OBSERVATION_LEDGER",
        "data/opportunity_snapshots/all_a_factor_observations.csv",
    )
)
HORIZONS = (20, 60, 120)
HORIZON_WEIGHTS = {20: 0.50, 60: 0.30, 120: 0.20}
FACTOR_NAMES = ("VALUE", "QUALITY", "REVERSAL", "MOMENTUM", "EARNINGS")
FACTOR_COLUMNS = {
    "VALUE": "factor_value",
    "QUALITY": "factor_quality",
    "REVERSAL": "factor_reversal",
    "MOMENTUM": "factor_momentum",
    "EARNINGS": "factor_earnings",
}
MIN_CROSS_SECTION = 30
MIN_COHORTS = 5
MIN_TOTAL_PAIRS = 150
IC_EFFECT_THRESHOLD = 0.02
MAX_COHORTS_PER_HORIZON = 60
MAX_OBSERVATION_DATES = 190

OBSERVATION_COLUMNS = [
    "observation_date",
    "code",
    "stock_name",
    "industry",
    "close",
    "factor_value",
    "factor_quality",
    "factor_reversal",
    "factor_momentum",
    "factor_earnings",
    "return_20d_pct",
    "return_60d_pct",
    "return_120d_pct",
    "rule_version",
]

DIAGNOSTIC_COLUMNS = (
    "valley_factor_validity_status",
    "valley_factor_ic",
    "valley_factor_ic_sample_count",
    "trend_factor_validity_status",
    "trend_factor_ic",
    "trend_factor_ic_sample_count",
    "earnings_factor_validity_status",
    "earnings_factor_ic",
    "earnings_factor_ic_sample_count",
    "factor_ic_monitor_rule_version",
)

_previous_build_quant_rows = None
_run_cache: dict[tuple[str, str], dict[str, Any]] = {}


def _finite_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _normalize_code(value: Any) -> str:
    text = str(value or "").strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text.zfill(6) if text.isdigit() else text


def _empty_ledger() -> pd.DataFrame:
    return pd.DataFrame(columns=OBSERVATION_COLUMNS)


def read_observations(path: Path | str = DEFAULT_STATE_PATH) -> pd.DataFrame:
    target = Path(path)
    if not target.exists() or target.stat().st_size == 0:
        return _empty_ledger()
    try:
        frame = pd.read_csv(target, dtype={"code": str})
    except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError):
        return _empty_ledger()
    for column in OBSERVATION_COLUMNS:
        if column not in frame.columns:
            frame[column] = ""
    frame["code"] = frame["code"].map(_normalize_code)
    return frame[OBSERVATION_COLUMNS].copy()


def _write_observations(frame: pd.DataFrame, path: Path | str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    local = frame.copy()
    for column in OBSERVATION_COLUMNS:
        if column not in local.columns:
            local[column] = ""
    local[OBSERVATION_COLUMNS].to_csv(target, index=False, encoding="utf-8")


def _rank_pct(values: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    return numeric.rank(method="average", pct=True)


def build_current_observations(
    rows: Iterable[Mapping[str, Any]], *, as_of: date,
) -> pd.DataFrame:
    """Build one point-in-time factor cross section with all factors oriented high=good."""

    raw = pd.DataFrame([dict(row) for row in rows])
    if raw.empty:
        return _empty_ledger()
    raw["code"] = raw.get("code", pd.Series(dtype=str)).map(_normalize_code)
    raw["close"] = pd.to_numeric(raw.get("close"), errors="coerce")
    raw["factor_value"] = pd.to_numeric(raw.get("valuation_score"), errors="coerce")
    raw["factor_quality"] = pd.to_numeric(
        raw.get("financial_safety_score"), errors="coerce"
    )
    percentile = pd.to_numeric(raw.get("price_percentile_5y"), errors="coerce")
    raw["factor_reversal"] = -percentile

    momentum_parts = []
    for column in (
        "relative_strength_20d",
        "relative_strength_60d",
        "trend_stabilization_score",
    ):
        if column in raw.columns:
            momentum_parts.append(_rank_pct(raw[column]))
    if momentum_parts:
        raw["factor_momentum"] = pd.concat(momentum_parts, axis=1).mean(
            axis=1, skipna=True
        )
    else:
        raw["factor_momentum"] = float("nan")

    current_profit = pd.to_numeric(raw.get("net_profit_yoy"), errors="coerce")
    previous_profit = pd.to_numeric(
        raw.get("previous_net_profit_yoy"), errors="coerce"
    )
    raw["factor_earnings"] = current_profit - previous_profit

    result = pd.DataFrame(
        {
            "observation_date": as_of.isoformat(),
            "code": raw["code"],
            "stock_name": raw.get("stock_name", ""),
            "industry": raw.get("normalized_industry", raw.get("industry", "")),
            "close": raw["close"],
            "factor_value": raw["factor_value"],
            "factor_quality": raw["factor_quality"],
            "factor_reversal": raw["factor_reversal"],
            "factor_momentum": raw["factor_momentum"],
            "factor_earnings": raw["factor_earnings"],
            "return_20d_pct": float("nan"),
            "return_60d_pct": float("nan"),
            "return_120d_pct": float("nan"),
            "rule_version": RULE_VERSION,
        }
    )
    result = result[result["code"].astype(str).str.len() > 0]
    result = result.drop_duplicates(["observation_date", "code"], keep="last")
    return result[OBSERVATION_COLUMNS].reset_index(drop=True)


def _prepared_histories(
    inputs: Iterable[BacktestInput], *, as_of: date,
) -> dict[str, pd.DataFrame]:
    histories: dict[str, pd.DataFrame] = {}
    for item in inputs:
        try:
            history = prepare_price_frame(item.price_df)
        except Exception:
            continue
        if history.empty:
            continue
        history = history[history["date"] <= as_of].copy().reset_index(drop=True)
        if history.empty:
            continue
        histories[_normalize_code(item.code)] = history
    return histories


def mature_forward_returns(
    observations: pd.DataFrame,
    inputs: Iterable[BacktestInput],
    *,
    as_of: date,
) -> pd.DataFrame:
    """Fill only returns whose future trading-session close is already observable."""

    if observations.empty:
        return observations.copy()
    result = observations.copy()
    result["code"] = result["code"].map(_normalize_code)
    result["observation_date"] = pd.to_datetime(
        result["observation_date"], errors="coerce"
    ).dt.date
    for horizon in HORIZONS:
        column = f"return_{horizon}d_pct"
        result[column] = pd.to_numeric(result[column], errors="coerce")

    histories = _prepared_histories(inputs, as_of=as_of)
    needs_any = result[[f"return_{h}d_pct" for h in HORIZONS]].isna().any(axis=1)
    unresolved = result[needs_any]

    for code, indexes in unresolved.groupby("code").groups.items():
        history = histories.get(code)
        if history is None or history.empty:
            continue
        dates = list(history["date"])
        closes = pd.to_numeric(history["close"], errors="coerce").tolist()
        date_to_index = {value: index for index, value in enumerate(dates)}
        for row_index in indexes:
            observation_date = result.at[row_index, "observation_date"]
            start_index = date_to_index.get(observation_date)
            if start_index is None:
                continue
            start_close = _finite_float(result.at[row_index, "close"])
            if start_close is None or start_close <= 0:
                start_close = _finite_float(closes[start_index])
            if start_close is None or start_close <= 0:
                continue
            for horizon in HORIZONS:
                column = f"return_{horizon}d_pct"
                if _finite_float(result.at[row_index, column]) is not None:
                    continue
                end_index = start_index + horizon
                if end_index >= len(closes):
                    continue
                end_close = _finite_float(closes[end_index])
                if end_close is None or end_close <= 0:
                    continue
                result.at[row_index, column] = round(
                    (end_close / start_close - 1.0) * 100.0,
                    6,
                )

    result["observation_date"] = result["observation_date"].map(
        lambda value: value.isoformat() if isinstance(value, date) else ""
    )
    return result


def _prune_observations(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    dates = sorted(
        value
        for value in pd.to_datetime(
            frame["observation_date"], errors="coerce"
        ).dt.date.dropna().unique()
    )
    if len(dates) <= MAX_OBSERVATION_DATES:
        return frame
    keep = set(dates[-MAX_OBSERVATION_DATES:])
    parsed = pd.to_datetime(frame["observation_date"], errors="coerce").dt.date
    return frame[parsed.isin(keep)].copy()


def update_observation_state(
    rows: Iterable[Mapping[str, Any]],
    inputs: Iterable[BacktestInput],
    *,
    as_of: date,
    state_path: Path | str = DEFAULT_STATE_PATH,
) -> pd.DataFrame:
    existing = read_observations(state_path)
    existing = mature_forward_returns(existing, inputs, as_of=as_of)
    current = build_current_observations(rows, as_of=as_of)
    if not current.empty:
        keys = set(zip(current["observation_date"], current["code"]))
        if not existing.empty:
            existing_keys = list(zip(existing["observation_date"], existing["code"]))
            existing = existing[
                [key not in keys for key in existing_keys]
            ].copy()
        existing = pd.concat([existing, current], ignore_index=True, sort=False)
    existing = _prune_observations(existing)
    existing = existing.sort_values(["observation_date", "code"]).reset_index(drop=True)
    _write_observations(existing, state_path)
    return existing


def rank_ic(factor: pd.Series, forward_return: pd.Series) -> float | None:
    pair = pd.DataFrame({"factor": factor, "return": forward_return})
    pair = pair.apply(pd.to_numeric, errors="coerce").dropna()
    if len(pair) < 3 or pair["factor"].nunique() < 2 or pair["return"].nunique() < 2:
        return None
    factor_rank = pair["factor"].rank(method="average")
    return_rank = pair["return"].rank(method="average")
    correlation = factor_rank.corr(return_rank)
    value = _finite_float(correlation)
    return None if value is None else float(value)


def factor_effectiveness(observations: pd.DataFrame) -> dict[str, Any]:
    horizon_rows: list[dict[str, Any]] = []
    factor_summaries: dict[str, dict[str, Any]] = {}
    if observations.empty:
        return {
            "rule_version": RULE_VERSION,
            "factor_summaries": {
                factor: {
                    "factor": factor,
                    "status": "UNKNOWN",
                    "aggregate_ic": None,
                    "sample_count": 0,
                    "cohort_count": 0,
                }
                for factor in FACTOR_NAMES
            },
            "engine_summaries": {},
            "horizon_metrics": [],
        }

    local = observations.copy()
    local["observation_date"] = local["observation_date"].astype(str)
    for factor, factor_column in FACTOR_COLUMNS.items():
        usable_horizons: list[dict[str, Any]] = []
        for horizon in HORIZONS:
            return_column = f"return_{horizon}d_pct"
            cohorts: list[dict[str, Any]] = []
            for observation_date, group in local.groupby("observation_date", sort=True):
                pair = group[[factor_column, return_column]].copy()
                pair = pair.apply(pd.to_numeric, errors="coerce").dropna()
                if len(pair) < MIN_CROSS_SECTION:
                    continue
                ic = rank_ic(pair[factor_column], pair[return_column])
                if ic is None:
                    continue
                cohorts.append(
                    {
                        "observation_date": observation_date,
                        "ic": ic,
                        "sample_count": len(pair),
                    }
                )
            cohorts = cohorts[-MAX_COHORTS_PER_HORIZON:]
            values = [row["ic"] for row in cohorts]
            sample_count = sum(int(row["sample_count"]) for row in cohorts)
            mean_ic = sum(values) / len(values) if values else None
            median_ic = float(pd.Series(values).median()) if values else None
            std_ic = float(pd.Series(values).std(ddof=1)) if len(values) >= 2 else None
            icir = (
                mean_ic / std_ic
                if mean_ic is not None and std_ic not in {None, 0.0}
                else None
            )
            positive_rate = (
                sum(value > 0 for value in values) / len(values) if values else None
            )
            metric = {
                "factor": factor,
                "horizon_sessions": horizon,
                "mean_ic": None if mean_ic is None else round(mean_ic, 6),
                "median_ic": None if median_ic is None else round(median_ic, 6),
                "icir": None if icir is None else round(icir, 6),
                "positive_rate": (
                    None if positive_rate is None else round(positive_rate, 6)
                ),
                "cohort_count": len(cohorts),
                "sample_count": sample_count,
            }
            horizon_rows.append(metric)
            if len(cohorts) >= MIN_COHORTS and sample_count >= MIN_TOTAL_PAIRS:
                usable_horizons.append(metric)

        if not usable_horizons:
            factor_summaries[factor] = {
                "factor": factor,
                "status": "UNKNOWN",
                "aggregate_ic": None,
                "sample_count": 0,
                "cohort_count": 0,
            }
            continue

        weight_total = sum(
            HORIZON_WEIGHTS[int(row["horizon_sessions"])] for row in usable_horizons
        )
        aggregate_ic = sum(
            float(row["mean_ic"]) * HORIZON_WEIGHTS[int(row["horizon_sessions"])]
            for row in usable_horizons
            if row["mean_ic"] is not None
        ) / weight_total
        if aggregate_ic >= IC_EFFECT_THRESHOLD:
            status = "VALID"
        elif aggregate_ic <= -IC_EFFECT_THRESHOLD:
            status = "INVALID"
        else:
            status = "NEUTRAL"
        factor_summaries[factor] = {
            "factor": factor,
            "status": status,
            "aggregate_ic": round(aggregate_ic, 6),
            "sample_count": sum(int(row["sample_count"]) for row in usable_horizons),
            "cohort_count": sum(int(row["cohort_count"]) for row in usable_horizons),
        }

    engine_summaries = build_engine_summaries(factor_summaries)
    return {
        "rule_version": RULE_VERSION,
        "factor_summaries": factor_summaries,
        "engine_summaries": engine_summaries,
        "horizon_metrics": horizon_rows,
    }


def _status_rank(status: str) -> int:
    return {"UNKNOWN": 0, "NEUTRAL": 1, "INVALID": 2, "VALID": 3}.get(status, 0)


def build_engine_summaries(
    factor_summaries: Mapping[str, Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    def summary(name: str) -> Mapping[str, Any]:
        return factor_summaries.get(
            name,
            {"status": "UNKNOWN", "aggregate_ic": None, "sample_count": 0},
        )

    reversal = summary("REVERSAL")
    value = summary("VALUE")
    reversal_status = str(reversal.get("status") or "UNKNOWN")
    value_status = str(value.get("status") or "UNKNOWN")
    if reversal_status == "INVALID" and value_status != "VALID":
        valley_status = "INVALID"
    elif "VALID" in {reversal_status, value_status}:
        valley_status = "VALID"
    elif "NEUTRAL" in {reversal_status, value_status}:
        valley_status = "NEUTRAL"
    else:
        valley_status = "UNKNOWN"
    valley_available = [
        item for item in (reversal, value) if _finite_float(item.get("aggregate_ic")) is not None
    ]
    valley_ic = (
        sum(float(item["aggregate_ic"]) for item in valley_available) / len(valley_available)
        if valley_available else None
    )
    valley_samples = sum(int(item.get("sample_count") or 0) for item in valley_available)

    momentum = summary("MOMENTUM")
    earnings = summary("EARNINGS")
    return {
        "VALLEY_REPAIR": {
            "engine": "VALLEY_REPAIR",
            "status": valley_status,
            "aggregate_ic": None if valley_ic is None else round(valley_ic, 6),
            "sample_count": valley_samples,
            "source_factors": "REVERSAL;VALUE",
        },
        "STRONG_TREND_PULLBACK": {
            "engine": "STRONG_TREND_PULLBACK",
            "status": str(momentum.get("status") or "UNKNOWN"),
            "aggregate_ic": momentum.get("aggregate_ic"),
            "sample_count": int(momentum.get("sample_count") or 0),
            "source_factors": "MOMENTUM",
        },
        "EARNINGS_INFLECTION": {
            "engine": "EARNINGS_INFLECTION",
            "status": str(earnings.get("status") or "UNKNOWN"),
            "aggregate_ic": earnings.get("aggregate_ic"),
            "sample_count": int(earnings.get("sample_count") or 0),
            "source_factors": "EARNINGS",
        },
    }


def enrich_rows(
    rows: Iterable[MutableMapping[str, Any]], effectiveness: Mapping[str, Any],
) -> None:
    engines = effectiveness.get("engine_summaries") or {}
    mapping = {
        "VALLEY_REPAIR": "valley",
        "STRONG_TREND_PULLBACK": "trend",
        "EARNINGS_INFLECTION": "earnings",
    }
    for row in rows:
        for engine, prefix in mapping.items():
            summary = engines.get(engine) or {}
            row[f"{prefix}_factor_validity_status"] = str(
                summary.get("status") or "UNKNOWN"
            )
            row[f"{prefix}_factor_ic"] = summary.get("aggregate_ic")
            row[f"{prefix}_factor_ic_sample_count"] = int(
                summary.get("sample_count") or 0
            )
        row["factor_ic_monitor_rule_version"] = RULE_VERSION


def update_and_enrich(
    rows: list[dict[str, Any]],
    inputs: Iterable[BacktestInput],
    *,
    as_of: date,
    state_path: Path | str = DEFAULT_STATE_PATH,
) -> dict[str, Any]:
    key = (str(Path(state_path)), as_of.isoformat())
    effectiveness = _run_cache.get(key)
    if effectiveness is None:
        observations = update_observation_state(
            rows, inputs, as_of=as_of, state_path=state_path
        )
        effectiveness = factor_effectiveness(observations)
        _run_cache[key] = effectiveness
    enrich_rows(rows, effectiveness)
    return effectiveness


def write_report(
    report_dir: Path | str,
    *,
    state_path: Path | str = DEFAULT_STATE_PATH,
) -> dict[str, Any]:
    target = Path(report_dir)
    target.mkdir(parents=True, exist_ok=True)
    observations = read_observations(state_path)
    effectiveness = factor_effectiveness(observations)
    metrics = pd.DataFrame(effectiveness.get("horizon_metrics") or [])
    metric_columns = [
        "factor", "horizon_sessions", "mean_ic", "median_ic", "icir",
        "positive_rate", "cohort_count", "sample_count",
    ]
    if metrics.empty:
        metrics = pd.DataFrame(columns=metric_columns)
    metrics.to_csv(target / "factor_effectiveness.csv", index=False, encoding="utf-8")
    (target / "factor_effectiveness.json").write_text(
        json.dumps(effectiveness, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    lines = [
        "# Factor IC Effectiveness",
        "",
        "Point-in-time research monitor; insufficient completed cohorts remain UNKNOWN.",
        "",
    ]
    for factor in FACTOR_NAMES:
        summary = effectiveness["factor_summaries"].get(factor, {})
        lines.append(
            f"- {factor}: {summary.get('status', 'UNKNOWN')} / "
            f"IC={summary.get('aggregate_ic')} / samples={summary.get('sample_count', 0)}"
        )
    lines.append("")
    lines.append("## Engine regimes")
    lines.append("")
    for engine, summary in (effectiveness.get("engine_summaries") or {}).items():
        lines.append(
            f"- {engine}: {summary.get('status')} / "
            f"IC={summary.get('aggregate_ic')} / samples={summary.get('sample_count', 0)}"
        )
    (target / "factor_effectiveness.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    return effectiveness


def _build_quant_rows(**kwargs: Any) -> list[dict[str, Any]]:
    if _previous_build_quant_rows is None:
        raise RuntimeError("factor IC monitor installed without wrapped quant builder")
    rows = _previous_build_quant_rows(**kwargs)
    as_of = kwargs.get("resolved_as_of")
    if not isinstance(as_of, date):
        return rows
    update_and_enrich(
        rows,
        kwargs.get("inputs", []),
        as_of=as_of,
        state_path=DEFAULT_STATE_PATH,
    )

    # The engine-aware pipeline may already have classified the preliminary
    # engine before the IC fields were attached. Re-run only its research-stage
    # blocker/status bookkeeping with the now observable factor regime.
    from src.strategies.genge_opportunity_discovery import opportunity_pipeline_policy

    for row in rows:
        hard, soft = opportunity_pipeline_policy._screen_blockers(row)
        row["hard_reject_blockers"] = ";".join(hard)
        row["soft_blockers"] = ";".join(soft)
        row["quant_screen_status"] = opportunity_pipeline_policy._screen_status(
            row, hard, soft
        )
        row["preliminary_opportunity_engine"] = (
            opportunity_pipeline_policy._preliminary_engine(row)
        )
    return rows


def install() -> None:
    """Install after opportunity_pipeline_policy so IC sees normalized earnings fields."""

    global _previous_build_quant_rows
    if pipeline._build_quant_rows is _build_quant_rows:
        return
    _previous_build_quant_rows = pipeline._build_quant_rows
    pipeline._build_quant_rows = _build_quant_rows
    for columns in (pipeline.QUANT_COLUMNS, pipeline.OPPORTUNITY_COLUMNS):
        for column in DIAGNOSTIC_COLUMNS:
            if column not in columns:
                columns.append(column)
