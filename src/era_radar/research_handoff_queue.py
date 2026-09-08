"""Build a fail-closed Era Radar -> A-share research handoff queue.

Trend evidence may prioritize authoritative research, but it cannot create a Formal action.
Only explicit trend-to-industry links and reviewed company-industry mappings are eligible.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterable, Mapping

from .handoff import build_research_handoff

FORMAL_ACTION_SOURCE = "FINALIZED_CANONICAL_ONLY"
ELIGIBLE_LIFECYCLES = {"ACCELERATING", "CONFIRMED"}
TRUSTED_SOURCE_TIERS = {"PRIMARY", "OFFICIAL", "HIGH_QUALITY_SECONDARY"}
REVIEWED_MAPPING_SOURCE_TYPE = "reviewed_research_mapping"


def _market(code: str) -> str | None:
    code = code.zfill(6)
    if code.startswith(("600", "601", "603", "605")):
        return "SH"
    if code.startswith(("000", "001", "002", "003")):
        return "SZ"
    return None


def _validated_company_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for raw in rows:
        code = str(raw.get("code") or "").strip().zfill(6)
        industry = str(raw.get("industry") or "").strip()
        source_type = str(raw.get("source_type") or "").strip()
        confidence = str(raw.get("confidence") or "").strip().upper()
        market = _market(code)
        if not market or not industry:
            continue
        if source_type != REVIEWED_MAPPING_SOURCE_TYPE or confidence != "HIGH":
            continue
        result.append({
            "code": code,
            "name": str(raw.get("stock_name") or raw.get("name") or "").strip(),
            "industry": industry,
            "market": market,
        })
    return result


def build_handoff_queue(
    snapshot: Mapping[str, Any],
    evidence_rows: Iterable[Mapping[str, Any]],
    company_rows: Iterable[Mapping[str, Any]],
    link_config: Mapping[str, Any],
) -> dict[str, Any]:
    if snapshot.get("formal_trading_authority") is not False or snapshot.get("no_auto_trade") is not True:
        raise ValueError("Era Radar snapshot must be research-only")
    if str(link_config.get("authority") or "") != "RESEARCH_ONLY":
        raise ValueError("trend-industry links must be research-only")
    if link_config.get("automatic_promotion_allowed") is not False:
        raise ValueError("trend-industry links cannot allow automatic promotion")
    if link_config.get("unknown_mapping_is_match") is not False:
        raise ValueError("unknown trend/industry mappings must fail closed")

    links = link_config.get("links") or {}
    if not isinstance(links, Mapping):
        raise ValueError("trend-industry links must be an object")

    evidence_by_trend: dict[str, list[Mapping[str, Any]]] = {}
    for row in evidence_rows:
        if not isinstance(row, Mapping):
            continue
        trend_id = str(row.get("trend_id") or "").strip()
        if trend_id:
            evidence_by_trend.setdefault(trend_id, []).append(row)

    companies = _validated_company_rows(company_rows)
    queue: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for trend in snapshot.get("trends") or []:
        if not isinstance(trend, Mapping):
            continue
        trend_id = str(trend.get("trend_id") or "").strip()
        lifecycle = str(trend.get("lifecycle") or "").strip().upper()
        try:
            confidence_score = float(trend.get("confidence_score"))
        except (TypeError, ValueError):
            continue
        if lifecycle not in ELIGIBLE_LIFECYCLES or confidence_score < 58.0:
            continue
        industries = {str(item).strip() for item in (links.get(trend_id) or []) if str(item).strip()}
        if not industries:
            continue

        trend_evidence = evidence_by_trend.get(trend_id) or []
        provenance_ok = bool(trend_evidence) and all(
            str(item.get("source_tier") or "") in TRUSTED_SOURCE_TIERS
            and str(item.get("source_url") or "").startswith("https://")
            for item in trend_evidence
        )
        freshness_ok = any(str(item.get("freshness") or "") == "FRESH" for item in trend_evidence)
        if not provenance_ok or not freshness_ok:
            continue

        for company in companies:
            if company["industry"] not in industries:
                continue
            key = (trend_id, company["code"])
            if key in seen:
                continue
            seen.add(key)
            rationale = (
                f"Era Radar {trend_id} is {lifecycle} at confidence {confidence_score:.2f}; "
                f"reviewed industry link={company['industry']}. Research re-underwrite only."
            )
            handoff = build_research_handoff(
                trend_id=trend_id,
                industry_link=company["industry"],
                symbol=company["code"],
                market=company["market"],
                rationale=rationale,
                confidence_score=confidence_score,
                provenance_ok=provenance_ok,
                freshness_ok=freshness_ok,
            )
            if handoff is None:
                continue
            row = asdict(handoff)
            row.update({
                "code": company["code"],
                "name": company["name"],
                "trend_lifecycle": lifecycle,
                "formal_action_eligible": False,
                "automatic_promotion_allowed": False,
                "no_auto_trade": True,
            })
            queue.append(row)

    queue.sort(key=lambda row: (-float(row["confidence_score"]), row["trend_id"], row["code"]))
    return {
        "contract_version": "ERA_RADAR_A_SHARE_RESEARCH_HANDOFF_V1",
        "radar_snapshot_id": str(snapshot.get("snapshot_id") or ""),
        "research_as_of": str(snapshot.get("research_as_of") or ""),
        "queue_count": len(queue),
        "trigger_full_authority_research": bool(queue),
        "formal_action_source": FORMAL_ACTION_SOURCE,
        "formal_action_recomputed": False,
        "formal_action_eligible": False,
        "automatic_promotion_allowed": False,
        "unknown_mapping_is_match": False,
        "no_auto_trade": True,
        "queue": queue,
    }


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--radar-root", type=Path, default=Path("data/era_radar"))
    parser.add_argument("--company-map", type=Path, default=Path("data/research_mapping/company_industry_map.csv"))
    parser.add_argument("--links", type=Path, default=Path("config/era_radar_industry_links.json"))
    parser.add_argument("--output", type=Path, default=Path("data/era_radar/research_handoff/latest.json"))
    args = parser.parse_args(argv)

    snapshot = _load_json(args.radar_root / "latest.json")
    snapshot_id = str(snapshot.get("snapshot_id") or "")
    if not snapshot_id:
        raise ValueError("Era Radar latest snapshot has no snapshot_id")
    evidence_bundle = _load_json(args.radar_root / "evidence" / f"{snapshot_id}.json")
    evidence_rows = evidence_bundle.get("records") or []
    if not isinstance(evidence_rows, list):
        raise ValueError("Era Radar evidence bundle records must be a list")
    with args.company_map.open("r", encoding="utf-8-sig", newline="") as handle:
        company_rows = list(csv.DictReader(handle))

    payload = build_handoff_queue(snapshot, evidence_rows, company_rows, _load_json(args.links))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "radar_snapshot_id": payload["radar_snapshot_id"],
        "queue_count": payload["queue_count"],
        "trigger_full_authority_research": payload["trigger_full_authority_research"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
