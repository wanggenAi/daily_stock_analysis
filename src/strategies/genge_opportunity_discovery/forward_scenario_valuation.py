"""Build live forward EPS scenarios and evidence-based reasonable PE bands.

Decision order for PE-applicable HARD_LOGIC_PASS companies:

1. Analyst consensus supplies forward EPS.  THS min/mean/max becomes
   bear/base/bull when enough institutions cover the company.  EastMoney's
   all-market consensus is a base-only fallback; missing bear/bull values are
   never fabricated.
2. A reasonable PE is anchored to the *current same-industry forward-PE
   distribution for the same forecast year*, not to the company's own
   historical PE.  Peer Forward PE is reconstructed from the same All-A price
   snapshot and EastMoney forecast EPS.
3. The peer median receives only bounded adjustments for the target's forecast
   growth relative to peers, recurring-earnings quality, and current earnings
   stage.  The result is clamped to the peer interquartile range.  Bear/bull
   multiples extend conservatively around that evidence band.
4. If peer evidence is sparse, the company is not PE-applicable, or analyst
   coverage is insufficient, reasonable PE remains unavailable.  The downstream
   price map then keeps its reference-only reverse-valuation fallback.

This module is LIVE research only.  Current analyst consensus is not point-in-
time historical data and must never be fed into historical walk-forward tests.
Historical PE is deliberately ignored by the reasonable-PE model.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

import pandas as pd

from .hard_logic_price_map import earnings_stage_assessment
from .industry_coverage import find_latest_report
from .valuation_model_routing import GENERAL_REVERSE_STRATEGY_ID, find_latest_routing_source

DISCLAIMER = "仅用于公开数据研究和估值判断，不构成买入或卖出建议，不应自动交易。"
POLICY_VERSION = "peer_forward_pe_v1"
DEFAULT_MIN_TARGET_INSTITUTIONS = 3
DEFAULT_MIN_PEER_REPORTS = 2
DEFAULT_MIN_PEER_SAMPLES = 6
DEFAULT_MAX_PEER_PE = 80.0
DEFAULT_MIN_PEER_PE = 3.0
DEFAULT_REASONABLE_PE_FLOOR = 5.0
DEFAULT_REASONABLE_PE_CAP = 50.0

FORECAST_COLUMN_RE = re.compile(r"^(\d{4})预测每股收益$")
PRICE_FIELDS = (
    "current_price",
    "latest_price",
    "latest_close",
    "close_price",
    "price",
    "close",
    "收盘价",
    "最新价",
)

OUTPUT_COLUMNS = [
    "code",
    "stock_name",
    "industry",
    "hard_logic_state",
    "valuation_primary_strategy_id",
    "earnings_stage",
    "earnings_stage_basis",
    "forecast_source",
    "forecast_snapshot_date",
    "forecast_year",
    "forecast_institution_count",
    "forecast_next_year",
    "forward_eps_bear",
    "forward_eps_base",
    "forward_eps_bull",
    "forward_eps_next_year_base",
    "forward_eps_growth_base_pct",
    "peer_forward_pe_sample_count",
    "peer_forward_pe_p25",
    "peer_forward_pe_median",
    "peer_forward_pe_p75",
    "peer_forward_eps_growth_sample_count",
    "peer_forward_eps_growth_median_pct",
    "reasonable_pe_policy_version",
    "reasonable_pe_status",
    "reasonable_pe_bear",
    "reasonable_pe_base",
    "reasonable_pe_bull",
    "reasonable_pe_growth_factor",
    "reasonable_pe_quality_factor",
    "reasonable_pe_stage_factor",
    "reasonable_pe_basis",
    "historical_pe_used_for_reasonable_pe",
    "scenario_fair_price_bear",
    "scenario_fair_price_base",
    "scenario_fair_price_bull",
    "scenario_valuation_status",
    "formal_signal_eligible",
    "automatic_promotion_allowed",
    "no_auto_trade",
    "disclaimer",
]


@dataclass(frozen=True)
class ForwardConsensus:
    status: str
    source: str
    forecast_year: int | None
    institution_count: int
    eps_bear: float | None
    eps_base: float | None
    eps_bull: float | None
    next_year: int | None
    next_eps_base: float | None
    growth_base: float | None


@dataclass(frozen=True)
class PeerEvidence:
    status: str
    pe_sample_count: int
    pe_p25: float | None
    pe_median: float | None
    pe_p75: float | None
    growth_sample_count: int
    growth_median: float | None


@dataclass(frozen=True)
class ReasonablePeDecision:
    status: str
    bear: float | None
    base: float | None
    bull: float | None
    growth_factor: float
    quality_factor: float
    stage_factor: float
    basis: str


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _positive(value: Any) -> float | None:
    number = _finite(value)
    return number if number is not None and number > 0 else None


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


def _industry(row: Mapping[str, Any]) -> str:
    return str(
        row.get("industry")
        or row.get("normalized_industry")
        or row.get("raw_industry")
        or ""
    ).strip()


def _price(row: Mapping[str, Any]) -> float | None:
    for field in PRICE_FIELDS:
        value = _positive(row.get(field))
        if value is not None:
            return value
    return None


def _clamp(value: float, low: float, high: float) -> float:
    return min(max(float(value), float(low)), float(high))


def _read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _forecast_columns(columns: Iterable[Any]) -> dict[int, str]:
    result: dict[int, str] = {}
    for raw in columns:
        name = str(raw)
        match = FORECAST_COLUMN_RE.match(name)
        if match:
            result[int(match.group(1))] = name
    return result


def extract_ths_consensus(
    frame: pd.DataFrame | None,
    *,
    as_of: date,
    min_institutions: int = DEFAULT_MIN_TARGET_INSTITUTIONS,
) -> ForwardConsensus:
    """Convert THS min/mean/max annual EPS consensus into explicit scenarios."""
    if frame is None or frame.empty:
        return ForwardConsensus("THS_UNAVAILABLE", "THS", None, 0, None, None, None, None, None, None)

    required = {"年度", "预测机构数", "最小值", "均值", "最大值"}
    if not required.issubset(set(frame.columns)):
        return ForwardConsensus("THS_SCHEMA_INCOMPLETE", "THS", None, 0, None, None, None, None, None, None)

    rows: list[dict[str, Any]] = []
    for raw in frame.to_dict("records"):
        year_value = _finite(raw.get("年度"))
        institutions = _finite(raw.get("预测机构数"))
        if year_value is None or institutions is None:
            continue
        year = int(year_value)
        if year < as_of.year or int(institutions) < max(1, int(min_institutions)):
            continue
        base = _positive(raw.get("均值"))
        if base is None:
            continue
        rows.append(
            {
                "year": year,
                "institutions": int(institutions),
                "bear": _positive(raw.get("最小值")),
                "base": base,
                "bull": _positive(raw.get("最大值")),
            }
        )
    if not rows:
        return ForwardConsensus("THS_COVERAGE_INSUFFICIENT", "THS", None, 0, None, None, None, None, None, None)

    rows.sort(key=lambda item: item["year"])
    selected = rows[0]
    next_row = next((item for item in rows[1:] if item["year"] > selected["year"]), None)
    next_year = int(next_row["year"]) if next_row else None
    next_base = _positive(next_row.get("base")) if next_row else None
    growth = None
    if next_base is not None and selected["base"] > 0:
        growth = next_base / selected["base"] - 1.0
    return ForwardConsensus(
        "OK",
        "THS_ANALYST_CONSENSUS_MIN_MEAN_MAX",
        int(selected["year"]),
        int(selected["institutions"]),
        selected["bear"],
        selected["base"],
        selected["bull"],
        next_year,
        next_base,
        growth,
    )


def _em_record_map(frame: pd.DataFrame | None) -> tuple[dict[str, dict[str, Any]], dict[int, str]]:
    if frame is None or frame.empty:
        return {}, {}
    columns = _forecast_columns(frame.columns)
    records: dict[str, dict[str, Any]] = {}
    for raw in frame.to_dict("records"):
        code = _normalize_code(raw.get("代码") or raw.get("code"))
        if code:
            records[code] = dict(raw)
    return records, columns


def extract_em_base_consensus(
    row: Mapping[str, Any] | None,
    forecast_columns: Mapping[int, str],
    *,
    as_of: date,
    min_reports: int = DEFAULT_MIN_TARGET_INSTITUTIONS,
) -> ForwardConsensus:
    """Use EastMoney all-market forecast as a base-only fallback."""
    if not row:
        return ForwardConsensus("EM_UNAVAILABLE", "EASTMONEY", None, 0, None, None, None, None, None, None)
    reports = _finite(row.get("研报数"))
    if reports is None or int(reports) < max(1, int(min_reports)):
        return ForwardConsensus("EM_COVERAGE_INSUFFICIENT", "EASTMONEY", None, int(reports or 0), None, None, None, None, None, None)

    years = sorted(year for year in forecast_columns if year >= as_of.year)
    selected_year = next(
        (
            year
            for year in years
            if _positive(row.get(forecast_columns[year])) is not None
        ),
        None,
    )
    if selected_year is None:
        return ForwardConsensus("EM_FORWARD_EPS_UNAVAILABLE", "EASTMONEY", None, int(reports), None, None, None, None, None, None)

    base = _positive(row.get(forecast_columns[selected_year]))
    next_year = next(
        (
            year
            for year in years
            if year > selected_year and _positive(row.get(forecast_columns[year])) is not None
        ),
        None,
    )
    next_base = _positive(row.get(forecast_columns[next_year])) if next_year is not None else None
    growth = next_base / base - 1.0 if next_base is not None and base is not None else None
    return ForwardConsensus(
        "BASE_ONLY",
        "EASTMONEY_ANALYST_CONSENSUS_BASE_ONLY",
        selected_year,
        int(reports),
        None,
        base,
        None,
        next_year,
        next_base,
        growth,
    )


def peer_forward_pe_evidence(
    *,
    target_code: str,
    industry: str,
    forecast_year: int | None,
    raw_all_a_rows: Iterable[Mapping[str, Any]],
    em_records: Mapping[str, Mapping[str, Any]],
    forecast_columns: Mapping[int, str],
    min_peer_reports: int = DEFAULT_MIN_PEER_REPORTS,
    min_peer_samples: int = DEFAULT_MIN_PEER_SAMPLES,
    min_peer_pe: float = DEFAULT_MIN_PEER_PE,
    max_peer_pe: float = DEFAULT_MAX_PEER_PE,
) -> PeerEvidence:
    """Build same-industry, same-year current forward-PE evidence from peers."""
    if forecast_year is None or forecast_year not in forecast_columns or not industry:
        return PeerEvidence("PEER_CONTEXT_UNAVAILABLE", 0, None, None, None, 0, None)

    pe_values: list[float] = []
    growth_values: list[float] = []
    current_col = forecast_columns[forecast_year]
    next_years = sorted(year for year in forecast_columns if year > forecast_year)
    next_year = next_years[0] if next_years else None
    next_col = forecast_columns.get(next_year) if next_year is not None else None

    for raw in raw_all_a_rows:
        code = _normalize_code(raw.get("code") or raw.get("代码"))
        if not code or code == target_code or _industry(raw) != industry:
            continue
        em = em_records.get(code)
        if not em:
            continue
        reports = _finite(em.get("研报数"))
        if reports is None or int(reports) < max(1, int(min_peer_reports)):
            continue
        eps = _positive(em.get(current_col))
        price = _price(raw)
        if eps is None or price is None:
            continue
        pe = price / eps
        if not math.isfinite(pe) or pe < min_peer_pe or pe > max_peer_pe:
            continue
        pe_values.append(pe)
        if next_col:
            next_eps = _positive(em.get(next_col))
            if next_eps is not None:
                growth = next_eps / eps - 1.0
                if math.isfinite(growth) and -0.80 <= growth <= 2.00:
                    growth_values.append(growth)

    if len(pe_values) < max(1, int(min_peer_samples)):
        return PeerEvidence("PEER_FORWARD_PE_INSUFFICIENT", len(pe_values), None, None, None, len(growth_values), None)

    series = pd.Series(pe_values, dtype="float64")
    p25 = float(series.quantile(0.25))
    median = float(series.quantile(0.50))
    p75 = float(series.quantile(0.75))
    growth_median = float(pd.Series(growth_values, dtype="float64").median()) if growth_values else None
    return PeerEvidence(
        "OK",
        len(pe_values),
        p25,
        median,
        p75,
        len(growth_values),
        growth_median,
    )


def reasonable_pe_from_peer_evidence(
    row: Mapping[str, Any],
    *,
    consensus: ForwardConsensus,
    peers: PeerEvidence,
    reasonable_pe_floor: float = DEFAULT_REASONABLE_PE_FLOOR,
    reasonable_pe_cap: float = DEFAULT_REASONABLE_PE_CAP,
) -> ReasonablePeDecision:
    """Turn peer forward-PE evidence into a bounded reasonable PE band.

    Historical PE is intentionally absent from this function.
    """
    strategy = str(row.get("valuation_primary_strategy_id") or "").strip()
    diagnostic = str(row.get("valuation_diagnostic_status") or "").strip().upper()
    if strategy and strategy != GENERAL_REVERSE_STRATEGY_ID:
        return ReasonablePeDecision("SPECIALIZED_MODEL_REQUIRED", None, None, None, 1.0, 1.0, 1.0, f"primary_strategy={strategy}")
    if diagnostic == "PE_MODEL_NOT_APPLICABLE":
        return ReasonablePeDecision("PE_MODEL_NOT_APPLICABLE", None, None, None, 1.0, 1.0, 1.0, "normalized recurring earnings do not support PE")
    if _positive(consensus.eps_base) is None:
        return ReasonablePeDecision("FORWARD_EPS_NOT_POSITIVE", None, None, None, 1.0, 1.0, 1.0, "positive forward base EPS required")
    if peers.status != "OK" or peers.pe_median is None or peers.pe_p25 is None or peers.pe_p75 is None:
        return ReasonablePeDecision("PEER_EVIDENCE_INSUFFICIENT", None, None, None, 1.0, 1.0, 1.0, f"peer_status={peers.status}")

    growth_factor = 1.0
    if consensus.growth_base is not None and peers.growth_median is not None:
        # Maximum +/-15% valuation adjustment for +/-15pp growth advantage.
        growth_factor = 1.0 + _clamp(consensus.growth_base - peers.growth_median, -0.15, 0.15)

    quality = _finite(row.get("earnings_quality_score"))
    quality_factor = 1.0
    if quality is not None:
        # 60/100 is neutral.  Quality can move fair PE by at most +/-10%.
        quality_factor = 1.0 + _clamp((quality - 60.0) / 200.0, -0.10, 0.10)

    stage, _stage_basis = earnings_stage_assessment(row)
    stage_factor = {
        "DETERIORATING": 0.85,
        "CONTRACTION": 0.90,
        "EARLY_RECOVERY": 0.95,
        "UNDETERMINED": 0.95,
        "EXPANSION": 1.00,
    }.get(stage, 0.95)

    raw_base = peers.pe_median * growth_factor * quality_factor * stage_factor
    evidence_low = max(float(reasonable_pe_floor), peers.pe_p25)
    evidence_high = min(float(reasonable_pe_cap), peers.pe_p75)
    if evidence_high < evidence_low:
        evidence_low = max(float(reasonable_pe_floor), min(peers.pe_p25, float(reasonable_pe_cap)))
        evidence_high = max(evidence_low, min(peers.pe_p75, float(reasonable_pe_cap)))
    base = _clamp(raw_base, evidence_low, evidence_high)
    bear = _clamp(min(base * 0.85, peers.pe_p25), float(reasonable_pe_floor), base)
    bull = _clamp(max(base * 1.15, peers.pe_p75), base, float(reasonable_pe_cap))

    basis = (
        f"{POLICY_VERSION};peer_p25={peers.pe_p25:.4f};peer_median={peers.pe_median:.4f};"
        f"peer_p75={peers.pe_p75:.4f};growth_factor={growth_factor:.4f};"
        f"quality_factor={quality_factor:.4f};stage={stage};stage_factor={stage_factor:.4f};"
        "historical_pe_used=false"
    )
    return ReasonablePeDecision(
        "OK",
        round(bear, 4),
        round(base, 4),
        round(bull, 4),
        round(growth_factor, 6),
        round(quality_factor, 6),
        round(stage_factor, 6),
        basis,
    )


def _fair_price(eps: float | None, pe: float | None) -> float | None:
    if eps is None or pe is None or eps <= 0 or pe <= 0:
        return None
    value = eps * pe
    return round(value, 4) if math.isfinite(value) and value > 0 else None


def build_forward_scenario_row(
    row: Mapping[str, Any],
    *,
    consensus: ForwardConsensus,
    peers: PeerEvidence,
) -> dict[str, Any]:
    pe = reasonable_pe_from_peer_evidence(row, consensus=consensus, peers=peers)
    stage, stage_basis = earnings_stage_assessment(row)
    bear_fair = _fair_price(consensus.eps_bear, pe.bear)
    base_fair = _fair_price(consensus.eps_base, pe.base)
    bull_fair = _fair_price(consensus.eps_bull, pe.bull)
    scenario_status = "OK" if base_fair is not None else pe.status
    return {
        "code": _normalize_code(row.get("code")),
        "stock_name": row.get("stock_name") or row.get("name") or "",
        "industry": _industry(row),
        "hard_logic_state": row.get("hard_logic_state") or "",
        "valuation_primary_strategy_id": row.get("valuation_primary_strategy_id") or "",
        "earnings_stage": stage,
        "earnings_stage_basis": stage_basis,
        "forecast_source": consensus.source,
        "forecast_snapshot_date": row.get("forecast_snapshot_date") or "",
        "forecast_year": consensus.forecast_year or "",
        "forecast_institution_count": consensus.institution_count,
        "forecast_next_year": consensus.next_year or "",
        "forward_eps_bear": consensus.eps_bear,
        "forward_eps_base": consensus.eps_base,
        "forward_eps_bull": consensus.eps_bull,
        "forward_eps_next_year_base": consensus.next_eps_base,
        "forward_eps_growth_base_pct": round(consensus.growth_base * 100.0, 4) if consensus.growth_base is not None else None,
        "peer_forward_pe_sample_count": peers.pe_sample_count,
        "peer_forward_pe_p25": round(peers.pe_p25, 4) if peers.pe_p25 is not None else None,
        "peer_forward_pe_median": round(peers.pe_median, 4) if peers.pe_median is not None else None,
        "peer_forward_pe_p75": round(peers.pe_p75, 4) if peers.pe_p75 is not None else None,
        "peer_forward_eps_growth_sample_count": peers.growth_sample_count,
        "peer_forward_eps_growth_median_pct": round(peers.growth_median * 100.0, 4) if peers.growth_median is not None else None,
        "reasonable_pe_policy_version": POLICY_VERSION,
        "reasonable_pe_status": pe.status,
        "reasonable_pe_bear": pe.bear,
        "reasonable_pe_base": pe.base,
        "reasonable_pe_bull": pe.bull,
        "reasonable_pe_growth_factor": pe.growth_factor,
        "reasonable_pe_quality_factor": pe.quality_factor,
        "reasonable_pe_stage_factor": pe.stage_factor,
        "reasonable_pe_basis": pe.basis,
        "historical_pe_used_for_reasonable_pe": False,
        "scenario_fair_price_bear": bear_fair,
        "scenario_fair_price_base": base_fair,
        "scenario_fair_price_bull": bull_fair,
        "scenario_valuation_status": scenario_status,
        "formal_signal_eligible": False,
        "automatic_promotion_allowed": False,
        "no_auto_trade": True,
        "disclaimer": DISCLAIMER,
    }


def build_forward_scenario_rows(
    *,
    routed_rows: Iterable[Mapping[str, Any]],
    hard_logic_source_rows: Iterable[Mapping[str, Any]],
    raw_all_a_rows: Iterable[Mapping[str, Any]],
    em_forecast_frame: pd.DataFrame,
    ths_frames: Mapping[str, pd.DataFrame | None],
    as_of: date,
    min_target_institutions: int = DEFAULT_MIN_TARGET_INSTITUTIONS,
    min_peer_reports: int = DEFAULT_MIN_PEER_REPORTS,
    min_peer_samples: int = DEFAULT_MIN_PEER_SAMPLES,
) -> list[dict[str, Any]]:
    raw_rows = [dict(row) for row in raw_all_a_rows]
    raw_by_code = {
        _normalize_code(row.get("code") or row.get("代码")): row
        for row in raw_rows
        if _normalize_code(row.get("code") or row.get("代码"))
    }
    routed_by_code = {
        _normalize_code(row.get("code")): dict(row)
        for row in routed_rows
        if _normalize_code(row.get("code"))
    }
    hard_pass_by_code = {
        _normalize_code(row.get("code")): dict(row)
        for row in hard_logic_source_rows
        if _normalize_code(row.get("code"))
        and str(row.get("hard_logic_state") or "").strip().upper() == "PASS"
    }
    em_records, forecast_columns = _em_record_map(em_forecast_frame)

    output: list[dict[str, Any]] = []
    for code in sorted(hard_pass_by_code):
        routed = routed_by_code.get(code)
        if routed is None:
            # Production workflow separately asserts PASS cannot disappear before valuation.
            continue
        merged = dict(raw_by_code.get(code, {}))
        merged.update(hard_pass_by_code[code])
        merged.update(routed)
        merged["code"] = code
        merged["hard_logic_state"] = "PASS"
        merged["forecast_snapshot_date"] = as_of.isoformat()

        ths = extract_ths_consensus(
            ths_frames.get(code),
            as_of=as_of,
            min_institutions=min_target_institutions,
        )
        consensus = ths
        if ths.status != "OK":
            consensus = extract_em_base_consensus(
                em_records.get(code),
                forecast_columns,
                as_of=as_of,
                min_reports=min_target_institutions,
            )
        peers = peer_forward_pe_evidence(
            target_code=code,
            industry=_industry(merged),
            forecast_year=consensus.forecast_year,
            raw_all_a_rows=raw_rows,
            em_records=em_records,
            forecast_columns=forecast_columns,
            min_peer_reports=min_peer_reports,
            min_peer_samples=min_peer_samples,
        )
        output.append(build_forward_scenario_row(merged, consensus=consensus, peers=peers))
    return output


def _latest_csv(root: Path, filename: str) -> Path:
    candidates = sorted(path for path in root.glob(f"**/{filename}") if path.is_file())
    if not candidates:
        raise FileNotFoundError(f"{filename} not found under {root}")
    return candidates[-1]


def _read_as_of(report_dir: Path) -> date:
    path = report_dir / "valuation_research_summary.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    return date.fromisoformat(str(payload["as_of_date"]))


def _load_or_fetch_em(cache_dir: Path, *, as_of: date) -> pd.DataFrame:
    path = cache_dir / f"{as_of.isoformat()}-eastmoney-profit-forecast.csv"
    if path.exists():
        return pd.read_csv(path, dtype={"代码": str})
    import akshare as ak

    frame = ak.stock_profit_forecast_em()
    cache_dir.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
    return frame


def _load_or_fetch_ths(code: str, cache_dir: Path, *, as_of: date) -> pd.DataFrame:
    path = cache_dir / f"{as_of.isoformat()}-ths-{code}.csv"
    if path.exists():
        return pd.read_csv(path)
    import akshare as ak

    frame = ak.stock_profit_forecast_ths(symbol=code, indicator="预测年报每股收益")
    cache_dir.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
    return frame


def _fetch_target_ths_frames(
    codes: Iterable[str],
    *,
    cache_dir: Path,
    as_of: date,
    max_workers: int,
    fetcher: Callable[[str, Path], pd.DataFrame] | None = None,
) -> dict[str, pd.DataFrame | None]:
    codes = list(dict.fromkeys(_normalize_code(code) for code in codes if _normalize_code(code)))
    result: dict[str, pd.DataFrame | None] = {}

    def one(code: str) -> pd.DataFrame:
        if fetcher is not None:
            return fetcher(code, cache_dir)
        return _load_or_fetch_ths(code, cache_dir, as_of=as_of)

    with ThreadPoolExecutor(max_workers=max(1, int(max_workers))) as executor:
        futures = {executor.submit(one, code): code for code in codes}
        for future in as_completed(futures):
            code = futures[future]
            try:
                result[code] = future.result()
            except Exception:
                result[code] = None
    return result


def write_forward_scenario_valuation(
    *,
    valuation_root: Path,
    hard_logic_source_dir: Path,
    all_a_report_root: Path,
    output_dir: Path,
    cache_dir: Path,
    min_target_institutions: int = DEFAULT_MIN_TARGET_INSTITUTIONS,
    min_peer_reports: int = DEFAULT_MIN_PEER_REPORTS,
    min_peer_samples: int = DEFAULT_MIN_PEER_SAMPLES,
    max_workers: int = 4,
) -> list[dict[str, Any]]:
    report_dir = find_latest_routing_source(valuation_root)
    as_of = _read_as_of(report_dir)
    routed_rows = _read_csv(report_dir / "valuation_research_routed.csv")
    hard_logic_rows = _read_csv(hard_logic_source_dir / "all_a_quant_screen.csv")
    all_a_report = find_latest_report(all_a_report_root)
    raw_source = next(
        (
            all_a_report / name
            for name in ("all_a_quant_screen.csv", "quant_screen_all.csv", "top80_evidence_queue.csv")
            if (all_a_report / name).exists()
        ),
        None,
    )
    if raw_source is None:
        raise FileNotFoundError("raw All-A source unavailable")
    raw_rows = _read_csv(raw_source)

    hard_pass_codes = [
        _normalize_code(row.get("code"))
        for row in hard_logic_rows
        if str(row.get("hard_logic_state") or "").strip().upper() == "PASS"
    ]
    em_frame = _load_or_fetch_em(cache_dir, as_of=as_of)
    ths_frames = _fetch_target_ths_frames(
        hard_pass_codes,
        cache_dir=cache_dir,
        as_of=as_of,
        max_workers=max_workers,
    )
    rows = build_forward_scenario_rows(
        routed_rows=routed_rows,
        hard_logic_source_rows=hard_logic_rows,
        raw_all_a_rows=raw_rows,
        em_forecast_frame=em_frame,
        ths_frames=ths_frames,
        as_of=as_of,
        min_target_institutions=min_target_institutions,
        min_peer_reports=min_peer_reports,
        min_peer_samples=min_peer_samples,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "forward_scenario_valuation.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=OUTPUT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "as_of_date": as_of.isoformat(),
        "row_count": len(rows),
        "hard_logic_pass_input_count": len(set(hard_pass_codes)),
        "forward_eps_base_ready_count": sum(_positive(row.get("forward_eps_base")) is not None for row in rows),
        "three_scenario_eps_ready_count": sum(
            all(_positive(row.get(field)) is not None for field in ("forward_eps_bear", "forward_eps_base", "forward_eps_bull"))
            for row in rows
        ),
        "reasonable_pe_ready_count": sum(row.get("reasonable_pe_status") == "OK" for row in rows),
        "forward_base_fair_value_ready_count": sum(_positive(row.get("scenario_fair_price_base")) is not None for row in rows),
        "reasonable_pe_policy_version": POLICY_VERSION,
        "reasonable_pe_anchor": "same_industry_same_forecast_year_current_forward_pe_distribution",
        "historical_pe_used_for_reasonable_pe": False,
        "analyst_consensus_is_live_not_historical_pit": True,
        "historical_backtest_eligible": False,
        "formal_signal_eligible": False,
        "automatic_promotion_allowed": False,
        "no_auto_trade": True,
    }
    (output_dir / "forward_scenario_valuation_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    lines = [
        "# Forward Scenario Valuation",
        "",
        "Live analyst consensus only; never use this artifact in historical walk-forward tests.",
        "Historical PE is not used to create reasonable PE.",
        "",
        f"- rows: {summary['row_count']}",
        f"- forward EPS base ready: {summary['forward_eps_base_ready_count']}",
        f"- three-scenario EPS ready: {summary['three_scenario_eps_ready_count']}",
        f"- reasonable PE ready: {summary['reasonable_pe_ready_count']}",
        f"- base fair value ready: {summary['forward_base_fair_value_ready_count']}",
        "",
    ]
    for row in rows:
        lines.append(
            f"- {row.get('code')} {row.get('stock_name')} | {row.get('industry')} | "
            f"EPS={row.get('forward_eps_bear')}/{row.get('forward_eps_base')}/{row.get('forward_eps_bull')} | "
            f"PE={row.get('reasonable_pe_bear')}/{row.get('reasonable_pe_base')}/{row.get('reasonable_pe_bull')} | "
            f"fair={row.get('scenario_fair_price_bear')}/{row.get('scenario_fair_price_base')}/{row.get('scenario_fair_price_bull')} | "
            f"status={row.get('scenario_valuation_status')}"
        )
    (output_dir / "forward_scenario_valuation.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--valuation-root", type=Path, required=True)
    parser.add_argument("--hard-logic-source-dir", type=Path, required=True)
    parser.add_argument("--all-a-report-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, default=Path("data/cache/forward_scenario_consensus"))
    parser.add_argument("--min-target-institutions", type=int, default=DEFAULT_MIN_TARGET_INSTITUTIONS)
    parser.add_argument("--min-peer-reports", type=int, default=DEFAULT_MIN_PEER_REPORTS)
    parser.add_argument("--min-peer-samples", type=int, default=DEFAULT_MIN_PEER_SAMPLES)
    parser.add_argument("--max-workers", type=int, default=4)
    args = parser.parse_args(argv)
    rows = write_forward_scenario_valuation(
        valuation_root=args.valuation_root,
        hard_logic_source_dir=args.hard_logic_source_dir,
        all_a_report_root=args.all_a_report_root,
        output_dir=args.output_dir,
        cache_dir=args.cache_dir,
        min_target_institutions=args.min_target_institutions,
        min_peer_reports=args.min_peer_reports,
        min_peer_samples=args.min_peer_samples,
        max_workers=args.max_workers,
    )
    print(f"forward_scenario_valuation={args.output_dir};count={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
