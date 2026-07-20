from __future__ import annotations

import argparse
import csv
import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.run_genge_real_research import _build_strategy_args, build_parser
from src.strategies.genge_cycle_bottom import cli as genge_cli
from src.strategies.genge_cycle_bottom.backtest import BacktestInput
from src.strategies.genge_cycle_bottom.current_snapshot import (
    AliasResolution,
    IndustryAliasResolver,
    SNAPSHOT_DECISIONS,
    _current_hard_logic,
    load_industry_alias_map,
    run_current_snapshot_report,
)
from src.strategies.genge_cycle_bottom.industry_evidence import load_industry_evidence_schema


def _price_frame(*, with_future: bool = True) -> pd.DataFrame:
    dates = pd.date_range(end="2026-06-24", periods=1000, freq="D")
    closes = np.concatenate(
        [
            np.linspace(22.0, 14.0, 650),
            np.linspace(14.0, 9.5, 220),
            np.linspace(9.5, 11.2, 80),
            np.linspace(11.0, 11.8, 50),
        ]
    )
    rows = []
    for index, (day, close) in enumerate(zip(dates, closes)):
        rows.append(
            {
                "date": day.date().isoformat(),
                "open": round(close * 0.995, 3),
                "high": round(close * 1.02, 3),
                "low": round(close * 0.98, 3),
                "close": round(float(close), 3),
                "volume": 1_500_000 + index * 100,
                "amount": 20_000_000 + index * 1000,
            }
        )
    if with_future:
        rows.append(
            {
                "date": "2026-07-01",
                "open": 55.0,
                "high": 60.0,
                "low": 52.0,
                "close": 58.0,
                "volume": 8_000_000,
                "amount": 500_000_000,
            }
        )
    return pd.DataFrame(rows)


def _valuation_frame() -> pd.DataFrame:
    dates = pd.date_range(end="2026-06-24", periods=900, freq="D")
    return pd.DataFrame(
        {
            "date": [day.date().isoformat() for day in dates],
            "pb": np.linspace(2.5, 1.0, len(dates)),
            "pe": np.linspace(32.0, 12.0, len(dates)),
            "ps": np.linspace(5.5, 1.6, len(dates)),
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
            },
            {
                "report_date": "2026-06-30",
                "disclosure_date": "2026-07-30",
                "debt_ratio": 95.0,
                "net_profit": -1_000_000_000,
                "operating_cash_flow": -1_000_000_000,
                "roe": -10.0,
            },
        ]
    )


def _industry_evidence_rows() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "date": "2026-06-15",
                "industry": "面板",
                "evidence_name": "面板价格",
                "evidence_value": "主流尺寸价格低位回升",
                "evidence_direction": "POSITIVE",
                "source": "公开产业数据",
                "source_type": "official_report",
            },
            {
                "date": "2026-06-16",
                "industry": "面板",
                "evidence_name": "稼动率",
                "evidence_value": "供给维持纪律性",
                "evidence_direction": "POSITIVE",
                "source": "行业公开摘要",
                "source_type": "user_supplied",
            },
            {
                "date": "2026-06-17",
                "industry": "面板",
                "evidence_name": "库存水位",
                "evidence_value": "库存下降至合理水平",
                "evidence_direction": "POSITIVE",
                "source": "行业公开摘要",
                "source_type": "user_supplied",
            },
            {
                "date": "2026-07-01",
                "industry": "面板",
                "evidence_name": "面板价格",
                "evidence_value": "未来负向行不应参与 as-of",
                "evidence_direction": "NEGATIVE",
                "source": "未来数据",
                "source_type": "official_report",
            },
        ]
    )


def _company_evidence_rows() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "date": "2026-06-18",
                "code": "000100",
                "stock_name": "TCL科技",
                "industry": "面板",
                "evidence_name": "产能结构",
                "evidence_value": "高端产线占比提升",
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
                "evidence_value": "库存周转改善",
                "evidence_direction": "POSITIVE",
                "source": "交易所披露",
                "source_type": "exchange_disclosure",
            },
        ]
    )


def test_industry_alias_resolution_supports_alias_code_priority_and_unresolved() -> None:
    alias_map = load_industry_alias_map("config/industry_alias_map.yaml")
    company_evidence = pd.concat(
        [
            _company_evidence_rows(),
            pd.DataFrame([{"code": "600003", "industry": "UNRESOLVED"}]),
        ],
        ignore_index=True,
    )
    resolver = IndustryAliasResolver(alias_map, company_evidence)

    code_priority = resolver.resolve(code="000100", stock_name="TCL科技", raw_industry="银行")
    alias = resolver.resolve(code="600000", stock_name="测试", raw_industry=" tft-lcd ")
    exact = resolver.resolve(code="600001", stock_name="测试", raw_industry="猪肉")
    structured = resolver.resolve(code="600003", stock_name="测试", raw_industry="C26化学原料和化学制品制造业")
    ambiguous_equipment = resolver.resolve(code="600004", stock_name="测试", raw_industry="C35专用设备制造业")
    explicit_machinery = resolver.resolve(code="600005", stock_name="测试", raw_industry="建筑工程机械制造业")
    unresolved = resolver.resolve(code="600002", stock_name="测试", raw_industry="未知行业")

    assert code_priority.normalized_industry == "面板"
    assert code_priority.match_type == "COMPANY_CODE"
    assert alias.normalized_industry == "面板"
    assert alias.match_type == "ALIAS"
    assert exact.match_type == "EXACT"
    assert structured.normalized_industry == "化工"
    assert structured.match_type == "SUBSTRING_ALIAS"
    assert ambiguous_equipment.normalized_industry == "UNRESOLVED"
    assert ambiguous_equipment.match_type == "UNRESOLVED"
    assert explicit_machinery.normalized_industry == "工程机械"
    assert unresolved.normalized_industry == "UNRESOLVED"
    assert unresolved.match_type == "UNRESOLVED"


def test_current_hard_logic_medium_and_strong_require_current_evidence() -> None:
    resolution = AliasResolution("000100", "TCL科技", "面板", "面板", "面板", "EXACT", "HIGH")
    base_row = {
        "industry_evidence_quality": "OFFICIAL_REPORT",
        "industry_evidence_confidence": "MEDIUM",
        "industry_cycle_phase": "RECOVERING",
        "industry_evidence_score": 72.0,
        "company_evidence_score": 62.0,
        "company_evidence_confidence": "LOW",
        "industry_evidence_positive_count": 3,
        "industry_evidence_negative_count": 0,
        "industry_evidence_stale_count": 0,
        "industry_evidence_items": json.dumps(
            [{"source_type": "OFFICIAL_REPORT", "evidence_direction": "POSITIVE", "freshness_days": 5}],
            ensure_ascii=False,
        ),
        "company_evidence_items": "[]",
        "company_evidence_source_type": "MISSING",
        "trend_confirmation_level": "MEDIUM",
        "financial_safety_score": 70.0,
        "execution_risk_quality": "good",
        "execution_risk_score": 5.0,
        "price_percentile_5y": 0.2,
        "risk_flags": "",
    }

    _, medium_level, _, medium_blockers = _current_hard_logic(dict(base_row), resolution)
    assert medium_level == "MEDIUM"
    assert "company_evidence" in medium_blockers

    strong_row = dict(base_row)
    strong_row.update(
        {
            "company_evidence_confidence": "MEDIUM",
            "company_evidence_source_type": "COMPANY_ANNOUNCEMENT",
            "company_evidence_items": json.dumps(
                [
                    {"source_type": "COMPANY_ANNOUNCEMENT", "evidence_direction": "POSITIVE", "freshness_days": 3},
                    {"source_type": "EXCHANGE_DISCLOSURE", "evidence_direction": "POSITIVE", "freshness_days": 2},
                ],
                ensure_ascii=False,
            ),
        }
    )
    _, strong_level, _, strong_blockers = _current_hard_logic(strong_row, resolution)
    assert strong_level == "STRONG"
    assert not strong_blockers

    unresolved = AliasResolution("000100", "TCL科技", "银行", "UNRESOLVED", "", "UNRESOLVED", "LOW")
    _, missing_level, _, missing_blockers = _current_hard_logic(dict(base_row), unresolved)
    assert missing_level == "NONE"
    assert "industry_evidence_missing_or_unresolved" in missing_blockers


def test_current_snapshot_report_uses_asof_current_evidence_and_writes_audits(tmp_path: Path) -> None:
    alias_map = load_industry_alias_map("config/industry_alias_map.yaml")
    schema = load_industry_evidence_schema("config/industry_evidence_schema.yaml")
    inputs = [
        BacktestInput(
            code="000100",
            stock_name="TCL科技",
            price_df=_price_frame(with_future=True),
            valuation_df=_valuation_frame(),
            financial_df=_financial_frame(),
            industry="光学光电子",
        )
    ]

    report_dir, summary = run_current_snapshot_report(
        inputs=inputs,
        requested_codes=["000100", "000999"],
        data_errors={"000999": "ValueError: delist invalid not found"},
        data_sources={"000100": "csv", "000999": "akshare"},
        benchmark_df=_price_frame(with_future=False),
        industry_cycle_df=None,
        industry_evidence_df=_industry_evidence_rows(),
        company_evidence_df=_company_evidence_rows(),
        industry_evidence_schema=schema,
        industry_alias_map=alias_map,
        requested_as_of_date="2026-06-24",
        output_dir=tmp_path,
        diagnostics={
            "industry_evidence_file": "data/user_supplied/industry_cycle_evidence.csv",
            "company_evidence_file": "data/user_supplied/company_cycle_evidence.csv",
            "industry_alias_map": "config/industry_alias_map.yaml",
            "no_auto_trade": True,
        },
    )

    assert summary["resolved_as_of_date"] == "2026-06-24"
    assert summary["latest_price_date_by_stock"]["000100"] == "2026-06-24"
    assert summary["snapshot_total_stocks"] == 2
    assert summary["snapshot_valid_stocks"] == 1
    assert summary["fatal_data_failures"] == 0
    assert summary["skipped_invalid_or_delisted"] == 1
    assert summary["current_industry_evidence_coverage"] == 100.0
    assert summary["current_company_evidence_coverage"] == 100.0
    assert summary["acceptance_enum"] == "PASS_CURRENT_SNAPSHOT_PIPELINE_READY"

    all_rows = list(csv.DictReader((report_dir / "current_snapshot_all.csv").open(encoding="utf-8")))
    assert all_rows[0]["latest_price_date"] == "2026-06-24"
    assert all_rows[0]["normalized_industry"] == "面板"
    assert all_rows[0]["snapshot_decision"] in SNAPSHOT_DECISIONS
    assert "BUY" not in all_rows[0]["snapshot_decision"]
    assert "SELL" not in all_rows[0]["snapshot_decision"]
    assert "未来负向行不应参与 as-of" not in all_rows[0]["evidence_items"]

    audit_rows = list(csv.DictReader((report_dir / "data_failure_audit.csv").open(encoding="utf-8")))
    assert audit_rows[0]["final_status"] == "SKIPPED_INVALID_OR_DELISTED"
    alias_rows = list(csv.DictReader((report_dir / "industry_alias_resolution.csv").open(encoding="utf-8")))
    assert alias_rows[0]["match_type"] == "COMPANY_CODE"
    assert (report_dir / "current_cycle_turning_point_candidates.csv").exists()
    candidate_text = (report_dir / "current_cycle_turning_point_candidates.csv").read_text(encoding="utf-8")
    assert "仅用于公开数据研究观察和人工复核，不构成买入建议，不应自动交易。" in candidate_text


def test_current_snapshot_all_price_failures_write_alias_audit_and_fail(tmp_path: Path) -> None:
    alias_map = load_industry_alias_map("config/industry_alias_map.yaml")
    schema = load_industry_evidence_schema("config/industry_evidence_schema.yaml")

    report_dir, summary = run_current_snapshot_report(
        inputs=[],
        requested_codes=["000100", "000725"],
        data_errors={
            "000100": "RuntimeError: current snapshot live price fetch skipped after 3 consecutive provider failures",
            "000725": "RuntimeError: current snapshot live price fetch skipped after 3 consecutive provider failures",
        },
        data_sources={
            "000100": "skipped_live_provider_budget",
            "000725": "skipped_live_provider_budget",
        },
        benchmark_df=None,
        industry_cycle_df=None,
        industry_evidence_df=_industry_evidence_rows(),
        company_evidence_df=_company_evidence_rows(),
        industry_evidence_schema=schema,
        industry_alias_map=alias_map,
        requested_as_of_date="2026-06-24",
        output_dir=tmp_path,
        diagnostics={
            "industry_evidence_file": "data/user_supplied/industry_cycle_evidence.csv",
            "company_evidence_file": "data/user_supplied/company_cycle_evidence.csv",
            "industry_alias_map": "config/industry_alias_map.yaml",
            "requested_stock_records": [
                {"code": "000100", "stock_name": "TCL科技", "industry": "光学光电子"},
                {"code": "000725", "stock_name": "京东方A", "industry": "显示器件"},
            ],
            "no_auto_trade": True,
        },
    )

    assert summary["snapshot_total_stocks"] == 2
    assert summary["snapshot_valid_stocks"] == 0
    assert summary["fatal_data_failures"] == 0
    assert summary["skipped_data_unavailable"] == 2
    assert summary["data_failure_status_distribution"] == {"SKIPPED_DATA_UNAVAILABLE": 2}
    assert summary["acceptance_enum"] == "FAIL_CURRENT_SNAPSHOT"

    alias_rows = list(csv.DictReader((report_dir / "industry_alias_resolution.csv").open(encoding="utf-8")))
    assert len(alias_rows) == 2
    assert {row["normalized_industry"] for row in alias_rows} == {"面板"}

    failure_rows = list(csv.DictReader((report_dir / "data_failure_audit.csv").open(encoding="utf-8")))
    assert len(failure_rows) == 2
    assert {row["final_status"] for row in failure_rows} == {"SKIPPED_DATA_UNAVAILABLE"}
    assert {row["provider"] for row in failure_rows} == {"skipped_live_provider_budget"}


def test_current_snapshot_live_price_failure_budget_marks_remaining(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []

    def failing_current_snapshot_fetch(stock_code: str, *_: object) -> tuple[pd.DataFrame, str]:
        calls.append(stock_code)
        raise RuntimeError("RemoteDisconnected connection timeout")

    pool_file = tmp_path / "pool.txt"
    pool_file.write_text(
        "\n".join(
            [
                "000001,测试1,面板",
                "000002,测试2,面板",
                "000003,测试3,面板",
                "000004,测试4,面板",
                "000005,测试5,面板",
            ]
        ),
        encoding="utf-8",
    )
    args = argparse.Namespace(
        current_snapshot=True,
        output_current_snapshot=True,
        price_data_dir=None,
        valuation_data_dir=None,
        financial_data_dir=None,
        stock_industry_map=None,
        stock_pool_file=str(pool_file),
        fundamental_cache_dir=str(tmp_path / "cache"),
        auto_fetch_valuation=False,
        auto_fetch_financial=False,
        years=5,
    )

    monkeypatch.setattr(genge_cli, "_fetch_price_live_current_snapshot", failing_current_snapshot_fetch)
    monkeypatch.setattr(genge_cli, "_get_manager", lambda: object())
    inputs, sources, errors, _ = genge_cli._load_inputs(
        codes=["000001", "000002", "000003", "000004", "000005"],
        args=args,
        start_date=date(2020, 1, 1),
        end_date=date(2026, 7, 5),
    )

    assert inputs == []
    assert len(calls) == genge_cli._CURRENT_SNAPSHOT_PRICE_FAILURE_LIMIT
    assert len(errors) == 5
    assert sources["000004"] == "skipped_live_provider_budget"
    assert sources["000005"] == "skipped_live_provider_budget"
    assert genge_cli._has_current_snapshot_provider_outage(errors, list(errors))


def test_current_snapshot_live_price_uses_manager_fallback() -> None:
    class FakeManager:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def get_daily_data(self, code: str, *, start_date: str, end_date: str, days: int):
            self.calls.append(
                {
                    "code": code,
                    "start_date": start_date,
                    "end_date": end_date,
                    "days": days,
                }
            )
            return _price_frame(with_future=False), "TencentFetcher"

    manager = FakeManager()

    df, source = genge_cli._fetch_price_live_current_snapshot(
        "000100",
        date(2021, 7, 5),
        date(2026, 7, 5),
        5,
        manager,
    )

    assert source == "TencentFetcher"
    assert not df.empty
    assert manager.calls[0]["code"] == "000100"
    assert manager.calls[0]["start_date"] == "2021-07-05"
    assert manager.calls[0]["end_date"] == "2026-07-05"


def test_real_runner_passes_current_snapshot_arguments(tmp_path: Path) -> None:
    pool_file = tmp_path / "pool.txt"
    pool_file.write_text("000100,TCL科技,面板\n", encoding="utf-8")
    parser = build_parser()
    args = parser.parse_args(
        [
            "--stock-pool-file",
            str(pool_file),
            "--years",
            "5",
            "--benchmark",
            "000905",
            "--output-dir",
            str(tmp_path / "reports"),
            "--industry-evidence-file",
            "data/user_supplied/industry_cycle_evidence.csv",
            "--company-evidence-file",
            "data/user_supplied/company_cycle_evidence.csv",
            "--industry-evidence-schema",
            "config/industry_evidence_schema.yaml",
            "--industry-alias-map",
            "config/industry_alias_map.yaml",
            "--current-snapshot",
            "--output-current-snapshot",
        ]
    )
    args.step_days = 1

    strategy_args = _build_strategy_args(args, pool_file)

    assert "--current-snapshot" in strategy_args
    assert "--output-current-snapshot" in strategy_args
    assert strategy_args[strategy_args.index("--industry-alias-map") + 1] == "config/industry_alias_map.yaml"
