from __future__ import annotations

from pathlib import Path

from src.strategies.genge_opportunity_discovery.canonical_holdings_reconciliation import (
    HOLDINGS_IN_SYNC,
    HOLDINGS_OUT_OF_SYNC,
    reconcile_holdings,
)
from src.strategies.genge_opportunity_discovery.canonical_snapshot import (
    PRODUCTION_BRIDGE,
    PRODUCTION_VERSION,
    build_snapshot,
)


def _snapshot(quantity: str = "300") -> dict:
    production = [
        {
            "code": "603369",
            "stock_name": "今世缘",
            "decision_scope": "HOLDING",
            "production_action": "HOLD_REVIEW",
            "production_model_version": PRODUCTION_VERSION,
            "v311_production_bridge": PRODUCTION_BRIDGE,
            "strict_pit_refresh_applied": "True",
            "upstream_policy_reused": "False",
            "no_auto_trade": "True",
            "current_price": "28.10",
            "decision_date": "2026-08-27",
            "price_date": "2026-08-26",
            "confirmed_quantity": quantity,
        }
    ]
    return build_snapshot(
        [],
        [],
        production,
        source_kind="every-industry",
        source_run_id="123",
        upstream_run_id="456",
        generated_at="2026-08-27T03:00:00+00:00",
        research_as_of="2026-08-27T03:00:00+00:00",
        source_hashes={
            "discovery_csv": "a" * 64,
            "deep_review_csv": "b" * 64,
            "production_csv": "c" * 64,
        },
    )


def _write_holdings(path: Path, rows: list[tuple[str, str, str]]) -> None:
    lines = [
        "# CURRENT_HOLDINGS",
        "",
        "| Code | Name | Quantity | Average cost (CNY) | Status | Evidence date |",
        "| --- | --- | ---: | ---: | --- | --- |",
    ]
    for code, name, quantity in rows:
        lines.append(f"| {code} | {name} | {quantity} | 29.5003 | HELD | 2026-08-27 |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_holdings_in_sync_when_codes_and_quantities_match(tmp_path: Path) -> None:
    holdings = tmp_path / "CURRENT_HOLDINGS.md"
    _write_holdings(holdings, [("603369", "今世缘", "300")])

    result = reconcile_holdings(_snapshot("300"), holdings)

    assert result["status"] == HOLDINGS_IN_SYNC
    assert result["in_sync"] is True
    assert result["formal_holding_actions_currently_usable"] is True
    assert result["candidate_formal_actions_affected_by_holdings_mismatch"] is False


def test_quantity_change_marks_holdings_out_of_sync(tmp_path: Path) -> None:
    holdings = tmp_path / "CURRENT_HOLDINGS.md"
    _write_holdings(holdings, [("603369", "今世缘", "400")])

    result = reconcile_holdings(_snapshot("300"), holdings)

    assert result["status"] == HOLDINGS_OUT_OF_SYNC
    assert result["formal_holding_actions_currently_usable"] is False
    assert result["quantity_mismatches"] == [
        {"code": "603369", "current_quantity": "400", "canonical_quantity": "300"}
    ]


def test_new_current_holding_without_canonical_action_fails_closed_for_holdings(tmp_path: Path) -> None:
    holdings = tmp_path / "CURRENT_HOLDINGS.md"
    _write_holdings(
        holdings,
        [
            ("603369", "今世缘", "300"),
            ("600276", "恒瑞医药", "100"),
        ],
    )

    result = reconcile_holdings(_snapshot("300"), holdings)

    assert result["status"] == HOLDINGS_OUT_OF_SYNC
    assert result["current_not_in_canonical"] == ["600276"]
    assert result["candidate_formal_actions_affected_by_holdings_mismatch"] is False


def test_canonical_holding_missing_from_current_portfolio_is_out_of_sync(tmp_path: Path) -> None:
    holdings = tmp_path / "CURRENT_HOLDINGS.md"
    _write_holdings(holdings, [])

    result = reconcile_holdings(_snapshot("300"), holdings)

    assert result["status"] == HOLDINGS_OUT_OF_SYNC
    assert result["canonical_not_in_current"] == ["603369"]
    assert result["formal_holding_actions_currently_usable"] is False
