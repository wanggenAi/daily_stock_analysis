#!/usr/bin/env python3
"""Build/validate the canonical network-free GenGe data-package boundary."""
from __future__ import annotations
import argparse, hashlib, json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CONTRACT="GEN_GE_REALTIME_DATA_PACKAGE_V1"
PACKAGE_DIR=Path("data/data_package"); LATEST_PATH=PACKAGE_DIR/"latest.json"; SNAPSHOT_DIR=PACKAGE_DIR/"snapshots"; STATE_PATH=PACKAGE_DIR/"watermarks.json"
MAX_LINEAGE_FILES=50
EXCLUDED_ROOTS={"data/data_package","data/research_input","data/decision_center","data/investor_chatgpt_handoff","data/investor_decision_dashboard","data/formal_decision_history","data/formal_decision_outcomes","data/deep_calculation","data/deep_calculation_fast","data/hourly_research_state"}
# name, root, execution-critical, wall-clock SLA minutes, freshness basis
PRODUCER_ROOTS=(
 ("all_a_market_snapshot","data/market_snapshots",True,None,"TRADE_DATE"),
 ("era_radar","data/era_radar",True,8*60,"WALL_CLOCK"),
 ("global_market_pulse","data/global_market_pulse",True,8*60,"WALL_CLOCK"),
 ("evidence_events","data/evidence_events",False,24*60,"WALL_CLOCK"),
 ("opportunity_snapshots","data/opportunity_snapshots",False,24*60,"WALL_CLOCK"),
 ("production_status","data/production_status",False,6*60,"WALL_CLOCK"),
 ("production_observability","data/production_observability",False,6*60,"WALL_CLOCK"),
 ("manual_execution_quotes","data/manual_execution_quotes",False,60,"WALL_CLOCK"),
 ("price_value_history","data/price_value_history",False,24*60,"WALL_CLOCK"),
 ("research_mapping","data/research_mapping",False,24*60,"WALL_CLOCK"),
 ("user_supplied","data/user_supplied",False,None,"NOT_APPLICABLE"),
 ("live_execution_quotes","data/live_execution_quotes",False,30,"WALL_CLOCK"),
)
TIMESTAMP_KEYS={"collected_at","generated_at","updated_at","observed_at","as_of","snapshot_at","research_as_of","latest_quote_observed_at","latest_observation_at","refreshed_at","ingested_at"}
DATE_KEYS={"latest_trade_date","last_valid_trade_date","trade_date","market_date","effective_date","as_of_date"}

def _utc_now(): return datetime.now(timezone.utc)
def _iso(dt): return dt.astimezone(timezone.utc).isoformat()
def _hour_epoch(dt): return dt.astimezone(timezone.utc).replace(minute=0,second=0,microsecond=0)
def _parse_dt(value):
 if not isinstance(value,str) or not value.strip(): return None
 text=value.strip().replace("Z","+00:00")
 try: dt=datetime.fromisoformat(text)
 except ValueError:
  try: dt=datetime.strptime(text[:10],"%Y-%m-%d").replace(tzinfo=timezone.utc)
  except ValueError: return None
 if dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
 return dt.astimezone(timezone.utc)
def _sha(path):
 h=hashlib.sha256()
 with path.open("rb") as fh:
  for chunk in iter(lambda:fh.read(1024*1024),b""): h.update(chunk)
 return h.hexdigest()
def _files(root):
 if not root.exists(): return []
 if root.is_file(): return [root]
 out=[]
 for p in root.rglob("*"):
  if not p.is_file(): continue
  rel=p.as_posix()
  if any(rel==x or rel.startswith(x+"/") for x in EXCLUDED_ROOTS): continue
  if p.suffix.lower() in {".json",".jsonl",".csv",".md",".parquet"}: out.append(p)
 return sorted(out)
def _extract_times(path):
 if path.suffix.lower()!=".json": return None,None
 try: payload=json.loads(path.read_text(encoding="utf-8"))
 except Exception: return None,None
 latest_dt=None; latest_date=None
 def visit(obj,depth=0):
  nonlocal latest_dt,latest_date
  if depth>5:return
  if isinstance(obj,dict):
   for k,v in obj.items():
    if k in TIMESTAMP_KEYS:
     d=_parse_dt(v)
     if d and (latest_dt is None or d>latest_dt): latest_dt=d
    if k in DATE_KEYS and isinstance(v,str) and len(v)>=10:
     d=v[:10]
     if latest_date is None or d>latest_date: latest_date=d
    if isinstance(v,(dict,list)): visit(v,depth+1)
  elif isinstance(obj,list):
   for v in obj[:1000]:
    if isinstance(v,(dict,list)): visit(v,depth+1)
 visit(payload); return latest_dt,latest_date

@dataclass
class DatasetManifest:
 name:str; root:str; execution_critical:bool; exists:bool; file_count:int; content_sha256:str|None; latest_observed_at:str|None; latest_trade_date:str|None; freshness_sla_minutes:int|None; freshness_basis:str; freshness_state:str; changed_since_previous:bool|None; watermark:str|None; lineage_file_sample:list[dict[str,Any]]; lineage_file_sample_truncated:bool

def _manifest(name,root_text,critical,sla,basis,*,now,previous):
 files=_files(Path(root_text)); rows=[]; latest_dt=None; latest_date=None; agg=hashlib.sha256()
 for i,p in enumerate(files):
  sha=_sha(p); obs,td=_extract_times(p); rel=p.as_posix(); agg.update(rel.encode()); agg.update(sha.encode())
  if i<MAX_LINEAGE_FILES: rows.append({"path":rel,"sha256":sha,"size":p.stat().st_size,"observed_at":_iso(obs) if obs else None,"trade_date":td})
  if obs and (latest_dt is None or obs>latest_dt): latest_dt=obs
  if td and (latest_date is None or td>latest_date): latest_date=td
 exists=bool(files); digest=agg.hexdigest() if exists else None
 if not exists: freshness="MISSING"
 elif basis=="TRADE_DATE": freshness="PENDING_TRADE_DATE_ALIGNMENT" if latest_date else "UNKNOWN"
 elif basis=="NOT_APPLICABLE" or sla is None: freshness="NOT_APPLICABLE"
 elif latest_dt is None: freshness="UNKNOWN"
 else: freshness="FRESH" if max(0,(now-latest_dt).total_seconds()/60)<=sla else "STALE"
 prev=(previous or {}).get("content_sha256"); changed=None if prev is None else prev!=digest
 wm=hashlib.sha256(f"{digest or 'MISSING'}|{latest_date or ''}|{_iso(latest_dt) if latest_dt else ''}".encode()).hexdigest()[:24] if exists else None
 return DatasetManifest(name,root_text,critical,exists,len(files),digest,_iso(latest_dt) if latest_dt else None,latest_date,sla,basis,freshness,changed,wm,rows,len(files)>MAX_LINEAGE_FILES)

def _previous():
 if not LATEST_PATH.is_file(): return {}
 try:p=json.loads(LATEST_PATH.read_text(encoding="utf-8"))
 except Exception:return {}
 return {str(x.get("name")):x for x in p.get("datasets") or [] if isinstance(x,dict)}

def build_package(*,now=None,write=True):
 now=now or _utc_now(); epoch=_hour_epoch(now); prev=_previous()
 datasets=[_manifest(n,r,c,s,b,now=now,previous=prev.get(n)) for n,r,c,s,b in PRODUCER_ROOTS]
 by={d.name:d for d in datasets}; pulse=by.get("global_market_pulse"); market=by.get("all_a_market_snapshot")
 expected_market_date=pulse.latest_trade_date if pulse else None
 if market and market.exists:
  if not expected_market_date: market.freshness_state="UNKNOWN"
  elif not market.latest_trade_date: market.freshness_state="UNKNOWN"
  elif market.latest_trade_date<expected_market_date: market.freshness_state="STALE"
  else: market.freshness_state="FRESH"
 missing=[d.name for d in datasets if d.execution_critical and not d.exists]
 stale=[d.name for d in datasets if d.execution_critical and d.freshness_state=="STALE"]
 unknown=[d.name for d in datasets if d.execution_critical and d.freshness_state in {"UNKNOWN","PENDING_TRADE_DATE_ALIGNMENT"}]
 optional_degraded=[d.name for d in datasets if not d.execution_critical and d.freshness_state in {"MISSING","STALE","UNKNOWN"}]
 if missing or unknown: status="INVALID"
 elif stale: status="STALE"
 else: status="READY"
 completeness="DEGRADED" if optional_degraded else "COMPLETE"
 latest_dates=sorted({d.latest_trade_date for d in datasets if d.latest_trade_date}); latest_trade_date=latest_dates[-1] if latest_dates else None
 basis={"contract":CONTRACT,"freshness_epoch":_iso(epoch),"expected_latest_a_share_trade_date":expected_market_date,"datasets":[{"name":d.name,"content_sha256":d.content_sha256,"watermark":d.watermark,"freshness_state":d.freshness_state} for d in datasets]}
 sid=hashlib.sha256(json.dumps(basis,sort_keys=True,separators=(",",":")).encode()).hexdigest()[:20]
 ext=PACKAGE_DIR/"external_fresh_evidence"/"events"; pending=0
 if ext.is_dir():
  for p in ext.glob("*.json"):
   try:e=json.loads(p.read_text(encoding="utf-8"))
   except Exception:continue
   if e.get("tag")=="EXTERNAL_FRESH_EVIDENCE" and e.get("backfill_status")!="CANONICAL_INGESTED":pending+=1
 payload={"contract":CONTRACT,"generated_at":_iso(epoch),"freshness_epoch":_iso(epoch),"snapshot_id":sid,"package_status":status,"completeness_state":completeness,"latest_trade_date":latest_trade_date,"expected_latest_a_share_trade_date":expected_market_date,"market_trade_date_alignment_ok":bool(market and expected_market_date and market.latest_trade_date and market.latest_trade_date>=expected_market_date),"incremental_update_contract":{"mode":"CONTENT_WATERMARK_INCREMENTAL","full_history_redownload_required_for_research":False,"research_may_fetch_network_by_default":False,"collector_layer_owns_acquisition":True,"filesystem_mtime_may_establish_freshness":False,"immutable_snapshot_overwrite_allowed":False},"missing_required_datasets":missing,"stale_required_datasets":stale,"unknown_required_datasets":unknown,"optional_degraded_datasets":optional_degraded,"pending_external_fresh_evidence_count":pending,"datasets":[asdict(d) for d in datasets]}
 if write:
  PACKAGE_DIR.mkdir(parents=True,exist_ok=True); SNAPSHOT_DIR.mkdir(parents=True,exist_ok=True)
  text=json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True)+"\n"; snap=SNAPSHOT_DIR/f"{sid}.json"
  if snap.exists():
   existing=json.loads(snap.read_text(encoding="utf-8"))
   if existing!=payload: raise RuntimeError(f"immutable snapshot collision: {sid}")
  else:snap.write_text(text,encoding="utf-8")
  LATEST_PATH.write_text(text,encoding="utf-8")
  STATE_PATH.write_text(json.dumps({"contract":"GEN_GE_DATA_PACKAGE_WATERMARKS_V1","updated_at":_iso(now),"snapshot_id":sid,"watermarks":{d.name:d.watermark for d in datasets}},ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
 return payload

def validate_package(*,require_fresh=False):
 if not LATEST_PATH.is_file():return False,{"error":"DATA_PACKAGE_MISSING","path":str(LATEST_PATH)}
 try:p=json.loads(LATEST_PATH.read_text(encoding="utf-8"))
 except Exception as e:return False,{"error":"DATA_PACKAGE_INVALID_JSON","detail":str(e)}
 if p.get("contract")!=CONTRACT:return False,{"error":"DATA_PACKAGE_CONTRACT_MISMATCH","contract":p.get("contract")}
 sid=str(p.get("snapshot_id") or ""); snap=SNAPSHOT_DIR/f"{sid}.json"
 if not sid or not snap.is_file():return False,{"error":"IMMUTABLE_SNAPSHOT_MISSING","snapshot_id":sid}
 try:immutable=json.loads(snap.read_text(encoding="utf-8"))
 except Exception as e:return False,{"error":"IMMUTABLE_SNAPSHOT_INVALID","detail":str(e)}
 if immutable!=p:return False,{"error":"LATEST_IMMUTABLE_SNAPSHOT_MISMATCH","snapshot_id":sid}
 if require_fresh and p.get("package_status")!="READY":return False,{"error":"DATA_PACKAGE_NOT_FRESH_READY","package_status":p.get("package_status"),"snapshot_id":sid}
 return True,p

def main(argv=None):
 parser=argparse.ArgumentParser(); sub=parser.add_subparsers(dest="command",required=True); b=sub.add_parser("build"); b.add_argument("--no-write",action="store_true"); v=sub.add_parser("validate"); v.add_argument("--require-fresh",action="store_true"); args=parser.parse_args(argv)
 if args.command=="build":
  p=build_package(write=not args.no_write); print(json.dumps({k:p.get(k) for k in ("contract","snapshot_id","package_status","completeness_state","latest_trade_date","expected_latest_a_share_trade_date")},ensure_ascii=False)); return 0 if p.get("package_status")!="INVALID" else 2
 ok,p=validate_package(require_fresh=args.require_fresh); print(json.dumps(p if not ok else {k:p.get(k) for k in ("contract","snapshot_id","package_status","completeness_state","latest_trade_date")},ensure_ascii=False)); return 0 if ok else 2
if __name__=="__main__": raise SystemExit(main())
