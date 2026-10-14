from src.strategies.genge_opportunity_discovery.unknown_safe_research_radar import build_radar


def _profile(*statuses: str):
    names = (
        "predictability",
        "long_term_demand",
        "moat",
        "financial_safety",
        "earnings_authenticity",
    )
    gates = {}
    for name, status in zip(names, statuses, strict=True):
        if status == "PASS":
            gates[name] = {
                "status": "PASS",
                "source": "EXPLICIT_VERIFIED",
                "evidence": [{"url": "https://example.com"}],
            }
        else:
            gates[name] = {
                "status": status,
                "source": "UNRESOLVED",
                "evidence": [],
            }
    return {"name": "测试", "industry": "测试", "gates": gates}


def _payload(profiles):
    return {
        "contract": "GEN_GE_V31_AUTOMATIC_DEEP_CALC_V1",
        "authority": "RESEARCH_ONLY",
        "automatic_formal_buy_allowed": False,
        "unknown_is_pass": False,
        "no_auto_trade": True,
        "source_run_id": "source-1",
        "profiles": profiles,
    }


def _row(code, quant, rank, industry=None, name=None):
    return {
        "code": code,
        "stock_name": name if name is not None else code,
        "industry": industry if industry is not None else f"行业-{code}",
        "quant_score": str(quant),
        "v31_review_rank": str(rank),
    }


def test_unknown_candidate_can_enter_radar_without_becoming_pass_or_formal():
    result = build_radar(
        [_row("000001", 80, 1)],
        _payload(
            {"000001": _profile("PASS", "PASS", "UNKNOWN", "UNKNOWN", "UNKNOWN")}
        ),
    )
    row = result["top_rows"][0]
    assert row["radar_tier"] == "UNKNOWN_RESEARCH"
    assert row["verified_pass_gate_count"] == 2
    assert row["unknown_gate_count"] == 3
    assert row["unknown_is_pass"] is False
    assert row["formal_trading_authority"] is False
    assert row["automatic_formal_buy_allowed"] is False
    assert row["mutates_authoritative_decision"] is False
    assert row["no_auto_trade"] is True


def test_any_true_hard_gate_fail_is_excluded_even_with_high_quant():
    result = build_radar(
        [_row("000001", 999, 1), _row("000002", 1, 2)],
        _payload(
            {
                "000001": _profile("PASS", "PASS", "FAIL", "PASS", "PASS"),
                "000002": _profile("PASS", "PASS", "UNKNOWN", "UNKNOWN", "UNKNOWN"),
            }
        ),
    )
    assert [row["code"] for row in result["top_rows"]] == ["000002"]
    assert result["summary"]["hard_fail_excluded_count"] == 1


def test_zero_or_one_verified_pass_is_not_promoted_by_unknowns():
    result = build_radar(
        [_row("000001", 99, 1), _row("000002", 98, 2)],
        _payload(
            {
                "000001": _profile(
                    "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"
                ),
                "000002": _profile(
                    "PASS", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"
                ),
            }
        ),
    )
    assert result["top_rows"] == []
    assert result["summary"]["insufficient_verified_progress_count"] == 2


def test_full_evidence_ranks_before_unknown_then_quant_breaks_ties():
    result = build_radar(
        [_row("000001", 1, 1), _row("000002", 99, 2), _row("000003", 80, 3)],
        _payload(
            {
                "000001": _profile("PASS", "PASS", "PASS", "PASS", "PASS"),
                "000002": _profile("PASS", "PASS", "UNKNOWN", "UNKNOWN", "UNKNOWN"),
                "000003": _profile("PASS", "PASS", "UNKNOWN", "UNKNOWN", "UNKNOWN"),
            }
        ),
    )
    assert [row["code"] for row in result["top_rows"]] == [
        "000001",
        "000002",
        "000003",
    ]
    assert result["top_rows"][0]["radar_tier"] == "FULL_EVIDENCE"


def test_unverified_pass_is_downgraded_to_unknown():
    profile = _profile("PASS", "PASS", "UNKNOWN", "UNKNOWN", "UNKNOWN")
    profile["gates"]["long_term_demand"] = {
        "status": "PASS",
        "source": "UPSTREAM",
        "evidence": [],
    }
    result = build_radar([_row("000001", 80, 1)], _payload({"000001": profile}))
    assert result["top_rows"] == []
    assert result["summary"]["unverified_pass_downgraded_count"] == 1
    assert result["summary"]["insufficient_verified_progress_count"] == 1


def test_top_n_never_pads_and_tie_break_is_deterministic():
    result = build_radar(
        [_row("000002", 50, 2), _row("000001", 50, 2)],
        _payload(
            {
                "000001": _profile("PASS", "PASS", "UNKNOWN", "UNKNOWN", "UNKNOWN"),
                "000002": _profile("PASS", "PASS", "UNKNOWN", "UNKNOWN", "UNKNOWN"),
            }
        ),
        top_n=10,
    )
    assert [row["code"] for row in result["top_rows"]] == ["000001", "000002"]
    assert result["summary"]["top_count"] == 2
    assert result["summary"]["requested_top_n"] == 10


def test_top_list_uses_one_representative_per_official_industry():
    result = build_radar(
        [
            _row("000001", 99, 1, "行业A"),
            _row("000002", 98, 2, "行业A"),
            _row("000003", 97, 3, "行业B"),
            _row("000004", 96, 4, "行业C"),
        ],
        _payload(
            {
                "000001": _profile("PASS", "PASS", "UNKNOWN", "UNKNOWN", "UNKNOWN"),
                "000002": _profile("PASS", "PASS", "UNKNOWN", "UNKNOWN", "UNKNOWN"),
                "000003": _profile("PASS", "PASS", "UNKNOWN", "UNKNOWN", "UNKNOWN"),
                "000004": _profile("PASS", "PASS", "UNKNOWN", "UNKNOWN", "UNKNOWN"),
            }
        ),
        top_n=3,
    )
    assert [row["code"] for row in result["top_rows"]] == [
        "000001",
        "000003",
        "000004",
    ]
    assert [row["diversified_rank"] for row in result["top_rows"]] == [1, 2, 3]
    assert result["summary"]["top_distinct_industry_count"] == 3
    assert result["summary"]["distinct_industry_count"] == 3
    assert result["summary"]["same_industry_backup_count"] == 1
    backup = next(row for row in result["eligible_rows"] if row["code"] == "000002")
    assert backup["selected_as_industry_representative"] is False
    assert backup["same_industry_representative_code"] == "000001"


def test_different_official_industries_with_same_healthcare_exposure_do_not_repeat():
    rows = [
        _row("603883", 99, 1, "F52零售业", "老百姓"),
        _row("300142", 98, 2, "C27医药制造业", "沃森生物"),
        _row("600019", 97, 3, "C31黑色金属冶炼和压延加工业", "宝钢股份"),
        _row("603596", 96, 4, "C36汽车制造业", "伯特利"),
    ]
    profiles = {
        row["code"]: _profile("PASS", "PASS", "UNKNOWN", "UNKNOWN", "UNKNOWN")
        for row in rows
    }
    result = build_radar(rows, _payload(profiles), top_n=3)

    assert [row["code"] for row in result["top_rows"]] == [
        "603883",
        "600019",
        "603596",
    ]
    assert [row["economic_exposure_cluster"] for row in result["top_rows"]] == [
        "HEALTHCARE",
        "MATERIALS_METALS",
        "AUTOMOTIVE",
    ]
    assert result["summary"]["top_distinct_economic_exposure_count"] == 3
    assert result["summary"]["distinct_industry_count"] == 4
    assert result["summary"]["same_industry_backup_count"] == 0
    assert result["summary"]["distinct_economic_exposure_count"] == 3
    assert result["summary"]["same_economic_exposure_backup_count"] == 1
    backup = next(row for row in result["eligible_rows"] if row["code"] == "300142")
    assert backup["selected_as_exposure_representative"] is False
    assert backup["same_exposure_representative_code"] == "603883"


def test_metal_mining_and_steel_do_not_consume_two_top_slots():
    rows = [
        _row("603993", 99, 1, "B09有色金属矿采选业", "洛阳钼业"),
        _row("600019", 98, 2, "C31黑色金属冶炼和压延加工业", "宝钢股份"),
        _row("002568", 97, 3, "C15酒、饮料和精制茶制造业", "百润股份"),
    ]
    profiles = {
        row["code"]: _profile("PASS", "PASS", "UNKNOWN", "UNKNOWN", "UNKNOWN")
        for row in rows
    }
    result = build_radar(rows, _payload(profiles), top_n=3)

    assert [row["code"] for row in result["top_rows"]] == ["603993", "002568"]
    assert result["top_rows"][0]["economic_exposure_cluster"] == "MATERIALS_METALS"
    assert result["summary"]["distinct_industry_count"] == 3
    assert result["summary"]["distinct_economic_exposure_count"] == 2
    steel = next(row for row in result["eligible_rows"] if row["code"] == "600019")
    assert steel["same_exposure_representative_code"] == "603993"
    assert steel["diversified_rank"] == 0


def test_business_model_overrides_fix_misleading_official_industries():
    rows = [
        _row("002959", 99, 1, "C38电气机械和器材制造业", "小熊电器"),
        _row("603970", 98, 2, "F51批发业", "中农立华"),
        _row("002612", 97, 3, "C18纺织服装、服饰业", "朗姿股份"),
    ]
    profiles = {
        row["code"]: _profile("PASS", "PASS", "UNKNOWN", "UNKNOWN", "UNKNOWN")
        for row in rows
    }
    result = build_radar(rows, _payload(profiles), top_n=3)
    clusters = {row["code"]: row["economic_exposure_cluster"] for row in result["top_rows"]}
    assert clusters == {
        "002959": "CONSUMER_DURABLES_APPLIANCES",
        "603970": "AGRICULTURE_INPUTS",
        "002612": "CONSUMER_SERVICES_MEDICAL_AESTHETICS",
    }


def test_unmapped_industries_fail_open_to_separate_exposure_clusters():
    rows = [
        _row("000001", 99, 1, "未知行业A"),
        _row("000002", 98, 2, "未知行业B"),
    ]
    profiles = {
        row["code"]: _profile("PASS", "PASS", "UNKNOWN", "UNKNOWN", "UNKNOWN")
        for row in rows
    }
    result = build_radar(rows, _payload(profiles), top_n=2)

    assert [row["code"] for row in result["top_rows"]] == ["000001", "000002"]
    assert result["summary"]["top_distinct_economic_exposure_count"] == 2
    assert all(
        row["economic_exposure_cluster"].startswith("INDUSTRY::")
        for row in result["top_rows"]
    )
