from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .dashboard import render_dashboard
from .engine import apply_changes, rank_candidates
from .sources import load_candidates, load_holdings, load_market_context


TZ = ZoneInfo("Asia/Shanghai")


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def run(root: Path, *, top_n: int, industry_cap: int, output: Path, json_output: Path) -> dict:
    now = datetime.now(TZ)
    run_id = now.strftime("v2-%Y%m%d-%H%M%S")
    raw_rows, source_meta = load_candidates(root)
    holdings = load_holdings(root)
    market = load_market_context(root)
    global_transmission = ((market.get("global") or {}).get("security_transmission") or {})
    chosen, all_candidates = rank_candidates(
        raw_rows,
        source_meta.get("source", ""),
        holdings,
        top_n=top_n,
        industry_cap=industry_cap,
        global_transmission=global_transmission,
    )
    previous = _load_json(json_output)
    removed = apply_changes(chosen, previous)

    payload = {
        "schema_version": "v2.1",
        "run_id": run_id,
        "generated_at": now.isoformat(),
        "source": source_meta,
        "market": market,
        "stats": {
            "raw_candidates": len(raw_rows),
            "normalized_candidates": len(all_candidates),
            "visible_pool": len(chosen),
            "buy": sum(c.state == "BUY" for c in chosen),
            "near_buy": sum(c.state == "NEAR_BUY" for c in chosen),
            "watch": sum(c.state == "WATCH" for c in chosen),
            "holdings_in_pool": sum(c.holding for c in chosen),
            "global_transmission_mapped": sum(c.code in global_transmission for c in chosen),
        },
        "removed": removed,
        "candidates": [c.to_dict() for c in chosen],
    }
    json_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output.write_text(render_dashboard(run_id=run_id, generated_at=payload["generated_at"], source_meta=source_meta, market=market, candidates=chosen, removed=removed, total_raw=len(raw_rows)), encoding="utf-8")
    if not chosen:
        raise RuntimeError("V2 produced zero visible candidates: no usable live scan or committed fallback")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build the GenGe Stock V2 single-truth dashboard")
    parser.add_argument("--root", default=".")
    parser.add_argument("--top", type=int, default=30)
    parser.add_argument("--industry-cap", type=int, default=3)
    parser.add_argument("--output", default="V2_DASHBOARD.md")
    parser.add_argument("--json-output", default="data/v2/latest_run.json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.root).resolve()
    payload = run(root, top_n=max(10, min(50, args.top)), industry_cap=max(1, args.industry_cap), output=root / args.output, json_output=root / args.json_output)
    print(f"[V2] {payload['run_id']} mode={payload['source']['mode']} visible={payload['stats']['visible_pool']} buy={payload['stats']['buy']} near_buy={payload['stats']['near_buy']} global_mapped={payload['stats']['global_transmission_mapped']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
