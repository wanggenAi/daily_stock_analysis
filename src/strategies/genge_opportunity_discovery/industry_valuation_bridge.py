"""Merge every-industry research coverage into the reverse-valuation source pool.

The bridge preserves the global opportunity queue while guaranteeing that every
represented industry contributes research names.  It is research-only: no row
is promoted to Formal BUY and hard blockers remain visible.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Iterable, Mapping


def _code(row: Mapping[str, Any]) -> str:
    text = str(row.get("code") or "").strip().upper()
    if "." in text:
        text = text.split(".", 1)[0]
    return text.zfill(6) if text.isdigit() else text


def _read(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def merge_sources(
    global_rows: Iterable[Mapping[str, Any]],
    industry_rows: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in global_rows:
        code = _code(raw)
        if not code or code in seen:
            continue
        row = dict(raw)
        row["code"] = code
        row["valuation_source_channel"] = "GLOBAL_RECALL"
        merged.append(row)
        seen.add(code)
    for raw in industry_rows:
        code = _code(raw)
        if not code or code in seen:
            continue
        row = dict(raw)
        row["code"] = code
        row["valuation_source_channel"] = "INDUSTRY_CHAMPION"
        # Industry coverage is a recall layer only. Never erase blockers or
        # synthesize buy eligibility merely to obtain sector representation.
        row["formal_signal_eligible"] = False
        row["automatic_promotion_allowed"] = False
        row["no_auto_trade"] = True
        merged.append(row)
        seen.add(code)
    return merged


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--all-a-report", type=Path, required=True)
    p.add_argument("--industry-coverage", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args(argv)

    global_rows = []
    for name in ("all_a_quant_screen.csv", "quant_screen_all.csv", "top80_evidence_queue.csv"):
        global_rows = _read(args.all_a_report / name)
        if global_rows:
            break
    industry_rows = _read(args.industry_coverage / "industry_top_candidates.csv")
    if not global_rows:
        raise SystemExit("missing global All-A source")
    if not industry_rows:
        raise SystemExit("missing industry coverage source")

    rows = merge_sources(global_rows, industry_rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with args.output.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader(); w.writerows(rows)
    industries = {str(r.get("industry") or "").strip() for r in industry_rows if str(r.get("industry") or "").strip()}
    summary = {
        "merged_count": len(rows),
        "industry_count": len(industries),
        "industry_champion_added_count": sum(r.get("valuation_source_channel") == "INDUSTRY_CHAMPION" for r in rows),
        "formal_signal_eligible": False,
        "automatic_promotion_allowed": False,
        "no_auto_trade": True,
    }
    args.output.with_suffix(".summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
