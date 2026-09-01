"""Route research work without changing V3.1.1 Formal actions.

Combines hourly research state, candidate lifecycle and reviewed mapping coverage
into an auditable Deep Review / mapping queue. This module is research-only.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

CONTRACT_VERSION = "GEN_GE_RESEARCH_PRIORITY_ROUTER_V3"
STRUCTURAL_REUNDERWRITE_PRICE_STATUSES = {"VALUE_ANCHOR_UNAVAILABLE"}


def _load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _tier_score(tier: str) -> int:
    text = (tier or "").upper()
    if "A1" in text:
        return 30
    if "A2" in text:
        return 20
    if "BUY_REVIEW" in text:
        return 18
    if "WAIT_PRICE" in text:
        return 15
    if "DOWNGRADED" in text:
        return 12
    return 5


def _requires_structural_reunderwrite(*, is_current_holding: bool, hourly_row: Mapping[str, Any]) -> bool:
    """Return whether a holding's finalized Canonical lacks a usable value anchor.

    HOLD_REVIEW is already a finalized Canonical action, not a research action. If
    that holding also exposes VALUE_ANCHOR_UNAVAILABLE with no validated anchor,
    price-only hourly research cannot resolve the condition. Route it back through
    the existing full Deep Review -> Production Finalizer authority chain instead
    of silently leaving the holding in a non-actionable review state.
    """

    if not is_current_holding:
        return False
    if str(hourly_row.get("formal_action") or "") != "HOLD_REVIEW":
        return False
    if str(hourly_row.get("price_evidence_status") or "") not in STRUCTURAL_REUNDERWRITE_PRICE_STATUSES:
        return False
    return hourly_row.get("validated_value_anchor") is None


def build_queue(hourly: Mapping[str, Any], lifecycle: Mapping[str, Any], coverage: Mapping[str, Any]) -> dict[str, Any]:
    life = lifecycle.get("candidates") or {}
    coverage_rows = {str(r.get("code") or "").zfill(6): r for r in (coverage.get("securities") or []) if isinstance(r, Mapping)}
    hourly_rows = {str(r.get("code") or "").zfill(6): r for r in (hourly.get("rows") or []) if isinstance(r, Mapping)}
    codes = sorted(set(life) | set(coverage_rows) | set(hourly_rows))
    queue: list[dict[str, Any]] = []
    for code in codes:
        l = life.get(code) or {}
        c = coverage_rows.get(code) or {}
        h = hourly_rows.get(code) or {}
        reasons: list[str] = []
        score = 0

        # Current-holding identity is an operational fact, not a research-mapping
        # attribute. Mapping coverage intentionally persists across holding/candidate
        # lifecycle changes, so its historical HOLDING scope must never project a
        # closed position back into CURRENT_HOLDING. The current hourly state is
        # produced from the reconciled current portfolio and is therefore the only
        # authority used by this research-only router for holding priority.
        is_current_holding = str(h.get("scope") or "").upper() == "HOLDING"
        if is_current_holding:
            score += 50; reasons.append("CURRENT_HOLDING")
        tier = str(l.get("research_tier") or "")
        ts = _tier_score(tier)
        score += ts
        if ts >= 15:
            reasons.append("HIGH_RESEARCH_TIER")
        conclusion = str(h.get("hourly_research_conclusion") or "")
        thesis = str(h.get("thesis_status") or "")
        structural_reunderwrite = _requires_structural_reunderwrite(
            is_current_holding=is_current_holding,
            hourly_row=h,
        )
        if conclusion in {"PRICE_ATTRACTIVE_RESEARCH_LEAD", "PRICE_ATTRACTIVE_AND_THESIS_STRENGTHENING_LEAD"}:
            score += 35; reasons.append(conclusion)
        if conclusion == "NEW_EVIDENCE_REUNDERWRITE_LEAD" or thesis == "REUNDERWRITE_REQUIRED" or structural_reunderwrite:
            score += 45; reasons.append("REUNDERWRITE_REQUIRED")
            if structural_reunderwrite:
                reasons.append("VALUE_ANCHOR_REUNDERWRITE_REQUIRED")
        elif thesis in {"WEAKENING_RESEARCH_SIGNAL", "MIXED_NEW_EVIDENCE"}:
            score += 25; reasons.append("MATERIAL_EVIDENCE_CHANGE")
        if str(h.get("deep_review_priority") or "") == "RAISE":
            score += 15; reasons.append("HOURLY_PRIORITY_RAISE")

        mapping_gaps: list[str] = []
        if not c.get("industry_mapped"):
            mapping_gaps.append("INDUSTRY")
        commodity_state = str(c.get("commodity_monitoring_state") or "")
        if commodity_state == "APPLICABLE_UNMAPPED":
            mapping_gaps.append("COMMODITY")
        elif commodity_state == "PARTIAL_MAPPED":
            mapping_gaps.append("COMMODITY_PARTIAL")
        if c.get("peer_monitoring_state") == "APPLICABLE_UNMAPPED":
            mapping_gaps.append("PEER")
        if mapping_gaps:
            score += min(15, 5 * len(mapping_gaps)); reasons.append("MAPPING_GAP")

        if score >= 70:
            priority = "P0"
        elif score >= 45:
            priority = "P1"
        elif score >= 25:
            priority = "P2"
        else:
            priority = "P3"
        queue.append({
            "code": code,
            "name": c.get("name") or l.get("stock_name") or h.get("name") or "",
            "priority": priority,
            "priority_score": score,
            "research_tier": tier,
            "thesis_status": thesis or None,
            "hourly_research_conclusion": conclusion or None,
            "mapping_gaps": mapping_gaps,
            "reason_codes": reasons,
            "formal_action": h.get("formal_action"),
            "formal_action_recomputed": False,
            "formal_action_eligible": False,
        })
    queue.sort(key=lambda r: (-int(r["priority_score"]), r["code"]))
    now = datetime.now(timezone.utc).isoformat()
    return {
        "contract_version": CONTRACT_VERSION,
        "generated_at": now,
        "canonical_snapshot_id": hourly.get("canonical_snapshot_id"),
        "formal_action_source": "FINALIZED_CANONICAL_ONLY",
        "formal_action_recomputed": False,
        "formal_action_eligible": False,
        "no_auto_trade": True,
        "queue_count": len(queue),
        "p0_count": sum(r["priority"] == "P0" for r in queue),
        "p1_count": sum(r["priority"] == "P1" for r in queue),
        "mapping_gap_count": sum(bool(r["mapping_gaps"]) for r in queue),
        "partial_mapping_gap_count": sum("COMMODITY_PARTIAL" in r["mapping_gaps"] for r in queue),
        "queue": queue,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--hourly", type=Path, default=Path("data/hourly_research_state/latest.json"))
    p.add_argument("--lifecycle", type=Path, default=Path("data/opportunity_snapshots/candidate_lifecycle_state.json"))
    p.add_argument("--coverage", type=Path, default=Path("data/research_mapping/coverage.json"))
    p.add_argument("--output", type=Path, default=Path("data/research_priority/latest.json"))
    args = p.parse_args(argv)
    payload = build_queue(_load(args.hourly), _load(args.lifecycle), _load(args.coverage))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: payload[k] for k in ("queue_count", "p0_count", "p1_count", "mapping_gap_count", "partial_mapping_gap_count")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
