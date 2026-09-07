import csv
import json
from pathlib import Path

from src.strategies.genge_opportunity_discovery.research_mapping_coverage import build


def test_mapping_coverage_reports_gaps_without_guessing(tmp_path: Path):
    holdings = tmp_path / "CURRENT_HOLDINGS.md"
    holdings.write_text("| 600406 | 国电南瑞 | 200 | 23.1 | HELD | 2026-08-25 |\n| 001316 | 润贝航科 | 200 | 26.1 | HELD | 2026-08-25 |\n", encoding="utf-8")
    lifecycle = tmp_path / "lifecycle.json"
    lifecycle.write_text(json.dumps({"candidates": {"601899": {"code": "601899", "stock_name": "紫金矿业", "lifecycle_state": "ACTIVE"}, "600309": {"code": "600309", "stock_name": "万华化学", "lifecycle_state": "ARCHIVED"}}}), encoding="utf-8")
    profiles = tmp_path / "profiles.json"
    profiles.write_text(json.dumps({"profiles": {"600406": {"name": "国电南瑞", "industry": "电力设备", "profile_status": "REVIEWED"}, "001316": {"name": "润贝航科", "industry": "UNRESOLVED", "profile_status": "NEEDS_INDUSTRY_REVIEW"}, "601899": {"name": "紫金矿业", "industry": "有色", "profile_status": "REVIEWED"}}}), encoding="utf-8")
    commodity = tmp_path / "commodity.json"
    commodity.write_text(json.dumps({"security_exposures": {"601899": [{"benchmark_id": "COPPER"}]}}), encoding="utf-8")
    peers = tmp_path / "peers.json"
    peers.write_text(json.dumps({"mappings": [{"target_code": "600406", "peer_code": "600312", "evidence_ref": "fixture"}]}), encoding="utf-8")

    payload, rows = build(holdings_path=holdings, lifecycle_path=lifecycle, profiles_path=profiles, commodity_path=commodity, peer_path=peers)
    assert payload["tracked_security_count"] == 3
    assert payload["industry_mapped_count"] == 2
    assert "001316" in payload["industry_unmapped_codes"]
    assert payload["commodity_mapped_count"] == 1
    assert payload["commodity_partial_mapped_count"] == 0
    assert payload["peer_mapped_count"] == 1
    assert payload["mapping_policy"] == "MISSING_APPLICABLE_MAPPING_IS_A_VISIBLE_RESEARCH_GAP_NOT_A_GUESS"
    assert payload["formal_action_eligible"] is False
    assert payload["formal_action_recomputed"] is False
    assert payload["no_auto_trade"] is True
    assert {row["code"] for row in rows} == {"600406", "601899"}


def test_partial_commodity_mapping_is_connected_but_remains_visible_gap(tmp_path: Path):
    holdings = tmp_path / "CURRENT_HOLDINGS.md"
    holdings.write_text("", encoding="utf-8")
    lifecycle = tmp_path / "lifecycle.json"
    lifecycle.write_text(json.dumps({"candidates": {"601020": {"code": "601020", "stock_name": "华钰矿业", "lifecycle_state": "ACTIVE"}}}), encoding="utf-8")
    profiles = tmp_path / "profiles.json"
    profiles.write_text(json.dumps({"profiles": {"601020": {"name": "华钰矿业", "industry": "有色", "profile_status": "REVIEWED", "commodity_monitoring": "PARTIAL_MAPPED", "peer_monitoring": "APPLICABLE_UNMAPPED"}}}), encoding="utf-8")
    commodity = tmp_path / "commodity.json"
    commodity.write_text(json.dumps({"security_exposures": {"601020": [{"benchmark_id": "GOLD"}]}}), encoding="utf-8")
    peers = tmp_path / "peers.json"
    peers.write_text(json.dumps({"mappings": []}), encoding="utf-8")
    payload, _ = build(holdings_path=holdings, lifecycle_path=lifecycle, profiles_path=profiles, commodity_path=commodity, peer_path=peers)
    security = payload["securities"][0]
    assert security["commodity_monitoring_state"] == "PARTIAL_MAPPED"
    assert security["commodity_mapped"] is True
    assert security["commodity_fully_mapped"] is False
    assert payload["commodity_connected_count"] == 1
    assert payload["commodity_partial_mapped_count"] == 1
    assert payload["commodity_partial_mapped_codes"] == ["601020"]
    assert payload["partial_mapping_policy"] == "PARTIAL_MAPPED_IS_CONNECTED_BUT_REMAINS_A_VISIBLE_RESEARCH_GAP"


def _base_inputs(tmp_path: Path):
    holdings = tmp_path / "CURRENT_HOLDINGS.md"
    holdings.write_text("| 001316 | 润贝航科 | 200 | 26.1 | HELD | 2026-08-25 |\n", encoding="utf-8")
    lifecycle = tmp_path / "lifecycle.json"
    lifecycle.write_text(json.dumps({"candidates": {"000526": {"code": "000526", "stock_name": "学大教育", "lifecycle_state": "ACTIVE"}, "600406": {"code": "600406", "stock_name": "国电南瑞", "lifecycle_state": "ACTIVE"}}}), encoding="utf-8")
    profiles = tmp_path / "profiles.json"
    profiles.write_text(json.dumps({"profiles": {"600406": {"name": "国电南瑞", "industry": "人工复核行业", "profile_status": "REVIEWED"}}}), encoding="utf-8")
    commodity = tmp_path / "commodity.json"
    commodity.write_text(json.dumps({"security_exposures": {}}), encoding="utf-8")
    peers = tmp_path / "peers.json"
    peers.write_text(json.dumps({"mappings": []}), encoding="utf-8")
    return holdings, lifecycle, profiles, commodity, peers


def test_explicit_production_industry_metadata_fills_only_industry_and_static_profile_wins(tmp_path: Path):
    holdings, lifecycle, profiles, commodity, peers = _base_inputs(tmp_path)
    industry_source = tmp_path / "all_a_quant_screen.csv"
    with industry_source.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["code", "stock_name", "industry"])
        writer.writeheader()
        writer.writerows([
            {"code": "001316", "stock_name": "润贝航科", "industry": "航空装备供应链"},
            {"code": "000526", "stock_name": "学大教育", "industry": "教育"},
            {"code": "600406", "stock_name": "国电南瑞", "industry": "生产扫描行业"},
        ])

    payload, rows = build(
        holdings_path=holdings,
        lifecycle_path=lifecycle,
        profiles_path=profiles,
        commodity_path=commodity,
        peer_path=peers,
        industry_source_path=industry_source,
        industry_source_label="opportunity-run:123",
    )
    by_code = {row["code"]: row for row in payload["securities"]}
    assert payload["contract_version"] == "GEN_GE_RESEARCH_MAPPING_COVERAGE_V4_PRODUCTION_INDUSTRY_METADATA"
    assert payload["industry_mapped_count"] == 3
    assert payload["industry_unmapped_codes"] == []
    assert by_code["001316"]["industry"] == "航空装备供应链"
    assert by_code["001316"]["industry_mapping_origin"] == "PRODUCTION_ALL_A_EXPLICIT_METADATA"
    assert by_code["600406"]["industry"] == "人工复核行业"
    assert by_code["600406"]["industry_mapping_origin"] == "REVIEWED_STATIC_PROFILE"
    assert by_code["001316"]["commodity_monitoring_state"] == "UNRESOLVED"
    assert by_code["001316"]["peer_monitoring_state"] == "UNRESOLVED"
    assert payload["industry_source_may_infer_commodity_or_peers"] is False
    assert payload["formal_action_eligible"] is False
    assert payload["changes_thresholds"] is False
    mapped_rows = {row["code"]: row for row in rows}
    assert mapped_rows["001316"]["source"] == "opportunity-run:123"
    assert mapped_rows["001316"]["source_type"] == "production_scan_industry_metadata"
    assert mapped_rows["600406"]["source"] == "config/research_security_profiles.json"


def test_conflicting_production_industry_metadata_fails_closed(tmp_path: Path):
    holdings, lifecycle, profiles, commodity, peers = _base_inputs(tmp_path)
    industry_source = tmp_path / "all_a_quant_screen.csv"
    with industry_source.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["code", "stock_name", "industry"])
        writer.writeheader()
        writer.writerows([
            {"code": "001316", "stock_name": "润贝航科", "industry": "航空装备供应链"},
            {"code": "001316.SZ", "stock_name": "润贝航科", "industry": "贸易"},
            {"code": "000526", "stock_name": "学大教育", "industry": "教育"},
        ])

    payload, _ = build(
        holdings_path=holdings,
        lifecycle_path=lifecycle,
        profiles_path=profiles,
        commodity_path=commodity,
        peer_path=peers,
        industry_source_path=industry_source,
    )
    by_code = {row["code"]: row for row in payload["securities"]}
    assert "001316" in payload["industry_source_conflict_codes"]
    assert by_code["001316"]["industry_mapped"] is False
    assert by_code["001316"]["industry_source_conflict"] is True
    assert by_code["000526"]["industry"] == "教育"
    assert by_code["600406"]["industry"] == "人工复核行业"
