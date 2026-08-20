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


def test_forward_sidecar_drives_strict_price_map_and_margin_of_safety():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        artifact = root / "postscan"
        output = root / "price_map"

        _write_csv(
            artifact / "reports" / "valuation_research_queue" / "20260820" / "valuation_research_queue.csv",
            [
                {
                    "code": "603369",
                    "stock_name": "今世缘",
                    "industry": "白酒",
                    "valuation_diagnostic_status": "OK",
                    "earnings_quality_score": 70,
                    "current_pe": 13.9,
                    "historical_median_pe_reference": 21.1,
                    "required_profit_growth_vs_reference": -0.34,
                }
            ],
        )
        _write_csv(
            artifact / "reports" / "hard_logic_research" / "hard_logic_research.csv",
            [
                {
                    "industry": "白酒",
                    "research_state": "PASS",
                    "selected_code": "603369",
                    "selected_name": "今世缘",
                    "selection_origin": "SEED",
                    "hard_logic_state": "PASS",
                    "hard_logic_score": 95,
                    "hard_logic_missing_evidence": "",
                    "hard_logic_structural_driver": "区域消费升级和宴席场景形成可持续的结构性需求基础",
                    "hard_logic_supply_constraint": "优质基酒产能与渠道培育需要较长周期",
                    "hard_logic_company_edge": "省内品牌、渠道密度和产品结构形成难以短期复制的区域竞争优势",
                    "hard_logic_profit_transmission": "需求与产品升级带动量价和产品结构改善，进而传导至收入、毛利率与利润",
                    "hard_logic_invalidation": "若核心市场份额持续下降且产品升级失败、渠道库存长期恶化则逻辑失效",
                    "hard_logic_duration_years": 5,
                    "hard_logic_persistence": "区域品牌和渠道网络的形成与替代均需要多年",
                    "hard_logic_evidence_sources": "公司年报 | https://example.com/annual-report",
                    "research_summary": "结构逻辑通过，估值需独立判断。",
                }
            ],
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
