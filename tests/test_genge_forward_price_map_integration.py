from __future__ import annotations

import csv
import tempfile
from pathlib import Path

from src.strategies.genge_opportunity_discovery.strict_hard_logic_price_map import (
    write_price_map,
)


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _hard_logic_research_row(code: str, name: str, industry: str) -> dict:
    return {
        "industry": industry,
        "research_state": "PASS",
        "selected_code": code,
        "selected_name": name,
        "selection_origin": "SEED",
        "hard_logic_state": "PASS",
        "hard_logic_score": 95,
        "hard_logic_missing_evidence": "",
        "hard_logic_structural_driver": "行业长期结构变化形成持续需求与盈利机会",
        "hard_logic_supply_constraint": "牌照、客户或资本约束限制有效供给扩张",
        "hard_logic_company_edge": "公司拥有难以短期复制的牌照、客户与规模优势",
        "hard_logic_profit_transmission": "行业结构改善传导至业务量、收入、利润率与现金流",
        "hard_logic_invalidation": "若行业结构逆转且核心客户/份额持续流失则逻辑失效",
        "hard_logic_duration_years": 5,
        "hard_logic_persistence": "关键竞争壁垒和行业结构预计持续多年",
        "hard_logic_evidence_sources": "公司年报 | https://example.com/annual-report",
        "research_summary": "结构逻辑通过，估值需独立判断。",
    }


def test_forward_sidecar_drives_strict_price_map_and_margin_of_safety():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        artifact = root / "postscan"
        output = root / "price_map"
        valuation_root = artifact / "reports" / "valuation_research_queue" / "20260820"

        valuation_row = {
            "code": "603369",
            "stock_name": "今世缘",
            "industry": "白酒",
            "valuation_diagnostic_status": "OK",
            "earnings_quality_score": 70,
            "current_pe": 13.9,
            "historical_median_pe_reference": 21.1,
            "required_profit_growth_vs_reference": -0.34,
        }
        _write_csv(
            valuation_root / "valuation_research_queue.csv",
            [valuation_row],
        )
        # Production price-map candidate membership comes from the routed
        # valuation sidecar, not from the queue alone.  Forward valuation is an
        # enrichment channel and must never create a security on its own.
        _write_csv(
            valuation_root / "valuation_research_routed.csv",
            [
                {
                    **valuation_row,
                    "valuation_primary_strategy_id": "general_reverse_earnings",
                    "valuation_route_status": "DEFAULT_GENERAL_REVERSE_EARNINGS",
                }
            ],
        )
        _write_csv(
            artifact / "reports" / "hard_logic_research" / "hard_logic_research.csv",
            [_hard_logic_research_row("603369", "今世缘", "白酒")],
        )
        _write_csv(
            artifact / "reports" / "forward_scenario_valuation" / "forward_scenario_valuation.csv",
            [
                {
                    "code": "603369",
                    "current_price": 28.92,
                    "earnings_stage": "EARLY_RECOVERY",
                    "forward_eps_bear": 2.00,
                    "forward_eps_base": 2.08,
                    "forward_eps_bull": 2.15,
                    "reasonable_pe_bear": 12.0,
                    "reasonable_pe_base": 15.0,
                    "reasonable_pe_bull": 18.0,
                    "scenario_fair_price_bear": 24.00,
                    "scenario_fair_price_base": 31.20,
                    "scenario_fair_price_bull": 38.70,
                    "historical_pe_used_for_reasonable_pe": False,
                }
            ],
        )

        write_price_map(artifact, output)

        rows = list(csv.DictReader((output / "hard_logic_price_map.csv").open(encoding="utf-8")))
        assert len(rows) == 1
        row = rows[0]
        assert row["code"] == "603369"
        assert row["hard_logic_state"] == "PASS"
        assert row["valuation_framework"] == "FORWARD_SCENARIO"
        assert float(row["scenario_fair_price_base"]) == 31.20
        assert round(float(row["entry_price_ceiling"]), 2) == 26.52
        assert round(float(row["ideal_price_ceiling"]), 2) == 23.40
        assert row["price_decision"] == "HOLD_FAIR_VALUE"
        assert row["price_zone"] == "HOLD_FAIR_ZONE"
        assert row["historical_pe_is_reference_only"] == "True"
        assert row["hard_logic_structural_driver"]
        assert row["hard_logic_company_edge"]
        assert row["hard_logic_profit_transmission"]
        assert row["hard_logic_invalidation"]
        assert row["hard_logic_evidence_sources"]


def test_executed_broker_specialized_model_drives_base_fair_price_without_pe():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        artifact = root / "postscan"
        output = root / "price_map"
        valuation_root = artifact / "reports" / "valuation_research_queue" / "20260820"

        routed = {
            "code": "600030",
            "stock_name": "中信证券",
            "industry": "证券",
            "earnings_quality_score": 70,
            "valuation_diagnostic_status": "PE_MODEL_NOT_APPLICABLE",
            "valuation_primary_strategy_id": "capital_markets_cycle",
            "valuation_route_status": "SPECIALIZED_MODEL_SELECTED",
        }
        _write_csv(valuation_root / "valuation_research_queue.csv", [routed])
        _write_csv(valuation_root / "valuation_research_routed.csv", [routed])
        _write_csv(
            valuation_root / "valuation_research_specialized.csv",
            [
                {
                    **routed,
                    "specialized_model_executed": True,
                    "specialized_model_execution_state": "SPECIALIZED_MODEL_EXECUTED_RESEARCH_ONLY",
                    "specialized_model_status": "OK",
                    "specialized_current_pb": 1.20,
                    "specialized_fair_pb": 1.50,
                }
            ],
        )
        _write_csv(
            artifact / "reports" / "hard_logic_research" / "hard_logic_research.csv",
            [_hard_logic_research_row("600030", "中信证券", "证券")],
        )
        # Forward research still supplies the current share price for specialized
        # routes, but deliberately refuses to fabricate a PE-based fair value.
        _write_csv(
            artifact / "reports" / "forward_scenario_valuation" / "forward_scenario_valuation.csv",
            [
                {
                    "code": "600030",
                    "current_price": 24.0,
                    "earnings_stage": "EXPANSION",
                    "reasonable_pe_status": "SPECIALIZED_MODEL_REQUIRED",
                    "scenario_fair_price_base": "",
                    "scenario_valuation_status": "SPECIALIZED_MODEL_REQUIRED",
                    "historical_pe_used_for_reasonable_pe": False,
                }
            ],
        )
        _write_csv(
            artifact / "reports" / "hard_logic_valuation_source" / "raw_all_a_universe.csv",
            [{"code": "600030", "stock_name": "中信证券", "industry": "证券", "raw_latest_close": 24.0}],
        )

        write_price_map(artifact, output)

        rows = list(csv.DictReader((output / "hard_logic_price_map.csv").open(encoding="utf-8")))
        assert len(rows) == 1
        row = rows[0]
        assert row["code"] == "600030"
        assert row["hard_logic_state"] == "PASS"
        assert row["valuation_framework"] == "FORWARD_SCENARIO"
        assert float(row["scenario_fair_price_base"]) == 30.0
        assert row["scenario_fair_price_bear"] == ""
        assert row["scenario_fair_price_bull"] == ""
        assert round(float(row["entry_price_ceiling"]), 2) == 25.50
        assert round(float(row["ideal_price_ceiling"]), 2) == 22.50
        assert row["price_decision"] == "BUYABLE"
        assert row["price_zone"] == "BUY_ZONE"
        assert row["specialized_scenario_bridge_status"] == "OK_BASE_ONLY"
        assert row["specialized_scenario_strategy_id"] == "capital_markets_cycle"
        assert "fair_pb/current_pb" in row["specialized_scenario_basis"]
