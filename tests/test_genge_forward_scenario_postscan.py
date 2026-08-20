from __future__ import annotations

import csv
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from src.strategies.genge_opportunity_discovery.forward_scenario_postscan import (
    write_postscan_forward_scenarios,
)
from src.strategies.genge_opportunity_discovery.hard_logic_valuation_merge import (
    write_source,
)


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _em_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"代码": "603369", "名称": "目标", "研报数": 8, "2026预测每股收益": 2.00, "2027预测每股收益": 2.24},
            {"代码": "600001", "名称": "同行1", "研报数": 5, "2026预测每股收益": 2.00, "2027预测每股收益": 2.20},
            {"代码": "600002", "名称": "同行2", "研报数": 5, "2026预测每股收益": 2.00, "2027预测每股收益": 2.10},
            {"代码": "600003", "名称": "同行3", "研报数": 5, "2026预测每股收益": 2.00, "2027预测每股收益": 2.40},
            {"代码": "600004", "名称": "同行4", "研报数": 5, "2026预测每股收益": 2.00, "2027预测每股收益": 2.20},
            {"代码": "600005", "名称": "同行5", "研报数": 5, "2026预测每股收益": 2.00, "2027预测每股收益": 2.30},
            {"代码": "600006", "名称": "同行6", "研报数": 5, "2026预测每股收益": 2.00, "2027预测每股收益": 2.10},
        ]
    )


def _ths_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"年度": 2026, "预测机构数": 8, "最小值": 1.80, "均值": 2.00, "最大值": 2.20, "行业平均数": 1.1},
            {"年度": 2027, "预测机构数": 7, "最小值": 2.00, "均值": 2.24, "最大值": 2.50, "行业平均数": 1.2},
        ]
    )


def _raw_rows() -> list[dict]:
    prices = {
        "603369": 28.92,
        "600001": 30.0,
        "600002": 40.0,
        "600003": 25.0,
        "600004": 36.0,
        "600005": 28.0,
        "600006": 32.0,
    }
    return [
        {
            "code": code,
            "stock_name": f"股票{code}",
            "industry": "白酒",
            "raw_latest_close": price,
            "adjusted_latest_close": price * 0.9,
        }
        for code, price in prices.items()
    ]


def test_hard_logic_valuation_bridge_preserves_full_raw_snapshot():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        valuation = root / "valuation"
        research = root / "research"
        output = root / "output"
        raw_path = root / "raw.csv"
        _write_csv(valuation / "all_a_quant_screen.csv", [{"code": "603369", "industry": "白酒"}])
        _write_csv(
            research / "hard_logic_research.csv",
            [
                {
                    "industry": "白酒",
                    "research_state": "PASS",
                    "hard_logic_state": "PASS",
                    "selected_code": "603369",
                    "selected_name": "目标",
                }
            ],
        )
        raw_rows = _raw_rows()
        _write_csv(raw_path, raw_rows)

        write_source(
            valuation_source_dir=valuation,
            hard_logic_research_dir=research,
            raw_all_a_csv=raw_path,
            output_dir=output,
        )

        snapshot = list(csv.DictReader((output / "raw_all_a_universe.csv").open(encoding="utf-8")))
        summary = json.loads((output / "hard_logic_valuation_source_summary.json").read_text(encoding="utf-8"))
        assert len(snapshot) == len(raw_rows)
        assert snapshot[0]["raw_latest_close"]
        assert summary["raw_all_a_snapshot_preserved"] is True
        assert summary["raw_all_a_snapshot_count"] == len(raw_rows)


def test_postscan_adapter_uses_raw_latest_close_and_writes_price_map_sidecar():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        artifact = root / "postscan"
        hard_source = artifact / "reports" / "hard_logic_valuation_source"
        valuation = artifact / "reports" / "valuation_research_queue" / "20260820"
        output = artifact / "reports" / "forward_scenario_valuation"

        raw_rows = _raw_rows()
        _write_csv(hard_source / "raw_all_a_universe.csv", raw_rows)
        _write_csv(
            hard_source / "all_a_quant_screen.csv",
            [
                {
                    "code": "603369",
                    "stock_name": "目标",
                    "industry": "白酒",
                    "hard_logic_state": "PASS",
                    "earnings_quality_score": 70,
                    "latest_quarter_profit_yoy_pct": 10,
                    "previous_quarter_profit_yoy_pct": -5,
                }
            ],
        )
        _write_csv(valuation / "valuation_research_queue.csv", [{"code": "603369"}])
        _write_csv(
            valuation / "valuation_research_routed.csv",
            [
                {
                    "code": "603369",
                    "stock_name": "目标",
                    "industry": "白酒",
                    "hard_logic_state": "PASS",
                    "earnings_quality_score": 70,
                    "latest_quarter_profit_yoy_pct": 10,
                    "previous_quarter_profit_yoy_pct": -5,
                    "valuation_primary_strategy_id": "general_reverse_earnings",
                    "valuation_diagnostic_status": "OK",
                }
            ],
        )
        (valuation / "valuation_research_summary.json").write_text(
            json.dumps({"as_of_date": "2026-08-20"}), encoding="utf-8"
        )

        with patch(
            "src.strategies.genge_opportunity_discovery.forward_scenario_postscan.core._load_or_fetch_em",
            return_value=_em_frame(),
        ), patch(
            "src.strategies.genge_opportunity_discovery.forward_scenario_postscan.core._fetch_target_ths_frames",
            return_value={"603369": _ths_frame()},
        ):
            rows = write_postscan_forward_scenarios(
                artifact_root=artifact,
                output_dir=output,
                cache_dir=root / "cache",
                min_peer_samples=6,
            )

        assert len(rows) == 1
        row = rows[0]
        assert row["code"] == "603369"
        assert row["current_price"] == 28.92
        assert row["reasonable_pe_status"] == "OK"
        assert row["scenario_fair_price_base"] is not None
        assert row["historical_pe_used_for_reasonable_pe"] is False

        written = list(csv.DictReader((output / "forward_scenario_valuation.csv").open(encoding="utf-8")))
        summary = json.loads((output / "forward_scenario_valuation_summary.json").read_text(encoding="utf-8"))
        assert written[0]["current_price"] == "28.92"
        assert summary["current_price_ready_count"] == 1
        assert summary["historical_pe_used_for_reasonable_pe"] is False
        assert summary["historical_backtest_eligible"] is False
        assert summary["peer_price_source"] == "postscan_raw_all_a_snapshot:raw_latest_close_first"
