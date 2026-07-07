from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import pandas as pd

from src.strategies.genge_cycle_bottom.backtest import BacktestInput
from src.strategies.genge_cycle_bottom.current_snapshot import load_industry_alias_map
from src.strategies.genge_cycle_bottom.industry_evidence import load_industry_evidence_schema
from src.strategies.genge_opportunity_discovery.pipeline import run_opportunity_discovery


def _price_frame() -> pd.DataFrame:
    dates = pd.date_range(end="2026-06-24", periods=1000, freq="D")
    closes = np.concatenate(
        [
            np.linspace(22.0, 14.0, 650),
            np.linspace(14.0, 9.5, 220),
            np.linspace(9.5, 11.2, 80),
            np.linspace(11.0, 11.8, 50),
        ]
    )
    return pd.DataFrame(
        [
            {
                "date": day.date().isoformat(),
                "open": round(float(close) * 0.995, 3),
                "high": round(float(close) * 1.02, 3),
                "low": round(float(close) * 0.98, 3),
                "close": round(float(close), 3),
                "volume": 2_000_000 + index * 100,
                "amount": 30_000_000 + index * 1000,
            }
            for index, (day, close) in enumerate(zip(dates, closes))
        ]
    )


def _valuation_frame() -> pd.DataFrame:
    dates = pd.date_range(end="2026-06-24", periods=900, freq="D")
    return pd.DataFrame(
        {
            "date": [day.date().isoformat() for day in dates],
            "pb": np.linspace(2.5, 1.0, len(dates)),
            "pe": np.linspace(30.0, 12.0, len(dates)),
            "ps": np.linspace(5.0, 1.5, len(dates)),
        }
    )


def _financial_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "report_date": "2025-12-31",
                "disclosure_date": "2026-04-20",
                "debt_ratio": 42.0,
                "net_profit": 1_000_000_000,
                "operating_cash_flow": 1_200_000_000,
                "roe": 8.5,
            }
        ]
    )


def _industry_evidence() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "date": "2026-06-15",
                "industry": "面板",
                "evidence_name": "面板价格",
                "evidence_value": "主流尺寸价格较底部回升 5%",
                "evidence_direction": "POSITIVE",
                "source": "公开产业数据",
                "source_type": "official_report",
            },
            {
                "date": "2026-06-16",
                "industry": "面板",
                "evidence_name": "稼动率",
                "evidence_value": "稼动率 75%，供给维持纪律性",
                "evidence_direction": "POSITIVE",
                "source": "行业公开摘要",
                "source_type": "user_supplied",
            },
            {
                "date": "2026-06-17",
                "industry": "面板",
                "evidence_name": "库存水位",
                "evidence_value": "库存下降 10% 至合理水平",
                "evidence_direction": "POSITIVE",
                "source": "行业公开摘要",
                "source_type": "user_supplied",
            },
            {
                "date": "2026-07-01",
                "industry": "面板",
                "evidence_name": "面板价格",
                "evidence_value": "未来数据不应参与 as-of",
                "evidence_direction": "NEGATIVE",
                "source": "未来数据",
                "source_type": "official_report",
            },
        ]
    )


def _company_evidence() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "date": "2026-06-18",
                "code": "000100",
                "stock_name": "TCL科技",
                "industry": "面板",
                "evidence_name": "产能结构",
                "evidence_value": "高端产线占比提升 8%",
                "evidence_direction": "POSITIVE",
                "source": "公司公告",
                "source_type": "company_announcement",
            },
            {
                "date": "2026-06-19",
                "code": "000100",
                "stock_name": "TCL科技",
                "industry": "面板",
                "evidence_name": "库存管理",
                "evidence_value": "库存周转天数下降 12%",
                "evidence_direction": "POSITIVE",
                "source": "交易所披露",
                "source_type": "exchange_disclosure",
            },
        ]
    )


def _input() -> BacktestInput:
    return BacktestInput(
        code="000100",
        stock_name="TCL科技",
        price_df=_price_frame(),
        valuation_df=_valuation_frame(),
        financial_df=_financial_frame(),
        industry="光学光电子",
    )


def _diagnostics() -> dict[str, object]:
    return {
        "requested_stock_records": [{"code": "000100", "stock_name": "TCL科技", "industry": "光学光电子"}],
        "source_mode": "fixture",
        "no_auto_trade": True,
    }


def test_opportunity_discovery_writes_research_outputs_and_forward_ledger(tmp_path: Path) -> None:
    schema = load_industry_evidence_schema("config/industry_evidence_schema.yaml")
    alias_map = load_industry_alias_map("config/industry_alias_map.yaml")
    exit_profiles = pd.DataFrame([{"code": "000100", "balanced_exit_historical_profile": "PASSED"}])

    report_dir, summary = run_opportunity_discovery(
        inputs=[_input()],
        requested_codes=["000100"],
        data_errors={},
        data_sources={"000100": "fixture"},
        benchmark_df=_price_frame(),
        industry_cycle_df=None,
        industry_evidence_df=_industry_evidence(),
        company_evidence_df=_company_evidence(),
        industry_evidence_schema=schema,
        industry_alias_map=alias_map,
        requested_as_of_date="2026-06-24",
        output_dir=tmp_path / "reports",
        diagnostics=_diagnostics(),
        exit_profile_df=exit_profiles,
        ledger_path=tmp_path / "ledger.csv",
    )

    assert summary["valid_stocks"] == 1
    assert "PASS_QUANT_RESEARCH_QUEUE_GENERATED" in summary["acceptance_milestones"]
    assert "PASS_EVIDENCE_ENRICHMENT_READY" in summary["acceptance_milestones"]
    assert (report_dir / "priority_research_queue.csv").exists()
    assert (report_dir / "evidence_gap_report.csv").exists()
    assert (report_dir / "evidence_inventory.csv").exists()
    assert (report_dir / "industry_research_tasks.json").exists()
    assert (report_dir / "company_research_tasks.json").exists()
    assert (report_dir / "forward_observation_ledger.csv").exists()
    assert summary["provider_distribution"] == {"fixture": 1}
    assert "opportunity_quality_top20" in summary
    assert "opportunity_proximity_top20" in summary

    tier_files = ["tier_a_candidates.csv", "tier_b_watchlist.csv", "tier_c_evidence_incomplete.csv"]
    tier_rows = []
    for file_name in tier_files:
        tier_rows.extend(csv.DictReader((report_dir / file_name).open(encoding="utf-8")))
    assert len(tier_rows) == 1
    assert tier_rows[0]["code"] == "000100"
    assert "BUY" not in tier_rows[0]["research_label"]
    assert "SELL" not in tier_rows[0]["research_label"]
    assert tier_rows[0]["opportunity_logic"]
    assert tier_rows[0]["top_risks"]
    assert tier_rows[0]["upgrade_conditions"]
    assert tier_rows[0]["downgrade_conditions"]

    evidence_rows = list(csv.DictReader((report_dir / "evidence_inventory.csv").open(encoding="utf-8")))
    required_columns = {
        "evidence_date",
        "collected_at",
        "industry",
        "indicator",
        "value",
        "direction",
        "source",
        "source_type",
        "confidence",
        "freshness_days",
        "raw_excerpt",
        "normalized_summary",
        "parser",
        "parse_status",
        "evidence_status",
        "warning_flags",
    }
    assert required_columns.issubset(evidence_rows[0].keys())
    assert any(row["evidence_status"] == "PARSE_FAILED" for row in evidence_rows)
    assert any("future_dated_evidence_excluded" in row["warning_flags"] for row in evidence_rows)

    quality_rows = list(csv.DictReader((report_dir / "data_quality_audit.csv").open(encoding="utf-8")))
    assert any(row["issue"] == "future_dated_evidence_excluded" for row in quality_rows)


def test_exit_profile_not_available_cannot_enter_tier_a(tmp_path: Path) -> None:
    schema = load_industry_evidence_schema("config/industry_evidence_schema.yaml")
    alias_map = load_industry_alias_map("config/industry_alias_map.yaml")

    report_dir, _summary = run_opportunity_discovery(
        inputs=[_input()],
        requested_codes=["000100"],
        data_errors={},
        data_sources={"000100": "fixture"},
        benchmark_df=_price_frame(),
        industry_cycle_df=None,
        industry_evidence_df=_industry_evidence(),
        company_evidence_df=_company_evidence(),
        industry_evidence_schema=schema,
        industry_alias_map=alias_map,
        requested_as_of_date="2026-06-24",
        output_dir=tmp_path / "reports",
        diagnostics=_diagnostics(),
        ledger_path=tmp_path / "ledger.csv",
    )

    assert list(csv.DictReader((report_dir / "tier_a_candidates.csv").open(encoding="utf-8"))) == []
    watch_rows = list(csv.DictReader((report_dir / "tier_b_watchlist.csv").open(encoding="utf-8")))
    incomplete_rows = list(csv.DictReader((report_dir / "tier_c_evidence_incomplete.csv").open(encoding="utf-8")))
    combined = watch_rows + incomplete_rows
    assert combined
    assert "balanced_exit_profile_not_available" in combined[0]["soft_blockers"]


def test_missing_evidence_goes_to_gap_report_not_silent_drop(tmp_path: Path) -> None:
    schema = load_industry_evidence_schema("config/industry_evidence_schema.yaml")
    alias_map = load_industry_alias_map("config/industry_alias_map.yaml")

    report_dir, summary = run_opportunity_discovery(
        inputs=[_input()],
        requested_codes=["000100"],
        data_errors={},
        data_sources={"000100": "fixture"},
        benchmark_df=_price_frame(),
        industry_cycle_df=None,
        industry_evidence_df=pd.DataFrame(),
        company_evidence_df=pd.DataFrame(),
        industry_evidence_schema=schema,
        industry_alias_map=alias_map,
        requested_as_of_date="2026-06-24",
        output_dir=tmp_path / "reports",
        diagnostics=_diagnostics(),
        ledger_path=tmp_path / "ledger.csv",
    )

    assert summary["valid_stocks"] == 1
    gap_rows = list(csv.DictReader((report_dir / "evidence_gap_report.csv").open(encoding="utf-8")))
    assert gap_rows
    tier_c = list(csv.DictReader((report_dir / "tier_c_evidence_incomplete.csv").open(encoding="utf-8")))
    assert tier_c
    assert tier_c[0]["missing_evidence"]


def test_existing_ledger_does_not_upgrade_without_current_tier_a_or_b(tmp_path: Path) -> None:
    schema = load_industry_evidence_schema("config/industry_evidence_schema.yaml")
    alias_map = load_industry_alias_map("config/industry_alias_map.yaml")
    ledger_path = tmp_path / "ledger.csv"
    ledger_path.write_text(
        "code,stock_name,industry,first_observation_date,first_tier,first_close,first_quant_score,"
        "first_evidence_status,rule_version,data_version,first_snapshot_json,latest_observation_date,"
        "latest_tier,latest_close,return_5d_pct,return_10d_pct,return_20d_pct,return_40d_pct,"
        "return_60d_pct,max_up_pct,max_down_pct,benchmark_return_20d_pct,status\n"
        "000999,旧观察,面板,2026-06-01,TIER_B,10,60,VERIFIED/VERIFIED,v1,fixture,{},"
        "2026-06-01,TIER_B,10,,,,,,,,OPEN\n",
        encoding="utf-8",
    )

    _report_dir, summary = run_opportunity_discovery(
        inputs=[_input()],
        requested_codes=["000100"],
        data_errors={},
        data_sources={"000100": "fixture"},
        benchmark_df=_price_frame(),
        industry_cycle_df=None,
        industry_evidence_df=pd.DataFrame(),
        company_evidence_df=pd.DataFrame(),
        industry_evidence_schema=schema,
        industry_alias_map=alias_map,
        requested_as_of_date="2026-06-24",
        output_dir=tmp_path / "reports",
        diagnostics=_diagnostics(),
        ledger_path=ledger_path,
    )

    assert summary["forward_observation"]["tracked_count"] == 1
    assert summary["forward_observation"]["observed_tier_a_b_count"] == 0
    assert "PASS_FORWARD_OBSERVATION_READY" not in summary["acceptance_milestones"]
    assert summary["acceptance_enum"] == "PASS_OPPORTUNITY_DISCOVERY_RESEARCH_READY"


def test_conflicting_and_stale_evidence_are_audited(tmp_path: Path) -> None:
    schema = load_industry_evidence_schema("config/industry_evidence_schema.yaml")
    alias_map = load_industry_alias_map("config/industry_alias_map.yaml")
    industry_evidence = pd.DataFrame(
        [
            {
                "date": "2025-01-01",
                "industry": "面板",
                "evidence_name": "面板价格",
                "evidence_value": "价格上涨 3%",
                "evidence_direction": "POSITIVE",
                "source": "官方公开数据",
                "source_type": "official_report",
            },
            {
                "date": "2025-01-02",
                "industry": "面板",
                "evidence_name": "面板价格",
                "evidence_value": "价格下跌 2%",
                "evidence_direction": "NEGATIVE",
                "source": "交易所披露",
                "source_type": "exchange_disclosure",
            },
            {
                "date": "2024-01-01",
                "industry": "面板",
                "evidence_name": "库存水位",
                "evidence_value": "库存处于历史低位 1",
                "evidence_direction": "POSITIVE",
                "source": "行业公开摘要",
                "source_type": "research_report_summary",
            },
        ]
    )

    report_dir, _summary = run_opportunity_discovery(
        inputs=[_input()],
        requested_codes=["000100"],
        data_errors={},
        data_sources={"000100": "fixture"},
        benchmark_df=_price_frame(),
        industry_cycle_df=None,
        industry_evidence_df=industry_evidence,
        company_evidence_df=pd.DataFrame(),
        industry_evidence_schema=schema,
        industry_alias_map=alias_map,
        requested_as_of_date="2026-06-24",
        output_dir=tmp_path / "reports",
        diagnostics=_diagnostics(),
        ledger_path=tmp_path / "ledger.csv",
    )

    evidence_rows = list(csv.DictReader((report_dir / "evidence_inventory.csv").open(encoding="utf-8")))
    statuses = {row["indicator"]: row["evidence_status"] for row in evidence_rows}
    assert statuses["面板价格"] == "CONFLICTING"
    assert statuses["库存水位"] == "STALE"
    assert any("conflicting_evidence" in row["warning_flags"] for row in evidence_rows)


def test_single_stock_failure_does_not_block_other_outputs(tmp_path: Path) -> None:
    schema = load_industry_evidence_schema("config/industry_evidence_schema.yaml")
    alias_map = load_industry_alias_map("config/industry_alias_map.yaml")

    report_dir, summary = run_opportunity_discovery(
        inputs=[_input()],
        requested_codes=["000100", "000999"],
        data_errors={"000999": "RuntimeError: provider unavailable"},
        data_sources={"000100": "fixture", "000999": "failed"},
        benchmark_df=_price_frame(),
        industry_cycle_df=None,
        industry_evidence_df=_industry_evidence(),
        company_evidence_df=_company_evidence(),
        industry_evidence_schema=schema,
        industry_alias_map=alias_map,
        requested_as_of_date="2026-06-24",
        output_dir=tmp_path / "reports",
        diagnostics=_diagnostics(),
        ledger_path=tmp_path / "ledger.csv",
    )

    assert summary["total_stocks"] == 2
    assert summary["valid_stocks"] == 1
    assert summary["data_failure_count"] == 1
    quality_rows = list(csv.DictReader((report_dir / "data_quality_audit.csv").open(encoding="utf-8")))
    assert any(row["code"] == "000999" and row["issue"] == "data_error" for row in quality_rows)


def test_github_actions_opportunity_workflow_contract() -> None:
    workflow = Path(".github/workflows/genge-opportunity-discovery.yml").read_text(encoding="utf-8")
    assert "cron:" in workflow
    assert "workflow_dispatch:" in workflow
    assert "run_mode:" in workflow
    assert "actions/upload-artifact@v4" in workflow
    assert "tests/test_genge_opportunity_discovery_*.py" in workflow
    assert "--run-mode" in workflow
    assert "daily-opportunity-report:" in workflow
