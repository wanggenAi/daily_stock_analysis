"""Bounded, read-only H1 handoff for the existing V4 investor publisher.

The handoff is navigation and dated research, never an independent trade engine.
Only the existing authorized Canonical can supply the reference decision epoch.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

CONTRACT = "GEN_GE_INVESTOR_CHATGPT_HANDOFF_V1"
FILES = {
    "dashboard": "data/investor_decision_dashboard/latest.json",
    "decision_center": "data/decision_center/latest.json",
    "era_radar": "data/era_radar/latest.json",
    "planning_capital": "CURRENT_CAPITAL.json",
    "fund_register": "CURRENT_FUNDS.md",
    "broker_quotes": "data/manual_execution_quotes/latest.json",
    "outcomes": "data/formal_decision_outcomes/latest.json",
}


def obj(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, dict) else {}


def rows(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Expected JSON object: " + str(path))
    return value


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def numeric_id(value: str | None) -> str | None:
    return value if isinstance(value, str) and value.isascii() and value.isdecimal() else None


def build_handoff(root: Path, canonical_file: Path, *,
                  finalizer_run_id: str | None = None,
                  market_run_id: str | None = None,
                  market_artifact_id: str | None = None) -> dict[str, Any]:
    dashboard = read_json(root / FILES["dashboard"])
    canonical = read_json(canonical_file)
    snapshot = str(dashboard.get("canonical_snapshot_id") or "")
    run_id = str(dashboard.get("canonical_source_run_id") or "")
    market_date = str(dashboard.get("latest_trade_date") or "")
    if (not snapshot or not run_id or not market_date
            or dashboard.get("formal_action_source") != "FINALIZED_CANONICAL_ONLY"
            or dashboard.get("formal_action_recomputed") is not False
            or dashboard.get("no_auto_trade") is not True
            or canonical.get("snapshot_id") != snapshot
            or str(canonical.get("source_run_id") or "") != run_id):
        raise ValueError("Authoritative Canonical/dashboard mismatch: refusing publication")
    canonical_date = str(canonical.get("latest_trade_date") or canonical.get("trade_date") or "")
    if canonical_date and canonical_date != market_date:
        raise ValueError("Canonical/dashboard trade-date mismatch")

    def optional(name: str) -> dict[str, Any]:
        path = root / FILES[name]
        return read_json(path) if path.is_file() and path.suffix == ".json" else {}

    center = optional("decision_center")
    radar = optional("era_radar")
    capital = optional("planning_capital")
    quotes = optional("broker_quotes")
    freshness = obj(dashboard.get("freshness_contract"))
    market = obj(dashboard.get("market"))
    portfolio = obj(dashboard.get("stock_portfolio"))
    funds = obj(dashboard.get("fund_portfolio"))
    summary = obj(dashboard.get("decision_summary"))
    terminal = obj(dashboard.get("terminal_opportunities"))
    research = obj(dashboard.get("terminal_research_snapshot"))
    reconciliation = obj(dashboard.get("holdings_reconciliation"))
    event = obj(dashboard.get("event_review"))
    center_matches = bool(
        center and center.get("canonical_snapshot_id") == snapshot
        and center.get("latest_trade_date") == market_date
        and (not center.get("canonical_source_run_id")
             or str(center["canonical_source_run_id"]) == run_id))
    market_matches = bool(
        (not market.get("as_of_date") or market["as_of_date"] == market_date)
        and (not freshness.get("canonical_source_run_id")
             or str(freshness["canonical_source_run_id"]) == run_id)
        and (not freshness.get("canonical_latest_trade_date")
             or freshness["canonical_latest_trade_date"] == market_date))
    fresh = bool(market_matches and freshness.get("status") == "FRESH"
                 and freshness.get("fresh") is True
                 and dashboard.get("formal_new_exposure_allowed") is True)
    verified_radar = bool(radar and radar.get("formal_trading_authority") is False
                          and radar.get("no_auto_trade") is True)
    quote_lineage = bool(
        quotes.get("canonical_snapshot_id") == snapshot
        and str(quotes.get("canonical_source_run_id") or "") == run_id
        and quotes.get("evidence_authority") == "USER_CONFIRMED_BROKER_SCREENSHOT"
        and quotes.get("formal_trading_authority") is False
        and quotes.get("no_auto_trade") is True)
    planning = (capital.get("planning_cash_cny")
                if capital.get("status") == "USER_CONFIRMED_FLOOR" else None)
    blockers = ["NO_CURRENT_BROKER_CASH_OR_POSITION_PROOF",
                "NO_CURRENT_EXECUTABLE_QUOTE_PROOF",
                "NO_INDEPENDENT_EXCHANGE_CALENDAR_VERIFICATION"]
    if not fresh:
        blockers.append("STALE_OR_UNVERIFIED_MARKET_SESSION")
    if not center_matches:
        blockers.append("CENTER_DIFFERENT_EPOCH_OR_MISSING")
    if reconciliation.get("in_sync") is not True:
        blockers.append("HOLDINGS_RECONCILIATION_NOT_PROVEN")
    if funds.get("status") != "CONFIRMED":
        blockers.append("FUND_POSITION_CONFIRMATION_MISSING")
    if not market_matches:
        blockers.append("CROSS_FEED_MARKET_LINEAGE_MISMATCH")

    all_holdings = rows(portfolio.get("rows"))
    holdings = []
    for holding in all_holdings[:16]:
        if not isinstance(holding, dict):
            continue
        action = (holding.get("formal_action") if
                  reconciliation.get("in_sync") is True
                  and holding.get("action_authority") == "FORMAL"
                  and holding.get("formal_action_currently_usable") is True else None)
        holdings.append({
            "code": str(holding.get("code") or ""),
            "name": str(holding.get("name") or ""),
            "last_reported_quantity": holding.get("quantity"),
            "frozen_reference_price": holding.get("current_price"),
            "reference_as_of": market_date,
            "value_range": [holding.get("value_low"), holding.get("value_high")],
            "valuation_confidence": holding.get("valuation_confidence") or "UNKNOWN",
            "recorded_formal_action": action,
            "presentation": "HISTORICAL_ONLY_NOT_AN_ORDER",
            "executable_shares": 0,
            "reason_codes": holding.get("reason_codes"),
            "source_path": FILES["dashboard"],
        })
    source_files = {}
    for name, rel in FILES.items():
        path = root / rel
        source_files[name] = ({"path": rel, "sha256": sha(path)} if path.is_file()
                              else {"path": rel, "status": "MISSING"})
    trends = [{
        "trend_id": str(t.get("trend_id") or ""),
        "lifecycle": str(t.get("lifecycle") or "UNKNOWN"),
        "as_of": radar.get("research_as_of"),
        "authority": "RESEARCH_ONLY",
        "source_path": FILES["era_radar"],
    } for t in rows(radar.get("trends"))[:5]
        if verified_radar and isinstance(t, dict)]
    # Exclude render-time, full raw source bytes and mutable Git SHAs from the
    # semantic identity. A mere re-render cannot become new market evidence.
    semantic = {
        "canonical_sha": sha(canonical_file), "market_date": market_date,
        "snapshot": snapshot, "run": run_id, "status": freshness.get("status"),
        "market_status": market.get("status"), "holdings": holdings,
        "formal_counts": [len(rows(terminal.get("buy_now"))),
                          len(rows(terminal.get("wait_price")))],
        "research_counts": [summary.get("research_buy_count"),
                            summary.get("research_gap_count")],
        "event_digest": event.get("signal_digest"),
        "radar_snapshot": radar.get("snapshot_id") if verified_radar else None,
        "quote_as_of": quotes.get("observed_at") if quote_lineage else None,
        "fund_status": funds.get("status"), "center_matches": center_matches,
    }
    epoch_id = hashlib.sha256(
        json.dumps(semantic, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:24]
    return {
        "contract_version": CONTRACT, "snapshot_id": epoch_id,
        "generated_at": dashboard.get("generated_at"),
        "market_session_as_of": market_date,
        "canonical_snapshot_id": snapshot, "canonical_source_run_id": run_id,
        "canonical_sha256": sha(canonical_file),
        "lineage": {
            "canonical_matches_dashboard": True,
            "canonical_trade_date_present": bool(canonical_date),
            "market_matches_dashboard": market_matches,
            "center_matches_dashboard": center_matches,
            "live_broker_positions_verified": False,
            "exchange_calendar_independently_verified": False,
        },
        "source_files": source_files,
        "production_provenance": {
            "finalizer_run_id": numeric_id(finalizer_run_id),
            "market_run_id": numeric_id(market_run_id),
            "market_artifact_id": numeric_id(market_artifact_id),
            "market_artifact_as_of_join": "UNVERIFIED",
        },
        "feeds": {
            "market_eod": {"as_of": market_date,
                           "status": "UPSTREAM_FRESH_CALENDAR_UNVERIFIED"
                           if fresh else "STALE_OR_UNVERIFIED",
                           "upstream_status": freshness.get("status") or "UNKNOWN",
                           "expected_min_trade_date": freshness.get("expected_min_trade_date")},
            "reference_quotes": {"as_of": market_date, "status": "FROZEN_CANONICAL_ONLY"},
            "executable_quotes": {"as_of": None, "status": "UNVERIFIED"},
            "dated_manual_quotes": {"as_of": quotes.get("observed_at") if quote_lineage else None,
                                    "status": "DATED_REFERENCE_ONLY" if quote_lineage
                                    else "MISSING_OR_WRONG_EPOCH"},
            "equities": {"as_of": market_date, "status": "REPO_RECONCILED_NOT_LIVE_BROKER"
                         if reconciliation.get("in_sync") is True else "UNVERIFIED"},
            "funds": {"as_of": None, "status": "UNVERIFIED" if funds.get("status") != "CONFIRMED"
                      else "REPO_CONFIRMED_NOT_LIVE_BROKER"},
            "planning_cash": {"as_of": capital.get("as_of") if planning is not None else None,
                              "amount_cny": planning, "status": "DATED_PLANNING_ONLY"
                              if planning is not None else "MISSING"},
            "broker_cash": {"as_of": None, "amount_cny": None, "status": "UNKNOWN"},
            "official_issuer": {"as_of": None, "status": "ORIGINAL_SOURCE_COVERAGE_NOT_PROVEN"},
            "formal_opportunities": {"as_of": market_date,
                                     "status": "NO_NEW_EXECUTION_VERIFIED_BY_HANDOFF"},
            "research_only": {"as_of": market_date, "status": "RESEARCH_ONLY"
                              if research.get("research_authority") == "RESEARCH_ONLY"
                              else "UNKNOWN"},
            "era_cycle": {"as_of": radar.get("research_as_of") if verified_radar else None,
                          "status": "DATED_RESEARCH_ONLY" if verified_radar else "UNVERIFIED"},
            "decision_outcomes": {"as_of": None, "status": "LINK_ONLY_NOT_REVALIDATED"
                                  if (root / FILES["outcomes"]).is_file() else "MISSING"},
            "realized_personal_pnl": {"as_of": None, "status": "UNKNOWN_NO_VERIFIED_FILLS"},
        },
        "holdings": holdings, "holdings_truncated": max(0, len(all_holdings)-16),
        "formal_buy_now": [], "formal_wait_price": [],
        "research_audit": {
            "upstream_formal_buy_now_count": len(rows(terminal.get("buy_now"))),
            "upstream_formal_wait_count": len(rows(terminal.get("wait_price"))),
            "research_buy_count": summary.get("research_buy_count"),
            "research_gap_count": summary.get("research_gap_count"),
            "research_is_not_formal": True,
        },
        "trend_research": trends,
        "event_audit": {"signal_digest": event.get("signal_digest"),
                        "closure_status": event.get("closure_status") or "UNKNOWN",
                        "verified_official_events": [],
                        "status": "NO_INDEPENDENT_ORIGINAL_OUTCOME_VERIFICATION"},
        "blocking_reasons": sorted(set(blockers)),
        "no_auto_trade": True,
    }


def render_markdown(m: Mapping[str, Any]) -> str:
    lines = [
        "# Investor V4 ChatGPT Web handoff", "",
        "This is a dated source index, not a live order sheet. ChatGPT Web is on demand only.", "",
        "Snapshot: " + str(m["snapshot_id"]),
        "Market as-of: " + str(m["market_session_as_of"]),
        "Generated at (not market freshness): " + str(m["generated_at"]),
        "Canonical/source run: " + str(m["canonical_snapshot_id"]) + " / "
        + str(m["canonical_source_run_id"]),
        "Market state: " + str(m["feeds"]["market_eod"]["status"]),
        "Current brokerage funds, executable prices and trade quantities: UNKNOWN / 0.", "",
        "## Existing holdings (historical reference, not an executable order)",
    ]
    for h in m["holdings"]:
        code = "".join(c for c in h["code"] if c.isdigit())[:8]
        action = "".join(c for c in str(h["recorded_formal_action"] or "UNVERIFIED")
                         if c.isascii() and (c.isalnum() or c == "_"))[:32]
        lines.append("- " + code + ": prior action " + action + "; frozen price "
                     + str(h["frozen_reference_price"]) + "; executable shares 0.")
    if not m["holdings"]:
        lines.append("- No reliable position rows available.")
    lines += [
        "", "## Research boundaries",
        "- New immediately executable Formal BUY: none verified in this handoff.",
        "- Historical research BUY and Jev opinions are never Formal authorization.",
        "- Planning cash is dated; broker-verified current cash is UNKNOWN.",
        "- Unverified issuer signal does not prove an approved resolution.",
        "- Era/cycle trend records are research-only.", "",
        "Blockers: " + ", ".join(m["blocking_reasons"]), "",
        "## Exact repository source references",
    ]
    for source in m["source_files"].values():
        if "sha256" in source:
            lines.append("- [" + source["path"] + "](https://github.com/wanggenAi/daily_stock_analysis/blob/main/" + source["path"] + ") (sha256 " + source["sha256"] + ")")
    lines += ["", "Verify current main and the machine handoff before following these paths.",
              "Drill into original documents only when independently verified.", ""]
    return "\n".join(lines)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, default=Path("."))
    p.add_argument("--canonical", type=Path, required=True)
    p.add_argument("--finalizer-run-id")
    p.add_argument("--market-run-id")
    p.add_argument("--market-artifact-id")
    p.add_argument("--json-output", type=Path, required=True)
    p.add_argument("--markdown-output", type=Path, required=True)
    args = p.parse_args()
    m = build_handoff(args.root, args.canonical,
                      finalizer_run_id=args.finalizer_run_id,
                      market_run_id=args.market_run_id,
                      market_artifact_id=args.market_artifact_id)
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    temp_json = args.json_output.with_suffix(".json.tmp")
    temp_md = args.markdown_output.with_suffix(".md.tmp")
    temp_json.write_text(json.dumps(m, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                         encoding="utf-8")
    temp_md.write_text(render_markdown(m), encoding="utf-8")
    os.replace(temp_json, args.json_output)
    os.replace(temp_md, args.markdown_output)
    print("H1 snapshot=" + m["snapshot_id"] + " as_of=" + m["market_session_as_of"]
          + " status=" + m["feeds"]["market_eod"]["status"]
          + " executable=UNVERIFIED")


if __name__ == "__main__":
    main()
