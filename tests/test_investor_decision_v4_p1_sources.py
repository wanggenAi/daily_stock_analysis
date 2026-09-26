"""P1 source timestamps and consumption regression tests."""
from src.strategies.genge_opportunity_discovery.investor_decision_v4_p1_sources import project_v4_p1_sources


def base():
    return {
        "no_auto_trade": True, "formal_action_source": "FINALIZED_CANONICAL_ONLY",
        "formal_action_recomputed": False, "canonical_snapshot_id": "s1",
        "latest_trade_date": "2026-09-24", "market": {"as_of_date": "2026-09-24", "status": "RED"},
        "stock_portfolio": {"rows": [{"code": "603993", "quantity": 1100, "formal_action": "HOLD",
                                      "action_authority": "FORMAL", "formal_action_currently_usable": True}]},
        "formal_holding_actions_currently_usable": True,
        "terminal_opportunities": {"buy_now": [{"code": "TEST"}]},
        "capital_deployment": {"available_cash_cny": 50000},
    }


def quotes(as_of="2026-09-22T12:17:51+08:00"):
    return {
        "no_auto_trade": True, "formal_trading_authority": False,
        "evidence_authority": "USER_CONFIRMED_BROKER_SCREENSHOT", "observed_at": as_of,
        "quotes": [{"code": "603993", "latest_price": 17.86, "observed_at": as_of, "status": "OK"}],
    }


def positions():
    return {
        "no_auto_trade": True, "evidence_authority": "USER_CONFIRMED_BROKER_SCREENSHOT",
        "observed_at": "2026-09-22T12:17:51+08:00",
        "positions": [{"code": "603993", "quantity": 1100, "available_shares": 1100}],
    }


def test_historical_quote_is_not_executable_and_funds_are_unknown():
    out = project_v4_p1_sources(base(), broker_quotes=quotes(), confirmed_positions=positions())
    holding = out["holdings"][0]
    assert holding["broker_quote"]["freshness"] == "STALE_OR_MISSING"
    assert holding["broker_position"]["status"] == "MATCHED_HISTORICAL_DISPLAY_ONLY"
    assert holding["executable_shares"] == 0
    assert out["funds_status"] == "LATEST_HOLDINGS_NOT_PERSISTED"
    assert out["formal_buy_now"] == []
    assert out["planned_immediate_cash_cny"] == 0


def test_same_session_quote_still_not_order():
    stamp = "2026-09-24T11:15:00+08:00"
    out = project_v4_p1_sources(base(), broker_quotes=quotes(stamp))
    assert out["holdings"][0]["broker_quote"]["same_market_session"] is True
    assert out["holdings"][0]["executable_shares"] == 0


def test_unknown_position_or_bad_quote_does_not_imply_zero_or_permission():
    source = positions()
    source["positions"][0]["quantity"] = 1000
    q = quotes()
    q["quotes"][0]["latest_price"] = -1
    out = project_v4_p1_sources(base(), broker_quotes=q, confirmed_positions=source)
    assert out["holdings"][0]["broker_position"]["status"] == "UNVERIFIED"
    assert out["holdings"][0]["broker_quote"]["price"] is None
    assert out["holdings"][0]["executable_shares"] == 0


def test_consumption_is_exposed_without_rearming_authority():
    consumed = {"no_auto_trade": True, "as_of": "2026-09-15T11:38:01+08:00",
                "consumptions": [{"code": "603993", "canonical_snapshot_id": "old",
                                  "authorization_type": "HOLDING_STAGED_ADD", "consumed_shares": 100}]}
    out = project_v4_p1_sources(base(), execution_state=consumed)
    assert out["holdings"][0]["authority_consumptions"][0]["consumed_shares"] == 100
    assert out["holdings"][0]["executable_shares"] == 0


def test_proposals_are_not_resolutions_and_unsupported_events_are_excluded():
    events = [
        {"code": "603993", "stage": "PROPOSAL", "outcome_status": "APPROVED",
         "original_url": "https://static.cninfo.com.cn/finalpage/2026-09-23/proposal.pdf",
         "original_document_verified": True, "publication_at": "2026-09-23T09:00:00+08:00"},
        {"code": "603993", "stage": "RESOLUTION", "outcome_status": "APPROVED",
         "original_url": "https://static.sse.com.cn/disclosure/listedinfo/result.pdf",
         "original_document_verified": True, "outcome_document_verified": True,
         "publication_at": "2026-09-24T09:00:00+08:00",
         "outcome_at": "2026-09-24T09:00:00+08:00"},
        {"stage": "PROPOSAL", "outcome_status": "APPROVED", "original_url": "nonsource",
         "publication_at": "bad"},
    ]
    out = project_v4_p1_sources(base(), official_events=events)
    assert [e["outcome"] for e in out["official_events"]] == ["PROPOSED_NOT_APPROVED", "APPROVED"]
    assert all(e["trade_authority"] is False for e in out["official_events"])


def test_projection_is_repeatable_without_mutating_sources():
    source, q, p = base(), quotes(), positions()
    snapshot = (repr(source), repr(q), repr(p))
    assert project_v4_p1_sources(source, broker_quotes=q, confirmed_positions=p) == (
        project_v4_p1_sources(source, broker_quotes=q, confirmed_positions=p)
    )
    assert snapshot == (repr(source), repr(q), repr(p))


def test_unverified_or_spoofed_official_event_never_becomes_approval():
    base_event = {
        "code": "603993", "stage": "RESOLUTION", "outcome_status": "APPROVED",
        "publication_at": "2026-09-24T09:00:00+08:00",
        "outcome_at": "2026-09-24T09:00:00+08:00",
        "original_url": "https://static.sse.com.cn/disclosure/approved.pdf",
    }
    spoofed = {**base_event, "original_url": "https://static.sse.com.cn.evil.test/approved.pdf",
               "original_document_verified": True, "outcome_document_verified": True}
    no_source_proof = {**base_event, "outcome_document_verified": True}
    no_outcome_proof = {**base_event, "original_document_verified": True}
    out = project_v4_p1_sources(base(), official_events=[
        spoofed, no_source_proof, no_outcome_proof,
    ])
    assert len(out["official_events"]) == 1
    assert out["official_events"][0]["outcome"] == "UNVERIFIED_OUTCOME"
    assert out["formal_buy_now"] == []
    assert out["holdings"][0]["executable_shares"] == 0
