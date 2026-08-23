"""Conservatively enrich valuation routes for obvious listed resource owners.

Some market-data providers expose a broad industry label such as 有色/工业金属
while the listed company name itself carries a strong mining-owner signal (for
example 矿业/钼业/煤业).  This sidecar upgrades only those broad-resource rows to
RESOURCE_ASSET review.  It does not execute NAV; the downstream resource executor
still requires a complete, as-of-safe reserve/cost/price evidence deck.

The enrichment never treats generic words such as 资源, 黄金, 稀土 or 铜业 alone
as proof of reserve ownership, because those names can describe processors,
traders or downstream businesses.  Explicit point-in-time company profiles keep
priority over this heuristic.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Mapping

DISCLAIMER = "仅用于公开数据研究排序和人工复核，不构成买入或卖出建议，不应自动交易。"
RESOURCE_STRATEGY_ID = "resource_asset_nav"
GENERAL_STRATEGY_ID = "general_reverse_earnings"

STRONG_NAME_TOKENS = ("矿业", "钼业", "煤业", "矿产")
RESOURCE_INDUSTRY_TOKENS = (
    "有色", "工业金属", "贵金属", "稀有金属", "小金属", "煤炭", "能源金属",
    "金属矿", "矿业", "采矿", "采选",
)
PROCESSOR_ONLY_TOKENS = ("冶炼", "精炼", "加工", "材料", "合金")


def _text(value: Any) -> str:
    return str(value or "").strip().lower()


def _truthy(value: Any) -> bool:
    return _text(value) in {"true", "1", "yes", "y"}


def should_upgrade(row: Mapping[str, Any]) -> bool:
    if _truthy(row.get("valuation_profile_used_for_routing")):
        return False
    if _text(row.get("valuation_primary_strategy_id")) == RESOURCE_STRATEGY_ID:
        return False
    name = _text(row.get("stock_name"))
    industry = _text(row.get("industry"))
    if not any(token in name for token in STRONG_NAME_TOKENS):
        return False
    if not any(token in industry for token in RESOURCE_INDUSTRY_TOKENS):
        return False
    # Processor words in the *industry* can mean the provider explicitly knows
    # the row is downstream; fail closed instead of overriding it by name.
    if any(token in industry for token in PROCESSOR_ONLY_TOKENS):
        return False
    return True


def enrich_rows(rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for raw in rows:
        row = dict(raw)
        row["resource_route_name_enriched"] = False
        if should_upgrade(row):
            old_primary = str(row.get("valuation_primary_strategy_id") or "").strip()
            old_alts = [x for x in str(row.get("valuation_alternative_strategy_ids") or "").split(";") if x]
            if old_primary and old_primary != RESOURCE_STRATEGY_ID and old_primary not in old_alts:
                old_alts.insert(0, old_primary)
            row.update({
                "resource_route_name_enriched": True,
                "valuation_route_status": "RESOURCE_OWNER_NAME_PLUS_INDUSTRY_REVIEW",
                "valuation_route_archetypes": "RESOURCE_ASSET",
                "valuation_strategy_ids": ";".join([RESOURCE_STRATEGY_ID] + old_alts),
                "valuation_primary_strategy_id": RESOURCE_STRATEGY_ID,
                "valuation_alternative_strategy_ids": ";".join(old_alts),
                "valuation_routing_confidence": min(float(row.get("valuation_routing_confidence") or 1.0), 0.88),
                "valuation_route_reasons": ";".join(
                    x for x in (
                        str(row.get("valuation_route_reasons") or "").strip(),
                        "stock_name_plus_resource_industry_requires_resource_nav_review",
                    ) if x
                ),
                "valuation_model_execution_state": "SPECIALIZED_MODEL_SELECTED_INPUTS_REQUIRED",
                "valuation_model_next_action": f"run_specialized_model:{RESOURCE_STRATEGY_ID}",
                "formal_signal_eligible": False,
                "automatic_promotion_allowed": False,
                "no_auto_trade": True,
                "disclaimer": DISCLAIMER,
            })
        output.append(row)
    return output


def _latest_report_dir(root: Path) -> Path:
    if (root / "valuation_research_routed.csv").exists():
        return root
    candidates = sorted(
        {p.parent for p in root.glob("**/valuation_research_routed.csv") if p.is_file()},
        key=str,
    )
    if not candidates:
        raise FileNotFoundError(f"no valuation_research_routed.csv under {root}")
    return candidates[-1]


def write_enriched(report_root: Path) -> dict[str, Any]:
    report_dir = _latest_report_dir(report_root)
    path = report_dir / "valuation_research_routed.csv"
    with path.open(encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        fields = list(reader.fieldnames or [])
        rows = list(reader)
    enriched = enrich_rows(rows)
    if "resource_route_name_enriched" not in fields:
        fields.append("resource_route_name_enriched")
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader(); writer.writerows(enriched)
    upgraded = [r for r in enriched if r.get("resource_route_name_enriched")]
    summary = {
        "row_count": len(enriched),
        "resource_name_enriched_count": len(upgraded),
        "resource_name_enriched_codes": [str(r.get("code") or "") for r in upgraded],
        "formal_signal_eligible": False,
        "automatic_promotion_allowed": False,
        "no_auto_trade": True,
        "disclaimer": DISCLAIMER,
    }
    (report_dir / "resource_route_enrichment_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-root", type=Path, required=True)
    args = parser.parse_args(argv)
    summary = write_enriched(args.report_root)
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
