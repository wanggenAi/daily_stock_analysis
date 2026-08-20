"""Sector-prioritized structural hard-logic research.

This adapter keeps the existing evidence-first hard-logic engine intact while
changing the *research order* from alphabetical industry order to the current
All-A sector-opportunity map.  Sector momentum/breadth is supplied to the LLM as
DISCOVERY CONTEXT ONLY and is explicitly forbidden from proving hard logic.

Every represented industry is still researched unless ``max_industries`` is
explicitly set.  A hot industry may therefore receive attention earlier, but it
must independently prove a 3-5+ year structural driver and company-specific edge
before HARD_LOGIC_PASS.  Conversely, a currently weak sector remains visible and
can still pass structural research if its long-run thesis is real.
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable, Mapping

from .hard_logic_research_runner import (
    OUTPUT_COLUMNS as BASE_OUTPUT_COLUMNS,
    RESEARCH_TOOL_NAMES,
    ResearchExecution,
    _candidate_prompt,
    _extract_json,
    _filtered_research_registry,
    _normalize_code,
    group_industry_seeds,
    normalize_research_payload,
)

logger = logging.getLogger(__name__)

SECTOR_CONTEXT_COLUMNS = [
    "sector_rank",
    "sector_opportunity_state",
    "sector_research_action",
    "sector_opportunity_score",
    "sector_advance_ratio",
    "sector_excess_return_1d_pct",
    "sector_excess_return_5d_pct",
    "sector_expanding_activity_ratio",
    "sector_overheated",
]
OUTPUT_COLUMNS = list(BASE_OUTPUT_COLUMNS) + [
    field for field in SECTOR_CONTEXT_COLUMNS if field not in BASE_OUTPUT_COLUMNS
]


def _read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def load_sector_context(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None or not path.exists():
        return {}
    output: dict[str, dict[str, Any]] = {}
    for row in _read_csv(path):
        industry = str(row.get("industry") or "").strip()
        if industry:
            output[industry] = row
    return output


def _rank_number(value: Any, default: float = 1e12) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def order_industries(
    industries: list[str],
    sector_context: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    """Priority sectors first, with deterministic alphabetical fallback."""
    return sorted(
        industries,
        key=lambda industry: (
            _rank_number((sector_context.get(industry) or {}).get("sector_rank")),
            industry,
        ),
    )


def _sector_context_text(industry: str, sector: Mapping[str, Any] | None) -> str:
    if not sector:
        return (
            "\nSECTOR DISCOVERY CONTEXT: unavailable. Do not infer structural hard logic "
            "from missing market-strength data.\n"
        )
    return f"""

SECTOR DISCOVERY CONTEXT (MARKET SNAPSHOT ONLY; NOT FUNDAMENTAL EVIDENCE):
- sector opportunity state: {sector.get('sector_opportunity_state', '')}
- sector opportunity score: {sector.get('sector_opportunity_score', '')}
- breadth / advance ratio: {sector.get('advance_ratio', '')}
- 1d excess return vs All-A median: {sector.get('excess_return_1d_pct', '')}%
- 5d excess return vs All-A median: {sector.get('excess_return_5d_pct', '')}%
- expanding-activity ratio: {sector.get('expanding_activity_ratio', '')}
- overheated flag: {sector.get('sector_overheated', '')}

IMPORTANT: The snapshot above exists only to explain why **{industry}** is being
researched now and to help identify whether the market may be repricing it. It
is NOT evidence of a 3-5 year structural thesis. Price rises, breadth, volume,
relative strength, limit-ups, or an EMERGING/LEADING label can NEVER substitute
for filings, industry data, durable company edge, or profit transmission. If
primary/credible evidence does not support the structural thesis, return NO_PASS
or REVIEW even when the sector is the strongest market sector today.
"""


def _production_sector_research_call(
    industry: str,
    seeds: list[Mapping[str, Any]],
    sector: Mapping[str, Any] | None,
    *,
    timeout_seconds: float,
) -> ResearchExecution:
    from src.agent.llm_adapter import LLMToolAdapter
    from src.agent.runner import run_agent_loop
    from src.config import get_config

    config = get_config()
    adapter = LLMToolAdapter(config)
    if not adapter.is_available:
        raise RuntimeError("LLM research adapter is not configured")

    user_prompt = _candidate_prompt(industry, seeds) + _sector_context_text(industry, sector)
    messages = [
        {
            "role": "system",
            "content": (
                "You are an evidence-first A-share INDUSTRY researcher. The current sector market snapshot "
                "may prioritize what you inspect, but it is never proof of structural hard logic. "
                "You MUST use research tools before any PASS. Never infer hard logic from sector return, "
                "breadth, volume, PE, price, technical signals, Quant rank, or broker target prices. "
                "Every source in the final JSON must come from tool outputs in this run. "
                "Your final response must be the exact JSON object requested by the user prompt."
            ),
        },
        {"role": "user", "content": user_prompt},
    ]
    result = run_agent_loop(
        messages=messages,
        tool_registry=_filtered_research_registry(),
        llm_adapter=adapter,
        max_steps=7,
        max_wall_clock_seconds=timeout_seconds,
        tool_call_timeout_seconds=max(10.0, timeout_seconds / 2.0),
    )
    if not result.success:
        raise RuntimeError(result.error or "industry research failed")

    successful_research_calls = sum(
        bool(item.get("success")) and item.get("tool") in RESEARCH_TOOL_NAMES
        for item in result.tool_calls_log
    )
    tool_context = "\n".join(
        str(message.get("content") or "")
        for message in result.messages
        if message.get("role") == "tool"
        and message.get("name") in RESEARCH_TOOL_NAMES
    )
    return ResearchExecution(
        content=result.content,
        tool_context=tool_context,
        successful_tool_calls=successful_research_calls,
    )


def _sector_fields(sector: Mapping[str, Any] | None) -> dict[str, Any]:
    sector = sector or {}
    return {
        "sector_rank": sector.get("sector_rank", ""),
        "sector_opportunity_state": sector.get("sector_opportunity_state", ""),
        "sector_research_action": sector.get("sector_research_action", ""),
        "sector_opportunity_score": sector.get("sector_opportunity_score", ""),
        "sector_advance_ratio": sector.get("advance_ratio", ""),
        "sector_excess_return_1d_pct": sector.get("excess_return_1d_pct", ""),
        "sector_excess_return_5d_pct": sector.get("excess_return_5d_pct", ""),
        "sector_expanding_activity_ratio": sector.get("expanding_activity_ratio", ""),
        "sector_overheated": sector.get("sector_overheated", ""),
    }


def research_one_industry(
    industry: str,
    seeds: list[Mapping[str, Any]],
    *,
    sector: Mapping[str, Any] | None,
    raw_universe_codes: set[str] | None,
    timeout_seconds: float,
    research_call: Callable[[str, list[Mapping[str, Any]]], str | ResearchExecution] | None,
) -> dict[str, Any]:
    try:
        if research_call is None:
            execution = _production_sector_research_call(
                industry,
                seeds,
                sector,
                timeout_seconds=timeout_seconds,
            )
            require_tool_evidence = True
        else:
            response = research_call(industry, seeds)
            execution = (
                response
                if isinstance(response, ResearchExecution)
                else ResearchExecution(str(response), "", 0)
            )
            require_tool_evidence = isinstance(response, ResearchExecution)

        payload = _extract_json(execution.content)
        row = normalize_research_payload(
            industry,
            seeds,
            payload,
            raw_universe_codes=raw_universe_codes,
            research_tool_context=execution.tool_context,
            successful_tool_calls=execution.successful_tool_calls,
            require_tool_evidence=require_tool_evidence,
        )
    except Exception as exc:
        logger.exception("sector-first hard-logic research failed for %s", industry)
        row = {
            "industry": industry,
            "research_state": "REVIEW",
            "selected_code": "",
            "selected_name": "",
            "selection_origin": "",
            "hard_logic_state": "REVIEW",
            "hard_logic_score": 0,
            "hard_logic_missing_evidence": "research_failed",
            "hard_logic_structural_driver": "",
            "hard_logic_supply_constraint": "",
            "hard_logic_company_edge": "",
            "hard_logic_profit_transmission": "",
            "hard_logic_invalidation": "",
            "hard_logic_duration_years": "",
            "hard_logic_persistence": "",
            "hard_logic_evidence_sources": "",
            "evidence_tool_call_count": 0,
            "evidence_source_verified": False,
            "evidence_verification_matches": "",
            "research_summary": "",
            "seed_codes": ";".join(_normalize_code(item.get("code")) for item in seeds),
            "seed_names": ";".join(str(item.get("stock_name") or "") for item in seeds),
            "research_error": str(exc),
            "formal_signal_eligible": False,
            "automatic_promotion_allowed": False,
            "no_auto_trade": True,
        }
    row.update(_sector_fields(sector))
    return row


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=OUTPUT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def run_sector_first_research(
    *,
    industry_candidates_csv: Path,
    sector_opportunity_csv: Path,
    output_dir: Path,
    all_a_universe_csv: Path | None = None,
    per_industry_limit: int = 5,
    max_workers: int = 3,
    timeout_seconds: float = 90.0,
    max_industries: int = 0,
    research_call: Callable[[str, list[Mapping[str, Any]]], str | ResearchExecution] | None = None,
) -> list[dict[str, Any]]:
    seeds = group_industry_seeds(
        _read_csv(industry_candidates_csv),
        per_industry_limit=per_industry_limit,
    )
    sector_context = load_sector_context(sector_opportunity_csv)
    industries = order_industries(list(seeds), sector_context)
    if max_industries > 0:
        industries = industries[:max_industries]

    raw_codes: set[str] | None = None
    if all_a_universe_csv is not None and all_a_universe_csv.exists():
        raw_codes = {
            _normalize_code(row.get("code") or row.get("代码"))
            for row in _read_csv(all_a_universe_csv)
            if _normalize_code(row.get("code") or row.get("代码"))
        }

    results: dict[str, dict[str, Any]] = {}
    workers = max(1, int(max_workers))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                research_one_industry,
                industry,
                seeds[industry],
                sector=sector_context.get(industry),
                raw_universe_codes=raw_codes,
                timeout_seconds=timeout_seconds,
                research_call=research_call,
            ): industry
            for industry in industries
        }
        for future in as_completed(futures):
            industry = futures[future]
            try:
                results[industry] = future.result()
            except Exception as exc:  # pragma: no cover - worker function fail-closes
                results[industry] = {
                    "industry": industry,
                    "research_state": "REVIEW",
                    "hard_logic_state": "REVIEW",
                    "research_error": str(exc),
                    "formal_signal_eligible": False,
                    "automatic_promotion_allowed": False,
                    "no_auto_trade": True,
                    **_sector_fields(sector_context.get(industry)),
                }

    # Preserve sector-priority order in the artifact even though workers execute concurrently.
    rows = [results[industry] for industry in industries]
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "hard_logic_research.csv", rows)

    state_counts: dict[str, int] = {}
    for sector in sector_context.values():
        state = str(sector.get("sector_opportunity_state") or "UNKNOWN")
        state_counts[state] = state_counts.get(state, 0) + 1
    summary = {
        "industry_count": len(rows),
        "hard_logic_pass_count": sum(row.get("hard_logic_state") == "PASS" for row in rows),
        "no_pass_count": sum(row.get("research_state") == "NO_PASS" for row in rows),
        "review_count": sum(row.get("research_state") == "REVIEW" for row in rows),
        "external_nomination_count": sum(
            row.get("selection_origin") == "EXTERNAL_A_SHARE_NOMINATION" for row in rows
        ),
        "tool_verified_pass_count": sum(
            row.get("hard_logic_state") == "PASS" and bool(row.get("evidence_source_verified"))
            for row in rows
        ),
        "sector_opportunity_used": bool(sector_context),
        "sector_state_counts": dict(sorted(state_counts.items())),
        "research_order": [row["industry"] for row in rows],
        "industry_first_discovery": True,
        "sector_strength_is_hard_logic": False,
        "sector_strength_can_create_buy": False,
        "topn_seed_is_answer": False,
        "valuation_is_hard_logic": False,
        "quant_rank_is_hard_logic": False,
        "all_industries_force_stock": False,
        "production_pass_requires_research_tools": True,
        "production_pass_requires_tool_verified_source": True,
        "external_nomination_requires_all_a_membership": True,
        "formal_signal_eligible": False,
        "automatic_promotion_allowed": False,
        "no_auto_trade": True,
    }
    (output_dir / "hard_logic_research_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--industry-candidates-csv", type=Path, required=True)
    parser.add_argument("--sector-opportunity-csv", type=Path, required=True)
    parser.add_argument("--all-a-universe-csv", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--per-industry-limit", type=int, default=5)
    parser.add_argument("--max-workers", type=int, default=3)
    parser.add_argument("--timeout-seconds", type=float, default=90.0)
    parser.add_argument("--max-industries", type=int, default=0)
    args = parser.parse_args(argv)
    rows = run_sector_first_research(
        industry_candidates_csv=args.industry_candidates_csv,
        sector_opportunity_csv=args.sector_opportunity_csv,
        all_a_universe_csv=args.all_a_universe_csv,
        output_dir=args.output_dir,
        per_industry_limit=args.per_industry_limit,
        max_workers=args.max_workers,
        timeout_seconds=args.timeout_seconds,
        max_industries=args.max_industries,
    )
    print(f"sector_first_hard_logic_research={args.output_dir};industries={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
