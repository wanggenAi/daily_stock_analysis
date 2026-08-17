"""Build a broad-recall reverse-valuation research queue.

This module is intentionally a sidecar.  It reads an existing opportunity/all-A
research report, refreshes public fundamental cache entries for a bounded
research population, and writes valuation diagnostics without changing any
Formal BUY, position-sizing, entry, exit, stop, or invalidation gate.

The first production diagnostic is deliberately unit-safe: it compares the
current positive PE with the stock's own historical positive-PE median.  The
ratio answers a narrow question: if the valuation multiple reverted to that
historical reference, how much earnings growth would the current price require?
The historical median is a REFERENCE multiple, not an asserted fair PE.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping

import pandas as pd

from src.strategies.genge_cycle_bottom.fundamentals import PublicFundamentalLoader
from src.strategies.genge_opportunity_discovery.fundamental_valuation import normalize_core_earnings


DISCLAIMER = "仅用于公开数据研究排序和人工复核，不构成买入或卖出建议，不应自动交易。"
DEFAULT_RESEARCH_LIMIT = 80

OUTPUT_COLUMNS = [
    "valuation_research_rank",
    "code",
    "stock_name",
    "industry",
    "quant_status",
    "quant_score",
    "current_pe",
    "historical_median_pe_reference",
    "historical_pe_sample_count",
    "historical_pe_reference_start",
    "historical_pe_reference_end",
    "required_profit_growth_vs_reference",
    "expectation_state",
    "headline_net_profit",
    "normalized_core_operating_profit",
    "operating_cash_flow",
    "cash_conversion_ratio",
    "earnings_quality_score",
    "earnings_quality_confidence",
    "earnings_normalization_method",
    "earnings_point_in_time_method",
    "financial_report_date",
    "financial_disclosure_date",
    "valuation_diagnostic_status",
    "next_research_action",
    "formal_signal_eligible",
    "automatic_promotion_allowed",
    "no_auto_trade",
    "disclaimer",
]


@dataclass(frozen=True)
class PeReferenceDiagnostic:
    current_pe: float | None
    reference_median_pe: float | None
    sample_count: int
    reference_start: str
    reference_end: str
    required_profit_growth: float | None
    status: str


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


def _coerce_date(value: Any) -> date | None:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.date()


def _positive_pe_frame(frame: pd.DataFrame | None, *, as_of: date) -> pd.DataFrame:
    if frame is None or frame.empty or "date" not in frame.columns or "pe" not in frame.columns:
        return pd.DataFrame(columns=["date", "pe"])
    local = frame[["date", "pe"]].copy()
    local["date"] = pd.to_datetime(local["date"], errors="coerce").dt.date
    local["pe"] = pd.to_numeric(local["pe"], errors="coerce")
    local = local.dropna(subset=["date", "pe"])
    local = local[(local["date"] <= as_of) & (local["pe"] > 0)]
    return local.sort_values("date").drop_duplicates("date", keep="last").reset_index(drop=True)


def build_pe_reference_diagnostic(frame: pd.DataFrame | None, *, as_of: date) -> PeReferenceDiagnostic:
    """Reverse-solve earnings growth using a stock's own historical PE median.

    The current observation is excluded from the historical reference sample so
    today's PE cannot mechanically pull its own benchmark toward itself.
    """

    local = _positive_pe_frame(frame, as_of=as_of)
    if local.empty:
        return PeReferenceDiagnostic(None, None, 0, "", "", None, "PE_MODEL_NOT_APPLICABLE")

    current = float(local.iloc[-1]["pe"])
    current_date = local.iloc[-1]["date"]
    history = local[local["date"] < current_date].copy()
    if history.empty:
        return PeReferenceDiagnostic(current, None, 0, "", "", None, "PE_REFERENCE_UNAVAILABLE")

    reference = float(history["pe"].median())
    if not math.isfinite(reference) or reference <= 0:
        return PeReferenceDiagnostic(current, None, len(history), "", "", None, "PE_REFERENCE_UNAVAILABLE")

    required_growth = current / reference - 1.0
    return PeReferenceDiagnostic(
        current_pe=current,
        reference_median_pe=reference,
        sample_count=len(history),
        reference_start=history.iloc[0]["date"].isoformat(),
        reference_end=history.iloc[-1]["date"].isoformat(),
        required_profit_growth=required_growth,
        status="OK",
    )


def _financial_pit_row(frame: pd.DataFrame | None, *, as_of: date) -> tuple[Mapping[str, Any], str]:
    if frame is None or frame.empty or "report_date" not in frame.columns:
        return {}, "FINANCIAL_DATA_UNAVAILABLE"
    local = frame.copy()
    local["report_date"] = pd.to_datetime(local["report_date"], errors="coerce").dt.date
    if "disclosure_date" in local.columns:
        local["disclosure_date"] = pd.to_datetime(local["disclosure_date"], errors="coerce").dt.date
        disclosed = local[local["disclosure_date"].notna() & (local["disclosure_date"] <= as_of)].copy()
        if not disclosed.empty:
            disclosed = disclosed.sort_values(["disclosure_date", "report_date"])
            return disclosed.iloc[-1].to_dict(), "DISCLOSURE_DATE_PIT"
    fallback = local[local["report_date"].notna() & (local["report_date"] <= as_of)].copy()
    if fallback.empty:
        return {}, "FINANCIAL_DATA_UNAVAILABLE"
    fallback = fallback.sort_values("report_date")
    return fallback.iloc[-1].to_dict(), "REPORT_DATE_FALLBACK"


def _expectation_state(required_growth: float | None, status: str) -> str:
    if status == "PE_MODEL_NOT_APPLICABLE":
        return "PE_MODEL_NOT_APPLICABLE"
    if required_growth is None:
        return "REFERENCE_UNAVAILABLE"
    if required_growth <= 0:
        return "EXPECTATION_NOT_ABOVE_HISTORICAL_REFERENCE"
    return "EARNINGS_GROWTH_REQUIRED"


def _next_research_action(expectation_state: str, earnings_confidence: str) -> str:
    actions: list[str] = []
    if expectation_state == "EXPECTATION_NOT_ABOVE_HISTORICAL_REFERENCE":
        actions.append("check_value_trap_and_cycle_peak_before_upgrading_research_priority")
    elif expectation_state == "EARNINGS_GROWTH_REQUIRED":
        actions.append("verify_credible_profit_growth_path_against_implied_requirement")
    elif expectation_state == "PE_MODEL_NOT_APPLICABLE":
        actions.append("use_non_PE_archetype_valuation")
    else:
        actions.append("complete_PE_reference_history")
    if str(earnings_confidence).upper() == "LOW":
        actions.append("upgrade_recurring_profit_and_cashflow_evidence")
    return ";".join(actions)


def _rank_key(row: Mapping[str, Any]) -> tuple[int, float, float, str]:
    growth = _finite(row.get("required_profit_growth_vs_reference"))
    quality = _finite(row.get("earnings_quality_score")) or 0.0
    quant = _finite(row.get("quant_score")) or 0.0
    return (1 if growth is None else 0, growth if growth is not None else math.inf, -quality, -quant, str(row.get("code") or ""))


def _read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _source_rows(report_dir: Path) -> list[dict[str, Any]]:
    # All-A production report first; generic opportunity report as fallback.
    for filename in ("top80_evidence_queue.csv", "all_a_quant_screen.csv", "quant_screen_all.csv"):
        rows = _read_csv(report_dir / filename)
        if rows:
            return rows
    return []


def _summary_as_of(report_dir: Path) -> date | None:
    for filename in ("run_summary.json", "quant_screen_summary.json"):
        path = report_dir / filename
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for key in ("as_of_date", "resolved_as_of_date"):
            parsed = _coerce_date(payload.get(key))
            if parsed is not None:
                return parsed
    return None


def build_valuation_research_rows(
    source_rows: Iterable[Mapping[str, Any]],
    *,
    as_of: date,
    loader: PublicFundamentalLoader,
    research_limit: int = DEFAULT_RESEARCH_LIMIT,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source in source_rows:
        code = _normalize_code(source.get("code"))
        hard = str(source.get("hard_blockers") or source.get("hard_reject_blockers") or "").strip()
        status = str(source.get("quant_status") or source.get("quant_screen_status") or "")
        if not code or code in seen or hard or status == "HARD_REJECT":
            continue
        candidates.append(dict(source))
        seen.add(code)
        if len(candidates) >= max(0, int(research_limit)):
            break

    output: list[dict[str, Any]] = []
    for source in candidates:
        code = _normalize_code(source.get("code"))
        try:
            fetched = loader.load(code, years=5, fetch_valuation=True, fetch_financial=True)
            valuation_frame = fetched.valuation_df
            financial_frame = fetched.financial_df
        except Exception:
            valuation_frame = None
            financial_frame = None

        pe_diag = build_pe_reference_diagnostic(valuation_frame, as_of=as_of)
        financial_row, pit_method = _financial_pit_row(financial_frame, as_of=as_of)
        earnings = normalize_core_earnings(
            net_profit=financial_row.get("net_profit"),
            recurring_profit=financial_row.get("recurring_profit"),
            investment_income=financial_row.get("investment_income"),
            fair_value_change_gain=financial_row.get("fair_value_change_gain"),
            operating_cash_flow=financial_row.get("operating_cash_flow"),
        )
        state = _expectation_state(pe_diag.required_profit_growth, pe_diag.status)
        output.append({
            "valuation_research_rank": 0,
            "code": code,
            "stock_name": source.get("stock_name") or "",
            "industry": source.get("industry") or source.get("normalized_industry") or source.get("raw_industry") or "",
            "quant_status": source.get("quant_status") or source.get("quant_screen_status") or "",
            "quant_score": source.get("quant_score") or "",
            "current_pe": pe_diag.current_pe,
            "historical_median_pe_reference": pe_diag.reference_median_pe,
            "historical_pe_sample_count": pe_diag.sample_count,
            "historical_pe_reference_start": pe_diag.reference_start,
            "historical_pe_reference_end": pe_diag.reference_end,
            "required_profit_growth_vs_reference": pe_diag.required_profit_growth,
            "expectation_state": state,
            "headline_net_profit": earnings.headline_net_profit,
            "normalized_core_operating_profit": earnings.normalized_core_operating_profit,
            "operating_cash_flow": earnings.operating_cash_flow,
            "cash_conversion_ratio": earnings.cash_conversion_ratio,
            "earnings_quality_score": earnings.earnings_quality_score,
            "earnings_quality_confidence": earnings.earnings_quality_confidence,
            "earnings_normalization_method": earnings.normalization_method,
            "earnings_point_in_time_method": pit_method,
            "financial_report_date": financial_row.get("report_date") or "",
            "financial_disclosure_date": financial_row.get("disclosure_date") or "",
            "valuation_diagnostic_status": pe_diag.status,
            "next_research_action": _next_research_action(state, earnings.earnings_quality_confidence),
            "formal_signal_eligible": False,
            "automatic_promotion_allowed": False,
            "no_auto_trade": True,
            "disclaimer": DISCLAIMER,
        })

    output.sort(key=_rank_key)
    for rank, row in enumerate(output, 1):
        row["valuation_research_rank"] = rank
    return output


def write_report(
    report_dir: Path,
    *,
    fundamental_cache_dir: Path = Path("data/cache/genge_fundamentals"),
    research_limit: int = DEFAULT_RESEARCH_LIMIT,
) -> list[dict[str, Any]]:
    as_of = _summary_as_of(report_dir)
    if as_of is None:
        raise ValueError("report as_of_date is unavailable")
    source_rows = _source_rows(report_dir)
    loader = PublicFundamentalLoader(fundamental_cache_dir)
    rows = build_valuation_research_rows(
        source_rows,
        as_of=as_of,
        loader=loader,
        research_limit=research_limit,
    )

    csv_path = report_dir / "valuation_research_queue.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows({key: row.get(key, "") for key in OUTPUT_COLUMNS} for row in rows)

    lines = [
        "# Reverse Valuation Research Queue",
        "",
        DISCLAIMER,
        "",
        "Historical median PE is a reference multiple, not an asserted fair PE. This queue never grants Formal BUY eligibility.",
        "",
    ]
    for row in rows:
        growth = _finite(row.get("required_profit_growth_vs_reference"))
        growth_text = "NA" if growth is None else f"{growth * 100:.2f}%"
        lines.extend([
            f"## {row['valuation_research_rank']}. {row['code']} {row['stock_name']}",
            f"- current/reference PE: {row['current_pe']} / {row['historical_median_pe_reference']}",
            f"- implied required profit growth: {growth_text}",
            f"- expectation state: {row['expectation_state']}",
            f"- earnings quality: {row['earnings_quality_score']} ({row['earnings_quality_confidence']})",
            f"- next research action: {row['next_research_action']}",
            "- formal signal eligible: False",
            "",
        ])
    if not rows:
        lines.append("No eligible broad-recall research candidates with available source rows.")
    (report_dir / "valuation_research_queue.md").write_text("\n".join(lines), encoding="utf-8")
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-dir", type=Path, required=True)
    parser.add_argument("--fundamental-cache-dir", type=Path, default=Path("data/cache/genge_fundamentals"))
    parser.add_argument("--research-limit", type=int, default=DEFAULT_RESEARCH_LIMIT)
    args = parser.parse_args(argv)
    rows = write_report(
        args.report_dir,
        fundamental_cache_dir=args.fundamental_cache_dir,
        research_limit=args.research_limit,
    )
    print(f"valuation_research_report={args.report_dir};count={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
