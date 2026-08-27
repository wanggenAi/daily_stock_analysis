from __future__ import annotations

from src.strategies.genge_opportunity_discovery.production_shortlist import build_shortlist


def test_broad_unknown_research_rows_do_not_enter_production_refresh() -> None:
    rows = build_shortlist(
        [
            {
                "code": "600001",
                "v31_a_eligible": "False",
                "v31_buy_ready": "False",
                "v31_candidate_class": "",
                "v31_hard_gate_unknowns": "long_term_demand;moat",
            },
            {
                "code": "600002",
                "v31_a_eligible": "True",
                "v31_buy_ready": "False",
            },
        ]
    )

    assert [row["code"] for row in rows] == ["600002"]
    assert rows[0]["production_shortlist_scope"] == "CANDIDATE"


def test_confirmed_holding_is_always_reunderwritten_and_reuses_dated_evidence() -> None:
    rows = build_shortlist(
        [],
        holding_rows=[{"code": "600406", "stock_name": "国电南瑞"}],
        evidence_rows=[
            {
                "code": "600406",
                "raw_latest_close": "23.06",
                "raw_latest_trade_date": "2026-08-27",
            }
        ],
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["production_shortlist_scope"] == "HOLDING"
    assert row["raw_latest_close"] == "23.06"
    assert row["raw_latest_trade_date"] == "2026-08-27"
    assert row["production_shortlist_price_provenance"] == "DATED_SAME_RUN_EVIDENCE"


def test_a_candidate_keeps_review_evidence_but_receives_same_run_price_provenance() -> None:
    rows = build_shortlist(
        [
            {
                "code": "603993",
                "stock_name": "洛阳钼业",
                "v31_a_eligible": "True",
                "v31_long_term_demand_status": "PASS",
            }
        ],
        evidence_rows=[
            {
                "code": "603993",
                "stock_name": "old name",
                "raw_latest_close": "18.42",
                "raw_latest_trade_date": "2026-08-27",
            }
        ],
    )

    row = rows[0]
    assert row["stock_name"] == "洛阳钼业"
    assert row["v31_long_term_demand_status"] == "PASS"
    assert row["raw_latest_close"] == "18.42"
    assert row["production_shortlist_price_provenance"] == "DATED_SAME_RUN_EVIDENCE"
