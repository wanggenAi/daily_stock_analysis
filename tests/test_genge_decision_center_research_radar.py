import pytest

from scripts.genge_bind_decision_center_snapshot import (
    RADAR_MD_END,
    RADAR_MD_START,
    _attach_research_radar,
    _inject_research_radar_markdown,
)


def _decision():
    return {
        "formal_action_source": "FINALIZED_CANONICAL_ONLY",
        "no_auto_trade": True,
        "pillar_1_holdings_deep_analysis": {
            "rows": [{"code": "603993", "name": "洛阳钼业"}],
        },
        "pillar_3_deep_opportunities": {
            "buy_now": [],
            "wait_price": [],
        },
        "executive_summary": {},
        "decision_readiness": {},
    }


def _row(code, name, industry, diversified_rank, radar_rank, *, unknown=0):
    return {
        "authority": "RESEARCH_ONLY",
        "automatic_formal_buy_allowed": False,
        "code": code,
        "diversified_rank": diversified_rank,
        "fail_gate_count": 0,
        "followup": "VALUATION_CLOSURE" if unknown == 0 else "EVIDENCE_CLOSURE",
        "formal_trading_authority": False,
        "industry": industry,
        "industry_key": industry,
        "mutates_authoritative_decision": False,
        "no_auto_trade": True,
        "quant_score": "80.5",
        "radar_rank": radar_rank,
        "radar_tier": "FULL_EVIDENCE" if unknown == 0 else "UNKNOWN_RESEARCH",
        "research_priority": "P1",
        "same_industry_representative_code": "",
        "selected_as_industry_representative": True,
        "stock_name": name,
        "unknown_gate_count": unknown,
        "unknown_gates": "predictability" if unknown else "",
        "unknown_is_pass": False,
        "v31_review_rank": str(radar_rank),
        "verified_pass_gate_count": 5 - unknown,
        "verified_pass_gates": "long_term_demand,moat,financial_safety,earnings_authenticity"
        + (",predictability" if unknown == 0 else ""),
    }


def _radar():
    rows = [
        _row("603596", "伯特利", "C36汽车制造业", 1, 1),
        _row("603993", "洛阳钼业", "B09有色金属矿采选业", 2, 2, unknown=1),
        _row("600019", "宝钢股份", "C31黑色金属冶炼和压延加工业", 3, 5, unknown=2),
    ]
    return {
        "summary": {
            "authority": "RESEARCH_ONLY",
            "automatic_formal_buy_allowed": False,
            "candidate_count": 501,
            "contract": "GEN_GE_V31_UNKNOWN_SAFE_RESEARCH_RADAR_V1",
            "distinct_industry_count": 42,
            "formal_trading_authority": False,
            "full_evidence_count": 1,
            "generated_at": "2026-10-14T00:40:29+00:00",
            "hard_fail_excluded_count": 1,
            "no_auto_trade": True,
            "radar_eligible_count": 109,
            "ranking_policy": "VERIFIED_PASS_COUNT_DESC_THEN_QUANT_DESC",
            "same_industry_backup_count": 67,
            "source_run_id": "38443849235",
            "top_count": len(rows),
            "top_distinct_industry_count": len(rows),
            "top_selection_policy": "ONE_REPRESENTATIVE_PER_OFFICIAL_INDUSTRY",
            "unknown_eligible_count": 108,
            "unknown_is_pass": False,
        },
        "top_rows": rows,
    }


def test_diversified_radar_is_attached_without_gaining_formal_authority():
    decision = _decision()
    view = _attach_research_radar(decision, _radar())

    assert view["available"] is True
    assert view["top_count"] == 3
    assert view["top_distinct_industry_count"] == 3
    assert view["new_research_candidate_count"] == 2
    assert view["current_holding_count"] == 1
    assert view["authority"] == "RESEARCH_ONLY"
    assert view["formal_trading_authority"] is False
    assert view["automatic_formal_buy_allowed"] is False
    assert view["unknown_is_pass"] is False
    assert view["no_auto_trade"] is True

    by_code = {row["code"]: row for row in view["rows"]}
    assert by_code["603596"]["portfolio_relation"] == "NEW_RESEARCH_CANDIDATE"
    assert by_code["603993"]["portfolio_relation"] == "CURRENT_HOLDING"
    assert "GLOBAL_RANK_1" in by_code["603596"]["selection_trace"]
    assert "INDUSTRY_REPRESENTATIVE[C36汽车制造业]" in by_code["603596"]["selection_trace"]

    pillar = decision["pillar_3_deep_opportunities"]
    assert pillar["diversified_research_radar"]["rows"] == view["rows"]
    assert decision["executive_summary"]["diversified_research_top_count"] == 3
    assert decision["executive_summary"]["diversified_research_new_candidate_count"] == 2
    assert decision["decision_readiness"]["diversified_research_top_unique_industries"] is True
    assert decision["formal_action_source"] == "FINALIZED_CANONICAL_ONLY"
    assert decision["no_auto_trade"] is True


def test_diversified_radar_rejects_duplicate_top_industries():
    radar = _radar()
    radar["top_rows"][2]["industry"] = "C36汽车制造业"
    radar["top_rows"][2]["industry_key"] = "C36汽车制造业"

    with pytest.raises(ValueError, match="duplicate industries"):
        _attach_research_radar(_decision(), radar)


def test_diversified_radar_rejects_authority_escalation():
    radar = _radar()
    radar["top_rows"][0]["formal_trading_authority"] = True

    with pytest.raises(ValueError, match="Formal authority"):
        _attach_research_radar(_decision(), radar)


def test_markdown_injection_is_visible_before_account_plan_and_idempotent():
    view = _attach_research_radar(_decision(), _radar())
    original = "# 决策中心\n\n## 3. 新机会\n\n无正式BUY\n\n## 4. 今日账户资金怎么处理\n\n保留现金\n"

    once = _inject_research_radar_markdown(original, view)
    twice = _inject_research_radar_markdown(once, view)

    assert once == twice
    assert once.count(RADAR_MD_START) == 1
    assert once.count(RADAR_MD_END) == 1
    assert once.index("### 行业去重研究雷达") < once.index("## 4. 今日账户资金怎么处理")
    assert "伯特利 603596" in once
    assert "洛阳钼业 603993" in once
    assert "当前持仓" in once
    assert "新研究候选" in once
    assert "不是买单" in once
    assert "UNKNOWN 仍然不是 PASS" in once
