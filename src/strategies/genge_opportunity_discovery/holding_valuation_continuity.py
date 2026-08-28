"""Holding valuation-continuity guard for GenGe V3.1.1 production."""
from __future__ import annotations
import json, math
from pathlib import Path
from typing import Any, Mapping

STATE_PATH = Path("data/opportunity_snapshots/holding_valuation_continuity_state.json")
SELL_ACTIONS = {"REDUCE_25", "REDUCE_50", "CORE_ONLY"}
NON_SELL_ACTIONS = {"HOLD", "HOLD_NO_ADD", "HOLD_REVIEW", "BUY", "WAIT"}
NEUTRAL_JUMP_THRESHOLD = 0.20
NORMALIZED_EARNINGS_JUMP_THRESHOLD = 0.20


def _finite(v: Any):
    try: x=float(v)
    except (TypeError,ValueError): return None
    return x if math.isfinite(x) else None

def _code(v: Any):
    t=str(v or '').strip().upper()
    if '.' in t: t=t.split('.')[0]
    for p in ('SH','SZ','BJ'):
        if t.startswith(p) and t[len(p):].isdigit(): t=t[len(p):]
    return t.zfill(6) if t.isdigit() else t

def load_state(path: Path = STATE_PATH):
    if not path.exists(): return {"contract_version":"V311_HOLDING_VALUATION_CONTINUITY_V1","holdings":{}}
    data=json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data.get('holdings'),dict): raise ValueError('invalid holding valuation continuity state')
    return data

def continuity_review_required(data: Mapping[str,Any], action: str, *, path: Path = STATE_PATH):
    if action not in SELL_ACTIONS: return False, ()
    has_position = bool(data.get('v311_has_position') or data.get('v32_has_position'))
    if not has_position: return False, ()
    code=_code(data.get('code'))
    prev=load_state(path).get('holdings',{}).get(code)
    if not prev: return False, ()
    prev_action=str(prev.get('action') or '')
    if prev_action not in NON_SELL_ACTIONS: return False, ()
    current_neutral=_finite(data.get('v31_neutral_value') or data.get('neutral_value'))
    previous_neutral=_finite(prev.get('neutral_value'))
    reasons=[]
    if previous_neutral is None or previous_neutral <= 0 or current_neutral is None or current_neutral <= 0:
        reasons.append('VALUATION_CONTINUITY_BASELINE_INCOMPLETE')
    else:
        jump=abs(current_neutral/previous_neutral-1.0)
        if jump >= NEUTRAL_JUMP_THRESHOLD: reasons.append('NEUTRAL_VALUE_DISCONTINUITY')
    current_norm=_finite(data.get('v31_normalized_profit') or data.get('normalized_earnings'))
    previous_norm=_finite(prev.get('normalized_earnings'))
    if previous_norm and current_norm and abs(current_norm/previous_norm-1.0) >= NORMALIZED_EARNINGS_JUMP_THRESHOLD:
        reasons.append('NORMALIZED_EARNINGS_DISCONTINUITY')
    evidence_id=str(data.get('valuation_continuity_evidence_id') or '').strip()
    evidence_at=str(data.get('valuation_continuity_evidence_observed_at') or '').strip()
    evidence_reason=str(data.get('valuation_continuity_evidence_reason') or '').strip()
    if reasons and evidence_id and evidence_at and evidence_reason:
        return False, ()
    return bool(reasons), tuple(reasons)

def persist_from_snapshot(snapshot_path: Path, state_path: Path = STATE_PATH):
    snapshot=json.loads(snapshot_path.read_text(encoding='utf-8'))
    state=load_state(state_path)
    holdings=state.setdefault('holdings',{})
    for row in snapshot.get('production',{}).get('holding_decisions',[]):
        code=_code(row.get('code'))
        if not code: continue
        holdings[code]={'action':row.get('action'),'neutral_value':row.get('neutral_value'),'normalized_earnings':row.get('normalized_earnings'),'valuation_confidence':row.get('valuation_confidence'),'canonical_snapshot_id':snapshot.get('snapshot_id'),'canonical_source_run_id':snapshot.get('source_run_id'),'decision_date':row.get('decision_date')}
    state['latest_applied_snapshot_id']=snapshot.get('snapshot_id')
    state['latest_applied_source_run_id']=snapshot.get('source_run_id')
    state['no_auto_trade']=True
    state_path.parent.mkdir(parents=True,exist_ok=True)
    state_path.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return state
