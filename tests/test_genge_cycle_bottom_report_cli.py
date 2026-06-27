from __future__ import annotations

import csv
import json
from pathlib import Path

from src.strategies.genge_cycle_bottom.cli import main
from src.strategies.genge_cycle_bottom.metrics import compute_summary
from src.strategies.genge_cycle_bottom.report import SIGNAL_DETAIL_COLUMNS, write_reports


FIXTURE_DIR = Path("tests/fixtures/genge_cycle_bottom")


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
        "entry_price",
        "entry_date",
        "entry_mode",
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
    assert summary["avg_raw_return_60d"] == 4.5
    assert summary["avg_max_drawdown_60d"] == -10.5
    assert summary["drawdown"]["default_basis"] == "low_max_drawdown"


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
    assert "drawdown" in summary
