"""Build an evidence-aware, read-only hourly research state over V3.1.1 authority.

The state combines canonical value anchors, persisted hourly prices, and recent
Evidence Events. It may raise/lower research priority, but Formal actions remain
copied from the finalized canonical and are never recomputed here.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from .evidence_event_store import recent_for_code

BEIJING = ZoneInfo("Asia/Shanghai")
CONTRACT_VERSION = "GEN_GE_V3_1_1_HOURLY_RESEARCH_STATE_V2"


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _parse_ts(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def load_price_history(root: Path) -> dict[str, list[dict[str, Any]]]:
    history: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for path in sorted(root.glob("????-??-??/*.json")):
        try:
            payload = _load(path)
        except Exception:
            continue
        generated_at = payload.get("generated_at")
        for row in payload.get("rows") or []:
            if not isinstance(row, Mapping):
                continue
            code = str(row.get("code") or "").zfill(6)
            if not code:
                continue
            history[code].append({
                "generated_at": generated_at,
                "canonical_snapshot_id": payload.get("canonical_snapshot_id"),
                "price": row.get("latest_price"),
                "validated_value_anchor": row.get("validated_value_anchor"),
                "price_to_value": row.get("price_to_value"),
                "margin_of_safety": row.get("margin_of_safety"),
                "price_evidence_status": row.get("price_evidence_status"),
            })
    for rows in history.values():
        rows.sort(key=lambda r: str(r.get("generated_at") or ""))
    return history


def _evidence_summary(events: list[dict[str, Any]], *, now: datetime) -> dict[str, Any]:
    cutoff = now - timedelta(hours=72)
    recent = [e for e in events if (_parse_ts(e.get("published_at")) or datetime.min.replace(tzinfo=timezone.utc)) >= cutoff]
    weakening = [e for e in recent if e.get("direction") == "WEAKENING"]
    strengthening = [e for e in recent if e.get("direction") == "STRENGTHENING"]
    high = [e for e in recent if e.get("materiality") == "HIGH"]
    material_weakening = [e for e in weakening if e.get("materiality") in {"HIGH", "MEDIUM"}]
    material_strengthening = [e for e in strengthening if e.get("materiality") in {"HIGH", "MEDIUM"}]
    high_weakening = [e for e in material_weakening if e.get("materiality") == "HIGH"]
    if high_weakening:
        thesis = "REUNDERWRITE_REQUIRED"
    elif material_weakening and not material_strengthening:
        thesis = "WEAKENING_RESEARCH_SIGNAL"
    elif material_strengthening and not material_weakening:
        thesis = "STRENGTHENING_RESEARCH_SIGNAL"
    elif material_weakening and material_strengthening:
        thesis = "MIXED_NEW_EVIDENCE"
    elif recent:
        thesis = "LOW_MATERIALITY_OR_NEUTRAL_EVIDENCE_ONLY"
    else:
        thesis = "NO_NEW_MATERIAL_EVIDENCE"
    return {
        "recent_evidence_count_72h": len(recent),
        "weakening_evidence_count_72h": len(weakening),
        "strengthening_evidence_count_72h": len(strengthening),
        "material_weakening_evidence_count_72h": len(material_weakening),
        "material_strengthening_evidence_count_72h": len(material_strengthening),
        "high_materiality_evidence_count_72h": len(high),
        "thesis_status": thesis,
        "latest_evidence": recent[:5],
    }


def build_state(price_overlay: Mapping[str, Any], evidence_root: Path, price_history_root: Path) -> dict[str, Any]:
    now = _parse_ts(price_overlay.get("generated_at")) or datetime.now(timezone.utc)
    history = load_price_history(price_history_root)
    rows: list[dict[str, Any]] = []
    for raw in price_overlay.get("rows") or []:
        row = dict(raw)
        code = str(row.get("code") or "").zfill(6)
        events = recent_for_code(evidence_root, code, limit=50)
        evidence = _evidence_summary(events, now=now)
        observations = history.get(code, [])
        attractive = [r for r in observations if r.get("price_evidence_status") == "PRICE_GATE_PASS_RESEARCH_ONLY"]
        consecutive = 0
        for obs in reversed(observations):
            if obs.get("price_evidence_status") == "PRICE_GATE_PASS_RESEARCH_ONLY":
                consecutive += 1
            else:
                break
        distinct_days = len({str(r.get("generated_at") or "")[:10] for r in attractive})
        priority = str(row.get("deep_review_priority") or "KEEP")
        conclusion = str(row.get("hourly_research_conclusion") or "FORMAL_ACTION_UNCHANGED")
        thesis = evidence["thesis_status"]
        price_attractive = row.get("price_evidence_status") == "PRICE_GATE_PASS_RESEARCH_ONLY"
        if thesis in {"REUNDERWRITE_REQUIRED", "WEAKENING_RESEARCH_SIGNAL", "MIXED_NEW_EVIDENCE"}:
            priority = "RAISE"
            conclusion = "NEW_EVIDENCE_REUNDERWRITE_LEAD"
        elif price_attractive and thesis == "STRENGTHENING_RESEARCH_SIGNAL":
            priority = "RAISE"
            conclusion = "PRICE_ATTRACTIVE_AND_THESIS_STRENGTHENING_LEAD"
        elif price_attractive and thesis in {"NO_NEW_MATERIAL_EVIDENCE", "LOW_MATERIALITY_OR_NEUTRAL_EVIDENCE_ONLY"}:
            conclusion = "PRICE_ATTRACTIVE_RESEARCH_LEAD"
        rows.append({
            **row,
            **evidence,
            "price_history_observation_count": len(observations),
            "price_attractive_observation_count": len(attractive),
            "price_attractive_consecutive_observations": consecutive,
            "price_attractive_distinct_days": distinct_days,
            "deep_review_priority": priority,
            "hourly_research_conclusion": conclusion,
            "formal_action_source": "FINALIZED_CANONICAL_ONLY",
            "formal_action_recomputed": False,
            "overlay_may_overwrite_formal_action": False,
            "evidence_may_overwrite_formal_action": False,
            "no_auto_trade": True,
        })
    return {
        "contract_version": CONTRACT_VERSION,
        "generated_at": now.isoformat(),
        "generated_at_beijing": now.astimezone(BEIJING).isoformat(),
        "canonical_snapshot_id": price_overlay.get("canonical_snapshot_id"),
        "canonical_source_run_id": price_overlay.get("canonical_source_run_id"),
        "formal_action_source": "FINALIZED_CANONICAL_ONLY",
        "formal_action_recomputed": False,
        "overlay_may_overwrite_formal_action": False,
        "evidence_may_overwrite_formal_action": False,
        "no_auto_trade": True,
        "workset_count": len(rows),
        "raise_count": sum(r.get("deep_review_priority") == "RAISE" for r in rows),
        "reunderwrite_lead_count": sum(r.get("hourly_research_conclusion") == "NEW_EVIDENCE_REUNDERWRITE_LEAD" for r in rows),
        "price_attractive_research_lead_count": sum(r.get("hourly_research_conclusion") == "PRICE_ATTRACTIVE_RESEARCH_LEAD" for r in rows),
        "price_attractive_strengthening_lead_count": sum(r.get("hourly_research_conclusion") == "PRICE_ATTRACTIVE_AND_THESIS_STRENGTHENING_LEAD" for r in rows),
        "rows": rows,
    }


def persist(payload: Mapping[str, Any], root: Path) -> tuple[Path, Path]:
    stamp = (_parse_ts(payload.get("generated_at")) or datetime.now(timezone.utc)).astimezone(BEIJING)
    history = root / stamp.strftime("%Y-%m-%d") / f"{stamp:%H}.json"
    latest = root / "latest.json"
    history.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    history.write_text(text, encoding="utf-8")
    latest.write_text(text, encoding="utf-8")
    return latest, history


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--price-overlay", type=Path, default=Path("data/hourly_deep_overlay/latest.json"))
    parser.add_argument("--price-history-root", type=Path, default=Path("data/hourly_deep_overlay"))
    parser.add_argument("--evidence-root", type=Path, default=Path("data/evidence_events"))
    parser.add_argument("--output-root", type=Path, default=Path("data/hourly_research_state"))
    args = parser.parse_args(argv)
    payload = build_state(_load(args.price_overlay), args.evidence_root, args.price_history_root)
    latest, history = persist(payload, args.output_root)
    print(json.dumps({"canonical_snapshot_id": payload["canonical_snapshot_id"], "workset_count": payload["workset_count"], "raise_count": payload["raise_count"], "reunderwrite_lead_count": payload["reunderwrite_lead_count"], "latest": str(latest), "history": str(history), "formal_action_recomputed": False}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
