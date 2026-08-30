from src.era_radar.engine import EvidenceSignal, score_trend


def sig(eid, family, source, direction=1, strength=0.9, quality=0.9, **components):
    components.setdefault("evidence_quality", 0.8)
    return EvidenceSignal(eid, family, source, direction, strength, quality, components)


def ageing_fixture():
    return [
        sig("demography", "GLOBAL_STRUCTURE", "census-series", structural_demand=1, global_confirmation=0.8),
        sig("care-demand", "REAL_DEMAND", "health-demand-series", real_demand_confirmation=0.9, structural_demand=0.8, profit_pool_quality=0.4),
        sig("policy", "POLICY_CAPITAL", "official-plan", policy_commitment=0.9),
        sig("capex", "INDUSTRIAL_CAPITAL", "industry-capex", industrial_capex=0.8, profit_pool_quality=0.5),
        sig("automation", "TECHNOLOGY", "assistive-tech", technology_enablement=0.7, investable_bottleneck_strength=0.5),
    ]


def test_ageing_is_derived_from_evidence_not_name():
    a = score_trend("ageing_longevity", ageing_fixture())
    b = score_trend("opaque_trend_123", ageing_fixture())
    assert a.structural_score == b.structural_score
    assert a.industrial_score == b.industrial_score
    assert a.confidence_score == b.confidence_score
    assert a.structural_score > 60
    assert a.independent_families >= 4


def test_duplicate_source_claim_does_not_double_count():
    base = ageing_fixture()
    first = score_trend("x", base)
    duplicate = base + [sig("reprint", "REAL_DEMAND", "health-demand-series", real_demand_confirmation=0.9, structural_demand=0.8, profit_pool_quality=0.4)]
    second = score_trend("x", duplicate)
    assert first == second


def test_policy_only_cannot_confirm():
    evidence = [sig("p1", "POLICY_CAPITAL", "plan-a", policy_commitment=1, structural_demand=1)]
    result = score_trend("policy_theme", evidence)
    assert result.confidence_score <= 39
    assert result.lifecycle != "CONFIRMED"


def test_counter_evidence_downgrades_scores():
    base = ageing_fixture()
    positive = score_trend("x", base)
    negative = score_trend("x", base + [sig("counter", "REAL_DEMAND", "new-demand-data", direction=-1, strength=1, quality=1, real_demand_confirmation=1, structural_demand=1, profit_pool_quality=1)])
    assert negative.structural_score < positive.structural_score
    assert negative.industrial_score < positive.industrial_score


def test_crowding_cannot_upgrade_structural_confidence():
    base = ageing_fixture()
    normal = score_trend("x", base)
    crowded = score_trend("x", base + [sig("flow", "FINANCIAL_CAPITAL", "flow-series", financial_crowding=1)])
    assert crowded.structural_score == normal.structural_score
    assert crowded.confidence_score == normal.confidence_score
    assert crowded.cyclical_score <= normal.cyclical_score


def test_three_horizons_are_independent_outputs():
    result = score_trend("x", ageing_fixture())
    assert result.structural_score != result.industrial_score
    assert result.cyclical_score != result.structural_score
