"""Independent reverse-valuation research queue for the All-A production scan.

This sidecar is intentionally research-only. It consumes the completed All-A
quant screen, broadens fundamental review without changing any production
eligibility gate, and ranks candidates by the profit level implied by their
current PE relative to their own point-in-time historical PE distribution.

It never creates a Formal BUY, position size, order, stop, or exit instruction.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping

import pandas as pd

from src.strategies.genge_cycle_bottom.fundamentals import PublicFundamentalLoader, normalize_code
from src.strategies.genge_opportunity_discovery.fundamental_valuation import normalize_core_earnings


DISCLAIMER = "仅用于公开数据研究观察和人工复核，不构成买入或卖出建议，不应自动交易。"
RELAXABLE_TECHNICAL_BLOCKERS = frozenset(
    {"price_too_high", "board_5d_abnormal_move", "board_10d_abnormal_move"}
)
NORMAL_RESEARCH_STATUSES = frozenset({"PRIORITY_RESEARCH", "SECONDARY_RESEARCH"})
WIDE_RECALL_STATUSES = frozenset({"PRIORITY_RESEARCH", "SECONDARY_RESEARCH", "LOW_PRIORITY", "HARD_REJECT"})

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
    "historical_median_pe",
    "historical_pe_sample_count",
    "historical_pe_percentile",
    "implied_profit_multiple_of_current",
    "required_profit_growth",
    "required_profit_growth_pct",
    "latest_net_profit",
    "latest_operating_cash_flow",
    "earnings_quality_score",
    "earnings_quality_confidence",
    "earnings_normalization_method",
    "valuation_diagnostic_status",
    "financial_review_status",
    "formal_buy_eligible",
    "automatic_promotion_allowed",
    "disclaimer",
]


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _blockers(value: Any) -> set[str]:
    return {item.strip() for item in str(value or "").split(";") if item.strip()}


def _quant_key(row: Mapping[str, Any]) -> tuple[float, float, str]:
    rank = _finite(row.get("quant_rank"))
    score = _finite(row.get("quant_score"))
    return (
        rank if rank is not None else 10**9,
        -(score if score is not None else -10**9),
        normalize_code(row.get("code")),
    )


def _wide_recall_reason(row: Mapping[str, Any]) -> str | None:
    status = str(row.get("quant_status") or "").strip().upper()
    if status not in WIDE_RECALL_STATUSES:
        return None
    hard = _blockers(row.get("hard_blockers"))
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
    quant_rows: Iterable[Mapping[str, Any]],
    *,
    max_candidates: int = 80,
    relaxed_reserve: int = 20,
) -> list[dict[str, Any]]:
    """Reserve research capacity for rows rejected only by soft/technical shape.

    Safety exclusions happen before ``all_a_quant_screen.csv`` is generated.
    Within that already-filtered universe, only the explicitly listed technical
    blockers may be recovered here. The result cannot promote a formal signal.
    """

    limit = max(0, int(max_candidates))
    reserve = max(0, min(limit, int(relaxed_reserve)))
    normal: list[dict[str, Any]] = []
    relaxed: list[dict[str, Any]] = []

    for source in quant_rows:
        reason = _wide_recall_reason(source)
        if reason is None:
            continue
        row = dict(source)
        row["wide_recall_reason"] = reason
        if reason == "NORMAL_RESEARCH_QUEUE":
            normal.append(row)
        else:
            relaxed.append(row)

    normal.sort(key=_quant_key)
    relaxed.sort(key=_quant_key)

    normal_budget = max(0, limit - reserve)
    selected = normal[:normal_budget] + relaxed[:reserve]
    used = {normalize_code(row.get("code")) for row in selected}

    leftovers = [
        row for row in (*normal[normal_budget:], *relaxed[reserve:])
        if normalize_code(row.get("code")) not in used
    ]
    leftovers.sort(key=_quant_key)
    selected.extend(leftovers[: max(0, limit - len(selected))])
    return selected[:limit]


def _asof_valuation_frame(frame: pd.DataFrame | None, *, as_of: date) -> pd.DataFrame:
    if frame is None or frame.empty or "date" not in frame.columns:
        return pd.DataFrame()
    local = frame.copy()
    local["date"] = pd.to_datetime(local["date"], errors="coerce").dt.date
    local["pe"] = pd.to_numeric(local.get("pe"), errors="coerce")
    local = local.dropna(subset=["date", "pe"])
    local = local[(local["date"] <= as_of) & (local["pe"] > 0)].copy()
    return local.sort_values("date").reset_index(drop=True)


def _asof_financial_frame(frame: pd.DataFrame | None, *, as_of: date) -> pd.DataFrame:
    if frame is None or frame.empty or "report_date" not in frame.columns:
        return pd.DataFrame()
    local = frame.copy()
    local["report_date"] = pd.to_datetime(local["report_date"], errors="coerce").dt.date
    if "disclosure_date" in local.columns:
        disclosure = pd.to_datetime(local["disclosure_date"], errors="coerce").dt.date
        local["disclosure_date"] = disclosure
        local = local[
            local["report_date"].notna()
            & (local["report_date"] <= as_of)
            & (local["disclosure_date"].isna() | (local["disclosure_date"] <= as_of))
        ].copy()
    else:
        local = local[local["report_date"].notna() & (local["report_date"] <= as_of)].copy()
    return local.sort_values("report_date").reset_index(drop=True)


def build_relative_pe_diagnostic(
    source: Mapping[str, Any],
    valuation_df: pd.DataFrame | None,
    *,
    as_of: date,
    minimum_pe_samples: int = 20,
) -> dict[str, Any]:
    """Reverse-solve required profit growth using only same-unit PE ratios."""

    row = dict(source)
    row["code"] = normalize_code(row.get("code"))
    row["source_hard_blockers"] = row.get("hard_blockers") or ""
    row["formal_buy_eligible"] = False
    row["automatic_promotion_allowed"] = False
    row["disclaimer"] = DISCLAIMER

    valuation = _asof_valuation_frame(valuation_df, as_of=as_of)
    sample_count = len(valuation)
    row["historical_pe_sample_count"] = sample_count

    if sample_count < max(1, int(minimum_pe_samples)):
        row.update(
            {
                "current_pe": "",
                "historical_median_pe": "",
                "historical_pe_percentile": "",
                "implied_profit_multiple_of_current": "",
                "required_profit_growth": "",
                "required_profit_growth_pct": "",
                "valuation_diagnostic_status": "PE_HISTORY_INSUFFICIENT",
            }
        )
        return row

    current_pe = _finite(valuation.iloc[-1].get("pe"))
    median_pe = _finite(pd.to_numeric(valuation["pe"], errors="coerce").dropna().median())
    if current_pe is None or current_pe <= 0 or median_pe is None or median_pe <= 0:
        row["valuation_diagnostic_status"] = "PE_MODEL_NOT_APPLICABLE"
        return row

    pe_values = pd.to_numeric(valuation["pe"], errors="coerce").dropna()
    percentile = float((pe_values <= current_pe).sum() / len(pe_values))
    implied_profit_multiple = current_pe / median_pe
    required_growth = implied_profit_multiple - 1.0

    row.update(
        {
            "current_pe": round(current_pe, 4),
            "historical_median_pe": round(median_pe, 4),
            "historical_pe_percentile": round(percentile, 6),
            "implied_profit_multiple_of_current": round(implied_profit_multiple, 6),
            "required_profit_growth": round(required_growth, 6),
            "required_profit_growth_pct": round(required_growth * 100.0, 4),
            "valuation_diagnostic_status": "OK_RELATIVE_PE_EXPECTATION",
        }
    )
    return row


def add_financial_quality(
    row: Mapping[str, Any],
    financial_df: pd.DataFrame | None,
    *,
    as_of: date,
) -> dict[str, Any]:
    result = dict(row)
    financial = _asof_financial_frame(financial_df, as_of=as_of)
    if financial.empty:
        result["financial_review_status"] = "FINANCIAL_DATA_UNAVAILABLE"
        return result

    latest = financial.iloc[-1]
    net_profit = _finite(latest.get("net_profit"))
    operating_cash_flow = _finite(latest.get("operating_cash_flow"))
    earnings = normalize_core_earnings(
        net_profit=net_profit,
        operating_cash_flow=operating_cash_flow,
    )

    result.update(
        {
            "latest_net_profit": net_profit if net_profit is not None else "",
            "latest_operating_cash_flow": operating_cash_flow if operating_cash_flow is not None else "",
            "earnings_quality_score": earnings.earnings_quality_score,
            "earnings_quality_confidence": earnings.earnings_quality_confidence,
            "earnings_normalization_method": earnings.normalization_method,
            "financial_review_status": "OK",
        }
    )
    if (
        earnings.normalized_core_operating_profit is None
        or earnings.normalized_core_operating_profit <= 0
    ):
        result["valuation_diagnostic_status"] = "PE_MODEL_NOT_APPLICABLE"
    return result


def rank_valuation_research_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    def key(row: Mapping[str, Any]) -> tuple[int, float, float, float, str]:
        status = str(row.get("valuation_diagnostic_status") or "")
        applicable = 0 if status == "OK_RELATIVE_PE_EXPECTATION" else 1
        growth = _finite(row.get("required_profit_growth"))
        quality = _finite(row.get("earnings_quality_score"))
        quant = _finite(row.get("quant_score"))
        return (
            applicable,
            growth if growth is not None else float("inf"),
            -(quality if quality is not None else -1.0),
            -(quant if quant is not None else -1.0),
            normalize_code(row.get("code")),
        )

    ranked = [dict(row) for row in rows]
    ranked.sort(key=key)
    for index, row in enumerate(ranked, 1):
        row["valuation_research_rank"] = index
    return ranked


def _read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _find_latest_all_a_report(report_root: Path) -> Path:
    if (report_root / "all_a_quant_screen.csv").exists():
        return report_root
    candidates = sorted(
        path for path in report_root.glob("**/all_a_quant_screen.csv")
        if path.is_file()
    )
    if not candidates:
        raise FileNotFoundError(f"all_a_quant_screen.csv not found under {report_root}")
    return candidates[-1].parent


def _load_as_of(report_dir: Path) -> date:
    summary_path = report_dir / "run_summary.json"
    if not summary_path.exists():
        raise FileNotFoundError(f"missing run_summary.json in {report_dir}")
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    value = payload.get("as_of_date")
    if not value:
        raise ValueError("run_summary.json missing as_of_date")
    return date.fromisoformat(str(value))


def _fetch_fundamental(
    code: str,
    *,
    cache_dir: Path,
    years: int,
    valuation: bool,
    financial: bool,
):
    loader = PublicFundamentalLoader(cache_dir)
    return loader.load(
        code,
        years=years,
        fetch_valuation=valuation,
        fetch_financial=financial,
    )


def _parallel_fetch(
    codes: Iterable[str],
    *,
    cache_dir: Path,
    years: int,
    fetch_valuation: bool,
    fetch_financial: bool,
    max_workers: int,
) -> dict[str, Any]:
    normalized = list(dict.fromkeys(normalize_code(code) for code in codes if normalize_code(code)))
    results: dict[str, Any] = {}
    with ThreadPoolExecutor(max_workers=max(1, int(max_workers))) as executor:
        futures = {
            executor.submit(
                _fetch_fundamental,
                code,
                cache_dir=cache_dir,
                years=years,
                valuation=fetch_valuation,
                financial=fetch_financial,
            ): code
            for code in normalized
        }
        for future in as_completed(futures):
            code = futures[future]
            try:
                results[code] = future.result()
            except Exception as exc:  # fail-open research diagnostic
                results[code] = exc
    return results


def _write_outputs(
    rows: list[Mapping[str, Any]],
    *,
    output_dir: Path,
    as_of: date,
    summary: Mapping[str, Any],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "valuation_research_queue.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in OUTPUT_COLUMNS})

    lines = [
        "# Reverse-Valuation Research Queue",
        "",
        DISCLAIMER,
        "",
        f"- as_of_date: {as_of.isoformat()}",
        f"- selected_count: {summary.get('selected_count')}",
        f"- valid_reverse_pe_count: {summary.get('valid_reverse_pe_count')}",
        "- formal_buy_eligible: False for every row",
        "",
        "## Priority research",
        "",
    ]
    for row in rows[:30]:
        growth = _finite(row.get("required_profit_growth_pct"))
        growth_text = f"{growth:.2f}%" if growth is not None else "NA"
        lines.append(
            "- {rank}. {code} {name} / {industry} / required_profit_growth={growth} / "
            "PE={current}/{median} / earnings_quality={quality}/{confidence} / recall={reason}".format(
                rank=row.get("valuation_research_rank"),
                code=row.get("code"),
                name=row.get("stock_name") or "",
                industry=row.get("industry") or "",
                growth=growth_text,
                current=row.get("current_pe") or "NA",
                median=row.get("historical_median_pe") or "NA",
                quality=row.get("earnings_quality_score") or "NA",
                confidence=row.get("earnings_quality_confidence") or "NA",
                reason=row.get("wide_recall_reason") or "",
            )
        )
    if not rows:
        lines.append("- No research candidates with usable inputs.")
    (output_dir / "valuation_research_queue.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (output_dir / "valuation_research_summary.json").write_text(
        json.dumps(dict(summary), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def run_sidecar(
    *,
    report_root: Path,
    output_root: Path,
    cache_dir: Path,
    max_candidates: int = 80,
    relaxed_reserve: int = 20,
    financial_review_limit: int = 30,
    years: int = 5,
    minimum_pe_samples: int = 20,
    max_workers: int = 6,
) -> tuple[Path, dict[str, Any]]:
    report_dir = _find_latest_all_a_report(report_root)
    as_of = _load_as_of(report_dir)
    quant_rows = _read_csv(report_dir / "all_a_quant_screen.csv")
    selected = select_wide_recall_rows(
        quant_rows,
        max_candidates=max_candidates,
        relaxed_reserve=relaxed_reserve,
    )

    valuation_results = _parallel_fetch(
        [row.get("code") for row in selected],
        cache_dir=cache_dir,
        years=years,
        fetch_valuation=True,
        fetch_financial=False,
        max_workers=max_workers,
    )
    diagnostics: list[dict[str, Any]] = []
    fetch_failures = 0
    for source in selected:
        code = normalize_code(source.get("code"))
        fetched = valuation_results.get(code)
        if isinstance(fetched, Exception) or fetched is None:
            fetch_failures += 1
            valuation_df = None
        else:
            valuation_df = fetched.valuation_df
        diagnostics.append(
            build_relative_pe_diagnostic(
                source,
                valuation_df,
                as_of=as_of,
                minimum_pe_samples=minimum_pe_samples,
            )
        )

    provisional = rank_valuation_research_rows(diagnostics)
    financial_codes = [
        row["code"]
        for row in provisional
        if row.get("valuation_diagnostic_status") == "OK_RELATIVE_PE_EXPECTATION"
    ][: max(0, int(financial_review_limit))]
    financial_results = _parallel_fetch(
        financial_codes,
        cache_dir=cache_dir,
        years=years,
        fetch_valuation=False,
        fetch_financial=True,
        max_workers=max_workers,
    )

    final_rows: list[dict[str, Any]] = []
    financial_failures = 0
    financial_code_set = set(financial_codes)
    for row in provisional:
        code = normalize_code(row.get("code"))
        if code not in financial_code_set:
            local = dict(row)
            local["financial_review_status"] = "NOT_SELECTED_FOR_DEEP_FINANCIAL_REVIEW"
            final_rows.append(local)
            continue
        fetched = financial_results.get(code)
        if isinstance(fetched, Exception) or fetched is None:
            financial_failures += 1
            financial_df = None
        else:
            financial_df = fetched.financial_df
        final_rows.append(add_financial_quality(row, financial_df, as_of=as_of))

    final_rows = rank_valuation_research_rows(final_rows)
    output_dir = output_root / as_of.strftime("%Y%m%d")
    summary = {
        "as_of_date": as_of.isoformat(),
        "source_report_dir": str(report_dir),
        "selected_count": len(selected),
        "normal_research_count": sum(
            row.get("wide_recall_reason") == "NORMAL_RESEARCH_QUEUE" for row in selected
        ),
        "relaxed_recovery_count": sum(
            row.get("wide_recall_reason") != "NORMAL_RESEARCH_QUEUE" for row in selected
        ),
        "valid_reverse_pe_count": sum(
            row.get("valuation_diagnostic_status") == "OK_RELATIVE_PE_EXPECTATION"
            for row in final_rows
        ),
        "pe_model_not_applicable_count": sum(
            row.get("valuation_diagnostic_status") == "PE_MODEL_NOT_APPLICABLE"
            for row in final_rows
        ),
        "valuation_fetch_failure_count": fetch_failures,
        "financial_review_count": len(financial_codes),
        "financial_fetch_failure_count": financial_failures,
        "max_candidates": int(max_candidates),
        "relaxed_reserve": int(relaxed_reserve),
        "financial_review_limit": int(financial_review_limit),
        "historical_pe_years": int(years),
        "minimum_pe_samples": int(minimum_pe_samples),
        "formal_buy_eligible": False,
        "automatic_promotion_allowed": False,
        "no_auto_trade": True,
        "ranking_semantics": (
            "valid relative-PE diagnostics first; lower implied required profit growth first; "
            "then higher earnings quality and existing quant score"
        ),
        "disclaimer": DISCLAIMER,
    }
    _write_outputs(final_rows, output_dir=output_dir, as_of=as_of, summary=summary)
    return output_dir, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=Path("reports/valuation_research_queue"))
    parser.add_argument("--cache-dir", type=Path, default=Path("data/cache/valuation_research_fundamentals"))
    parser.add_argument("--max-candidates", type=int, default=80)
    parser.add_argument("--relaxed-reserve", type=int, default=20)
    parser.add_argument("--financial-review-limit", type=int, default=30)
    parser.add_argument("--years", type=int, default=5)
    parser.add_argument("--minimum-pe-samples", type=int, default=20)
    parser.add_argument("--max-workers", type=int, default=6)
    args = parser.parse_args(argv)

    output_dir, summary = run_sidecar(
        report_root=args.report_root,
        output_root=args.output_root,
        cache_dir=args.cache_dir,
        max_candidates=args.max_candidates,
        relaxed_reserve=args.relaxed_reserve,
        financial_review_limit=args.financial_review_limit,
        years=args.years,
        minimum_pe_samples=args.minimum_pe_samples,
        max_workers=args.max_workers,
    )
    print(
        "valuation_research_queue={};selected={};valid_reverse_pe={}".format(
            output_dir,
            summary["selected_count"],
            summary["valid_reverse_pe_count"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
