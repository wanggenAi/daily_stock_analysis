"""Build the final research-priority view across industry and valuation channels.

This module does not invent a new BUY score. Existing valuation research order
remains authoritative for research priority. Frozen V3.1 long-term Formal BUY is
overlaid as a separate decision dimension. Legacy TRY_POSITION rows may still be
visible for audit, but they are never actionable.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping

DISCLAIMER = "仅用于公开数据研究排序和人工复核，不构成买入或卖出建议，不应自动交易。"
ACTIONABLE_LONG_TERM = {"LONG_TERM_BUY_READY"}


def _read(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _code(value: Any) -> str:
    text = str(value or "").strip().upper()
    if "." in text:
        base, suffix = text.rsplit(".", 1)
        if suffix in {"SH", "SZ", "BJ"}:
            text = base
    for prefix in ("SH", "SZ", "BJ"):
        if text.startswith(prefix) and text[len(prefix):].isdigit():
            text = text[len(prefix):]
            break
    return text.zfill(6) if text.isdigit() else text


def _float(value: Any, default: float = -math.inf) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _int(value: Any, default: int = 10**9) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _bool(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def _latest_valuation(root: Path) -> Path:
    if (root / "valuation_research_routed.csv").exists():
        return root
    candidates = sorted(
        {p.parent for p in root.glob("**/valuation_research_routed.csv") if p.is_file()},
        key=str,
    )
    if not candidates:
        raise FileNotFoundError(f"no valuation_research_routed.csv under {root}")
    return candidates[-1]


def _overlay_missing(target: dict[str, Any], source: Mapping[str, Any], keys: Iterable[str]) -> None:
    for key in keys:
        if str(target.get(key) or "").strip():
            continue
        value = source.get(key)
        if str(value or "").strip():
            target[key] = value


def _formal_map(rows: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    return {_code(row.get("code")): dict(row) for row in rows if _code(row.get("code"))}


def build_master_rows(
    industry_rows: Iterable[Mapping[str, Any]],
    valuation_rows: Iterable[Mapping[str, Any]],
    formal_rows: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Return one auditable research row per code without creating a new buy score."""
    industry_list = [dict(row) for row in industry_rows if _code(row.get("code"))]
    valuation_list = [dict(row) for row in valuation_rows if _code(row.get("code"))]
    industry_by_code = {_code(row.get("code")): row for row in industry_list}
    formal_by_code = _formal_map(formal_rows)

    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    max_rank = 0

    valuation_list.sort(key=lambda row: (_int(row.get("valuation_research_rank")), _code(row.get("code"))))
    for raw in valuation_list:
        code = _code(raw.get("code"))
        if code in seen:
            continue
        row = dict(raw)
        row["code"] = code
        industry = industry_by_code.get(code, {})
        _overlay_missing(
            row,
            industry,
            (
                "industry",
                "stock_name",
                "industry_research_rank",
                "industry_candidate_state",
                "industry_status",
                "hard_blockers",
            ),
        )
        if industry:
            row["master_source"] = "VALUATION+INDUSTRY"
            row.setdefault("industry_research_rank", industry.get("industry_research_rank", ""))
            row.setdefault("industry_candidate_state", industry.get("industry_candidate_state", ""))
            row.setdefault("industry_status", industry.get("industry_status", ""))
        else:
            row["master_source"] = "VALUATION"

        formal = formal_by_code.get(code, {})
        _apply_formal_overlay(row, formal)
        rank = _int(raw.get("valuation_research_rank"), len(result) + 1)
        max_rank = max(max_rank, rank)
        row["master_research_rank"] = rank
        row["master_research_bucket"] = _bucket(row, has_valuation=True)
        _lock_research_only_policy(row)
        result.append(row)
        seen.add(code)

    remaining = [row for row in industry_list if _code(row.get("code")) not in seen]
    remaining.sort(
        key=lambda row: (
            -_float(row.get("quant_score")),
            str(row.get("industry") or ""),
            _int(row.get("industry_research_rank")),
            _code(row.get("code")),
        )
    )
    next_rank = max_rank + 1
    for raw in remaining:
        code = _code(raw.get("code"))
        row = dict(raw)
        row["code"] = code
        row["master_source"] = "INDUSTRY"
        formal = formal_by_code.get(code, {})
        _apply_formal_overlay(row, formal)
        row["master_research_rank"] = next_rank
        next_rank += 1
        row["master_research_bucket"] = _bucket(row, has_valuation=False)
        _lock_research_only_policy(row)
        result.append(row)
        seen.add(code)
    return result


def _apply_formal_overlay(target: dict[str, Any], formal: Mapping[str, Any]) -> None:
    for key in (
        "long_term_classification",
        "long_term_formal_buy_eligible",
        "long_term_blockers",
        "real_reward_risk_ratio",
        "current_price",
        "entry_low",
        "entry_high",
        "risk_invalidation_price",
        "target_1",
        "target_2",
        "current_action",
        "v31_policy_version",
        "v31_hard_gates_passed",
        "v31_candidate_class",
        "v31_score_total",
        "v31_buy_ready",
        "v31_blockers",
        "production_model_version",
        "production_model_name",
        "production_action",
        "production_target_position_fraction",
        "valuation_confidence",
        "valuation_confidence_reason_codes",
        "reason_codes",
        "normalized_earnings",
        "realistic_growth",
        "market_implied_growth",
        "expectation_gap",
        "neutral_value",
        "price_to_neutral",
    ):
        if key in formal:
            target[key] = formal.get(key)


def _bucket(row: Mapping[str, Any], *, has_valuation: bool) -> str:
    classification = str(row.get("long_term_classification") or "").strip()
    if classification == "LONG_TERM_TRY_POSITION":
        return "LONG_TERM_REVIEW_BLOCKED_LEGACY_TRY_POSITION"
    if classification:
        return classification
    if has_valuation:
        return "VALUATION_RESEARCHED"
    if str(row.get("industry_candidate_state") or "") == "RESEARCH_CANDIDATE":
        return "INDUSTRY_RESEARCH_ONLY"
    return "BLOCKED_INDUSTRY_RESEARCH_ONLY"


def _lock_research_only_policy(row: dict[str, Any]) -> None:
    row["formal_signal_eligible"] = False
    row["automatic_promotion_allowed"] = False
    row["no_auto_trade"] = True
    row["disclaimer"] = DISCLAIMER


def enrich_industry_rows(
    industry_rows: Iterable[Mapping[str, Any]],
    valuation_rows: Iterable[Mapping[str, Any]],
    formal_rows: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    valuation_by_code = {_code(row.get("code")): dict(row) for row in valuation_rows if _code(row.get("code"))}
    formal_by_code = _formal_map(formal_rows)
    result: list[dict[str, Any]] = []
    for raw in industry_rows:
        code = _code(raw.get("code"))
        if not code:
            continue
        row = dict(raw)
        row["code"] = code
        valuation = valuation_by_code.get(code, {})
        for key in (
            "valuation_research_rank",
            "valuation_source_channel",
            "current_pe",
            "historical_median_pe_reference",
            "required_profit_growth_pct",
            "cash_conversion_ratio",
            "earnings_quality_score",
            "earnings_quality_confidence",
            "financial_review_status",
            "valuation_diagnostic_status",
            "valuation_primary_strategy_id",
            "valuation_model_execution_state",
        ):
            if key in valuation:
                row[key] = valuation.get(key)
        _apply_formal_overlay(row, formal_by_code.get(code, {}))
        row["master_research_bucket"] = _bucket(row, has_valuation=bool(valuation))
        _lock_research_only_policy(row)
        result.append(row)
    result.sort(
        key=lambda row: (
            str(row.get("industry") or ""),
            _int(row.get("industry_research_rank")),
            _code(row.get("code")),
        )
    )
    return result


def actionable_long_term_rows(formal_rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in formal_rows:
        classification = str(raw.get("long_term_classification") or "")
        if classification not in ACTIONABLE_LONG_TERM or not _bool(raw.get("long_term_formal_buy_eligible")):
            continue
        row = dict(raw)
        row["code"] = _code(row.get("code"))
        _lock_research_only_policy(row)
        rows.append(row)
    rows.sort(
        key=lambda row: (
            -_float(row.get("v31_score_total"), -math.inf),
            -_float(row.get("real_reward_risk_ratio"), -math.inf),
            _code(row.get("code")),
        )
    )
    return rows


def _write_csv(path: Path, rows: list[dict[str, Any]], preferred: list[str]) -> None:
    fields = list(preferred)
    extra = sorted({key for row in rows for key in row if key not in fields})
    fields.extend(extra)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_reports(
    industry_coverage: Path,
    valuation_root: Path,
    long_term_formal_buy: Path,
    output_dir: Path,
) -> dict[str, Any]:
    industry_rows = _read(industry_coverage / "industry_top_candidates.csv")
    valuation_dir = _latest_valuation(valuation_root)
    valuation_rows = _read(valuation_dir / "valuation_research_routed.csv")
    formal_rows = _read(long_term_formal_buy / "long_term_formal_buy_candidates.csv")
    if not industry_rows:
        raise FileNotFoundError("missing industry_top_candidates.csv")
    if not valuation_rows:
        raise FileNotFoundError("missing valuation_research_routed.csv")

    master = build_master_rows(industry_rows, valuation_rows, formal_rows)
    industry = enrich_industry_rows(industry_rows, valuation_rows, formal_rows)
    actionable = actionable_long_term_rows(formal_rows)
    output_dir.mkdir(parents=True, exist_ok=True)

    preferred = [
        "master_research_rank", "code", "stock_name", "industry",
        "master_research_bucket", "master_source", "valuation_research_rank",
        "industry_research_rank", "industry_candidate_state", "quant_status",
        "quant_rank", "quant_score", "source_hard_blockers", "hard_blockers",
        "valuation_source_channel", "valuation_model_execution_state",
        "valuation_primary_strategy_id", "financial_review_status",
        "valuation_diagnostic_status", "current_pe", "historical_median_pe_reference",
        "required_profit_growth_pct", "cash_conversion_ratio", "earnings_quality_score",
        "earnings_quality_confidence", "v31_candidate_class", "v31_score_total",
        "v31_hard_gates_passed", "v31_buy_ready", "long_term_classification",
        "long_term_formal_buy_eligible", "long_term_blockers", "real_reward_risk_ratio",
        "current_price", "entry_low", "entry_high", "risk_invalidation_price",
        "target_1", "target_2", "current_action", "formal_signal_eligible",
        "production_model_version", "production_action", "valuation_confidence", "reason_codes",
        "automatic_promotion_allowed", "no_auto_trade", "disclaimer",
    ]
    _write_csv(output_dir / "master_opportunity_ranking.csv", master, preferred)
    _write_csv(output_dir / "every_industry_top5_enriched.csv", industry, preferred)
    _write_csv(output_dir / "actionable_long_term_candidates.csv", actionable, preferred)

    clean_industries = {
        str(row.get("industry") or "")
        for row in industry
        if row.get("industry_candidate_state") == "RESEARCH_CANDIDATE"
    }
    summary = {
        "ranking_semantics": "research_priority_not_trade_score",
        "master_count": len(master),
        "industry_map_count": len(industry),
        "represented_industry_count": len({str(row.get('industry') or '') for row in industry}),
        "clean_industry_count": len(clean_industries),
        "valuation_researched_count": len(valuation_rows),
        "actionable_long_term_count": len(actionable),
        "buy_ready_count": sum(row.get("long_term_classification") == "LONG_TERM_BUY_READY" for row in actionable),
        "try_position_count": 0,
        "blocked_long_term_count": sum(
            row.get("long_term_classification") == "LONG_TERM_REVIEW_BLOCKED" for row in formal_rows
        ),
        "legacy_try_position_actionable": False,
        "ordering_rule": "existing valuation_research_rank first; remaining industry Top5 by quant_score; frozen V3.1 long-term BUY is an overlay, not a new research score",
        "formal_signal_eligible": False,
        "automatic_promotion_allowed": False,
        "no_auto_trade": True,
    }
    (output_dir / "master_opportunity_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    lines = [
        "# Master Opportunity Ranking",
        "",
        "Research priority only; this is not a trade score and never authorizes automatic trading.",
        "",
        f"- master names: {summary['master_count']}",
        f"- represented industries: {summary['represented_industry_count']}",
        f"- clean industries: {summary['clean_industry_count']}",
        f"- valuation researched: {summary['valuation_researched_count']}",
        f"- actionable frozen-V3.1 long-term review: {summary['actionable_long_term_count']}",
        "",
        "## Top research queue",
    ]
    for row in master[:30]:
        lines.append(
            f"- #{row['master_research_rank']} {row.get('code','')} {row.get('stock_name','')} | "
            f"{row.get('master_research_bucket','')} | quant={row.get('quant_score','')} | "
            f"required_growth={row.get('required_profit_growth_pct','')}%"
        )
    lines.extend(["", "## Actionable frozen-V3.1 long-term manual review"])
    if actionable:
        for row in actionable:
            lines.append(
                f"- {row.get('code','')} {row.get('stock_name','')} | {row.get('long_term_classification','')} | "
                f"entry={row.get('entry_low','')}–{row.get('entry_high','')} | "
                f"stop={row.get('risk_invalidation_price','')} | R/R={row.get('real_reward_risk_ratio','')}"
            )
    else:
        lines.append("- none")
    (output_dir / "master_opportunity_ranking.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--industry-coverage", type=Path, required=True)
    parser.add_argument("--valuation-root", type=Path, required=True)
    parser.add_argument("--long-term-formal-buy", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    summary = write_reports(
        args.industry_coverage,
        args.valuation_root,
        args.long_term_formal_buy,
        args.output_dir,
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
