"""Research one auditable structural thesis per industry before valuation.

The industry Top-N list is a *seed*, never the answer.  The research agent may:

* select one of the seed A-share companies;
* discover and nominate a stronger A-share outside the seed list; or
* conclude that no company currently has enough evidence for HARD_LOGIC_PASS.

The agent is explicitly forbidden to use Quant rank, price, PE, historical PE, or
technical shape as proof of a structural thesis.  Every selected company is
re-checked by :mod:`hard_logic_engine` before it can be labelled PASS.

Production additionally requires actual research-tool evidence.  A model-written
source reference must be traceable to the tool results from the same run; a PASS
with invented/unseen sources is downgraded to REVIEW.  External nominations are
accepted only when the selected six-digit code exists in the supplied raw All-A
universe.

Production output is research-only.  Missing/failed research becomes REVIEW,
never an invented thesis and never an automatic trade.
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from .hard_logic_engine import evaluate_hard_logic

logger = logging.getLogger(__name__)

RESEARCH_TOOL_NAMES = (
    "search_industry_web",
    "search_stock_news",
    "search_comprehensive_intel",
    "get_stock_info",
    "get_sector_rankings",
)

OUTPUT_COLUMNS = [
    "industry",
    "research_state",
    "selected_code",
    "selected_name",
    "selection_origin",
    "hard_logic_state",
    "hard_logic_score",
    "hard_logic_missing_evidence",
    "hard_logic_structural_driver",
    "hard_logic_supply_constraint",
    "hard_logic_company_edge",
    "hard_logic_profit_transmission",
    "hard_logic_invalidation",
    "hard_logic_duration_years",
    "hard_logic_persistence",
    "hard_logic_evidence_sources",
    "evidence_tool_call_count",
    "evidence_source_verified",
    "evidence_verification_matches",
    "research_summary",
    "seed_codes",
    "seed_names",
    "research_error",
    "formal_signal_eligible",
    "automatic_promotion_allowed",
    "no_auto_trade",
]


@dataclass(frozen=True)
class ResearchExecution:
    content: str
    tool_context: str
    successful_tool_calls: int


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


def _stock_name(row: Mapping[str, Any]) -> str:
    return str(row.get("stock_name") or row.get("name") or row.get("股票") or "").strip()


def _industry_name(row: Mapping[str, Any]) -> str:
    return str(row.get("industry") or row.get("normalized_industry") or row.get("行业") or "").strip()


def _rank_value(row: Mapping[str, Any]) -> tuple[float, str]:
    for field in ("industry_rank", "行业排名", "rank_in_industry", "master_rank", "Master排名"):
        try:
            return float(row.get(field)), _normalize_code(row.get("code") or row.get("代码"))
        except (TypeError, ValueError):
            continue
    return float("inf"), _normalize_code(row.get("code") or row.get("代码"))


def group_industry_seeds(
    rows: Iterable[Mapping[str, Any]],
    *,
    per_industry_limit: int = 5,
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for raw in rows:
        row = dict(raw)
        code = _normalize_code(row.get("code") or row.get("代码"))
        industry = _industry_name(row)
        if not code or not industry:
            continue
        row["code"] = code
        grouped.setdefault(industry, []).append(row)
    limit = max(1, int(per_industry_limit))
    for industry, industry_rows in grouped.items():
        industry_rows.sort(key=_rank_value)
        grouped[industry] = industry_rows[:limit]
    return grouped


def _source_items(value: Any) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    if isinstance(value, list):
        for item in value:
            if isinstance(item, Mapping):
                title = str(item.get("title") or item.get("name") or "").strip()
                url = str(item.get("url") or item.get("source") or "").strip()
                if title or url:
                    items.append((title, url))
            elif str(item or "").strip():
                items.append((str(item).strip(), ""))
        return items
    text = str(value or "").strip()
    if text:
        items.append((text, ""))
    return items


def _source_text(value: Any) -> str:
    return "; ".join(
        " | ".join(part for part in (title, url) if part)
        for title, url in _source_items(value)
        if title or url
    )


def _normalized_match_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).lower()


def _verify_sources_against_tool_context(
    sources: Any,
    tool_context: str,
) -> tuple[bool, list[str]]:
    haystack = _normalized_match_text(tool_context)
    if not haystack:
        return False, []
    matches: list[str] = []
    for title, url in _source_items(sources):
        normalized_url = _normalized_match_text(url)
        normalized_title = _normalized_match_text(title)
        if normalized_url and len(normalized_url) >= 8 and normalized_url in haystack:
            matches.append(url)
            continue
        if normalized_title and len(normalized_title) >= 8 and normalized_title in haystack:
            matches.append(title)
    return bool(matches), matches


def _append_error(existing: str, token: str) -> str:
    return f"{existing};{token}" if existing else token


def _extract_json(text: str) -> dict[str, Any]:
    raw = str(text or "").strip()
    if not raw:
        raise ValueError("empty research response")
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("research response does not contain a JSON object")
    parsed = json.loads(raw[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("research JSON must be an object")
    return parsed


def _candidate_prompt(industry: str, seeds: list[Mapping[str, Any]]) -> str:
    seed_text = "\n".join(
        f"- {_normalize_code(row.get('code'))} {_stock_name(row)}"
        for row in seeds
    )
    return f"""Research the A-share industry **{industry}** and determine whether there is a company with a genuine 3-5+ year structural hard logic.

Seed companies from the quantitative scan (SEEDS ONLY; do not assume any is good):
{seed_text}

Rules:
1. Start from the INDUSTRY, not from valuation. Explain the structural demand/industry driver that can persist for at least ~3 years. A one-quarter rebound, low PE, technical oversold condition, theme hype, or broker target price is NOT hard logic.
2. Use `search_industry_web` to discover the industry's structural drivers, bottlenecks and potentially stronger A-share companies beyond the seed list. Then use company-specific research tools to verify the selected company.
3. Explain why the selected COMPANY specifically captures that driver: resource/technology/license/customer certification/cost curve/network effect/brand/pricing power/scale or another durable edge that competitors cannot quickly copy.
4. Trace the economic transmission: industry change -> volume/price/mix/cost -> revenue/margin -> profit/cash flow. Do not merely quote an EPS growth forecast.
5. Define falsifiable invalidation conditions.
6. Use research tools and give source references that actually appear in those tool results. Prefer company filings, exchange disclosures, regulator/industry data, and other primary sources. Cross-check material claims.
7. Supply constraint/scarcity is valuable when real, but is not mandatory for every business model.
8. The seed list is NOT a closed universe. If a different A-share is materially stronger, nominate it with its six-digit code. If evidence is insufficient for every company, return NO_PASS rather than forcing a stock.
9. Ignore current share price, PE, historical PE, Quant score, Master rank, MA/technical shape, and buy/sell timing during this stage.

Return ONLY one JSON object, no Markdown, with exactly these keys:
{{
  "research_state": "PASS|NO_PASS|REVIEW",
  "selected_code": "six-digit A-share code or empty",
  "selected_name": "company name or empty",
  "hard_logic_structural_driver": "evidence-backed structural industry driver",
  "hard_logic_supply_constraint": "optional supply/scarcity constraint or empty",
  "hard_logic_company_edge": "why this company specifically",
  "hard_logic_profit_transmission": "industry -> business -> profit chain",
  "hard_logic_invalidation": "falsifiable thesis-break conditions",
  "hard_logic_duration_years": 0,
  "hard_logic_persistence": "why the driver persists",
  "hard_logic_evidence_sources": [{{"title":"source title","url":"source URL or source identifier from tool output"}}],
  "research_summary": "short conclusion"
}}
"""


def normalize_research_payload(
    industry: str,
    seeds: list[Mapping[str, Any]],
    payload: Mapping[str, Any],
    *,
    raw_universe_codes: set[str] | None = None,
    research_tool_context: str = "",
    successful_tool_calls: int = 0,
    require_tool_evidence: bool = False,
) -> dict[str, Any]:
    selected_code = _normalize_code(payload.get("selected_code"))
    selected_name = str(payload.get("selected_name") or "").strip()
    research_state = str(payload.get("research_state") or "REVIEW").strip().upper()
    seed_codes = [_normalize_code(row.get("code")) for row in seeds]
    seed_names = [_stock_name(row) for row in seeds]
    origin = ""
    error = ""

    if research_state not in {"PASS", "NO_PASS", "REVIEW"}:
        research_state = "REVIEW"
        error = "invalid_research_state"
    if research_state == "PASS" and not selected_code:
        research_state = "REVIEW"
        error = "pass_without_selected_code"
    if selected_code:
        if selected_code in seed_codes:
            origin = "SEED"
        elif raw_universe_codes is None:
            research_state = "REVIEW"
            error = _append_error(error, "external_nomination_unverifiable_without_all_a_universe")
            selected_code = ""
            selected_name = ""
            origin = "REJECTED_EXTERNAL_NOMINATION"
        elif selected_code in raw_universe_codes:
            origin = "EXTERNAL_A_SHARE_NOMINATION"
        else:
            research_state = "REVIEW"
            error = _append_error(error, "selected_code_not_found_in_all_a_universe")
            selected_code = ""
            selected_name = ""
            origin = "REJECTED_EXTERNAL_NOMINATION"

    source_verified, source_matches = _verify_sources_against_tool_context(
        payload.get("hard_logic_evidence_sources"),
        research_tool_context,
    )

    row: dict[str, Any] = {
        "industry": industry,
        "research_state": research_state,
        "selected_code": selected_code,
        "selected_name": selected_name,
        "selection_origin": origin,
        "hard_logic_structural_driver": str(payload.get("hard_logic_structural_driver") or "").strip(),
        "hard_logic_supply_constraint": str(payload.get("hard_logic_supply_constraint") or "").strip(),
        "hard_logic_company_edge": str(payload.get("hard_logic_company_edge") or "").strip(),
        "hard_logic_profit_transmission": str(payload.get("hard_logic_profit_transmission") or "").strip(),
        "hard_logic_invalidation": str(payload.get("hard_logic_invalidation") or "").strip(),
        "hard_logic_duration_years": payload.get("hard_logic_duration_years"),
        "hard_logic_persistence": str(payload.get("hard_logic_persistence") or "").strip(),
        "hard_logic_evidence_sources": _source_text(payload.get("hard_logic_evidence_sources")),
        "evidence_tool_call_count": int(successful_tool_calls),
        "evidence_source_verified": bool(source_verified),
        "evidence_verification_matches": ";".join(source_matches),
        "research_summary": str(payload.get("research_summary") or "").strip(),
        "seed_codes": ";".join(seed_codes),
        "seed_names": ";".join(seed_names),
        "research_error": error,
        "formal_signal_eligible": False,
        "automatic_promotion_allowed": False,
        "no_auto_trade": True,
    }

    # Validate the selected thesis independently.  The model's PASS is only a
    # claim until the deterministic evidence gate accepts the required fields.
    evidence_row = dict(row)
    evidence_row["code"] = selected_code
    evidence_row["stock_name"] = selected_name
    evaluation = evaluate_hard_logic(evidence_row)
    row["hard_logic_state"] = evaluation.state if selected_code else "REVIEW"
    row["hard_logic_score"] = evaluation.score if selected_code else 0
    missing_evidence = list(evaluation.missing_evidence) if selected_code else ["selected_company"]

    if research_state == "PASS" and row["hard_logic_state"] != "PASS":
        row["research_state"] = "REVIEW"
        row["research_error"] = _append_error(
            row["research_error"],
            "deterministic_hard_logic_gate_rejected_model_pass",
        )

    if research_state == "PASS" and require_tool_evidence:
        if successful_tool_calls <= 0:
            missing_evidence.append("research_tool_call")
            row["research_state"] = "REVIEW"
            row["hard_logic_state"] = "REVIEW"
            row["research_error"] = _append_error(row["research_error"], "pass_without_research_tool_call")
        if not source_verified:
            missing_evidence.append("tool_verified_source")
            row["research_state"] = "REVIEW"
            row["hard_logic_state"] = "REVIEW"
            row["research_error"] = _append_error(row["research_error"], "claimed_sources_not_found_in_tool_results")

    if research_state == "NO_PASS":
        row["selected_code"] = ""
        row["selected_name"] = ""
        row["selection_origin"] = ""
        row["hard_logic_state"] = "REVIEW"
        row["hard_logic_score"] = 0
        missing_evidence = ["no_industry_company_passed_research"]

    row["hard_logic_missing_evidence"] = ";".join(sorted(set(missing_evidence)))
    return row


def _industry_search_tool():
    from src.agent.tools.registry import ToolDefinition, ToolParameter

    def handler(query: str, max_results: int = 6, days: int = 365) -> dict[str, Any]:
        from src.search_service import get_search_service

        service = get_search_service()
        if not service.is_available:
            return {"error": "No search engine available (no API keys configured)", "retriable": False}
        limit = max(1, min(int(max_results), 10))
        lookback = max(30, min(int(days), 1825))
        errors: list[str] = []
        for provider in service._providers:  # shared provider stack; research-only adapter
            if not provider.is_available:
                continue
            try:
                response = provider.search(query, max_results=limit, days=lookback)
            except Exception as exc:
                errors.append(f"{provider.name}:{exc}")
                continue
            if response.success and response.results:
                return {
                    "query": response.query,
                    "provider": response.provider,
                    "success": True,
                    "results": [
                        {
                            "title": item.title,
                            "snippet": item.snippet,
                            "url": item.url,
                            "source": item.source,
                            "published_date": item.published_date,
                        }
                        for item in response.results[:limit]
                    ],
                }
            errors.append(f"{provider.name}:{response.error_message or 'no results'}")
        return {
            "query": query,
            "success": False,
            "error": "all industry-search providers failed or returned no results",
            "details": errors[:5],
        }

    return ToolDefinition(
        name="search_industry_web",
        description=(
            "Search public web sources for an A-share industry's structural demand drivers, supply constraints, "
            "competitive landscape, bottlenecks and candidate companies. Use this before choosing a company; "
            "returns source titles, snippets and URLs for evidence verification."
        ),
        parameters=[
            ToolParameter(
                name="query",
                type="string",
                description="Industry research query in Chinese or English; include structural driver/bottleneck/company keywords.",
            ),
            ToolParameter(
                name="max_results",
                type="integer",
                description="Maximum result count (1-10, default 6).",
                required=False,
                default=6,
            ),
            ToolParameter(
                name="days",
                type="integer",
                description="Lookback window in days (30-1825, default 365).",
                required=False,
                default=365,
            ),
        ],
        handler=handler,
        category="search",
    )


def _filtered_research_registry():
    from src.agent.factory import get_tool_registry
    from src.agent.tools.registry import ToolRegistry

    full = get_tool_registry()
    filtered = ToolRegistry()
    filtered.register(_industry_search_tool())
    for name in RESEARCH_TOOL_NAMES:
        if name == "search_industry_web":
            continue
        tool_def = full.get(name)
        if tool_def is not None:
            filtered.register(tool_def)
    if not filtered.list_names():
        raise RuntimeError("no research tools are registered")
    return filtered


def _production_research_call(
    industry: str,
    seeds: list[Mapping[str, Any]],
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
    messages = [
        {
            "role": "system",
            "content": (
                "You are an evidence-first A-share industry researcher. You MUST use research tools before any PASS. "
                "Never infer hard logic from valuation, price, technical signals, Quant rank, or broker target prices. "
                "Every source in the final JSON must come from the tool outputs in this run. "
                "Your final response must be the exact JSON object requested by the user prompt."
            ),
        },
        {"role": "user", "content": _candidate_prompt(industry, seeds)},
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


def research_industry(
    industry: str,
    seeds: list[Mapping[str, Any]],
    *,
    raw_universe_codes: set[str] | None = None,
    timeout_seconds: float = 90.0,
    research_call: Callable[[str, list[Mapping[str, Any]]], str | ResearchExecution] | None = None,
) -> dict[str, Any]:
    try:
        if research_call is None:
            execution = _production_research_call(industry, seeds, timeout_seconds=timeout_seconds)
            require_tool_evidence = True
        else:
            response = research_call(industry, seeds)
            execution = response if isinstance(response, ResearchExecution) else ResearchExecution(str(response), "", 0)
            require_tool_evidence = isinstance(response, ResearchExecution)
        payload = _extract_json(execution.content)
        return normalize_research_payload(
            industry,
            seeds,
            payload,
            raw_universe_codes=raw_universe_codes,
            research_tool_context=execution.tool_context,
            successful_tool_calls=execution.successful_tool_calls,
            require_tool_evidence=require_tool_evidence,
        )
    except Exception as exc:
        logger.exception("hard-logic research failed for industry %s", industry)
        return {
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
            "seed_codes": ";".join(_normalize_code(row.get("code")) for row in seeds),
            "seed_names": ";".join(_stock_name(row) for row in seeds),
            "research_error": str(exc),
            "formal_signal_eligible": False,
            "automatic_promotion_allowed": False,
            "no_auto_trade": True,
        }


def _read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=OUTPUT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def run_research(
    *,
    industry_candidates_csv: Path,
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
    industries = sorted(seeds)
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
                research_industry,
                industry,
                seeds[industry],
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
            except Exception as exc:  # defensive: research_industry already fail-closes
                logger.exception("unexpected industry research future failure: %s", industry)
                results[industry] = {
                    "industry": industry,
                    "research_state": "REVIEW",
                    "selected_code": "",
                    "selected_name": "",
                    "selection_origin": "",
                    "hard_logic_state": "REVIEW",
                    "hard_logic_score": 0,
                    "hard_logic_missing_evidence": "unexpected_worker_failure",
                    "evidence_tool_call_count": 0,
                    "evidence_source_verified": False,
                    "evidence_verification_matches": "",
                    "research_error": str(exc),
                    "formal_signal_eligible": False,
                    "automatic_promotion_allowed": False,
                    "no_auto_trade": True,
                }

    rows = [results[industry] for industry in industries]
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "hard_logic_research.csv", rows)
    summary = {
        "industry_count": len(rows),
        "hard_logic_pass_count": sum(row.get("hard_logic_state") == "PASS" for row in rows),
        "no_pass_count": sum(row.get("research_state") == "NO_PASS" for row in rows),
        "review_count": sum(row.get("research_state") == "REVIEW" for row in rows),
        "external_nomination_count": sum(row.get("selection_origin") == "EXTERNAL_A_SHARE_NOMINATION" for row in rows),
        "tool_verified_pass_count": sum(
            row.get("hard_logic_state") == "PASS" and bool(row.get("evidence_source_verified"))
            for row in rows
        ),
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
    parser.add_argument("--all-a-universe-csv", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--per-industry-limit", type=int, default=5)
    parser.add_argument("--max-workers", type=int, default=3)
    parser.add_argument("--timeout-seconds", type=float, default=90.0)
    parser.add_argument("--max-industries", type=int, default=0)
    args = parser.parse_args(argv)
    rows = run_research(
        industry_candidates_csv=args.industry_candidates_csv,
        all_a_universe_csv=args.all_a_universe_csv,
        output_dir=args.output_dir,
        per_industry_limit=args.per_industry_limit,
        max_workers=args.max_workers,
        timeout_seconds=args.timeout_seconds,
        max_industries=args.max_industries,
    )
    print(f"hard_logic_research={args.output_dir};industries={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
