from __future__ import annotations
import json
from datetime import datetime,timedelta,timezone
from pathlib import Path
from scripts import genge_bind_decision_center_snapshot as binder
from scripts import genge_data_package as dp
from scripts import genge_external_fresh_evidence as ext
from scripts import genge_research_input as ri

def w(p:Path,x:dict): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(x),encoding='utf-8')
def cfg(monkeypatch,tmp):
 pkg=tmp/'data/data_package'; era=tmp/'data/era_radar'; gp=tmp/'data/global_market_pulse'; m=tmp/'data/market_snapshots'; opt=tmp/'data/optional'
 for k,v in [('PACKAGE_DIR',pkg),('LATEST_PATH',pkg/'latest.json'),('SNAPSHOT_DIR',pkg/'snapshots'),('STATE_PATH',pkg/'watermarks.json')]: monkeypatch.setattr(dp,k,v)
 monkeypatch.setattr(dp,'PRODUCER_ROOTS',(("all_a_market_snapshot",str(m),True,None,"TRADE_DATE"),("era_radar",str(era),True,480,"WALL_CLOCK"),("global_market_pulse",str(gp),True,480,"WALL_CLOCK"),("optional",str(opt),False,60,"WALL_CLOCK")))
 return era,gp,m,opt

def seed(era,gp,m,now,date='2026-10-09'):
 w(era/'latest.json',{'research_as_of':now.isoformat()}); w(gp/'latest.json',{'generated_at':now.isoformat(),'last_valid_trade_date':date}); w(m/'latest.json',{'contract':'GEN_GE_ALL_A_MARKET_SNAPSHOT_V1','generated_at':now.isoformat(),'latest_trade_date':date,'rows':[{'code':'600000','latest_trade_date':date,'research_reference_price':'10'}]})

def test_same_hour_same_snapshot_next_hour_new_snapshot(monkeypatch,tmp_path):
 era,gp,m,_=cfg(monkeypatch,tmp_path); now=datetime(2026,10,9,12,5,tzinfo=timezone.utc); seed(era,gp,m,now)
 a=dp.build_package(now=now,write=True); b=dp.build_package(now=now+timedelta(minutes=20),write=True); c=dp.build_package(now=now+timedelta(hours=1),write=True)
 assert a['package_status']=='READY'; assert a['snapshot_id']==b['snapshot_id']; assert a['snapshot_id']!=c['snapshot_id']; assert a['market_trade_date_alignment_ok'] is True

def test_optional_degradation_does_not_destroy_execution_readiness(monkeypatch,tmp_path):
 era,gp,m,_=cfg(monkeypatch,tmp_path); now=datetime(2026,10,9,12,tzinfo=timezone.utc); seed(era,gp,m,now); p=dp.build_package(now=now,write=True)
 assert p['package_status']=='READY'; assert p['completeness_state']=='DEGRADED'; assert 'optional' in p['optional_degraded_datasets']

def test_market_snapshot_lag_fails_closed(monkeypatch,tmp_path):
 era,gp,m,_=cfg(monkeypatch,tmp_path); now=datetime(2026,10,9,12,tzinfo=timezone.utc); seed(era,gp,m,now,date='2026-10-08'); w(gp/'latest.json',{'generated_at':now.isoformat(),'last_valid_trade_date':'2026-10-09'}); p=dp.build_package(now=now,write=True)
 assert p['package_status']=='STALE'; assert 'all_a_market_snapshot' in p['stale_required_datasets']

def test_missing_business_clock_is_invalid(monkeypatch,tmp_path):
 era,gp,m,_=cfg(monkeypatch,tmp_path); now=datetime(2026,10,9,12,tzinfo=timezone.utc); seed(era,gp,m,now); w(era/'latest.json',{'x':1}); p=dp.build_package(now=now,write=True)
 assert p['package_status']=='INVALID'; assert 'era_radar' in p['unknown_required_datasets']

def test_stale_research_allowed_but_execution_blocked(monkeypatch,tmp_path):
 era,gp,m,_=cfg(monkeypatch,tmp_path); now=datetime(2026,10,10,12,tzinfo=timezone.utc); old=now-timedelta(days=1); seed(era,gp,m,old); p=dp.build_package(now=now,write=True); assert p['package_status']=='STALE'
 out=tmp_path/'research'; monkeypatch.setattr(ri,'PACKAGE_LATEST',dp.LATEST_PATH); monkeypatch.setattr(ri,'PACKAGE_SNAPSHOTS',dp.SNAPSHOT_DIR); monkeypatch.setattr(ri,'OUT_DIR',out); monkeypatch.setattr(ri,'OUT_LATEST',out/'latest.json')
 r=ri.lock_research_input(mode='manual',allow_stale_research_only=True,write=True); assert r['research_allowed'] is True and r['execution_allowed'] is False; assert r['network_policy']=='CANONICAL_PACKAGE_ONLY'

def test_external_evidence_has_no_formal_authority(monkeypatch,tmp_path):
 monkeypatch.setattr(ext,'OUT_DIR',tmp_path/'ext'); e=ext.ingest({'source_url':'https://example.com','observed_at':'2026-10-10T01:00:00+00:00','thesis':'material','affected_codes':['600406']})
 assert e['tag']=='EXTERNAL_FRESH_EVIDENCE'; assert e['formal_action_authority']=='NONE'; assert e['automatic_execution_allowed'] is False

def test_decision_stale_guard_preserves_formal_action(tmp_path):
 package=tmp_path/'p.json'; receipt=tmp_path/'r.json'; decision=tmp_path/'d.json'; handoff=tmp_path/'h.json'
 w(package,{'contract':'GEN_GE_REALTIME_DATA_PACKAGE_V1','snapshot_id':'s','generated_at':'2026-10-10T00:00:00+00:00','package_status':'STALE','latest_trade_date':'2026-10-09'}); w(receipt,{'contract':'GEN_GE_RESEARCH_INPUT_LOCK_V1','input_snapshot_id':'s','research_mode':'manual','locked_at':'x','network_policy':'CANONICAL_PACKAGE_ONLY','external_fresh_evidence_policy':'TAGGED_EXCEPTION_ONLY','execution_allowed':False,'fail_closed_reason':'STALE'}); w(decision,{'today_account_plan':{'available_cash_cny':50000,'planned_immediate_cash_cny':10000,'operations':[{'formal_action':'REDUCE_25','immediate_execution_eligible':True,'executable_shares':100}]}}); w(handoff,{})
 o=binder.bind(decision_path=decision,package_path=package,receipt_path=receipt,handoff_path=handoff); op=o['today_account_plan']['operations'][0]; assert op['formal_action']=='REDUCE_25'; assert op['executable_shares']==0; assert o['today_account_plan']['planned_immediate_cash_cny']==0
