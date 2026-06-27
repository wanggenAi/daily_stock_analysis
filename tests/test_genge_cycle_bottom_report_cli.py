from __future__ import annotations

import csv
import json
from datetime import date, timedelta
from pathlib import Path

from src.strategies.genge_cycle_bottom.acceptance import (
    FAIL_DATA_QUALITY,
    PASS_PAPER_TRADING_READY,
    PASS_REAL_DATA_RESEARCH,
    PASS_RESEARCH_ONLY,
)
from src.strategies.genge_cycle_bottom.cli import main
from src.strategies.genge_cycle_bottom.metrics import compute_summary
from src.strategies.genge_cycle_bottom.report import SIGNAL_DETAIL_COLUMNS, write_reports


FIXTURE_DIR = Path("tests/fixtures/genge_cycle_bottom")


def _summary_row(
    index: int,
    *,
    signal_type: str = "LEFT_SMALL_BUY",
    industry: str = "光伏",
    net_20d: float = 1.0,
    net_60d: float = 2.0,
    net_120d: float = 3.0,
    net_250d: float = 4.0,
    drawdown: float = -6.0,
    missing_fields: str = "",
    risk_flags: str = "",
    trend_score: float = 75.0,
    market_score: float = 60.0,
    industry_score: float = 65.0,
    outperform: bool = True,
    executable_entry_quality: str = "normal",
) -> dict:
    as_of = date(2021, 1, 1) + timedelta(days=index * 30)
    return {
        "code": f"{index:06d}",
        "stock_name": f"测试{index}",
        "as_of_date": as_of.isoformat(),
        "signal_type": signal_type,
        "industry": industry,
        "industry_cycle_phase": "bottom_repair",
        "market_environment_state": "neutral",
        "trend_stabilization_score": trend_score,
        "market_environment_score": market_score,
        "industry_cycle_score": industry_score,
        "valuation_score": 55.0,
        "missing_fields": missing_fields,
        "risk_flags": risk_flags,
        "net_return_20d": net_20d,
        "net_return_60d": net_60d,
        "net_return_120d": net_120d,
        "net_return_250d": net_250d,
        "raw_return_20d": net_20d + 0.3,
        "raw_return_60d": net_60d + 0.3,
        "raw_return_120d": net_120d + 0.3,
        "raw_return_250d": net_250d + 0.3,
        "low_max_drawdown_20d": drawdown,
        "low_max_drawdown_60d": drawdown,
        "low_max_drawdown_120d": drawdown,
        "low_max_drawdown_250d": drawdown,
        "outperform_benchmark_20d": outperform,
        "outperform_benchmark_60d": outperform,
        "outperform_benchmark_120d": outperform,
        "outperform_benchmark_250d": outperform,
        "suspended_or_missing_bar": executable_entry_quality == "missing",
        "limit_up_entry_risk": False,
        "limit_down_entry_risk": False,
        "limit_down_exit_risk": False,
        "abnormal_gap_open": False,
        "low_liquidity_risk": False,
        "executable_entry_quality": executable_entry_quality,
    }


def test_report_fields_include_p0_required_columns(tmp_path: Path) -> None:
    rows = [
        {
            "code": "000001",
            "stock_name": "测试股票",
            "as_of_date": "2024-01-01",
            "signal_type": "LEFT_SMALL_BUY",
            "total_score": 70,
            "price_percentile_score": 80,
            "valuation_score": 70,
            "financial_safety_score": 70,
            "trend_stabilization_score": 70,
            "market_environment_score": 60,
            "industry_cycle_score": 50,
            "industry": "测试行业",
            "industry_cycle_phase": "bottom_repair",
            "market_environment_state": "neutral",
            "entry_price": 10,
            "entry_date": "2024-01-02",
            "entry_mode": "next_open",
            "net_return_60d": 5.0,
            "low_max_drawdown_60d": -3.0,
        }
    ]
    summary = compute_summary(rows, extra_diagnostics={"start_date": "2024-01-01", "end_date": "2024-12-31"})

    report_dir = write_reports(rows, summary, tmp_path)

    with (report_dir / "signal_details.csv").open(newline="", encoding="utf-8") as fh:
        header = next(csv.reader(fh))
    for column in (
        "industry_cycle_score",
        "industry",
        "industry_cycle_phase",
        "market_environment_state",
        "entry_price",
        "entry_date",
        "entry_mode",
        "suspended_or_missing_bar",
        "limit_up_entry_risk",
        "limit_down_entry_risk",
        "limit_down_exit_risk",
        "abnormal_gap_open",
        "low_liquidity_risk",
        "executable_entry_quality",
        "net_return_60d",
        "low_max_drawdown_60d",
        "hit_stop_loss_60d",
    ):
        assert column in SIGNAL_DETAIL_COLUMNS
        assert column in header


def test_summary_defaults_to_net_return_and_low_drawdown() -> None:
    rows = [
        {"code": "1", "as_of_date": "2024-01-01", "signal_type": "LEFT_SMALL_BUY", "raw_return_60d": 10, "net_return_60d": 8, "low_max_drawdown_60d": -9, "close_max_drawdown_60d": -3},
        {"code": "2", "as_of_date": "2024-01-02", "signal_type": "LEFT_SMALL_BUY", "raw_return_60d": -1, "net_return_60d": -3, "low_max_drawdown_60d": -12, "close_max_drawdown_60d": -4},
    ]

    summary = compute_summary(rows)

    assert summary["avg_return_60d"] == 2.5
    assert summary["avg_net_return_60d"] == 2.5
    assert summary["avg_raw_return_60d"] == 4.5
    assert summary["avg_max_drawdown_60d"] == -10.5
    assert summary["drawdown"]["default_basis"] == "low_max_drawdown"
    assert summary["paper_trading_gate"]["verdict"] == PASS_RESEARCH_ONLY


def test_summary_schema_grouping_time_split_failure_reasons_and_data_errors() -> None:
    rows = [
        _summary_row(0, industry="光伏", signal_type="LEFT_SMALL_BUY", net_60d=5.0),
        _summary_row(
            1,
            industry="光伏",
            signal_type="CONFIRM_BUY",
            net_60d=-8.0,
            net_120d=-12.0,
            net_250d=-20.0,
            drawdown=-28.0,
            missing_fields="financial;industry_cycle",
            risk_flags="loss_making",
            trend_score=50.0,
            market_score=35.0,
            industry_score=40.0,
            outperform=False,
        ),
        _summary_row(40, industry="猪肉", signal_type="CONFIRM_BUY", net_60d=4.0),
    ]

    summary = compute_summary(
        rows,
        extra_diagnostics={
            "source_mode": "fixture",
            "fixture_smoke_passed": True,
            "data_errors": {"000999": "TimeoutError: fixture diagnostic"},
        },
    )

    for key in (
        "industry_summary",
        "signal_type_summary",
        "market_environment_summary",
        "industry_cycle_phase_summary",
        "time_split_summary",
        "drawdown_diagnostics",
        "expectancy_diagnostics",
        "failure_reason_summary",
        "low_max_drawdown",
        "benchmark_outperform",
        "paper_trading_gate",
        "valuation_coverage_rate",
        "financial_coverage_rate",
        "industry_cycle_coverage_rate",
        "execution_diagnostics",
    ):
        assert key in summary
    assert summary["industry_summary"]["光伏"]["total_signals"] == 2
    assert summary["signal_type_summary"]["CONFIRM_BUY"]["total_signals"] == 2
    assert "recent_2y" in summary["time_split_summary"]
    assert summary["diagnostics"]["data_errors"]["000999"].startswith("TimeoutError")
    assert summary["diagnostics"]["data_gap_counts"]["financial_missing"] == 1
    assert summary["financial_missing_count"] == 1
    assert summary["industry_cycle_missing_count"] == 1
    assert summary["execution_diagnostics"]["missing_entry_count"] == 0
    assert "coverage" in summary["diagnostics"]
    assert "execution_diagnostics" in summary["diagnostics"]
    assert summary["failure_reason_summary"]["reason_counts"]["趋势未确认"] >= 1
    assert summary["failure_reason_summary"]["reason_counts"]["财务缺失或恶化"] >= 1


def test_paper_trading_gate_keeps_poor_expectancy_out_of_paper_only() -> None:
    good_fixture_rows = [_summary_row(index, net_60d=3.0, net_120d=4.0) for index in range(120)]
    fixture_summary = compute_summary(
        good_fixture_rows,
        extra_diagnostics={"ci_passed": True, "fixture_smoke_passed": True, "source_mode": "fixture"},
    )
    assert fixture_summary["paper_trading_gate"]["verdict"] == PASS_RESEARCH_ONLY

    poor_real_rows = [
        _summary_row(index, net_60d=-1.5, net_120d=-2.0, drawdown=-32.0, outperform=False)
        for index in range(120)
    ]
    poor_summary = compute_summary(
        poor_real_rows,
        extra_diagnostics={
            "ci_passed": True,
            "fixture_smoke_passed": True,
            "source_mode": "real",
            "real_5y_passed": True,
            "real_10y_passed": True,
        },
    )
    assert poor_summary["paper_trading_gate"]["verdict"] == PASS_REAL_DATA_RESEARCH
    assert poor_summary["paper_trading_gate"]["verdict"] != PASS_PAPER_TRADING_READY
    assert "60 日平均净收益未转正" in poor_summary["paper_trading_gate"]["reasons"]


def test_real_data_research_gate_requires_samples_and_fundamental_coverage() -> None:
    good_rows = [_summary_row(index, net_60d=2.0, net_120d=2.5) for index in range(120)]
    good_summary = compute_summary(
        good_rows,
        extra_diagnostics={
            "ci_passed": False,
            "fixture_smoke_passed": True,
            "source_mode": "real",
            "real_5y_passed": True,
            "no_lookahead_risk": True,
            "no_auto_trade": True,
        },
    )

    assert good_summary["valuation_coverage_rate"] == 100.0
    assert good_summary["financial_coverage_rate"] == 100.0
    assert good_summary["paper_trading_gate"]["verdict"] == PASS_REAL_DATA_RESEARCH
    assert good_summary["paper_trading_gate"]["verdict"] != PASS_PAPER_TRADING_READY

    missing_rows = [_summary_row(index, missing_fields="valuation;financial", net_60d=2.0, net_120d=2.5) for index in range(120)]
    missing_summary = compute_summary(
        missing_rows,
        extra_diagnostics={
            "ci_passed": True,
            "fixture_smoke_passed": True,
            "source_mode": "real",
            "real_5y_passed": True,
            "no_lookahead_risk": True,
            "no_auto_trade": True,
        },
    )

    assert missing_summary["valuation_coverage_rate"] == 0.0
    assert missing_summary["financial_coverage_rate"] == 0.0
    assert missing_summary["paper_trading_gate"]["verdict"] == FAIL_DATA_QUALITY
    assert missing_summary["paper_trading_gate"]["verdict"] != PASS_PAPER_TRADING_READY

    valuation_missing_rows = [
        _summary_row(index, missing_fields="valuation", net_60d=2.0, net_120d=2.5)
        for index in range(120)
    ]
    valuation_missing_summary = compute_summary(
        valuation_missing_rows,
        extra_diagnostics={
            "ci_passed": True,
            "fixture_smoke_passed": True,
            "source_mode": "real",
            "real_5y_passed": True,
            "no_lookahead_risk": True,
            "no_auto_trade": True,
        },
    )

    assert valuation_missing_summary["valuation_coverage_rate"] == 0.0
    assert valuation_missing_summary["financial_coverage_rate"] == 100.0
    assert valuation_missing_summary["paper_trading_gate"]["verdict"] == FAIL_DATA_QUALITY

    financial_missing_rows = [
        _summary_row(index, missing_fields="financial", net_60d=2.0, net_120d=2.5)
        for index in range(120)
    ]
    financial_missing_summary = compute_summary(
        financial_missing_rows,
        extra_diagnostics={
            "ci_passed": True,
            "fixture_smoke_passed": True,
            "source_mode": "real",
            "real_5y_passed": True,
            "no_lookahead_risk": True,
            "no_auto_trade": True,
        },
    )

    assert financial_missing_summary["valuation_coverage_rate"] == 100.0
    assert financial_missing_summary["financial_coverage_rate"] == 0.0
    assert financial_missing_summary["paper_trading_gate"]["verdict"] == FAIL_DATA_QUALITY

    small_sample_summary = compute_summary(
        [_summary_row(index, net_60d=2.0, net_120d=2.5) for index in range(90)],
        extra_diagnostics={
            "ci_passed": True,
            "fixture_smoke_passed": True,
            "source_mode": "real",
            "real_5y_passed": True,
            "no_lookahead_risk": True,
            "no_auto_trade": True,
        },
    )

    assert small_sample_summary["paper_trading_gate"]["verdict"] != PASS_REAL_DATA_RESEARCH
    assert small_sample_summary["paper_trading_gate"]["verdict"] != PASS_PAPER_TRADING_READY


def test_github_fixture_smoke_workflow_contract_is_present() -> None:
    workflow = Path(".github/workflows/genge-cycle-bottom.yml").read_text(encoding="utf-8")

    assert "actions/checkout@v4" in workflow
    assert "actions/setup-python@v5" in workflow
    assert "actions/upload-artifact@v4" in workflow
    assert "genge-cycle-bottom-ci-smoke" in workflow
    assert "python -m pytest tests/test_genge_cycle_bottom_*.py" in workflow
    assert "--output-dir reports/genge_cycle_bottom_ci_smoke" in workflow
    assert "summary.md" in workflow
    assert "summary.json" in workflow
    assert "signal_details.csv" in workflow
    assert "execution_diagnostics" in workflow
    assert "valuation_coverage_rate" in workflow


def test_cli_smoke_with_local_fixture_csv(tmp_path: Path) -> None:
    output_dir = tmp_path / "reports"
    exit_code = main(
        [
            "--codes",
            "000001,000002",
            "--years",
            "5",
            "--benchmark",
            "000300",
            "--price-data-dir",
            str(FIXTURE_DIR / "prices"),
            "--valuation-data-dir",
            str(FIXTURE_DIR / "valuation"),
            "--financial-data-dir",
            str(FIXTURE_DIR / "financial"),
            "--industry-cycle-file",
            str(FIXTURE_DIR / "industry_cycle.csv"),
            "--stock-industry-map",
            str(FIXTURE_DIR / "stock_industry_map.csv"),
            "--step-days",
            "20",
            "--output-dir",
            str(output_dir),
        ]
    )

    assert exit_code == 0
    report_dirs = sorted(path for path in output_dir.iterdir() if path.is_dir())
    assert report_dirs
    latest = report_dirs[-1]
    for filename in ("signal_details.csv", "summary.json", "summary.md"):
        assert (latest / filename).exists()
    summary = json.loads((latest / "summary.json").read_text(encoding="utf-8"))
    assert summary["total_signals"] > 0
    assert "avg_return_60d" in summary
    assert "avg_net_return_60d" in summary
    assert "drawdown" in summary
    assert "industry_summary" in summary
    assert "paper_trading_gate" in summary
    assert "execution_diagnostics" in summary
    assert "provider_errors" in summary["diagnostics"]
    assert summary["diagnostics"]["industry_cycle_source"] == "fixture"


def test_cli_fixture_smoke_context_flag_for_real_runs(tmp_path: Path) -> None:
    output_dir = tmp_path / "reports"
    pool_file = tmp_path / "pool.txt"
    pool_file.write_text("000001,测试银行,银行\n", encoding="utf-8")
    exit_code = main(
        [
            "--stock-pool-file",
            str(pool_file),
            "--years",
            "5",
            "--benchmark",
            "000300",
            "--price-data-dir",
            str(FIXTURE_DIR / "prices"),
            "--valuation-data-dir",
            str(FIXTURE_DIR / "valuation"),
            "--financial-data-dir",
            str(FIXTURE_DIR / "financial"),
            "--benchmark-file",
            str(FIXTURE_DIR / "prices" / "000300.csv"),
            "--step-days",
            "60",
            "--fixture-smoke-passed",
            "--ci-passed",
            "--output-dir",
            str(output_dir),
        ]
    )

    assert exit_code == 0
    latest = sorted(path for path in output_dir.iterdir() if path.is_dir())[-1]
    summary = json.loads((latest / "summary.json").read_text(encoding="utf-8"))
    assert summary["diagnostics"]["fixture_smoke_passed"] is True
    assert summary["diagnostics"]["ci_passed"] is True


def test_real_runner_step_days_defaults_and_fast_smoke() -> None:
    from scripts.run_genge_real_research import build_parser, resolve_step_days

    parser = build_parser()
    assert resolve_step_days(parser.parse_args([])) == 1
    assert resolve_step_days(parser.parse_args(["--fast-smoke"])) == 20
    assert resolve_step_days(parser.parse_args(["--fast-smoke", "--step-days", "7"])) == 7
    assert parser.parse_args(["--fixture-smoke-passed"]).fixture_smoke_passed is True
    assert parser.parse_args(["--ci-passed"]).ci_passed is True
