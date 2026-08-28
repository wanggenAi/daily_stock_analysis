"""Build a human-readable production/learning status dashboard.

Formal authority remains sourced only from finalized canonical. Learning state is
shown for operations and research prioritization only and cannot overwrite it.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _load(path: Path, *, required: bool = True) -> dict[str, Any]:
    if not path.is_file():
        if required:
            raise FileNotFoundError(path)
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected object: {path}")
    return data


def build(authoritative_root: Path, *, main_sha: str = "", state_root: Path = Path(".")) -> dict[str, Any]:
    authority = _load(authoritative_root / "production_authority.json")
    snapshot = _load(authoritative_root / "canonical_snapshot" / "latest.json")
    holdings = _load(authoritative_root / "holdings_reconciliation.json")
    lifecycle = _load(authoritative_root / "candidate_lifecycle" / "summary.json")
    priority = _load(state_root / "data/research_priority/latest.json", required=False)
    price_value = _load(state_root / "data/price_value_history/summary.json", required=False)
    outcomes = _load(state_root / "data/formal_decision_outcomes/latest.json", required=False)
    production = snapshot.get("production") or {}
    rows = list(production.get("candidate_decisions") or []) + list(production.get("holding_decisions") or [])
    actions = Counter(str(r.get("action") or r.get("formal_action") or "UNKNOWN") for r in rows if isinstance(r, dict))
    source_sha = str(authority.get("source_head_sha") or authority.get("canonical_source_head_sha") or "")
    drift = "NO_CODE_DRIFT" if main_sha and source_sha == main_sha else "CODE_DRIFT_MAIN_ADVANCED"
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "health": "HEALTHY" if authority.get("authorized") is True else "UNHEALTHY",
        "main_sha": main_sha,
        "canonical_source_sha": source_sha,
        "code_drift_status": drift,
        "canonical_snapshot_id": authority.get("canonical_snapshot_id") or snapshot.get("snapshot_id"),
        "canonical_source_run_id": authority.get("canonical_source_run_id") or snapshot.get("source_run_id"),
        "source_workflow": authority.get("source_workflow"),
        "latest_trade_date": authority.get("latest_trade_date") or snapshot.get("latest_trade_date"),
        "research_as_of": authority.get("research_as_of") or snapshot.get("research_as_of"),
        "holdings_status": holdings.get("status"),
        "formal_holding_actions_currently_usable": holdings.get("formal_holding_actions_currently_usable"),
        "candidate_lifecycle_active": lifecycle.get("active_count"),
        "candidate_lifecycle_inactive": lifecycle.get("inactive_count"),
        "formal_action_counts": dict(actions),
        "research_learning": {
            "available": bool(priority and price_value and outcomes),
            "p0_count": priority.get("p0_count"),
            "p1_count": priority.get("p1_count"),
            "mapping_gap_count": priority.get("mapping_gap_count"),
            "price_value_security_count": len(price_value.get("rows") or []),
            "formal_outcome_record_count": outcomes.get("record_count"),
            "observed_horizon_count": outcomes.get("observed_horizon_count"),
            "pending_horizon_count": outcomes.get("pending_horizon_count"),
            "parameter_tuning_allowed": False,
            "priority_orders_deep_review_only": True,
        },
        "formal_action_source": "FINALIZED_CANONICAL_ONLY",
        "no_auto_trade": True,
    }


def render_md(status: dict[str, Any]) -> str:
    counts = status.get("formal_action_counts") or {}
    learning = status.get("research_learning") or {}
    lines = [
        "# GenGe V3.1.1 Production Status", "",
        f"- Health: **{status.get('health')}**",
        f"- Main SHA: `{status.get('main_sha')}`",
        f"- Canonical source SHA: `{status.get('canonical_source_sha')}`",
        f"- Drift: `{status.get('code_drift_status')}`",
        f"- Canonical snapshot: `{status.get('canonical_snapshot_id')}`",
        f"- Source run: `{status.get('canonical_source_run_id')}`",
        f"- Source workflow: `{status.get('source_workflow')}`",
        f"- Latest trade date: `{status.get('latest_trade_date')}`",
        f"- Holdings: `{status.get('holdings_status')}`",
        f"- Holding Formal actions usable: `{status.get('formal_holding_actions_currently_usable')}`",
        f"- Candidate lifecycle active: `{status.get('candidate_lifecycle_active')}`", "",
        "## Formal Actions", "",
    ]
    if counts:
        for action, count in sorted(counts.items()):
            lines.append(f"- {action}: **{count}**")
    else:
        lines.append("- No production actions in snapshot")
    lines += ["", "## Research Learning", ""]
    if learning.get("available"):
        lines += [
            f"- P0 deep-review priorities: **{learning.get('p0_count')}**",
            f"- P1 deep-review priorities: **{learning.get('p1_count')}**",
            f"- Visible mapping gaps: **{learning.get('mapping_gap_count')}**",
            f"- Price/Value tracked securities: **{learning.get('price_value_security_count')}**",
            f"- Formal outcome records: **{learning.get('formal_outcome_record_count')}**",
            f"- Observed 5/20/60 horizons: **{learning.get('observed_horizon_count')}**",
            f"- Pending 5/20/60 horizons: **{learning.get('pending_horizon_count')}**",
            "- Automatic V3.1.1 parameter tuning: **DISABLED**",
        ]
    else:
        lines.append("- Learning state not available yet")
    lines += [
        "",
        "> Formal actions come only from the finalized canonical. Research priority may reorder Deep Review only; it cannot filter Broad Discovery, change frozen gates, or overwrite Formal actions.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--authoritative-root", type=Path, required=True)
    p.add_argument("--main-sha", default="")
    p.add_argument("--state-root", type=Path, default=Path("."))
    p.add_argument("--json-output", type=Path, default=Path("data/production_status/latest.json"))
    p.add_argument("--md-output", type=Path, default=Path("PRODUCTION_STATUS.md"))
    args = p.parse_args(argv)
    status = build(args.authoritative_root, main_sha=args.main_sha, state_root=args.state_root)
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(status, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.md_output.write_text(render_md(status), encoding="utf-8")
    print(json.dumps(status, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
