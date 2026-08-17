"""Build a broad-recall reverse-valuation research queue.

This module is intentionally a sidecar. It reads an existing All-A/opportunity
research report, refreshes public fundamentals for a bounded research population,
and writes valuation diagnostics without changing any Formal BUY, position-size,
entry, exit, stop, or invalidation gate.

The first production diagnostic is deliberately unit-safe: it compares the
current positive PE with the stock's own point-in-time historical positive-PE
median. The current observation is excluded from that median. The ratio answers
one narrow question: if the multiple reverted to that historical reference, how
much earnings would today's price require relative to the current earnings base?

The historical median is a REFERENCE multiple, not an asserted fair PE.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping

import pandas as pd

from src.strategies.genge_cycle_bottom.fundamentals import PublicFundamentalLoader
from src.strategies.genge_opportunity_discovery.fundamental_valuation import normalize_core_earnings


DISCLAIMER = "仅用于公开数据研究排序和人工复核，不构成买入或卖出建议，不应自动交易。"
DEFAULT_RESEARCH_LIMIT = 80
DEFAULT_RELAXED_RESERVE = 20
DEFAULT_FINANCIAL_REVIEW_LIMIT = 30
RELAXABLE_TECHNICAL_BLOCKERS = frozenset(
    {"price_too_high", "board_5d_abnormal_move", "board_10d_abnormal_move"}
)
NORMAL_RESEARCH_STATUSES = frozenset({"PRIORITY_RESEARCH", "SECONDARY_RESEARCH"})
WIDE_RECALL_STATUSES = frozenset(
    {"PRIORITY_RESEARCH", "SECONDARY_RESEARCH", "LOW_PRIORITY", "HARD_REJECT"}
)

OUTPUT_COLUMNS = [
    "valuation_research_rank",
    "code",
    "stock_name",
    "industry",
    "wide_recall_reason",
    "quant_status",
    "quant_rank",
    "quant_score",
    "source_hard_blockers",
    "current_pe",
    "historical_median_pe_reference",
    "historical_pe_sample_count",
    "historical_pe_reference_start",
    "historical_pe_reference_end",
    "historical_pe_percentile",
    "implied_profit_multiple_of_current",
    "required_profit_growth_vs_reference",
    "required_profit_growth_pct",
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
    "financial_review_status",
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
    percentile: float | None
    implied_profit_multiple: float | None
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


def _blockers(value: Any) -> set[str]:
    return {item.strip() for item in str(value or "").split(";") if item.strip()}


def _quant_order_key(row: Mapping[str, Any]) -> tuple[float, float, str]:
    rank = _finite(row.get("quant_rank"))
    score = _finite(row.get("quant_score"))
    return (
        rank if rank is not None else 10**9,
        -(score if score is not None else -10**9),
        _normalize_code(row.get("code")),
    )


def _wide_recall_reason(source: Mapping[str, Any]) -> str | None:
    status = str(
        source.get("quant_status") or source.get("quant_screen_status") or ""
    ).strip().upper()
    if status not in WIDE_RECALL_STATUSES:
        return None

    hard = _blockers(source.get("hard_blockers") or source.get("hard_reject_blockers"))
    non_relaxable = hard - RELAXABLE_TECHNICAL_BLOCKERS
    if non_relaxable:
        return None
    if status in NORMAL_RESEARCH_STATUSES:
        return "NORMAL_RESEARCH_QUEUE"
    if status == "LOW_PRIORITY" and not hard:
        return "SOFT_FILTER_RECOVERY"
    if status == "HARD_REJECT" and hard and hard <= RELAXABLE_TECHNICAL_BLOCKERS:
        return "RELAXABLE_TECHNICAL_RECOVERY"
    return None


def select_wide_recall_rows(
    source_rows: Iterable[Mapping[str, Any]],
    *,
    research_limit: int = DEFAULT_RESEARCH_LIMIT,
    relaxed_reserve: int = DEFAULT_RELAXED_RESERVE,
) -> list[dict[str, Any]]:
    """Build a bounded broad-recall pool without changing formal eligibility.

    ``all_a_quant_screen.csv`` is already downstream of the universe safety
    filters. Inside that screened universe, this sidecar may recover only the
    explicitly listed technical blockers. Missing price data, unknown mappings,
    financial safety failures, ST/delisting exclusions, and other hard risks are
    never recovered here.
    """

    limit = max(0, int(research_limit))
    reserve = max(0, min(limit, int(relaxed_reserve)))
    normal: list[dict[str, Any]] = []
    relaxed: list[dict[str, Any]] = []
    seen: set[str] = set()

    for raw in source_rows:
        code = _normalize_code(raw.get("code"))
        if not code or code in seen:
            continue
        reason = _wide_recall_reason(raw)
        if reason is None:
            continue
        row = dict(raw)
        row["code"] = code
        row["wide_recall_reason"] = reason
        row["source_hard_blockers"] = (
            row.get("hard_blockers") or row.get("hard_reject_blockers") or ""
        )
        if reason == "NORMAL_RESEARCH_QUEUE":
            normal.append(row)
        else:
            relaxed.append(row)
        seen.add(code)

    normal.sort(key=_quant_order_key)
    relaxed.sort(key=_quant_order_key)

    normal_budget = max(0, limit - reserve)
    selected = normal[:normal_budget] + relaxed[:reserve]
    used = {_normalize_code(row.get("code")) for row in selected}
    leftovers = [
        row
        for row in (*normal[normal_budget:], *relaxed[reserve:])
        if _normalize_code(row.get("code")) not in used
    ]
    leftovers.sort(key=_quant_order_key)
    selected.extend(leftovers[: max(0, limit - len(selected))])
    return selected[:limit]


def _positive_pe_frame(frame: pd.DataFrame | None, *, as_of: date) -> pd.DataFrame:
    if frame is None or frame.empty or "date" not in frame.columns or "pe" not in frame.columns:
        return pd.DataFrame(columns=["date", "pe"])
    local = frame[["date", "pe"]].copy()
    local["date"] = pd.to_datetime(local["date"], errors="coerce").dt.date
    local["pe"] = pd.to_numeric(local["pe"], errors="coerce")
    local = local.dropna(subset=["date", "pe"])
    local = local[(local["date"] <= as_of) & (local["pe"] > 0)]
    return (
        local.sort_values("date")
        .drop_duplicates("date", keep="last")
        .reset_index(drop=True)
    )


def build_pe_reference_diagnostic(
    frame: pd.DataFrame | None,
    *,
    as_of: date,
    minimum_history_samples: int = 1,
) -> PeReferenceDiagnostic:
    """Reverse-solve earnings growth using the stock's own historical PE median.

    The current observation is excluded from the reference sample so today's PE
    cannot mechanically pull its own benchmark toward itself.
    """

    local = _positive_pe_frame(frame, as_of=as_of)
    if local.empty:
        return PeReferenceDiagnostic(
            None, None, 0, "", "", None, None, None, "PE_MODEL_NOT_APPLICABLE"
        )

    current = float(local.iloc[-1]["pe"])
    current_date = local.iloc[-1]["date"]
    history = local[local["date"] < current_date].copy()
    if len(history) < max(1, int(minimum_history_samples)):
        return PeReferenceDiagnostic(
            current,
            None,
            len(history),
            history.iloc[0]["date"].isoformat() if not history.empty else "",
            history.iloc[-1]["date"].isoformat() if not history.empty else "",
            None,
            None,
            None,
            "PE_REFERENCE_INSUFFICIENT",
        )

    reference = float(history["pe"].median())
    if not math.isfinite(reference) or reference <= 0:
        return PeReferenceDiagnostic(
            current,
            None,
            len(history),
            "",
            "",
            None,
            None,
            None,
            "PE_REFERENCE_UNAVAILABLE",
        )

    pe_values = pd.to_numeric(history["pe"], errors="coerce").dropna()
    percentile = float((pe_values <= current).sum() / len(pe_values))
    implied_profit_multiple = current / reference
    required_growth = implied_profit_multiple - 1.0
    return PeReferenceDiagnostic(
        current_pe=current,
        reference_median_pe=reference,
        sample_count=len(history),
        reference_start=history.iloc[0]["date"].isoformat(),
        reference_end=history.iloc[-1]["date"].isoformat(),
        percentile=percentile,
        implied_profit_multiple=implied_profit_multiple,
        required_profit_growth=required_growth,
        status="OK",
    )


def _financial_pit_row(
    frame: pd.DataFrame | None,
    *,
    as_of: date,
) -> tuple[Mapping[str, Any], str]:
    if frame is None or frame.empty or "report_date" not in frame.columns:
        return {}, "FINANCIAL_DATA_UNAVAILABLE"
    local = frame.copy()
    local["report_date"] = pd.to_datetime(local["report_date"], errors="coerce").dt.date
    if "disclosure_date" in local.columns:
        local["disclosure_date"] = pd.to_datetime(
            local["disclosure_date"], errors="coerce"
        ).dt.date
        known_disclosures = local[local["disclosure_date"].notna()].copy()
        disclosed = known_disclosures[
            known_disclosures["disclosure_date"] <= as_of
        ].copy()
        if not disclosed.empty:
            disclosed = disclosed.sort_values(["disclosure_date", "report_date"])
            return disclosed.iloc[-1].to_dict(), "DISCLOSURE_DATE_PIT"
        if not known_disclosures.empty:
            return {}, "DISCLOSURE_DATE_NOT_YET_AVAILABLE"

    fallback = local[
        local["report_date"].notna() & (local["report_date"] <= as_of)
    ].copy()
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


def _next_research_action(
    expectation_state: str,
    earnings_confidence: str,
    financial_review_status: str,
) -> str:
    actions: list[str] = []
    if expectation_state == "EXPECTATION_NOT_ABOVE_HISTORICAL_REFERENCE":
        actions.append("check_value_trap_and_cycle_peak_before_upgrading_research_priority")
    elif expectation_state == "EARNINGS_GROWTH_REQUIRED":
        actions.append("verify_credible_profit_growth_path_against_implied_requirement")
    elif expectation_state == "PE_MODEL_NOT_APPLICABLE":
        actions.append("use_non_PE_archetype_valuation")
    else:
        actions.append("complete_PE_reference_history")
    if financial_review_status == "NOT_SELECTED_FOR_DEEP_FINANCIAL_REVIEW":
        actions.append("deep_financial_review_pending")
    elif str(earnings_confidence).upper() == "LOW":
        actions.append("upgrade_recurring_profit_and_cashflow_evidence")
    return ";".join(actions)


def _rank_key(row: Mapping[str, Any]) -> tuple[int, float, float, float, str]:
    status = str(row.get("valuation_diagnostic_status") or "")
    applicable = 0 if status == "OK" else 1
    growth = _finite(row.get("required_profit_growth_vs_reference"))
    quality = _finite(row.get("earnings_quality_score"))
    quant = _finite(row.get("quant_score"))
    return (
        applicable,
        growth if growth is not None else math.inf,
        -(quality if quality is not None else -1.0),
        -(quant if quant is not None else -1.0),
        str(row.get("code") or ""),
    )


def _load_many(
    loader: PublicFundamentalLoader,
    codes: Iterable[str],
    *,
    years: int,
    fetch_valuation: bool,
    fetch_financial: bool,
    max_workers: int,
) -> dict[str, Any]:
    normalized = list(
        dict.fromkeys(_normalize_code(code) for code in codes if _normalize_code(code))
    )
    results: dict[str, Any] = {}

    def load_one(code: str):
        return loader.load(
            code,
            years=years,
            fetch_valuation=fetch_valuation,
            fetch_financial=fetch_financial,
        )

    if max_workers <= 1:
        for code in normalized:
            try:
                results[code] = load_one(code)
            except Exception as exc:
                results[code] = exc
        return results

    with ThreadPoolExecutor(max_workers=max(1, int(max_workers))) as executor:
        futures = {executor.submit(load_one, code): code for code in normalized}
        for future in as_completed(futures):
            code = futures[future]
            try:
                results[code] = future.result()
            except Exception as exc:
                results[code] = exc
    return results


def _base_row(
    source: Mapping[str, Any],
    pe_diag: PeReferenceDiagnostic,
) -> dict[str, Any]:
    state = _expectation_state(pe_diag.required_profit_growth, pe_diag.status)
    return {
        "valuation_research_rank": 0,
        "code": _normalize_code(source.get("code")),
        "stock_name": source.get("stock_name") or "",
        "industry": (
            source.get("industry")
            or source.get("normalized_industry")
            or source.get("raw_industry")
            or ""
        ),
        "wide_recall_reason": source.get("wide_recall_reason") or "",
        "quant_status": source.get("quant_status") or source.get("quant_screen_status") or "",
        "quant_rank": source.get("quant_rank") or "",
        "quant_score": source.get("quant_score") or "",
        "source_hard_blockers": (
            source.get("source_hard_blockers")
            or source.get("hard_blockers")
            or source.get("hard_reject_blockers")
            or ""
        ),
        "current_pe": pe_diag.current_pe,
        "historical_median_pe_reference": pe_diag.reference_median_pe,
        "historical_pe_sample_count": pe_diag.sample_count,
        "historical_pe_reference_start": pe_diag.reference_start,
        "historical_pe_reference_end": pe_diag.reference_end,
        "historical_pe_percentile": pe_diag.percentile,
        "implied_profit_multiple_of_current": pe_diag.implied_profit_multiple,
        "required_profit_growth_vs_reference": pe_diag.required_profit_growth,
        "required_profit_growth_pct": (
            pe_diag.required_profit_growth * 100.0
            if pe_diag.required_profit_growth is not None
            else None
        ),
        "expectation_state": state,
        "headline_net_profit": None,
        "normalized_core_operating_profit": None,
        "operating_cash_flow": None,
        "cash_conversion_ratio": None,
        "earnings_quality_score": None,
        "earnings_quality_confidence": "",
        "earnings_normalization_method": "",
        "earnings_point_in_time_method": "",
        "financial_report_date": "",
        "financial_disclosure_date": "",
        "financial_review_status": "NOT_SELECTED_FOR_DEEP_FINANCIAL_REVIEW",
        "valuation_diagnostic_status": pe_diag.status,
        "next_research_action": _next_research_action(
            state, "", "NOT_SELECTED_FOR_DEEP_FINANCIAL_REVIEW"
        ),
        "formal_signal_eligible": False,
        "automatic_promotion_allowed": False,
        "no_auto_trade": True,
        "disclaimer": DISCLAIMER,
    }


def _add_financial_review(
    row: Mapping[str, Any],
    financial_frame: pd.DataFrame | None,
    *,
    as_of: date,
) -> dict[str, Any]:
    local = dict(row)
    financial_row, pit_method = _financial_pit_row(financial_frame, as_of=as_of)
    earnings = normalize_core_earnings(
        net_profit=financial_row.get("net_profit"),
        recurring_profit=financial_row.get("recurring_profit"),
        investment_income=financial_row.get("investment_income"),
        fair_value_change_gain=financial_row.get("fair_value_change_gain"),
        operating_cash_flow=financial_row.get("operating_cash_flow"),
    )
    financial_status = "OK" if financial_row else pit_method
    local.update(
        {
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
            "financial_review_status": financial_status,
        }
    )
    if (
        earnings.normalized_core_operating_profit is not None
        and earnings.normalized_core_operating_profit <= 0
    ):
        local["valuation_diagnostic_status"] = "PE_MODEL_NOT_APPLICABLE"
        local["expectation_state"] = "PE_MODEL_NOT_APPLICABLE"
    local["next_research_action"] = _next_research_action(
        str(local.get("expectation_state") or ""),
        str(local.get("earnings_quality_confidence") or ""),
        str(local.get("financial_review_status") or ""),
    )
    return local


def build_valuation_research_rows(
    source_rows: Iterable[Mapping[str, Any]],
    *,
    as_of: date,
    loader: PublicFundamentalLoader,
    research_limit: int = DEFAULT_RESEARCH_LIMIT,
    relaxed_reserve: int = DEFAULT_RELAXED_RESERVE,
    financial_review_limit: int = DEFAULT_FINANCIAL_REVIEW_LIMIT,
    minimum_pe_samples: int = 1,
    years: int = 5,
    max_workers: int = 1,
) -> list[dict[str, Any]]:
    selected = select_wide_recall_rows(
        source_rows,
        research_limit=research_limit,
        relaxed_reserve=relaxed_reserve,
    )

    valuation_results = _load_many(
        loader,
        [row.get("code") for row in selected],
        years=years,
        fetch_valuation=True,
        fetch_financial=False,
        max_workers=max_workers,
    )
    provisional: list[dict[str, Any]] = []
    for source in selected:
        code = _normalize_code(source.get("code"))
        fetched = valuation_results.get(code)
        valuation_frame = None if isinstance(fetched, Exception) or fetched is None else fetched.valuation_df
        pe_diag = build_pe_reference_diagnostic(
            valuation_frame,
            as_of=as_of,
            minimum_history_samples=minimum_pe_samples,
        )
        provisional.append(_base_row(source, pe_diag))

    provisional.sort(key=_rank_key)
    financial_codes = [
        row["code"]
        for row in provisional
        if row.get("valuation_diagnostic_status") == "OK"
    ][: max(0, int(financial_review_limit))]
    financial_results = _load_many(
        loader,
        financial_codes,
        years=years,
        fetch_valuation=False,
        fetch_financial=True,
        max_workers=max_workers,
    )

    reviewed: list[dict[str, Any]] = []
    financial_code_set = set(financial_codes)
    for row in provisional:
        code = _normalize_code(row.get("code"))
        if code not in financial_code_set:
            reviewed.append(dict(row))
            continue
        fetched = financial_results.get(code)
        financial_frame = None if isinstance(fetched, Exception) or fetched is None else fetched.financial_df
        reviewed.append(_add_financial_review(row, financial_frame, as_of=as_of))

    reviewed.sort(key=_rank_key)
    for rank, row in enumerate(reviewed, 1):
        row["valuation_research_rank"] = rank
    return reviewed


def _read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _source_rows(report_dir: Path) -> list[dict[str, Any]]:
    # Prefer the full quant screen so the sidecar can recover technical-only
    # rejects. The top80 queue is already narrowed and would defeat broad recall.
    for filename in ("all_a_quant_screen.csv", "quant_screen_all.csv", "top80_evidence_queue.csv"):
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


def find_latest_report(report_root: Path) -> Path:
    if any(
        (report_root / name).exists()
        for name in ("all_a_quant_screen.csv", "quant_screen_all.csv", "top80_evidence_queue.csv")
    ):
        return report_root
    candidates = sorted(
        {
            path.parent
            for pattern in ("**/all_a_quant_screen.csv", "**/quant_screen_all.csv", "**/top80_evidence_queue.csv")
            for path in report_root.glob(pattern)
            if path.is_file()
        },
        key=lambda path: str(path),
    )
    if not candidates:
        raise FileNotFoundError(f"no valuation research source report under {report_root}")
    return candidates[-1]


def write_report(
    report_dir: Path,
    *,
    output_dir: Path | None = None,
    fundamental_cache_dir: Path = Path("data/cache/valuation_research_fundamentals"),
    research_limit: int = DEFAULT_RESEARCH_LIMIT,
    relaxed_reserve: int = DEFAULT_RELAXED_RESERVE,
    financial_review_limit: int = DEFAULT_FINANCIAL_REVIEW_LIMIT,
    minimum_pe_samples: int = 20,
    years: int = 5,
    max_workers: int = 6,
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
        relaxed_reserve=relaxed_reserve,
        financial_review_limit=financial_review_limit,
        minimum_pe_samples=minimum_pe_samples,
        years=years,
        max_workers=max_workers,
    )

    target = output_dir or report_dir
    target.mkdir(parents=True, exist_ok=True)
    csv_path = target / "valuation_research_queue.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows({key: row.get(key, "") for key in OUTPUT_COLUMNS} for row in rows)

    lines = [
        "# Reverse Valuation Research Queue",
        "",
        DISCLAIMER,
        "",
        "Historical median PE is a reference multiple, not an asserted fair PE. "
        "This queue never grants Formal BUY eligibility.",
        "",
        f"- as_of_date: {as_of.isoformat()}",
        f"- selected_count: {len(rows)}",
        f"- relaxed_recovery_count: {sum(row.get('wide_recall_reason') != 'NORMAL_RESEARCH_QUEUE' for row in rows)}",
        f"- financial_review_count: {sum(row.get('financial_review_status') != 'NOT_SELECTED_FOR_DEEP_FINANCIAL_REVIEW' for row in rows)}",
        "",
    ]
    for row in rows[:30]:
        growth = _finite(row.get("required_profit_growth_vs_reference"))
        growth_text = "NA" if growth is None else f"{growth * 100:.2f}%"
        lines.extend(
            [
                f"## {row['valuation_research_rank']}. {row['code']} {row['stock_name']}",
                f"- recall: {row['wide_recall_reason']}",
                f"- current/reference PE: {row['current_pe']} / {row['historical_median_pe_reference']}",
                f"- implied required profit growth: {growth_text}",
                f"- expectation state: {row['expectation_state']}",
                f"- earnings quality: {row['earnings_quality_score']} ({row['earnings_quality_confidence']})",
                f"- next research action: {row['next_research_action']}",
                "- formal signal eligible: False",
                "",
            ]
        )
    if not rows:
        lines.append("No eligible broad-recall research candidates with available source rows.")
    (target / "valuation_research_queue.md").write_text("\n".join(lines), encoding="utf-8")

    summary = {
        "as_of_date": as_of.isoformat(),
        "source_report_dir": str(report_dir),
        "selected_count": len(rows),
        "normal_research_count": sum(
            row.get("wide_recall_reason") == "NORMAL_RESEARCH_QUEUE" for row in rows
        ),
        "relaxed_recovery_count": sum(
            row.get("wide_recall_reason") != "NORMAL_RESEARCH_QUEUE" for row in rows
        ),
        "valid_reverse_pe_count": sum(
            row.get("valuation_diagnostic_status") == "OK" for row in rows
        ),
        "pe_model_not_applicable_count": sum(
            row.get("valuation_diagnostic_status") == "PE_MODEL_NOT_APPLICABLE"
            for row in rows
        ),
        "financial_review_count": sum(
            row.get("financial_review_status") != "NOT_SELECTED_FOR_DEEP_FINANCIAL_REVIEW"
            for row in rows
        ),
        "research_limit": int(research_limit),
        "relaxed_reserve": int(relaxed_reserve),
        "financial_review_limit": int(financial_review_limit),
        "minimum_pe_samples": int(minimum_pe_samples),
        "historical_pe_years": int(years),
        "formal_signal_eligible": False,
        "automatic_promotion_allowed": False,
        "no_auto_trade": True,
        "ranking_semantics": (
            "valid PE-reference diagnostics first; lower implied required profit "
            "growth first; then higher earnings quality and existing quant score"
        ),
        "disclaimer": DISCLAIMER,
    }
    (target / "valuation_research_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-dir", type=Path)
    parser.add_argument("--report-root", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument(
        "--fundamental-cache-dir",
        type=Path,
        default=Path("data/cache/valuation_research_fundamentals"),
    )
    parser.add_argument("--research-limit", type=int, default=DEFAULT_RESEARCH_LIMIT)
    parser.add_argument("--relaxed-reserve", type=int, default=DEFAULT_RELAXED_RESERVE)
    parser.add_argument(
        "--financial-review-limit",
        type=int,
        default=DEFAULT_FINANCIAL_REVIEW_LIMIT,
    )
    parser.add_argument("--minimum-pe-samples", type=int, default=20)
    parser.add_argument("--years", type=int, default=5)
    parser.add_argument("--max-workers", type=int, default=6)
    args = parser.parse_args(argv)

    if bool(args.report_dir) == bool(args.report_root):
        parser.error("provide exactly one of --report-dir or --report-root")
    report_dir = args.report_dir or find_latest_report(args.report_root)
    output_dir = args.output_dir
    if output_dir is not None:
        report_as_of = _summary_as_of(report_dir)
        if report_as_of is None:
            raise ValueError("report as_of_date is unavailable")
        output_dir = output_dir / report_as_of.strftime("%Y%m%d")
    rows = write_report(
        report_dir,
        output_dir=output_dir,
        fundamental_cache_dir=args.fundamental_cache_dir,
        research_limit=args.research_limit,
        relaxed_reserve=args.relaxed_reserve,
        financial_review_limit=args.financial_review_limit,
        minimum_pe_samples=args.minimum_pe_samples,
        years=args.years,
        max_workers=args.max_workers,
    )
    print(f"valuation_research_report={output_dir or report_dir};count={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
