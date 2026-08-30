from src.era_radar.handoff import build_research_handoff


def test_only_sh_sz_research_handoff_is_emitted():
    handoff = build_research_handoff(
        trend_id="grid_modernization",
        industry_link="power automation",
        symbol="600406",
        market="SH",
        rationale="evidence-backed research mapping",
        confidence_score=75,
        provenance_ok=True,
        freshness_ok=True,
    )
    assert handoff is not None
    assert handoff.authority == "RESEARCH_ONLY"
    assert not hasattr(handoff, "formal_action")


def test_non_tradable_market_is_rejected():
    assert build_research_handoff(
        trend_id="x",
        industry_link="x",
        symbol="AAPL",
        market="US",
        rationale="x",
        confidence_score=90,
        provenance_ok=True,
        freshness_ok=True,
    ) is None


def test_bad_provenance_or_stale_evidence_fails_closed():
    assert build_research_handoff(
        trend_id="x",
        industry_link="x",
        symbol="000001",
        market="SZ",
        rationale="x",
        confidence_score=90,
        provenance_ok=False,
        freshness_ok=True,
    ) is None
    assert build_research_handoff(
        trend_id="x",
        industry_link="x",
        symbol="000001",
        market="SZ",
        rationale="x",
        confidence_score=90,
        provenance_ok=True,
        freshness_ok=False,
    ) is None
