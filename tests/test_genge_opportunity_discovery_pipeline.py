from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.strategies.genge_cycle_bottom.backtest import BacktestInput
from src.strategies.genge_cycle_bottom.current_snapshot import load_industry_alias_map
from src.strategies.genge_cycle_bottom.industry_evidence import load_industry_evidence_schema
from src.strategies.genge_opportunity_discovery.evidence_collectors.cache import EvidenceCache
from src.strategies.genge_opportunity_discovery.exit_profile import generate_exit_profile_from_reports
from src.strategies.genge_opportunity_discovery.pipeline import _rank_opportunities, run_opportunity_discovery


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


def _input(code: str = "000100", stock_name: str = "TCL科技", industry: str = "光学光电子") -> BacktestInput:
    return BacktestInput(
        code=code,
        stock_name=stock_name,
        price_df=_price_frame(),
        valuation_df=_valuation_frame(),
        financial_df=_financial_frame(),
        industry=industry,
    )


def _diagnostics() -> dict[str, object]:
    return {
        "requested_stock_records": [{"code": "000100", "stock_name": "TCL科技", "industry": "光学光电子"}],
        "source_mode": "fixture",
        "no_auto_trade": True,
    }


def _auto_company_evidence(
    code: str = "000100",
    stock_name: str = "TCL科技",
    industry: str = "面板",
    evidence_date: str = "2026-06-20",
) -> list[dict[str, object]]:
    return [
        {
            "date": evidence_date,
            "publish_date": evidence_date,
            "scope": "company",
            "code": code,
            "stock_name": stock_name,
            "industry": industry,
            "evidence_name": "定期报告原文数值",
            "indicator": "定期报告原文数值",
            "evidence_value": "营业收入增长 8%",
            "value": "8",
            "unit": "%",
            "comparison_period": evidence_date[:4],
            "evidence_direction": "POSITIVE",
            "direction": "POSITIVE",
            "source": f"https://static.cninfo.com.cn/finalpage/test/{code}.PDF",
            "original_url": f"https://static.cninfo.com.cn/finalpage/test/{code}.PDF",
            "source_domain": "static.cninfo.com.cn",
            "source_type": "EXCHANGE_DISCLOSURE",
            "confidence": "HIGH",
            "raw_excerpt": "营业收入增长 8%",
            "normalized_summary": "定期报告原文：营业收入增长 8%",
            "title": "年度报告",
            "parser": "fixture_company_announcement",
            "collector": "fixture_company_announcement",
            "parse_status": "OK",
            "evidence_status": "VERIFIED",
            "content_hash": f"hash-{code}",
            "extraction_confidence": "HIGH",
            "warning_flags": "",
        }
    ]


def _fake_auto_collector(*, company_rows: list[dict[str, object]] | None = None):
    def _collect(**_kwargs):
        rows = company_rows if company_rows is not None else _auto_company_evidence()
        return (
            [],
            rows,
            [],
            {
                "enabled": True,
                "executed": True,
                "task_count": 1,
                "actual_fetch_count": 1,
                "fetch_success_count": 1,
                "verified_count": len(rows),
                "partially_verified_count": 0,
                "failed_count": 0,
                "missing_count": 0,
                "cache_hit_count": 0,
                "cache_miss_count": 1,
                "audit_count": 0,
                "cache_dir": "fixture",
            },
        )

    return _collect


def test_opportunity_discovery_writes_research_outputs_and_forward_ledger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    schema = load_industry_evidence_schema("config/industry_evidence_schema.yaml")
    alias_map = load_industry_alias_map("config/industry_alias_map.yaml")
    exit_profiles = pd.DataFrame([{"code": "000100", "balanced_exit_historical_profile": "PASSED"}])
    monkeypatch.setattr(
        "src.strategies.genge_opportunity_discovery.pipeline.collect_auto_evidence",
        _fake_auto_collector(company_rows=_auto_company_evidence(evidence_date="2026-06-10")),
    )

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
        state_dir=tmp_path / "state",
    )

    assert summary["valid_stocks"] == 1
    assert "PASS_QUANT_RESEARCH_QUEUE_GENERATED" in summary["acceptance_milestones"]
    assert "PASS_EVIDENCE_TASKS_GENERATED" in summary["acceptance_milestones"]
    assert "PASS_AUTO_EVIDENCE_COLLECTION_READY" in summary["acceptance_milestones"]
    assert (report_dir / "priority_research_queue.csv").exists()
    assert (report_dir / "evidence_gap_report.csv").exists()
    assert (report_dir / "evidence_inventory.csv").exists()
    assert (report_dir / "auto_evidence_audit.csv").exists()
    assert (report_dir / "industry_research_tasks.json").exists()
    assert (report_dir / "company_research_tasks.json").exists()
    assert (report_dir / "forward_observation_ledger.csv").exists()
    assert summary["provider_distribution"] == {"fixture": 1}
    assert summary["auto_evidence_verified_count"] == 1
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
    assert any(row["evidence_status"] == "VERIFIED" and row["content_hash"] for row in evidence_rows)
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
        run_mode="quant-evidence",
        auto_evidence_limit=0,
        state_dir=tmp_path / "state",
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
        run_mode="quant-evidence",
        auto_evidence_limit=0,
        state_dir=tmp_path / "state",
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
        run_mode="full",
        auto_evidence_limit=0,
        state_dir=tmp_path / "state",
    )

    assert summary["forward_observation"]["tracked_count"] == 1
    assert summary["forward_observation"]["observed_tier_a_b_count"] == 0
    assert "PASS_FORWARD_OBSERVATION_READY" not in summary["acceptance_milestones"]
    assert summary["acceptance_enum"] == "PASS_EVIDENCE_TASKS_GENERATED"


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
        run_mode="quant-evidence",
        auto_evidence_limit=0,
        state_dir=tmp_path / "state",
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
        run_mode="quant-only",
        state_dir=tmp_path / "state",
    )

    assert summary["total_stocks"] == 2
    assert summary["valid_stocks"] == 1
    assert summary["data_failure_count"] == 1
    quality_rows = list(csv.DictReader((report_dir / "data_quality_audit.csv").open(encoding="utf-8")))
    assert any(row["code"] == "000999" and row["issue"] == "data_error" for row in quality_rows)


def test_manual_authoritative_source_is_capped_at_partially_verified(tmp_path: Path) -> None:
    schema = load_industry_evidence_schema("config/industry_evidence_schema.yaml")
    alias_map = load_industry_alias_map("config/industry_alias_map.yaml")

    report_dir, _summary = run_opportunity_discovery(
        inputs=[_input()],
        requested_codes=["000100"],
        data_errors={},
        data_sources={"000100": "fixture"},
        benchmark_df=_price_frame(),
        industry_cycle_df=None,
        industry_evidence_df=_industry_evidence().iloc[:1],
        company_evidence_df=_company_evidence().iloc[:1],
        industry_evidence_schema=schema,
        industry_alias_map=alias_map,
        requested_as_of_date="2026-06-24",
        output_dir=tmp_path / "reports",
        diagnostics=_diagnostics(),
        run_mode="quant-evidence",
        auto_evidence_limit=0,
        state_dir=tmp_path / "state",
    )

    rows = list(csv.DictReader((report_dir / "evidence_inventory.csv").open(encoding="utf-8")))
    assert rows
    assert "VERIFIED" not in {row["evidence_status"] for row in rows}
    assert any(row["evidence_status"] == "PARTIALLY_VERIFIED" for row in rows)
    assert any("user_supplied_authoritative_label_capped_at_partial" in row["warning_flags"] for row in rows)


def test_exit_profile_status_controls_tier_a_for_non_sample_stock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    schema = load_industry_evidence_schema("config/industry_evidence_schema.yaml")
    alias_map = load_industry_alias_map("config/industry_alias_map.yaml")
    code = "600123"
    stock_name = "测试周期"
    industry = "有色"
    industry_evidence = pd.DataFrame(
        [
            {
                "date": "2026-06-15",
                "industry": industry,
                "evidence_name": "金属价格",
                "evidence_value": "公开原文显示价格增长 6%",
                "evidence_direction": "POSITIVE",
                "source": "https://example.com/official.pdf",
                "source_type": "official_report",
                "parser": "fixture_public_data",
                "parse_status": "OK",
                "content_hash": "hash-industry",
            },
            {
                "date": "2026-06-16",
                "industry": industry,
                "evidence_name": "库存",
                "evidence_value": "库存下降 10%",
                "evidence_direction": "POSITIVE",
                "source": "https://example.com/official2.pdf",
                "source_type": "official_report",
                "parser": "fixture_public_data",
                "parse_status": "OK",
                "content_hash": "hash-industry2",
            },
            {
                "date": "2026-06-17",
                "industry": industry,
                "evidence_name": "加工费",
                "evidence_value": "加工费改善 3%",
                "evidence_direction": "POSITIVE",
                "source": "https://example.com/official3.pdf",
                "source_type": "official_report",
                "parser": "fixture_public_data",
                "parse_status": "OK",
                "content_hash": "hash-industry3",
            },
        ]
    )
    company_rows = _auto_company_evidence(code=code, stock_name=stock_name, industry=industry)
    monkeypatch.setattr(
        "src.strategies.genge_opportunity_discovery.pipeline.collect_auto_evidence",
        _fake_auto_collector(company_rows=company_rows),
    )

    for status, should_enter_a in {
        "PASSED": True,
        "NOT_AVAILABLE": False,
        "DEGRADED": False,
        "FAILED": False,
    }.items():
        report_dir, _summary = run_opportunity_discovery(
            inputs=[_input(code=code, stock_name=stock_name, industry=industry)],
            requested_codes=[code],
            data_errors={},
            data_sources={code: "fixture"},
            benchmark_df=_price_frame(),
            industry_cycle_df=None,
            industry_evidence_df=industry_evidence,
            company_evidence_df=pd.DataFrame(),
            industry_evidence_schema=schema,
            industry_alias_map=alias_map,
            requested_as_of_date="2026-06-24",
            output_dir=tmp_path / f"reports_{status}",
            diagnostics={
                "requested_stock_records": [{"code": code, "stock_name": stock_name, "industry": industry}],
                "source_mode": "fixture",
            },
            exit_profile_df=pd.DataFrame([{"code": code, "balanced_exit_historical_profile": status}]),
            ledger_path=tmp_path / f"ledger_{status}.csv",
            state_dir=tmp_path / f"state_{status}",
        )
        tier_a_rows = list(csv.DictReader((report_dir / "tier_a_candidates.csv").open(encoding="utf-8")))
        assert bool(tier_a_rows) is should_enter_a


def test_run_modes_execute_different_stages(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    schema = load_industry_evidence_schema("config/industry_evidence_schema.yaml")
    alias_map = load_industry_alias_map("config/industry_alias_map.yaml")
    calls = {"count": 0}

    def fake_collect(**kwargs):
        calls["count"] += 1
        return _fake_auto_collector()(**kwargs)

    monkeypatch.setattr("src.strategies.genge_opportunity_discovery.pipeline.collect_auto_evidence", fake_collect)
    common = {
        "inputs": [_input()],
        "requested_codes": ["000100"],
        "data_errors": {},
        "data_sources": {"000100": "fixture"},
        "benchmark_df": _price_frame(),
        "industry_cycle_df": None,
        "industry_evidence_df": _industry_evidence(),
        "company_evidence_df": _company_evidence(),
        "industry_evidence_schema": schema,
        "industry_alias_map": alias_map,
        "requested_as_of_date": "2026-06-24",
        "diagnostics": _diagnostics(),
        "exit_profile_df": pd.DataFrame([{"code": "000100", "balanced_exit_historical_profile": "PASSED"}]),
    }

    q_dir, q_summary = run_opportunity_discovery(
        **common,
        output_dir=tmp_path / "quant_only",
        run_mode="quant-only",
        ledger_path=tmp_path / "quant_only_ledger.csv",
        state_dir=tmp_path / "state_quant",
    )
    assert calls["count"] == 0
    assert q_summary["stages_executed"] == ["quant_screen", "research_queue"]
    assert not (tmp_path / "quant_only_ledger.csv").exists()
    assert list(csv.DictReader((q_dir / "tier_a_candidates.csv").open(encoding="utf-8"))) == []

    qe_dir, qe_summary = run_opportunity_discovery(
        **common,
        output_dir=tmp_path / "quant_evidence",
        run_mode="quant-evidence",
        ledger_path=tmp_path / "quant_evidence_ledger.csv",
        state_dir=tmp_path / "state_qe",
    )
    assert calls["count"] == 1
    assert "auto_evidence_collection" in qe_summary["stages_executed"]
    assert "forward_ledger_update" not in qe_summary["stages_executed"]
    assert not (tmp_path / "quant_evidence_ledger.csv").exists()
    assert (qe_dir / "evidence_inventory.csv").exists()

    full_dir, full_summary = run_opportunity_discovery(
        **common,
        output_dir=tmp_path / "full",
        run_mode="full",
        ledger_path=tmp_path / "full_ledger.csv",
        state_dir=tmp_path / "state_full",
    )
    assert calls["count"] == 2
    assert "forward_ledger_update" in full_summary["stages_executed"]
    assert (tmp_path / "full_ledger.csv").exists()
    assert (full_dir / "forward_observation_ledger.csv").exists()


def test_forward_ledger_preserves_first_observation_and_updates_returns(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    schema = load_industry_evidence_schema("config/industry_evidence_schema.yaml")
    alias_map = load_industry_alias_map("config/industry_alias_map.yaml")
    monkeypatch.setattr(
        "src.strategies.genge_opportunity_discovery.pipeline.collect_auto_evidence",
        _fake_auto_collector(),
    )
    ledger_path = tmp_path / "ledger.csv"

    report_1, _summary_1 = run_opportunity_discovery(
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
        requested_as_of_date="2026-06-18",
        output_dir=tmp_path / "reports",
        diagnostics=_diagnostics(),
        exit_profile_df=pd.DataFrame([{"code": "000100", "balanced_exit_historical_profile": "PASSED"}]),
        ledger_path=ledger_path,
        state_dir=tmp_path / "state",
    )
    rows_1 = list(csv.DictReader((report_1 / "forward_observation_ledger.csv").open(encoding="utf-8")))
    assert len(rows_1) == 1
    assert rows_1[0]["first_observation_date"] == "2026-06-18"

    report_2, summary_2 = run_opportunity_discovery(
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
        exit_profile_df=pd.DataFrame([{"code": "000100", "balanced_exit_historical_profile": "PASSED"}]),
        ledger_path=ledger_path,
        state_dir=tmp_path / "state",
    )
    rows_2 = list(csv.DictReader((report_2 / "forward_observation_ledger.csv").open(encoding="utf-8")))
    assert len(rows_2) == 1
    assert rows_2[0]["first_observation_date"] == "2026-06-18"
    assert rows_2[0]["return_5d_pct"] != ""
    assert summary_2["previous_state_restored"] is True


def test_exit_profile_generation_from_historical_signal_details(tmp_path: Path) -> None:
    report = tmp_path / "reports" / "sample" / "signal_details.csv"
    report.parent.mkdir(parents=True)
    report.write_text(
        "code,stock_name,balanced_hybrid_60d_exit_exit_adjusted_net_return_60d,balanced_hybrid_60d_exit_exit_adjusted_max_drawdown_250d\n"
        "600123,测试周期,2.5,-8\n"
        "600123,测试周期,1.5,-9\n"
        "600456,测试退化,1,-15\n"
        "600456,测试退化,-3,-16\n"
        "600789,测试失败,-9,-25\n"
        "600789,测试失败,-8,-20\n",
        encoding="utf-8",
    )
    output, summary = generate_exit_profile_from_reports(output_file=tmp_path / "exit_profile.csv", source_dirs=[tmp_path / "reports"])
    rows = {row["code"]: row for row in csv.DictReader(output.open(encoding="utf-8"))}
    assert summary["row_count"] == 3
    assert rows["600123"]["balanced_exit_historical_profile"] == "PASSED"
    assert rows["600456"]["balanced_exit_historical_profile"] == "DEGRADED"
    assert rows["600789"]["balanced_exit_historical_profile"] == "FAILED"


def test_proximity_rank_excludes_hard_risk_rejects() -> None:
    rows = _rank_opportunities(
        [
            {
                "code": "600001",
                "tier": "TIER_B",
                "quant_screen_status": "PRIORITY_RESEARCH",
                "a_condition_fail_count": 2,
                "opportunity_quality_score": 60,
                "quant_score": 70,
                "hard_blockers": "",
            },
            {
                "code": "600002",
                "tier": "TIER_C",
                "quant_screen_status": "PRIORITY_RESEARCH",
                "a_condition_fail_count": 1,
                "opportunity_quality_score": 55,
                "quant_score": 65,
                "hard_blockers": "",
            },
            {
                "code": "600003",
                "tier": "REJECTED",
                "quant_screen_status": "HARD_REJECT",
                "a_condition_fail_count": 0,
                "opportunity_quality_score": 80,
                "quant_score": 90,
                "hard_blockers": "financial_safety_failed",
            },
            {
                "code": "600004",
                "tier": "TIER_B",
                "quant_screen_status": "PRIORITY_RESEARCH",
                "a_condition_fail_count": 0,
                "opportunity_quality_score": 80,
                "quant_score": 90,
                "hard_blockers": "balanced_exit_profile_failed",
            },
        ]
    )
    by_code = {row["code"]: row for row in rows}
    assert by_code["600002"]["opportunity_proximity_rank"] == 1
    assert by_code["600001"]["opportunity_proximity_rank"] == 2
    assert by_code["600003"]["opportunity_proximity_rank"] == ""
    assert by_code["600004"]["opportunity_proximity_rank"] == ""


def test_evidence_cache_reuses_unexpired_payload(tmp_path: Path) -> None:
    cache = EvidenceCache(tmp_path / "cache", ttl_days=14)
    key = cache.key_for({"collector": "fixture", "code": "600123"})
    assert cache.get(key) is None
    cache.set(key, {"evidence_rows": [{"code": "600123"}], "audit_rows": []})
    cached = cache.get(key)
    assert cached is not None
    assert cached["cache_hit"] is True
    assert cached["evidence_rows"][0]["code"] == "600123"
    assert cache.cache_hits == 1


def test_github_actions_opportunity_workflow_contract() -> None:
    workflow = Path(".github/workflows/genge-opportunity-discovery.yml").read_text(encoding="utf-8")
    assert "cron:" in workflow
    assert "workflow_dispatch:" in workflow
    assert "run_mode:" in workflow
    assert "actions/upload-artifact@v4" in workflow
    assert "actions/cache/restore@v4" in workflow
    assert "actions/cache/save@v4" in workflow
    assert "data/opportunity_snapshots" in workflow
    assert "data/cache/opportunity_evidence" in workflow
    assert "tests/test_genge_opportunity_discovery_*.py" in workflow
    assert "--run-mode" in workflow
    assert "--exit-profile-file" in workflow
    assert "--forward-ledger-file" in workflow
    assert "--evidence-cache-dir" in workflow
    assert "daily-opportunity-report:" in workflow
    assert "PASS_EVIDENCE_ENRICHMENT_READY" not in workflow
