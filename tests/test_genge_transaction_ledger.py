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


def _snapshot(txid, code, name, qty, average_cost):
    return {
        "transaction_id": txid,
        "event": "POSITION_SNAPSHOT",
        "code": code,
        "name": name,
        "quantity": qty,
        "average_cost": average_cost,
        "effective_date": "2026-09-01",
        "evidence_source": "confirmed holdings fixture",
        "confirmed_at": "2026-09-01T05:33:00Z",
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


def test_position_snapshot_reconciles_quantity_and_cost_without_fake_trade():
    holdings = project_holdings([
        _tx("old-open", "OPENING_POSITION", 200, 23.1258),
        _snapshot("nari-snapshot", "600406", "国电南瑞", 200, 23.1253),
        _snapshot("pingan-snapshot", "601318", "中国平安", 300, 57.1676),
        _snapshot("closed-snapshot", "603369", "今世缘", 0, 0),
    ])
    assert holdings["600406"]["confirmed_quantity"] == "200"
    assert holdings["600406"]["average_cost"] == "23.1253"
    assert holdings["601318"]["confirmed_quantity"] == "300"
    assert holdings["601318"]["average_cost"] == "57.1676"
    assert "603369" not in holdings


def test_zero_quantity_is_only_allowed_for_position_snapshot():
    assert project_holdings([_snapshot("closed", "600276", "恒瑞医药", 0, 0)]) == {}
    with pytest.raises(ValueError, match="transaction quantity must be positive"):
        project_holdings([_tx("zero-buy", "BUY", 0, 23)])


def test_positive_position_snapshot_requires_average_cost():
    with pytest.raises(ValueError, match="positive average_cost"):
        project_holdings([_snapshot("bad-snapshot", "601318", "中国平安", 300, 0)])
