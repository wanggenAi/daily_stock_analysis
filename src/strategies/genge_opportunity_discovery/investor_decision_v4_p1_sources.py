"""P1 additive read-only source reconciliation for V4; no execution authority.

The *existing* V3 dashboard and finalized Canonical remain decision sources.
P1 enriches the presentation with evidence dates and hard-blocking diagnostics;
it never grants current trade executability from a quote, position or lifecycle.
"""
from __future__ import annotations

from datetime import datetime
from urllib.parse import urlsplit
from typing import Any, Mapping

from .investor_decision_v4_projection import project_v4_p0

CONTRACT = "GEN_GE_INVESTOR_PRESENTATION_V4_P1_SOURCES"

_OFFICIAL_ISSUER_HOSTS = frozenset({
    "static.cninfo.com.cn", "www.cninfo.com.cn", "www.sse.com.cn",
    "static.sse.com.cn", "www.szse.cn", "disc.static.szse.cn",
})


def _official_original_url(value: Any) -> bool:
    """Accept documented original-host URLs only; HTTPS lookalikes fail closed."""
    if not isinstance(value, str):
        return False
    try:
        url = urlsplit(value)
        return url.scheme == "https" and url.hostname in _OFFICIAL_ISSUER_HOSTS
    except ValueError:
        return False



def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _iso(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return result if result.tzinfo is not None else None
    except ValueError:
        return None


def project_v4_p1_sources(
    dashboard: Mapping[str, Any],
    decision_center: Mapping[str, Any] | None = None,
    era_radar: Mapping[str, Any] | None = None,
    *,
    broker_quotes: Mapping[str, Any] | None = None,
    confirmed_positions: Mapping[str, Any] | None = None,
    execution_state: Mapping[str, Any] | None = None,
    confirmed_funds: Mapping[str, Any] | None = None,
    official_events: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Attach dated source evidence; no output represents executable orders.

    confirmed_positions format is a parsed user-confirmed broker source with
    `observed_at` and `positions` items {code, quantity, available_shares}.
    Missing user confirmation must remain UNKNOWN, not an empty account.
    official_events must already be independently verified upstream; a proposal
    is never presented as an approved meeting outcome.
    """
    funds = _mapping(confirmed_funds)
    funds_verified = funds.get("status") == "USER_CONFIRMED" and _iso(funds.get("as_of")) is not None
    view = project_v4_p0(
        dashboard, decision_center, era_radar,
        confirmed_funds_status="CONFIRMED" if funds_verified else "LATEST_HOLDINGS_NOT_PERSISTED",
    )
    quotes = _mapping(broker_quotes)
    positions = _mapping(confirmed_positions)
    consumed = _mapping(execution_state)
    quote_timestamp = _iso(quotes.get("observed_at"))
    position_timestamp = _iso(positions.get("observed_at"))
    quote_map = {str(q.get("code")): q for q in quotes.get("quotes", [])
                 if isinstance(q, Mapping) and q.get("code")}
    position_map = {str(p.get("code")): p for p in positions.get("positions", [])
                    if isinstance(p, Mapping) and p.get("code")}
    quote_source_valid = (
        quotes.get("no_auto_trade") is True
        and quotes.get("formal_trading_authority") is False
        and quotes.get("evidence_authority") == "USER_CONFIRMED_BROKER_SCREENSHOT"
        and quote_timestamp is not None
    )
    position_source_valid = (
        positions.get("evidence_authority") == "USER_CONFIRMED_BROKER_SCREENSHOT"
        and positions.get("no_auto_trade") is True
        and position_timestamp is not None
    )
    consumed_valid = consumed.get("no_auto_trade") is True and isinstance(consumed.get("consumptions"), list)
    consumptions = consumed.get("consumptions", []) if consumed_valid else []
    for row in view["holdings"]:
        code = str(row.get("code") or "")
        q, p = _mapping(quote_map.get(code)), _mapping(position_map.get(code))
        qt = _iso(q.get("observed_at"))
        quote_matches = (quote_source_valid and qt is not None and
                         qt == quote_timestamp and q.get("status") == "OK"
                         and isinstance(q.get("latest_price"), (int, float))
                         and q["latest_price"] > 0)
        # Market as-of and quote date must be identical before labeling a
        # quotation same-session. Same-session is NOT sufficient for trading.
        market_date = str(view["feeds"]["market"]["as_of"] or "")
        same_session = bool(quote_matches and qt.date().isoformat() == market_date)
        position_matches = (
            position_source_valid and isinstance(p.get("quantity"), int)
            and p.get("quantity") == row.get("quantity")
            and isinstance(p.get("available_shares"), int)
            and 0 <= p["available_shares"] <= p["quantity"]
        )
        row["broker_quote"] = {
            "price": q.get("latest_price") if quote_matches else None,
            "as_of": qt.isoformat() if quote_matches else None,
            "source": "data/manual_execution_quotes/latest.json" if quote_matches else None,
            "same_market_session": same_session,
            "freshness": "SAME_SESSION_DISPLAY_ONLY" if same_session else "STALE_OR_MISSING",
        }
        row["broker_position"] = {
            "as_of": position_timestamp.isoformat() if position_matches else None,
            "quantity": p.get("quantity") if position_matches else None,
            "available_shares_at_observation": p.get("available_shares") if position_matches else None,
            "status": "MATCHED_HISTORICAL_DISPLAY_ONLY" if position_matches else "UNVERIFIED",
        }
        row["authority_consumptions"] = [
            {"canonical_snapshot_id": c.get("canonical_snapshot_id"),
             "authorization_type": c.get("authorization_type"),
             "consumed_shares": c.get("consumed_shares"),
             "consumed_at": c.get("consumed_at")}
            for c in consumptions if isinstance(c, Mapping) and str(c.get("code")) == code
        ]
        row["execution_eligibility"] = "NOT_ESTABLISHED"
        row["executable_shares"] = 0
        row["lot_t1_status"] = "REQUIRES_LIVE_BROKER_AND_AUTHORITY_VALIDATION"
        row["recorded_action_not_order"] = True
    validated_events = []
    for event in official_events or []:
        if not isinstance(event, Mapping):
            continue
        publication = _iso(event.get("publication_at"))
        original = event.get("original_url")
        if not (publication and _official_original_url(original)
                and event.get("original_document_verified") is True):
            continue
        outcome = str(event.get("outcome_status") or "UNKNOWN").upper()
        stage = str(event.get("stage") or "UNKNOWN").upper()
        verified_approval = bool(
            stage == "RESOLUTION" and outcome == "APPROVED"
            and _iso(event.get("outcome_at")) is not None
            and event.get("outcome_document_verified") is True
        )
        validated_events.append({
            "code": event.get("code"), "title": event.get("title"),
            "original_url": original, "publication_at": publication.isoformat(),
            "stage": stage, "outcome": "APPROVED" if verified_approval else
            ("PROPOSED_NOT_APPROVED" if stage == "PROPOSAL" else "UNVERIFIED_OUTCOME"),
            "outcome_at": event.get("outcome_at") if verified_approval else None,
            "trade_authority": False,
        })
    view["contract_version"] = CONTRACT
    view["feeds"]["quotes"] = {"as_of": quote_timestamp.isoformat() if quote_source_valid else None,
                                 "freshness": "HISTORICAL_DISPLAY_ONLY" if quote_source_valid else "MISSING",
                                 "fallback": "NO_EXECUTION"}
    view["feeds"]["positions"] = {"as_of": position_timestamp.isoformat() if position_source_valid else None,
                                    "freshness": "HISTORICAL_DISPLAY_ONLY" if position_source_valid else "MISSING",
                                    "fallback": "NO_NEW_POSITION_INFERENCE"}
    view["feeds"]["execution_consumption"] = {
        "as_of": consumed.get("as_of") if consumed_valid else None,
        "freshness": "PERSISTED_HISTORICAL" if consumed_valid else "UNKNOWN",
        "fallback": "NO_REUSED_AUTHORIZATION",
    }
    view["feeds"]["official_events"] = {"as_of": None, "freshness": "PER_EVENT_DATED",
                                          "fallback": "NO_APPROVAL_INFERENCE"}
    view["confirmed_fund_positions"] = funds.get("positions") if funds_verified else None
    view["official_events"] = validated_events
    view["action_status"] = "NO_EXECUTABLE_ACTION_P1_SOURCE_RECONCILIATION_ONLY"
    view["formal_buy_now"] = []
    view["formal_wait_price"] = []
    view["planned_immediate_cash_cny"] = 0
    return view
