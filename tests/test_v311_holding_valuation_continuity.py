import json
from pathlib import Path

from src.strategies.genge_opportunity_discovery.holding_valuation_continuity import continuity_review_required


def test_holding_sell_with_missing_prior_valuation_fails_to_review(tmp_path: Path):
    state=tmp_path/'state.json'
    state.write_text(json.dumps({'holdings':{'600276':{'action':'HOLD_REVIEW','neutral_value':None}}}),encoding='utf-8')
    required,reasons=continuity_review_required({'code':'600276','v311_has_position':True,'v31_neutral_value':28.75},'REDUCE_50',path=state)
    assert required is True
    assert 'VALUATION_CONTINUITY_BASELINE_INCOMPLETE' in reasons


def test_large_neutral_jump_fails_to_review_without_evidence(tmp_path: Path):
    state=tmp_path/'state.json'
    state.write_text(json.dumps({'holdings':{'600406':{'action':'HOLD','neutral_value':24.0,'normalized_earnings':10.0}}}),encoding='utf-8')
    required,reasons=continuity_review_required({'code':'600406','v311_has_position':True,'v31_neutral_value':17.0,'v31_normalized_profit':10.1},'REDUCE_25',path=state)
    assert required is True
    assert 'NEUTRAL_VALUE_DISCONTINUITY' in reasons


def test_evidence_bound_override_allows_sell(tmp_path: Path):
    state=tmp_path/'state.json'
    state.write_text(json.dumps({'holdings':{'600406':{'action':'HOLD','neutral_value':24.0}}}),encoding='utf-8')
    required,reasons=continuity_review_required({
        'code':'600406',
        'v311_has_position':True,
        'v31_neutral_value':17.0,
        'valuation_continuity_evidence_id':'filing-1',
        'valuation_continuity_evidence_observed_at':'2026-08-28T00:00:00Z',
        'valuation_continuity_evidence_reason':'new audited earnings materially reset normalized profit',
        'valuation_continuity_evidence_type':'EARNINGS_POWER_DETERIORATION',
        'valuation_continuity_evidence_material':True,
        'valuation_continuity_thesis_link':'audited earnings directly impair the prior normalized-earnings valuation thesis',
    },'REDUCE_25',path=state)
    assert required is False
    assert 'SELL_RATIONALE_MATERIAL_REUNDERWRITE_EVIDENCE' in reasons


def test_hard_exit_is_not_intercepted(tmp_path: Path):
    state=tmp_path/'state.json'
    state.write_text(json.dumps({'holdings':{'600276':{'action':'HOLD','neutral_value':50.0}}}),encoding='utf-8')
    required,_=continuity_review_required({'code':'600276','v311_has_position':True,'v31_neutral_value':20.0},'EXIT',path=state)
    assert required is False
