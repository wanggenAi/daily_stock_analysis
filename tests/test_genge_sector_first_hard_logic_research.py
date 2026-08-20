from __future__ import annotations

import csv
import json
from pathlib import Path

from src.strategies.genge_opportunity_discovery.sector_first_hard_logic_research import (
    order_industries,
    run_sector_first_research,
)


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _pass_payload(code: str, name: str) -> dict:
    return {
        "research_state": "PASS",
        "selected_code": code,
        "selected_name": name,
        "hard_logic_structural_driver": "行业未来五年渗透率持续提升并带来结构性增量需求",
        "hard_logic_supply_constraint": "核心供给和客户认证周期较长，有效供给扩张受约束",
        "hard_logic_company_edge": "公司拥有核心工艺和头部客户认证，竞争优势难以快速复制",
        "hard_logic_profit_transmission": "行业需求增长带动销量和产品价值量提升，并经规模效应传导到利润与现金流",
        "hard_logic_invalidation": "若行业渗透率长期停滞且核心客户份额持续下降则逻辑失效",
        "hard_logic_duration_years": 5,
        "hard_logic_persistence": "结构需求、认证和产能壁垒预计持续五年以上",
        "hard_logic_evidence_sources": [
            {"title": "公司年度报告", "url": "https://example.com/report"}
        ],
        "research_summary": "结构逻辑通过，价格与估值另行判断。",
    }


def test_sector_rank_controls_research_order_not_alphabetical_order():
    ordered = order_industries(
        ["A_WEAK", "Z_STRONG", "M_MIDDLE"],
        {
            "Z_STRONG": {"sector_rank": "1"},
            "M_MIDDLE": {"sector_rank": "2"},
            "A_WEAK": {"sector_rank": "3"},
        },
    )
    assert ordered == ["Z_STRONG", "M_MIDDLE", "A_WEAK"]


def test_sector_first_runner_researches_all_industries_in_sector_priority(tmp_path: Path):
    candidates = tmp_path / "industry_top_candidates.csv"
    raw = tmp_path / "all_a_quant_screen.csv"
    sector = tmp_path / "sector_opportunity.csv"
    out = tmp_path / "out"

    _write_csv(
        candidates,
        [
            {"industry": "A_WEAK", "code": "600001", "stock_name": "弱行业公司", "industry_research_rank": 1},
            {"industry": "Z_STRONG", "code": "000001", "stock_name": "强行业公司", "industry_research_rank": 1},
        ],
    )
    _write_csv(
        raw,
        [
            {"industry": "A_WEAK", "code": "600001", "stock_name": "弱行业公司"},
            {"industry": "Z_STRONG", "code": "000001", "stock_name": "强行业公司"},
        ],
    )
    _write_csv(
        sector,
        [
            {
                "industry": "Z_STRONG",
                "sector_rank": 1,
                "sector_opportunity_state": "EMERGING",
                "sector_research_action": "PRIORITY_RESEARCH",
                "sector_opportunity_score": 76,
                "advance_ratio": 0.83,
                "excess_return_1d_pct": 2.1,
                "excess_return_5d_pct": 1.8,
                "expanding_activity_ratio": 0.67,
                "sector_overheated": False,
            },
            {
                "industry": "A_WEAK",
                "sector_rank": 2,
                "sector_opportunity_state": "WEAK",
                "sector_research_action": "LOW_PRIORITY_RESEARCH",
                "sector_opportunity_score": 31,
                "advance_ratio": 0.17,
                "excess_return_1d_pct": -1.8,
                "excess_return_5d_pct": -3.2,
                "expanding_activity_ratio": 0.50,
                "sector_overheated": False,
            },
        ],
    )

    call_order: list[str] = []

    def fake_call(industry, seeds):
        call_order.append(industry)
        return json.dumps(
            _pass_payload(seeds[0]["code"], seeds[0]["stock_name"]),
            ensure_ascii=False,
        )

    rows = run_sector_first_research(
        industry_candidates_csv=candidates,
        sector_opportunity_csv=sector,
        all_a_universe_csv=raw,
        output_dir=out,
        max_workers=1,
        research_call=fake_call,
    )

    assert call_order == ["Z_STRONG", "A_WEAK"]
    assert [row["industry"] for row in rows] == ["Z_STRONG", "A_WEAK"]
    assert len(rows) == 2
    assert rows[0]["sector_opportunity_state"] == "EMERGING"
    assert rows[1]["sector_opportunity_state"] == "WEAK"
    # A weak current market sector may still have a valid long-run hard logic;
    # sector strength is not itself part of the deterministic hard-logic gate.
    assert all(row["hard_logic_state"] == "PASS" for row in rows)

    summary = json.loads((out / "hard_logic_research_summary.json").read_text(encoding="utf-8"))
    assert summary["sector_opportunity_used"] is True
    assert summary["industry_first_discovery"] is True
    assert summary["sector_strength_is_hard_logic"] is False
    assert summary["sector_strength_can_create_buy"] is False
    assert summary["research_order"] == ["Z_STRONG", "A_WEAK"]
    assert summary["industry_count"] == 2
    assert summary["no_auto_trade"] is True


def test_hot_sector_does_not_bypass_missing_structural_evidence(tmp_path: Path):
    candidates = tmp_path / "industry_top_candidates.csv"
    raw = tmp_path / "all_a_quant_screen.csv"
    sector = tmp_path / "sector_opportunity.csv"
    out = tmp_path / "out"

    _write_csv(candidates, [{"industry": "HOT", "code": "600001", "stock_name": "热门公司"}])
    _write_csv(raw, [{"industry": "HOT", "code": "600001", "stock_name": "热门公司"}])
    _write_csv(
        sector,
        [{
            "industry": "HOT",
            "sector_rank": 1,
            "sector_opportunity_state": "LEADING",
            "sector_research_action": "PRIORITY_RESEARCH",
            "sector_opportunity_score": 92,
            "advance_ratio": 0.95,
            "excess_return_1d_pct": 4.5,
            "excess_return_5d_pct": 12.0,
            "expanding_activity_ratio": 0.9,
            "sector_overheated": False,
        }],
    )

    def fake_call(industry, seeds):
        payload = _pass_payload("600001", "热门公司")
        payload["hard_logic_company_edge"] = ""
        return json.dumps(payload, ensure_ascii=False)

    rows = run_sector_first_research(
        industry_candidates_csv=candidates,
        sector_opportunity_csv=sector,
        all_a_universe_csv=raw,
        output_dir=out,
        max_workers=1,
        research_call=fake_call,
    )

    assert rows[0]["sector_opportunity_state"] == "LEADING"
    assert rows[0]["research_state"] == "REVIEW"
    assert rows[0]["hard_logic_state"] == "REVIEW"
    assert "company_edge" in rows[0]["hard_logic_missing_evidence"]
