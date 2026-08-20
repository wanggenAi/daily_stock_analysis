from __future__ import annotations

import csv
import json
from pathlib import Path

from src.strategies.genge_opportunity_discovery.sector_opportunity_engine import (
    build_sector_opportunities,
    write_sector_opportunity,
)


def _row(code: str, industry: str, *, r1: float, r5: float, r10: float,
         activity: float, ma20: bool, ma60: bool, state: str = "NEUTRAL",
         board: str = "SSE_MAIN") -> dict:
    return {
        "code": code,
        "stock_name": code,
        "industry": industry,
        "board": board,
        "return_1d_pct": r1,
        "return_5d_pct": r5,
        "return_10d_pct": r10,
        "volume_ratio_20": activity,
        "amount_ratio_20": activity,
        "above_ma20": ma20,
        "above_ma60": ma60,
        "price_volume_state": state,
        "exclusion_reason": "",
    }


def _fixture_rows() -> list[dict]:
    rows: list[dict] = []
    # Emerging: broad, fresh 1d relative strength, activity expansion, not extended on 5d.
    for i in range(6):
        rows.append(_row(
            f"6001{i:02d}", "Z_STRONG", r1=2.2 + i * 0.08, r5=3.0 + i * 0.2,
            r10=5.0 + i * 0.25, activity=1.45, ma20=True, ma60=True,
            state="ACCUMULATION",
        ))
    # Overheated: still strong, but already too extended to be a chase candidate.
    for i in range(6):
        rows.append(_row(
            f"3002{i:02d}", "M_OVERHEATED", r1=4.0 + i * 0.1, r5=13.0 + i * 0.3,
            r10=22.0 + i * 0.5, activity=1.7, ma20=True, ma60=True,
            state="ACCUMULATION", board="CHINEXT",
        ))
    # Weak/risk-off industry.
    for i in range(6):
        rows.append(_row(
            f"0003{i:02d}", "A_WEAK", r1=-2.2 - i * 0.1, r5=-5.0 - i * 0.2,
            r10=-8.0 - i * 0.3, activity=1.35, ma20=False, ma60=False,
            state="DISTRIBUTION",
        ))
    return rows


def test_sector_engine_prioritizes_fresh_strength_without_turning_it_into_hard_logic():
    rows = build_sector_opportunities(_fixture_rows())
    by_industry = {row["industry"]: row for row in rows}

    assert by_industry["Z_STRONG"]["sector_opportunity_state"] in {"EMERGING", "LEADING"}
    assert by_industry["Z_STRONG"]["sector_research_action"] == "PRIORITY_RESEARCH"
    assert by_industry["Z_STRONG"]["sector_rank"] < by_industry["A_WEAK"]["sector_rank"]
    assert by_industry["A_WEAK"]["sector_opportunity_state"] in {"WEAK", "RISK_OFF"}
    assert all(row["sector_strength_is_hard_logic"] is False for row in rows)
    assert all(row["formal_signal_eligible"] is False for row in rows)
    assert all(row["automatic_promotion_allowed"] is False for row in rows)
    assert all(row["no_auto_trade"] is True for row in rows)


def test_overheated_sector_is_visible_but_explicitly_not_a_chase():
    rows = build_sector_opportunities(_fixture_rows())
    hot = next(row for row in rows if row["industry"] == "M_OVERHEATED")

    assert hot["sector_opportunity_state"] == "OVERHEATED"
    assert hot["sector_research_action"] == "WATCH_AVOID_CHASE"
    assert hot["sector_overheated"] is True
    assert hot["sector_strength_is_hard_logic"] is False


def test_write_sector_opportunity_keeps_every_industry_and_contract(tmp_path: Path):
    report = tmp_path / "report"
    report.mkdir()
    source = report / "all_a_quant_screen.csv"
    rows = _fixture_rows()
    fields = sorted({key for row in rows for key in row})
    with source.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    out = tmp_path / "sector"
    written = write_sector_opportunity(report, out)
    summary = json.loads((out / "sector_opportunity_summary.json").read_text(encoding="utf-8"))
    csv_rows = list(csv.DictReader((out / "sector_opportunity.csv").open(encoding="utf-8")))

    assert len(written) == 3
    assert len(csv_rows) == 3
    assert {row["industry"] for row in csv_rows} == {"Z_STRONG", "M_OVERHEATED", "A_WEAK"}
    assert summary["industry_count"] == 3
    assert summary["industry_first_discovery"] is True
    assert summary["sector_strength_is_hard_logic"] is False
    assert summary["sector_strength_can_create_buy"] is False
    assert summary["all_industries_remain_visible"] is True
    assert summary["no_auto_trade"] is True
