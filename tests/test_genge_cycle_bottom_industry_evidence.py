from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

import pandas as pd

from scripts.update_industry_evidence_from_research import main as update_evidence_main
from src.strategies.genge_cycle_bottom.backtest import BALANCED_EXIT_POLICY_NAME
from src.strategies.genge_cycle_bottom.cli import main as cli_main
from src.strategies.genge_cycle_bottom.features import FeatureSet
from src.strategies.genge_cycle_bottom.industry_evidence import (
    ConfidenceLevel,
    CyclePhase,
    EvidenceDirection,
    EvidenceItem,
    EvidenceQuality,
    HardLogicLevel,
    compute_company_evidence_score,
    compute_hard_logic_level,
    compute_industry_evidence_score,
    load_industry_evidence_schema,
)
from src.strategies.genge_cycle_bottom.metrics import compute_summary
from src.strategies.genge_cycle_bottom.report import write_reports
from src.strategies.genge_cycle_bottom.signals import SignalType
from src.strategies.genge_cycle_bottom.strategy import GenGeCycleBottomStrategy


FIXTURE_DIR = Path("tests/fixtures/genge_cycle_bottom")
FORBIDDEN_WORDS = (
    "保证" + "上涨",
    "确定" + "买入",
    "必" + "买",
    "必" + "卖",
    "稳" + "赚",
    "确定" + "上涨",
    "买入" + "清单",
)


def _schema() -> dict:
    return load_industry_evidence_schema("config/industry_evidence_schema.yaml")


def _industry_rows() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "date": "2024-01-01",
                "industry": "猪肉",
                "evidence_name": "能繁母猪存栏变化",
                "evidence_value": "同比下降",
                "evidence_direction": "POSITIVE",
                "source": "统计局",
                "source_type": "provider_derived",
                "confidence": "HIGH",
            },
            {
                "date": "2024-01-03",
                "industry": "猪肉",
                "evidence_name": "猪粮比价",
                "evidence_value": "低位修复",
                "evidence_direction": "POSITIVE",
                "source": "发改委",
                "source_type": "provider_derived",
                "confidence": "HIGH",
            },
            {
                "date": "2024-01-05",
                "industry": "猪肉",
                "evidence_name": "行业亏损持续时间",
                "evidence_value": "亏损延续后收窄",
                "evidence_direction": "POSITIVE",
                "source": "行业协会",
                "source_type": "user_supplied",
                "confidence": "MEDIUM",
            },
            {
                "date": "2024-01-05",
                "industry": "猪肉",
                "evidence_name": "仔猪价格变化",
                "evidence_value": "企稳",
                "evidence_direction": "POSITIVE",
                "source": "行业协会",
                "source_type": "user_supplied",
                "confidence": "MEDIUM",
            },
        ]
    )


def test_schema_dataclasses_and_yaml_loading_cover_required_industries() -> None:
    schema = _schema()

    assert {"猪肉", "面板", "稀土", "光伏", "锂电", "化工", "有色"}.issubset(schema["industries"])
    assert schema["aliases"]["养殖"] == "猪肉"
    for config in schema["industries"].values():
        assert len(config["indicators"]) >= 5
    item = EvidenceItem(
        evidence_name="测试证据",
        evidence_value="测试值",
        evidence_direction=EvidenceDirection.POSITIVE.value,
        evidence_date="2024-01-01",
        source="公开来源",
        source_type=EvidenceQuality.USER_SUPPLIED.value,
        freshness_days=1,
        weight=1.0,
    )
    assert item.to_dict()["evidence_direction"] == EvidenceDirection.POSITIVE.value


def test_pork_and_panel_scoring_use_schema_alias_and_ignore_future_rows() -> None:
    schema = _schema()
    rows = pd.concat(
        [
            _industry_rows(),
            pd.DataFrame(
                [
                    {
                        "date": "2025-01-01",
                        "industry": "猪肉",
                        "evidence_name": "冻品库存变化",
                        "evidence_value": "未来行",
                        "evidence_direction": "NEGATIVE",
                        "source": "未来来源",
                        "source_type": "provider_derived",
                    },
                    {
                        "date": "2024-01-02",
                        "industry": "面板",
                        "evidence_name": "面板价格月度变化",
                        "evidence_value": "止跌回升",
                        "evidence_direction": "POSITIVE",
                        "source": "WitsView",
                        "source_type": "user_supplied",
                    },
                    {
                        "date": "2024-01-02",
                        "industry": "面板",
                        "evidence_name": "稼动率变化",
                        "evidence_value": "温和提升",
                        "evidence_direction": "POSITIVE",
                        "source": "产业链调研",
                        "source_type": "user_supplied",
                    },
                ]
            ),
        ],
        ignore_index=True,
    )

    pork = compute_industry_evidence_score("养殖", date(2024, 2, 1), rows, schema)
    panel = compute_industry_evidence_score("面板", date(2024, 2, 1), rows, schema)

    assert pork.evidence_score > 60
    assert pork.cycle_phase in {CyclePhase.BOTTOMING.value, CyclePhase.RECOVERING.value}
    assert pork.negative_evidence_count == 0
    assert panel.evidence_score > 55
    assert panel.confidence_level in {ConfidenceLevel.LOW.value, ConfidenceLevel.MEDIUM.value}


def test_stale_missing_manual_and_conflict_flags_are_conservative() -> None:
    schema = _schema()
    stale_rows = pd.DataFrame(
        [
            {
                "date": "2022-01-01",
                "industry": "猪肉",
                "evidence_name": "能繁母猪存栏变化",
                "evidence_value": "旧证据",
                "evidence_direction": "POSITIVE",
                "source": "模板",
                "source_type": "manual_template",
            },
            {
                "date": "2024-01-01",
                "industry": "猪肉",
                "evidence_name": "能繁母猪存栏变化",
                "evidence_value": "方向冲突",
                "evidence_direction": "NEGATIVE",
                "source": "模板",
                "source_type": "manual_template",
            },
        ]
    )

    evidence = compute_industry_evidence_score("猪肉", date(2024, 8, 1), stale_rows, schema)

    assert evidence.stale_evidence_count >= 1
    assert "stale_evidence" in evidence.warning_flags
    assert "missing_required_evidence" in evidence.warning_flags
    assert "evidence_conflict" in evidence.warning_flags
    assert evidence.evidence_quality == EvidenceQuality.MANUAL_TEMPLATE.value
    assert evidence.confidence_level != ConfidenceLevel.HIGH.value


def test_hard_logic_strong_requires_non_manual_industry_and_company_evidence() -> None:
    schema = _schema()
    industry_evidence = compute_industry_evidence_score("猪肉", date(2024, 2, 1), _industry_rows(), schema)
    missing_company = compute_company_evidence_score("000001", date(2024, 2, 1), pd.DataFrame())
    weak = compute_hard_logic_level(industry_evidence, missing_company)

    company_rows = pd.DataFrame(
        [
            {
                "date": "2024-01-05",
                "code": "000001",
                "stock_name": "测试",
                "industry": "猪肉",
                "evidence_name": "成本改善",
                "evidence_value": "饲料成本下降",
                "evidence_direction": "POSITIVE",
                "source": "公告",
                "source_type": "provider_derived",
            },
            {
                "date": "2024-01-06",
                "code": "000001",
                "stock_name": "测试",
                "industry": "猪肉",
                "evidence_name": "现金流",
                "evidence_value": "改善",
                "evidence_direction": "POSITIVE",
                "source": "公告",
                "source_type": "provider_derived",
            },
        ]
    )
    company = compute_company_evidence_score("000001", date(2024, 2, 1), company_rows)
    strong = compute_hard_logic_level(industry_evidence, company)

    assert weak.hard_logic_level in {HardLogicLevel.WEAK.value, HardLogicLevel.MEDIUM.value}
    assert strong.hard_logic_level in {HardLogicLevel.MEDIUM.value, HardLogicLevel.STRONG.value}
    manual = compute_industry_evidence_score(
        "猪肉",
        date(2024, 2, 1),
        _industry_rows().assign(source_type="manual_template"),
        schema,
    )
    assert compute_hard_logic_level(manual, company).hard_logic_level != HardLogicLevel.STRONG.value


def test_negative_evidence_downgrades_confirm_signal() -> None:
    feature = FeatureSet(
        as_of_date=date(2024, 1, 1),
        close=10,
        financial_safety_score=80,
        trend_stabilization_score=90,
        market_environment_score=70,
        industry_cycle_score=70,
        history_sufficiency_quality="adequate",
        long_term_position_risk_score=20,
        no_falling_knife_filter=True,
        stabilization_days=8,
        trend_confirmation_level="MEDIUM",
        stop_loss_distance_pct=6,
        industry_cycle_quality="user_supplied",
        industry_evidence_quality=EvidenceQuality.USER_SUPPLIED.value,
        industry_evidence_score=35,
        hard_logic_level=HardLogicLevel.WEAK.value,
    )

    signal = GenGeCycleBottomStrategy()._classify(85, feature, ["negative_industry_evidence"])

    assert signal == SignalType.WATCH


def _candidate_row() -> dict:
    return {
        "code": "000001",
        "stock_name": "测试股票",
        "industry": "猪肉",
        "as_of_date": "2024-02-01",
        "signal_type": "LEFT_SMALL_BUY",
        "total_score": 78,
        "price_percentile_5y": 0.22,
        "valuation_score": 62,
        "financial_safety_score": 68,
        "trend_confirmation_level": "MEDIUM",
        "industry_cycle_phase": "RECOVERING",
        "industry_evidence_score": 70,
        "industry_evidence_confidence": "MEDIUM",
        "industry_evidence_quality": "USER_SUPPLIED",
        "industry_evidence_source_type": "USER_SUPPLIED",
        "industry_evidence_summary": "猪肉 行业证据分 70.0，阶段 RECOVERING。",
        "industry_evidence_positive_count": 4,
        "industry_evidence_negative_count": 0,
        "industry_evidence_neutral_count": 0,
        "industry_evidence_stale_count": 0,
        "industry_evidence_warning_flags": "",
        "industry_evidence_missing_fields": "",
        "hard_logic_level": "MEDIUM",
        "hard_logic_score": 72,
        "value_trap_score": 30,
        "execution_risk_score": 10,
        "executable_entry_quality": "good",
        "stop_loss_distance_pct": 8,
        "long_term_position_risk_score": 30,
        "history_sufficiency_quality": "adequate",
        "risk_flags": "",
        f"{BALANCED_EXIT_POLICY_NAME}_exit_adjusted_net_return_60d": 1.2,
        "net_return_60d": 1.2,
        "low_max_drawdown_250d": -8,
    }


def test_candidate_csv_evidence_cards_and_disclaimer_have_no_forbidden_words(tmp_path: Path) -> None:
    rows = [_candidate_row()]
    summary = compute_summary(rows)

    report_dir = write_reports(
        rows,
        summary,
        tmp_path,
        output_industry_evidence_cards=True,
        output_cycle_turning_point_candidates=True,
    )

    candidate_text = (report_dir / "cycle_turning_point_candidates.csv").read_text(encoding="utf-8")
    cards_text = (report_dir / "industry_evidence_cards.md").read_text(encoding="utf-8")
    assert "研究观察候选" in candidate_text
    assert "不构成买入建议" in candidate_text
    assert "STRONG 表示行业与公司证据相对一致" in cards_text
    for word in FORBIDDEN_WORDS:
        assert word not in candidate_text
        assert word not in cards_text


def test_industry_evidence_acceptance_uses_new_conservative_enum() -> None:
    rows = [_candidate_row()]
    summary = compute_summary(
        rows,
        extra_diagnostics={
            "source_mode": "real",
            "ci_passed": True,
            "fixture_smoke_passed": True,
            "real_5y_passed": True,
            "no_lookahead_risk": True,
            "no_auto_trade": True,
            "industry_evidence_file": "data/examples/industry_cycle_evidence_template.csv",
            "company_evidence_file": "data/examples/company_cycle_evidence_template.csv",
            "industry_evidence_source": "manual_template",
            "company_evidence_source": "manual_template",
            "industry_evidence_schema": "config/industry_evidence_schema.yaml",
            "industry_evidence_schema_industries": ["猪肉", "面板", "稀土", "光伏", "锂电", "化工", "有色"],
        },
    )

    assert summary["paper_trading_gate"]["verdict"] == "PASS_INDUSTRY_EVIDENCE_FRAMEWORK"
    assert summary["evidence_source_type_distribution"]["industry"]["USER_SUPPLIED"] == 1
    assert summary["evidence_source_type_distribution"]["company"]["MISSING"] == 1


def test_research_update_script_downgrades_missing_source(tmp_path: Path) -> None:
    research_dir = tmp_path / "research"
    research_dir.mkdir()
    (research_dir / "pork.json").write_text(
        json.dumps(
            {
                "industry_evidence": [
                    {
                        "date": "2024-01-01",
                        "industry": "猪肉",
                        "evidence_name": "能繁母猪存栏变化",
                        "evidence_value": "下降",
                        "evidence_direction": "POSITIVE",
                    }
                ],
                "company_evidence": [
                    {
                        "date": "2024-01-02",
                        "code": "1",
                        "stock_name": "测试",
                        "industry": "猪肉",
                        "evidence_name": "成本改善",
                        "evidence_value": "改善",
                        "evidence_direction": "POSITIVE",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    industry_output = tmp_path / "industry.csv"
    company_output = tmp_path / "company.csv"

    assert update_evidence_main(
        [
            "--research-dir",
            str(research_dir),
            "--output",
            str(industry_output),
            "--company-output",
            str(company_output),
        ]
    ) == 0

    rows = list(csv.DictReader(industry_output.open(encoding="utf-8")))
    company_rows = list(csv.DictReader(company_output.open(encoding="utf-8")))
    report_text = (industry_output.parent / "evidence_quality_report.md").read_text(encoding="utf-8")
    assert rows[0]["source_type"] == "manual_template"
    assert rows[0]["confidence"] == "LOW"
    assert company_rows[0]["code"] == "000001"
    assert "missing_source_rows: 2" in report_text


def test_cli_fixture_smoke_with_evidence_args(tmp_path: Path) -> None:
    output_dir = tmp_path / "smoke"

    assert cli_main(
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
            "--industry-evidence-file",
            str(FIXTURE_DIR / "industry_evidence.csv"),
            "--company-evidence-file",
            str(FIXTURE_DIR / "company_evidence.csv"),
            "--industry-evidence-schema",
            "config/industry_evidence_schema.yaml",
            "--output-industry-evidence-cards",
            "--output-cycle-turning-point-candidates",
            "--output-dir",
            str(output_dir),
        ]
    ) == 0

    latest = sorted(path for path in output_dir.iterdir() if path.is_dir())[-1]
    summary = json.loads((latest / "summary.json").read_text(encoding="utf-8"))
    assert (latest / "industry_evidence_cards.md").exists()
    assert (latest / "cycle_turning_point_candidates.csv").exists()
    assert "industry_evidence_coverage_rate" in summary
    assert "evidence_source_type_distribution" in summary
    assert "hard_logic_level_summary" in summary


def test_no_auto_trade_and_no_lookahead_contracts_remain_explicit() -> None:
    summary = compute_summary(
        [_candidate_row()],
        extra_diagnostics={"no_auto_trade": True, "no_lookahead_risk": True},
    )

    assert summary["diagnostics"]["no_auto_trade"] is True
    assert summary["diagnostics"]["no_lookahead_risk"] is True
