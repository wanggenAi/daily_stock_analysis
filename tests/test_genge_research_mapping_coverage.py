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
    assert payload["peer_mapped_count"] == 1
    assert payload["formal_action_eligible"] is False
    assert payload["no_auto_trade"] is True
    assert {row["code"] for row in rows} == {"600406", "601899"}
