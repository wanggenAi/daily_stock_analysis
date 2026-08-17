"""Industry-balanced recall policy for long-horizon A-share research.

The policy separates *recall* from *final ranking*.

Invariant:
- true hard rejects never re-enter research unless the caller's explicit
  research eligibility policy already classified them as recoverable;
- every industry keeps up to ``per_industry_target`` eligible representatives;
- the strongest global candidates are preserved as a separate seed;
- ``total_limit`` is only a minimum capacity target and may not truncate the
  union of protected industry representatives plus the global seed;
- global ranking may order candidates later, but may not erase an industry
  before fundamental/valuation research has had a chance to inspect it.

This module is research-only and never grants Formal BUY eligibility.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping

RESEARCH_STATUSES = frozenset(
    {"PRIORITY_RESEARCH", "SECONDARY_RESEARCH", "LOW_PRIORITY"}
)
_STATUS_PRIORITY = {
    "PRIORITY_RESEARCH": 0,
    "SECONDARY_RESEARCH": 1,
    "LOW_PRIORITY": 2,
}


@dataclass(frozen=True)
class IndustryRecallPolicy:
    total_limit: int
    global_seed: int = 80
    per_industry_target: int = 3

    def normalized(self) -> "IndustryRecallPolicy":
        return IndustryRecallPolicy(
            total_limit=max(0, int(self.total_limit)),
            global_seed=max(0, int(self.global_seed)),
            per_industry_target=max(1, int(self.per_industry_target)),
        )


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
        row.get("normalized_industry")
        or row.get("industry")
        or row.get("raw_industry")
        or "UNRESOLVED"
    ).strip() or "UNRESOLVED"


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _order_key(row: Mapping[str, Any]) -> tuple[int, float, float, str]:
    status = str(row.get("quant_status") or row.get("quant_screen_status") or "").upper()
    rank = _finite(row.get("quant_rank"))
    score = _finite(row.get("quant_score"))
    return (
        _STATUS_PRIORITY.get(status, 9),
        rank if rank is not None else 10**9,
        -(score if score is not None else -10**9),
        _normalize_code(row.get("code")),
    )


def default_research_eligibility(row: Mapping[str, Any]) -> bool:
    """Allow soft research tiers but never revive a true hard reject."""

    status = str(row.get("quant_status") or row.get("quant_screen_status") or "").upper()
    hard = str(
        row.get("hard_blockers")
        or row.get("hard_reject_blockers")
        or row.get("source_hard_blockers")
        or ""
    ).strip()
    return status in RESEARCH_STATUSES and not hard


def prepare_candidates(
    rows: Iterable[Mapping[str, Any]],
    *,
    eligibility: Callable[[Mapping[str, Any]], bool] = default_research_eligibility,
) -> list[dict[str, Any]]:
    """Normalize, deduplicate and deterministically order eligible research rows."""

    by_code: dict[str, dict[str, Any]] = {}
    for raw in rows:
        if not eligibility(raw):
            continue
        code = _normalize_code(raw.get("code"))
        if not code:
            continue
        candidate = dict(raw)
        candidate["code"] = code
        candidate["industry"] = _industry(candidate)
        previous = by_code.get(code)
        if previous is None or _order_key(candidate) < _order_key(previous):
            by_code[code] = candidate
    return sorted(by_code.values(), key=_order_key)


def industry_leaders(
    rows: Iterable[Mapping[str, Any]],
    *,
    per_industry: int = 1,
    eligibility: Callable[[Mapping[str, Any]], bool] = default_research_eligibility,
) -> list[dict[str, Any]]:
    """Return the best eligible rows within every industry."""

    target = max(1, int(per_industry))
    prepared = prepare_candidates(rows, eligibility=eligibility)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in prepared:
        grouped[_industry(row)].append(row)

    selected: list[dict[str, Any]] = []
    for industry in sorted(grouped):
        for rank, row in enumerate(grouped[industry][:target], 1):
            item = dict(row)
            item["industry_recall_rank"] = rank
            selected.append(item)
    return selected


def select_industry_balanced_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    policy: IndustryRecallPolicy,
    eligibility: Callable[[Mapping[str, Any]], bool] = default_research_eligibility,
) -> list[dict[str, Any]]:
    """Build the mandatory union of global leaders and industry-protected recall.

    ``total_limit`` is a minimum capacity target, not permission to delete an
    eligible industry representative. The complete union of the global seed and
    up to ``per_industry_target`` rows from every eligible industry is mandatory.
    If that union exceeds ``total_limit``, the function deliberately exceeds the
    target rather than weaken research recall.
    """

    policy = policy.normalized()
    prepared = prepare_candidates(rows, eligibility=eligibility)
    if not prepared:
        return []

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in prepared:
        grouped[_industry(row)].append(row)

    global_rows = prepared[: policy.global_seed]
    global_rank = {
        _normalize_code(row.get("code")): index
        for index, row in enumerate(global_rows, 1)
    }

    chosen: dict[str, dict[str, Any]] = {}
    sources: dict[str, set[str]] = defaultdict(set)
    industry_rank: dict[str, int] = {}

    for industry in sorted(grouped):
        for rank, row in enumerate(
            grouped[industry][: policy.per_industry_target],
            1,
        ):
            code = _normalize_code(row.get("code"))
            chosen.setdefault(code, dict(row))
            sources[code].add("INDUSTRY_PROTECTED")
            industry_rank[code] = min(industry_rank.get(code, rank), rank)

    for row in global_rows:
        code = _normalize_code(row.get("code"))
        chosen.setdefault(code, dict(row))
        sources[code].add("GLOBAL_SEED")

    effective_limit = max(policy.total_limit, len(chosen))
    for row in prepared:
        if len(chosen) >= effective_limit:
            break
        code = _normalize_code(row.get("code"))
        if code in chosen:
            continue
        chosen[code] = dict(row)
        sources[code].add("GLOBAL_FILL")

    result = list(chosen.values())
    result.sort(key=_order_key)
    for item in result:
        code = _normalize_code(item.get("code"))
        item["research_recall_sources"] = ";".join(sorted(sources[code]))
        item["industry_recall_rank"] = industry_rank.get(code, "")
        item["global_recall_rank"] = global_rank.get(code, "")
        item["industry_recall_guaranteed"] = bool(industry_rank.get(code) == 1)
    return result


def coverage_audit(
    source_rows: Iterable[Mapping[str, Any]],
    selected_rows: Iterable[Mapping[str, Any]],
    *,
    eligibility: Callable[[Mapping[str, Any]], bool] = default_research_eligibility,
) -> dict[str, Any]:
    prepared = prepare_candidates(source_rows, eligibility=eligibility)
    selected = prepare_candidates(selected_rows, eligibility=lambda row: True)
    eligible_industries = sorted({_industry(row) for row in prepared})
    covered_industries = sorted({_industry(row) for row in selected})
    missing = sorted(set(eligible_industries) - set(covered_industries))
    source_counts: dict[str, int] = defaultdict(int)
    selected_counts: dict[str, int] = defaultdict(int)
    for row in prepared:
        source_counts[_industry(row)] += 1
    for row in selected:
        selected_counts[_industry(row)] += 1
    return {
        "eligible_candidate_count": len(prepared),
        "selected_candidate_count": len(selected),
        "eligible_industry_count": len(eligible_industries),
        "covered_industry_count": len(covered_industries),
        "all_eligible_industries_covered": not missing,
        "missing_eligible_industries": missing,
        "eligible_industries": eligible_industries,
        "industry_source_candidate_counts": dict(sorted(source_counts.items())),
        "industry_selected_candidate_counts": dict(sorted(selected_counts.items())),
        "hard_reject_revival_allowed": False,
        "formal_signal_eligible": False,
        "automatic_promotion_allowed": False,
        "no_auto_trade": True,
    }
