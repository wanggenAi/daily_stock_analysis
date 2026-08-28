"""Build a human-readable production health dashboard from finalized authority."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected object: {path}")
    return data


def build(authoritative_root: Path, *, main_sha: str = "") -> dict[str, Any]:
    authority = _load(authoritative_root / "production_authority.json")
    snapshot = _load(authoritative_root / "canonical_snapshot" / "latest.json")
    holdings = _load(authoritative_root / "holdings_reconciliation.json")
    lifecycle = _load(authoritative_root / "candidate_lifecycle" / "summary.json")
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
        "formal_action_source": "FINALIZED_CANONICAL_ONLY",
        "no_auto_trade": True,
    }


def render_md(status: dict[str, Any]) -> str:
    counts = status.get("formal_action_counts") or {}
    lines = [
        "# GenGe V3.1.1 Production Status",
        "",
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
        f"- Candidate lifecycle active: `{status.get('candidate_lifecycle_active')}`",
        "",
        "## Formal Actions",
        "",
    ]
    if counts:
        for action, count in sorted(counts.items()):
            lines.append(f"- {action}: **{count}**")
    else:
        lines.append("- No production actions in snapshot")
    lines += [
        "",
        "> Formal actions come only from the finalized canonical. Research overlays cannot overwrite them.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--authoritative-root", type=Path, required=True)
    p.add_argument("--main-sha", default="")
    p.add_argument("--json-output", type=Path, default=Path("data/production_status/latest.json"))
    p.add_argument("--md-output", type=Path, default=Path("PRODUCTION_STATUS.md"))
    args = p.parse_args(argv)
    status = build(args.authoritative_root, main_sha=args.main_sha)
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(status, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.md_output.write_text(render_md(status), encoding="utf-8")
    print(json.dumps(status, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
