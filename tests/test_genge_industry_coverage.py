import csv

from src.strategies.genge_opportunity_discovery.industry_coverage import (
    find_latest_report,
    select_industry_coverage,
)


def test_every_industry_keeps_up_to_five_research_names():
    rows = []
    for industry in ("钨", "银行", "半导体"):
        for i in range(8):
            rows.append({
                "code": f"{len(rows)+1:06d}",
                "stock_name": f"{industry}{i}",
                "industry": industry,
                "quant_status": "SECONDARY_RESEARCH" if i < 3 else "LOW_PRIORITY",
                "quant_score": 80 - i,
                "hard_blockers": "",
            })
    selected = select_industry_coverage(rows, per_industry=5)
    assert len(selected) == 15
    for industry in ("钨", "银行", "半导体"):
        group = [row for row in selected if row["industry"] == industry]
        assert len(group) == 5
        assert [row["industry_research_rank"] for row in group] == [1, 2, 3, 4, 5]
        assert all(row["formal_signal_eligible"] is False for row in group)


def test_bad_industry_is_visible_but_never_promoted():
    rows = [
        {"code": "000001", "industry": "风险行业", "quant_status": "HARD_REJECT", "quant_score": 90, "hard_blockers": "financial_risk"},
        {"code": "000002", "industry": "风险行业", "quant_status": "HARD_REJECT", "quant_score": 80, "hard_blockers": "data_invalid"},
        {"code": "600001", "industry": "正常行业", "quant_status": "LOW_PRIORITY", "quant_score": 50, "hard_blockers": ""},
    ]
    selected = select_industry_coverage(rows, per_industry=5)
    risk = [row for row in selected if row["industry"] == "风险行业"]
    assert len(risk) == 2
    assert all(row["industry_status"] == "NO_INVESTABLE_CANDIDATE" for row in risk)
    assert all(row["industry_candidate_state"] == "BLOCKED_RESEARCH_ONLY" for row in risk)
    assert all(row["automatic_promotion_allowed"] is False for row in risk)
    normal = [row for row in selected if row["industry"] == "正常行业"]
    assert normal[0]["industry_status"] == "RESEARCH_CANDIDATES_AVAILABLE"


def test_find_latest_report_materializes_legacy_alias_for_flattened_artifact(tmp_path):
    upstream = tmp_path / "upstream"
    flattened_report = upstream / "20260818"
    flattened_report.mkdir(parents=True)
    with (flattened_report / "all_a_quant_screen.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["code", "industry", "quant_score"])
        writer.writeheader()
        writer.writerow({"code": "603369", "industry": "白酒", "quant_score": "76"})
    (flattened_report / "run_summary.json").write_text("{}", encoding="utf-8")

    legacy_root = upstream / "reports" / "all_a_full_scan"
    resolved = find_latest_report(legacy_root)

    assert resolved.resolve() == flattened_report.resolve()
    assert legacy_root.exists()
    assert legacy_root.resolve() == flattened_report.resolve()
    assert (legacy_root / "all_a_quant_screen.csv").exists()
    assert (legacy_root / "run_summary.json").exists()


def test_flattened_artifact_prefers_top_level_all_a_over_nested_deep_review(tmp_path):
    upstream = tmp_path / "upstream"
    canonical = upstream / "20260818"
    deep_review = canonical / "_deep_review" / "20260818_022714"
    deep_review.mkdir(parents=True)

    with (canonical / "all_a_quant_screen.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["code", "industry", "quant_score"])
        writer.writeheader()
        writer.writerow({"code": "603369", "industry": "白酒", "quant_score": "76"})
    (canonical / "run_summary.json").write_text("{}", encoding="utf-8")

    with (deep_review / "quant_screen_all.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["code", "industry", "quant_score"])
        writer.writeheader()
        writer.writerow({"code": "999999", "industry": "DECOY", "quant_score": "99"})

    legacy_root = upstream / "reports" / "all_a_full_scan"
    resolved = find_latest_report(legacy_root)

    assert resolved.resolve() == canonical.resolve()
    assert legacy_root.resolve() == canonical.resolve()
    assert (legacy_root / "run_summary.json").exists()
    assert not (legacy_root / "quant_screen_all.csv").exists()
