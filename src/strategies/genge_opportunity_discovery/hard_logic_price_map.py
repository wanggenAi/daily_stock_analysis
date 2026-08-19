"""Hard-logic company pool + reverse-valuation price expectation map.

The decision model is intentionally narrow:

1. Company first: only company-level structural hard risks may block the company.
   Market regime, technical timing, entry geometry, R/R, position sizing and exit
   profile gates remain visible context but cannot veto company quality here.
2. Price second: reverse-solve how much profit growth today's price already
   requires relative to the stock's own strictly-prior historical PE reference.
3. If an explicit hard-logic-supported profit-growth range exists, compare it
   directly with the market-implied requirement. Missing growth support is never
   invented.
4. Keep every qualifying company independently. Ranking is only for reading
   convenience; the market is never collapsed to one global winner.

Outputs are research-only and never authorize automatic trading.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping


DISCLAIMER = "仅用于公开数据研究和估值判断，不构成买入或卖出建议，不应自动交易。"

NON_COMPANY_GATE_TOKENS = frozenset(
    {
        "price_too_high",
        "board_5d_abnormal_move",
        "board_10d_abnormal_move",
        "ma20_not_ready",
        "ma60_not_ready",
        "price_above_ma20_limit",
        "price_above_ma60_limit",
        "too_far_from_ma20",
        "too_far_from_ma60",
        "reward_risk_below_min",
        "rr_below_min",
        "entry_not_ready",
        "market_regime_not_ready",
    }
)
NON_COMPANY_GATE_PREFIXES = (
    "exit_profile_",
    "profile_validation_",
    "profile_data_",
    "technical_",
    "timing_",
    "ma5_",
    "ma10_",
    "ma20_",
    "ma60_",
    "market_",
    "industry_timing_",
    "entry_",
    "breakout_",
    "pullback_",
    "stop_",
    "invalidation_",
    "reward_risk_",
    "risk_reward_",
    "rr_",
    "position_",
    "sizing_",
    "execution_",
    "liquidity_timing_",
    "volume_timing_",
)

COMPANY_BLOCKER_FIELDS = (
    "hard_blockers",
    "source_hard_blockers",
    "hard_reject_blockers",
)
NON_VETO_CONTEXT_FIELDS = (
    "strict_gate_failed",
    "missing_conditions",
    "classification_missing_conditions",
)

SUPPORTED_GROWTH_FIELDS = {
    "low": (
        "hard_logic_supported_profit_growth_low_pct",
        "supported_profit_growth_low_pct",
        "profit_growth_support_low_pct",
    ),
    "base": (
        "hard_logic_supported_profit_growth_base_pct",
        "supported_profit_growth_base_pct",
        "profit_growth_support_base_pct",
    ),
    "high": (
        "hard_logic_supported_profit_growth_high_pct",
        "supported_profit_growth_high_pct",
        "profit_growth_support_high_pct",
    ),
}

ACTION_PRIORITY = {
    "BUY_DEEP_VALUE": 0,
    "BUYABLE": 1,
    "BUYABLE_WITH_SUPPORTED_GROWTH": 2,
    "WAIT_FOR_BETTER_PRICE": 3,
    "EXPECTATIONS_HIGH_WAIT": 4,
    "NEED_HARD_LOGIC_GROWTH_SUPPORT": 5,
    "VALUATION_REFERENCE_UNAVAILABLE": 6,
    "HARD_LOGIC_REVIEW": 7,
    "HARD_LOGIC_BLOCKED": 8,
}

OUTPUT_COLUMNS = [
    "price_map_rank",
    "code",
    "stock_name",
    "industry",
    "hard_logic_state",
    "hard_logic_reasons",
    "structural_blockers",
    "non_veto_context",
    "current_price",
    "current_pe",
    "historical_median_pe_reference",
    "historical_pe_percentile",
    "required_profit_growth_pct",
    "supported_profit_growth_low_pct",
    "supported_profit_growth_base_pct",
    "supported_profit_growth_high_pct",
    "expectation_headroom_pct",
    "buyable_price_ceiling",
    "deep_value_price_ceiling",
    "historical_reference_price",
    "price_if_market_requires_minus20pct_growth",
    "price_if_market_requires_minus10pct_growth",
    "price_if_market_requires_zero_growth",
    "price_if_market_requires_plus10pct_growth",
    "price_if_market_requires_plus20pct_growth",
    "supported_fair_price_low",
    "supported_fair_price_base",
    "supported_fair_price_high",
    "price_decision",
    "decision_basis",
    "technical_context_is_non_veto",
    "formal_signal_eligible",
    "automatic_promotion_allowed",
    "no_auto_trade",
    "disclaimer",
]


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


def _split_tokens(value: Any) -> set[str]:
    return {token.strip() for token in str(value or "").split(";") if token.strip()}


def _is_non_company_gate(token: str) -> bool:
    return token in NON_COMPANY_GATE_TOKENS or token.startswith(NON_COMPANY_GATE_PREFIXES)


def _blocker_partition(row: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    """Separate company hard risks from execution/timing context."""
    structural: set[str] = set()
    context: set[str] = set()

    for key in COMPANY_BLOCKER_FIELDS:
        for token in _split_tokens(row.get(key)):
            if _is_non_company_gate(token):
                context.add(token)
            else:
                structural.add(token)

    for key in NON_VETO_CONTEXT_FIELDS:
        context.update(_split_tokens(row.get(key)))

    return sorted(structural), sorted(context)


def _first_finite(row: Mapping[str, Any], names: Iterable[str]) -> float | None:
    for name in names:
        value = _finite(row.get(name))
        if value is not None:
            return value
    return None


def _current_price(row: Mapping[str, Any]) -> float | None:
    return _first_finite(row, ("current_price", "price", "latest_price", "close", "last_price"))


def _supported_growth_ratio(row: Mapping[str, Any], band: str) -> float | None:
    for field in SUPPORTED_GROWTH_FIELDS[band]:
        value = _finite(row.get(field))
        if value is not None:
            return value / 100.0
    return None


def _explicit_hard_logic_state(row: Mapping[str, Any]) -> str:
    return str(row.get("hard_logic_state") or row.get("hard_logic_status") or "").strip().upper()


def hard_logic_assessment(row: Mapping[str, Any]) -> tuple[str, list[str], list[str], list[str]]:
    """Return PASS/REVIEW/BLOCKED using company evidence, not trade timing."""
    structural, context = _blocker_partition(row)
    reasons: list[str] = []
    explicit = _explicit_hard_logic_state(row)

    if explicit in {"FAIL", "FAILED", "BLOCKED", "REJECT", "HARD_REJECT"}:
        structural = sorted(set(structural + [f"explicit_hard_logic_state={explicit}"]))
    if structural:
        return "BLOCKED", ["structural_hard_risk_present"], structural, context

    core_profit = _finite(row.get("normalized_core_operating_profit"))
    if core_profit is not None and core_profit <= 0:
        return (
            "BLOCKED",
            ["normalized_core_profit_non_positive"],
            ["normalized_core_profit_non_positive"],
            context,
        )

    if explicit in {"PASS", "PASSED", "STRONG", "CONFIRMED", "HARD_LOGIC_PASS"}:
        reasons.append("explicit_hard_logic_pass")
        if context:
            reasons.append("execution_context_ignored_for_company_quality")
        return "PASS", reasons, [], context

    second_pass = str(row.get("long_term_second_pass_status") or "").strip().upper()
    industry_state = str(row.get("industry_candidate_state") or "").strip().upper()
    valuation_status = str(row.get("valuation_diagnostic_status") or "").strip().upper()
    quality = _finite(row.get("earnings_quality_score"))

    if second_pass == "PASSED_ALL_NON_EXIT_PROFILE_HARD_GATES":
        reasons.append("passed_all_non_exit_profile_hard_gates")
        if context:
            reasons.append("execution_context_ignored_for_company_quality")
        return "PASS", reasons, [], context

    if industry_state == "RESEARCH_CANDIDATE":
        reasons.append("clean_industry_research_candidate")
        if valuation_status == "OK":
            reasons.append("reverse_valuation_ready")
        if quality is not None and quality >= 50:
            reasons.append("earnings_quality_not_weak")
        if valuation_status == "OK" and quality is not None and quality >= 50:
            if context:
                reasons.append("execution_context_ignored_for_company_quality")
            return "PASS", reasons, [], context
        reasons.append("hard_logic_confirmation_incomplete")
        return "REVIEW", reasons, [], context

    if valuation_status == "OK":
        return (
            "REVIEW",
            ["valuation_ready_but_hard_logic_evidence_incomplete"],
            [],
            context,
        )

    return "REVIEW", ["hard_logic_evidence_incomplete"], [], context


def _required_growth_ratio(row: Mapping[str, Any]) -> float | None:
    pct = _finite(row.get("required_profit_growth_pct"))
    if pct is not None:
        return pct / 100.0
    ratio = _finite(row.get("required_profit_growth_vs_reference"))
    if ratio is not None:
        return ratio
    current_pe = _finite(row.get("current_pe"))
    reference_pe = _finite(row.get("historical_median_pe_reference"))
    if current_pe is not None and current_pe > 0 and reference_pe is not None and reference_pe > 0:
        return current_pe / reference_pe - 1.0
    return None


def _price_for_required_growth(
    current_price: float | None,
    current_required: float | None,
    target_required: float,
) -> float | None:
    if current_price is None or current_price <= 0 or current_required is None or current_required <= -1:
        return None
    price = current_price * (1.0 + target_required) / (1.0 + current_required)
    return round(price, 4) if math.isfinite(price) and price > 0 else None


def _valuation_price_thresholds(
    current_price: float | None,
    required_growth: float | None,
    supported_base: float | None,
) -> tuple[float | None, float | None]:
    """Return (buyable ceiling, deep-value ceiling).

    With supported business growth, preserve at least 15pp expectation headroom
    for BUYABLE and 30pp for DEEP_VALUE. Without supported growth, use the
    deliberately conservative zero-growth and -20%-growth reference thresholds.
    """
    if supported_base is None:
        buyable_required = 0.0
        deep_required = -0.20
    else:
        buyable_required = supported_base - 0.15
        deep_required = supported_base - 0.30
    return (
        _price_for_required_growth(current_price, required_growth, buyable_required),
        _price_for_required_growth(current_price, required_growth, deep_required),
    )


def _decision(
    *,
    hard_logic_state: str,
    required_growth: float | None,
    supported_base: float | None,
) -> tuple[str, str, float | None]:
    if hard_logic_state == "BLOCKED":
        return "HARD_LOGIC_BLOCKED", "structural company risk blocks valuation entry", None
    if hard_logic_state != "PASS":
        return "HARD_LOGIC_REVIEW", "company hard-logic evidence is not yet strong enough", None
    if required_growth is None:
        return (
            "VALUATION_REFERENCE_UNAVAILABLE",
            "cannot reverse-solve market expectations from available valuation history",
            None,
        )

    if supported_base is not None:
        headroom = supported_base - required_growth
        if headroom >= 0.30:
            return (
                "BUY_DEEP_VALUE",
                "market-implied growth is at least 30pp below hard-logic-supported base growth",
                headroom,
            )
        if headroom >= 0.15:
            return (
                "BUYABLE_WITH_SUPPORTED_GROWTH",
                "market-implied growth is at least 15pp below hard-logic-supported base growth",
                headroom,
            )
        if headroom >= 0:
            return (
                "WAIT_FOR_BETTER_PRICE",
                "hard logic can support current expectations but valuation headroom is thin",
                headroom,
            )
        return (
            "EXPECTATIONS_HIGH_WAIT",
            "current price requires more growth than the hard logic currently supports",
            headroom,
        )

    if required_growth <= -0.20:
        return (
            "BUY_DEEP_VALUE",
            "current price implies at least 20% profit contraction at the historical reference multiple",
            None,
        )
    if required_growth <= 0:
        return (
            "BUYABLE",
            "current price does not require profit growth at the historical reference multiple",
            None,
        )
    return (
        "NEED_HARD_LOGIC_GROWTH_SUPPORT",
        "current price requires profit growth; compare with explicit hard-logic-supported growth before buying",
        None,
    )


def build_price_expectation_row(row: Mapping[str, Any]) -> dict[str, Any]:
    hard_state, reasons, structural, context = hard_logic_assessment(row)
    current_price = _current_price(row)
    current_pe = _finite(row.get("current_pe"))
    reference_pe = _finite(row.get("historical_median_pe_reference"))
    percentile = _finite(row.get("historical_pe_percentile"))
    required = _required_growth_ratio(row)
    supported_low = _supported_growth_ratio(row, "low")
    supported_base = _supported_growth_ratio(row, "base")
    supported_high = _supported_growth_ratio(row, "high")

    decision, basis, headroom = _decision(
        hard_logic_state=hard_state,
        required_growth=required,
        supported_base=supported_base,
    )
    buyable_ceiling, deep_ceiling = _valuation_price_thresholds(
        current_price,
        required,
        supported_base,
    )

    def supported_price(growth: float | None) -> float | None:
        if growth is None:
            return None
        return _price_for_required_growth(current_price, required, growth)

    return {
        "price_map_rank": 0,
        "code": _normalize_code(row.get("code")),
        "stock_name": row.get("stock_name") or row.get("name") or "",
        "industry": row.get("industry") or row.get("normalized_industry") or row.get("raw_industry") or "",
        "hard_logic_state": hard_state,
        "hard_logic_reasons": ";".join(reasons),
        "structural_blockers": ";".join(structural),
        "non_veto_context": ";".join(context),
        "current_price": current_price,
        "current_pe": current_pe,
        "historical_median_pe_reference": reference_pe,
        "historical_pe_percentile": percentile,
        "required_profit_growth_pct": round(required * 100.0, 4) if required is not None else None,
        "supported_profit_growth_low_pct": round(supported_low * 100.0, 4) if supported_low is not None else None,
        "supported_profit_growth_base_pct": round(supported_base * 100.0, 4) if supported_base is not None else None,
        "supported_profit_growth_high_pct": round(supported_high * 100.0, 4) if supported_high is not None else None,
        "expectation_headroom_pct": round(headroom * 100.0, 4) if headroom is not None else None,
        "buyable_price_ceiling": buyable_ceiling,
        "deep_value_price_ceiling": deep_ceiling,
        "historical_reference_price": _price_for_required_growth(current_price, required, 0.0),
        "price_if_market_requires_minus20pct_growth": _price_for_required_growth(current_price, required, -0.20),
        "price_if_market_requires_minus10pct_growth": _price_for_required_growth(current_price, required, -0.10),
        "price_if_market_requires_zero_growth": _price_for_required_growth(current_price, required, 0.0),
        "price_if_market_requires_plus10pct_growth": _price_for_required_growth(current_price, required, 0.10),
        "price_if_market_requires_plus20pct_growth": _price_for_required_growth(current_price, required, 0.20),
        "supported_fair_price_low": supported_price(supported_low),
        "supported_fair_price_base": supported_price(supported_base),
        "supported_fair_price_high": supported_price(supported_high),
        "price_decision": decision,
        "decision_basis": basis,
        "technical_context_is_non_veto": True,
        "formal_signal_eligible": False,
        "automatic_promotion_allowed": False,
        "no_auto_trade": True,
        "disclaimer": DISCLAIMER,
    }


def _rank_key(row: Mapping[str, Any]) -> tuple[int, int, float, str]:
    hard_rank = {"PASS": 0, "REVIEW": 1, "BLOCKED": 2}.get(str(row.get("hard_logic_state")), 3)
    action_rank = ACTION_PRIORITY.get(str(row.get("price_decision")), 99)
    required = _finite(row.get("required_profit_growth_pct"))
    return (hard_rank, action_rank, required if required is not None else math.inf, str(row.get("code") or ""))


def build_price_expectation_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Evaluate every supplied company independently; never truncate to Top-1."""
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in rows:
        code = _normalize_code(raw.get("code"))
        if not code or code in seen:
            continue
        local = dict(raw)
        local["code"] = code
        output.append(build_price_expectation_row(local))
        seen.add(code)
    output.sort(key=_rank_key)
    for rank, row in enumerate(output, 1):
        row["price_map_rank"] = rank
    return output


def _read_csv(path: Path | None) -> list[dict[str, Any]]:
    if path is None or not path.exists():
        return []
    with path.open(encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _choose_path(root: Path, filename: str, preferred_token: str = "") -> Path | None:
    candidates = sorted((p for p in root.glob(f"**/{filename}") if p.is_file()), key=str)
    if not candidates:
        return None
    if preferred_token:
        preferred = [p for p in candidates if preferred_token in str(p)]
        if preferred:
            return preferred[-1]
    return candidates[-1]


def load_artifact_company_rows(artifact_root: Path) -> list[dict[str, Any]]:
    """Merge Postscan research channels into one row per researched company."""
    raw_path = _choose_path(artifact_root, "all_a_quant_screen.csv", "final_valuation_source")
    industry_path = _choose_path(artifact_root, "industry_top_candidates.csv")
    valuation_path = _choose_path(artifact_root, "valuation_research_routed.csv")
    master_path = _choose_path(artifact_root, "master_opportunity_ranking.csv")
    second_pass_path = _choose_path(artifact_root, "long_term_second_pass_candidates.csv")

    raw_by_code = {
        _normalize_code(row.get("code")): row
        for row in _read_csv(raw_path)
        if _normalize_code(row.get("code"))
    }
    channels = [
        _read_csv(industry_path),
        _read_csv(valuation_path),
        _read_csv(master_path),
        _read_csv(second_pass_path),
    ]

    candidate_codes: set[str] = set()
    for channel in channels:
        candidate_codes.update(
            _normalize_code(row.get("code"))
            for row in channel
            if _normalize_code(row.get("code"))
        )

    merged: dict[str, dict[str, Any]] = {
        code: dict(raw_by_code.get(code, {})) for code in candidate_codes
    }
    for channel in channels:
        for row in channel:
            code = _normalize_code(row.get("code"))
            if not code or code not in candidate_codes:
                continue
            merged.setdefault(code, {})
            merged[code].update(row)
            merged[code]["code"] = code
    return list(merged.values())


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=OUTPUT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_price_map(artifact_root: Path, output_dir: Path) -> list[dict[str, Any]]:
    rows = build_price_expectation_rows(load_artifact_company_rows(artifact_root))
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "hard_logic_price_map.csv", rows)

    summary = {
        "candidate_count": len(rows),
        "hard_logic_pass_count": sum(row["hard_logic_state"] == "PASS" for row in rows),
        "buy_deep_value_count": sum(row["price_decision"] == "BUY_DEEP_VALUE" for row in rows),
        "buyable_count": sum(
            row["price_decision"] in {"BUYABLE", "BUYABLE_WITH_SUPPORTED_GROWTH"}
            for row in rows
        ),
        "wait_count": sum(
            row["price_decision"]
            in {
                "WAIT_FOR_BETTER_PRICE",
                "EXPECTATIONS_HIGH_WAIT",
                "NEED_HARD_LOGIC_GROWTH_SUPPORT",
            }
            for row in rows
        ),
        "semantics": "company hard logic first; reverse valuation decides whether current price already embeds too much expectation",
        "global_top1_required": False,
        "technical_context_is_non_veto": True,
        "formal_signal_eligible": False,
        "automatic_promotion_allowed": False,
        "no_auto_trade": True,
    }
    (output_dir / "hard_logic_price_map_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines = [
        "# Hard Logic × Price Expectation Map",
        "",
        "Company hard logic is judged first. Market/technical/execution context is visible but non-veto here. Reverse valuation then judges today's price.",
        "",
        f"- hard-logic pass: {summary['hard_logic_pass_count']}/{summary['candidate_count']}",
        f"- deep-value: {summary['buy_deep_value_count']}",
        f"- buyable: {summary['buyable_count']}",
        f"- wait / need growth support: {summary['wait_count']}",
        "",
        "## Current price decisions",
    ]
    for row in rows:
        if row["hard_logic_state"] != "PASS":
            continue
        lines.append(
            f"- #{row['price_map_rank']} {row.get('code','')} {row.get('stock_name','')} | "
            f"{row.get('price_decision','')} | price={row.get('current_price','')} | "
            f"required_growth={row.get('required_profit_growth_pct','')}% | "
            f"buyable<={row.get('buyable_price_ceiling','')} | "
            f"deep_value<={row.get('deep_value_price_ceiling','')} | "
            f"supported_base_value={row.get('supported_fair_price_base','')}"
        )
    (output_dir / "hard_logic_price_map.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    rows = write_price_map(args.artifact_root, args.output_dir)
    print(f"hard_logic_price_map={args.output_dir};count={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
