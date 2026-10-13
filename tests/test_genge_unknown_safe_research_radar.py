from src.strategies.genge_opportunity_discovery.unknown_safe_research_radar import build_radar


def _profile(*statuses: str):
    names = ("predictability", "long_term_demand", "moat", "financial_safety", "earnings_authenticity")
    gates = {}
    for name, status in zip(names, statuses, strict=True):
        if status == "PASS":
            gates[name] = {
                "status": "PASS",
                "source": "EXPLICIT_VERIFIED",
                "evidence": [{"url": "https://example.com"}],
            }
        else:
            gates[name] = {"status": status, "source": "UNRESOLVED", "evidence": []}
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


def _row(code, quant, rank, industry=""):
    return {
        "code": code,
        "stock_name": code,
        "industry": industry,
        "quant_score": str(quant),
        "v31_review_rank": str(rank),
    }


def test_unknown_candidate_can_enter_radar_without_becoming_pass_or_formal():
    result = build_radar(
        [_row("000001", 80, 1)],
        _payload({"000001": _profile("PASS", "PASS", "UNKNOWN", "UNKNOWN", "UNKNOWN")}),
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
                "000001": _profile("UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),
                "000002": _profile("PASS", "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN"),
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
    assert [row["code"] for row in result["top_rows"]] == ["000001", "000002", "000003"]
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
    assert [row["code"] for row in result["top_rows"]] == ["000001", "000003", "000004"]
    assert [row["diversified_rank"] for row in result["top_rows"]] == [1, 2, 3]
    assert result["summary"]["top_distinct_industry_count"] == 3
    assert result["summary"]["distinct_industry_count"] == 3
    assert result["summary"]["same_industry_backup_count"] == 1
    backup = next(row for row in result["eligible_rows"] if row["code"] == "000002")
    assert backup["selected_as_industry_representative"] is False
    assert backup["same_industry_representative_code"] == "000001"
