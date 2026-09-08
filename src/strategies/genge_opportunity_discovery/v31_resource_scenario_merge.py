"""Map executed resource NAV scenarios and explicit reviews into frozen V3.1.

Only direct semantic mappings are allowed. Resource NAV can fill valuation decks
only when an auditable four-scenario model actually executed. Judgement-heavy
hard gates are then resolved only by the fail-closed explicit deep-review
executor; no legacy score or cheap price can promote a gate or Formal BUY.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Mapping

from .v31_explicit_deep_review import (
    _latest_valuation_csv,
    _load_config,
    apply_explicit_reviews,
)

DISCLAIMER = "仅用于公开数据研究与人工复核，不构成买入或卖出建议，不应自动交易。"
DEFAULT_REVIEW_CONFIG = Path("config/v31_explicit_deep_reviews.json")


def _code(value: Any) -> str:
    text = str(value or "").strip().upper()
    if "." in text:
        base, suffix = text.rsplit(".", 1)
        if suffix in {"SH", "SZ", "BJ"}:
            text = base
    for prefix in ("SH", "SZ", "BJ"):
        if text.startswith(prefix) and text[len(prefix):].isdigit():
            text = text[len(prefix):]
            break
    return text.zfill(6) if text.isdigit() else text


def _read(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def merge_rows(v31_rows: list[Mapping[str, Any]], resource_rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    resources = {_code(r.get("code")): r for r in resource_rows if _code(r.get("code"))}
    output: list[dict[str, Any]] = []
    for raw in v31_rows:
        row = dict(raw)
        code = _code(row.get("code"))
        resource = resources.get(code)
        row["v31_resource_scenario_source"] = ""
        row["v31_resource_scenario_status"] = ""
        if (
            resource
            and str(resource.get("resource_nav_executed")).lower() == "true"
            and resource.get("resource_nav_status") == "OK"
        ):
            mapping = {
                "v31_extreme_stress_value": "resource_nav_extreme_stress_per_share",
                "v31_pessimistic_value": "resource_nav_bear_per_share",
                "v31_neutral_value": "resource_nav_base_per_share",
                "v31_optimistic_value": "resource_nav_bull_per_share",
            }
            if all(str(resource.get(source) or "").strip() for source in mapping.values()):
                for target, source in mapping.items():
                    row[target] = resource[source]
                row["v31_resource_scenario_source"] = "FINITE_LIFE_RESOURCE_NAV_FOUR_DECK"
                row["v31_resource_scenario_status"] = "MAPPED"
                evidence = str(resource.get("resource_nav_evidence_urls") or "").strip()
                if evidence:
                    existing = str(row.get("v31_review_evidence_urls") or "").strip()
                    row["v31_review_evidence_urls"] = ";".join(x for x in (existing, evidence) if x)
            else:
                row["v31_resource_scenario_status"] = "EXECUTED_VALUES_INCOMPLETE"
        elif resource and resource.get("resource_nav_status") != "NOT_RESOURCE_ROUTE":
            row["v31_resource_scenario_status"] = resource.get("resource_nav_status") or "RESOURCE_REVIEW_REQUIRED"
        row.update(
            {
                "formal_signal_eligible": False,
                "automatic_promotion_allowed": False,
                "no_auto_trade": True,
                "disclaimer": DISCLAIMER,
            }
        )
        output.append(row)
    return output


def write_report(
    v31_dir: Path,
    resource_root: Path,
    output_dir: Path,
    review_config: Path = DEFAULT_REVIEW_CONFIG,
) -> list[dict[str, Any]]:
    v31_path = v31_dir / "v31_review_queue.csv"
    resource_runs = (
        sorted(
            p
            for p in resource_root.iterdir()
            if p.is_dir() and (p / "valuation_research_resource_nav.csv").exists()
        )
        if resource_root.exists()
        else []
    )
    direct = resource_root / "valuation_research_resource_nav.csv"
    resource_path = direct if direct.exists() else (resource_runs[-1] / "valuation_research_resource_nav.csv" if resource_runs else None)
    if resource_path is None:
        raise FileNotFoundError("valuation_research_resource_nav.csv not found")

    rows = merge_rows(_read(v31_path), _read(resource_path))
    deep_review_summary: dict[str, Any] | None = None
    if review_config.exists():
        valuation_path = _latest_valuation_csv(resource_root)
        rows, deep_review_summary = apply_explicit_reviews(
            rows,
            _read(valuation_path),
            _load_config(review_config),
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    preferred = list(rows[0].keys()) if rows else []
    with (output_dir / "v31_review_queue_enriched.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=preferred, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    if deep_review_summary is not None:
        (output_dir / "v31_explicit_deep_review_summary.json").write_text(
            json.dumps(deep_review_summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    summary = {
        "candidate_count": len(rows),
        "resource_four_scenario_mapped_count": sum(r.get("v31_resource_scenario_status") == "MAPPED" for r in rows),
        "explicit_deep_review": deep_review_summary,
        "formal_signal_eligible": False,
        "automatic_promotion_allowed": False,
        "no_auto_trade": True,
        "semantics": "frozen_v31_queue_plus_auditable_resource_nav_plus_explicit_deep_review",
    }
    (output_dir / "v31_resource_scenario_merge_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--v31-dir", type=Path, required=True)
    parser.add_argument("--resource-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--review-config", type=Path, default=DEFAULT_REVIEW_CONFIG)
    args = parser.parse_args(argv)
    rows = write_report(args.v31_dir, args.resource_root, args.output_dir, args.review_config)
    print(f"v31_resource_scenario_merge={args.output_dir};count={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
