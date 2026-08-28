from pathlib import Path

import pytest

from src.strategies.genge_opportunity_discovery.transaction_ledger import project_holdings


def _tx(txid, event, qty, price):
    return {
        "transaction_id": txid,
        "event": event,
        "code": "600406",
        "name": "国电南瑞",
        "quantity": qty,
        "price": price,
        "trade_date": "2026-08-25",
        "evidence_source": "fixture",
        "confirmed_at": "2026-08-25T08:00:00Z",
    }


def test_projection_tracks_weighted_cost_and_sell():
    holdings = project_holdings([
        _tx("open", "OPENING_POSITION", 200, 23.1258),
        _tx("buy", "BUY", 100, 24.0),
        _tx("sell", "SELL", 50, 25.0),
    ])
    row = holdings["600406"]
    assert row["confirmed_quantity"] == "250"
    assert row["source"] == "TRANSACTION_LEDGER_PROJECTION"


def test_projection_fails_closed_on_oversell():
    with pytest.raises(ValueError, match="exceeds"):
        project_holdings([_tx("open", "OPENING_POSITION", 100, 23), _tx("sell", "SELL", 200, 24)])
