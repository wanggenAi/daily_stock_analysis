"""Force strict HARD_LOGIC_PASS companies into the valuation research source.

This is the bridge that restores the intended decision order:

    industry research -> structural hard logic -> valuation research -> price map

A selected company outside the Quant Top-N seed list may enter valuation only when
(1) the strict hard-logic research row is PASS and (2) its code exists in the raw
All-A scan.  The sidecar alone can never invent a security.
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
from pathlib import Path
from typing import Any, Mapping


HARD_LOGIC_FIELDS = (
    "hard_logic_state",
    "hard_logic_score",
    "hard_logic_missing_evidence",
    "hard_logic_structural_driver",
    "hard_logic_supply_constraint",
    "hard_logic_company_edge",
    "hard_logic_profit_transmission",
    "hard_logic_invalidation",
    "hard_logic_duration_years",
    "hard_logic_persistence",
    "hard_logic_evidence_sources",
    "research_summary",
    "research_state",
    "selection_origin",
)


def _read(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _code(value: Any) -> str:
    if isinstance(value, Mapping):
        value = value.get("code") or value.get("selected_code") or value.get("代码")
    text = str(value or "").strip().upper()
    if "." in text:
        base, suffix = text.rsplit(".", 1)
        if suffix in {"SH", "SZ", "BJ"} and base.isdigit():
            text = base
    for prefix in ("SH", "SZ", "BJ"):
        if text.startswith(prefix) and text[len(prefix):].isdigit():
            text = text[len(prefix):]
            break
    return text.zfill(6) if text.isdigit() else text


def merge_hard_logic_into_valuation(
    valuation_rows: list[Mapping[str, Any]],
    hard_logic_rows: list[Mapping[str, Any]],
    raw_all_a_rows: list[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    merged: list[dict[str, Any]] = []
    by_code: dict[str, dict[str, Any]] = {}
    raw_by_code = {
        _code(row): dict(row)
        for row in raw_all_a_rows
        if _code(row)
    }

    for raw in valuation_rows:
        code = _code(raw)
        if not code or code in by_code:
            continue
        row = dict(raw)
        row["code"] = code
        merged.append(row)
        by_code[code] = row

    stats = {
        "hard_logic_pass_input_count": 0,
        "hard_logic_routed_count": 0,
        "external_nomination_routed_count": 0,
        "missing_from_all_a_count": 0,
    }

    for research in hard_logic_rows:
        if str(research.get("hard_logic_state") or "").strip().upper() != "PASS":
            continue
        if str(research.get("research_state") or "").strip().upper() != "PASS":
            continue
        code = _code(research.get("selected_code"))
        if not code:
            continue
        stats["hard_logic_pass_input_count"] += 1

        if code not in by_code:
            raw_row = raw_by_code.get(code)
            if raw_row is None:
                stats["missing_from_all_a_count"] += 1
                continue
            row = dict(raw_row)
            row["code"] = code
            row["valuation_source_channel"] = "HARD_LOGIC_PASS"
            row["wide_recall_reason"] = "STRUCTURAL_HARD_LOGIC_PASS"
            row["quant_status"] = row.get("quant_status") or "HARD_LOGIC_RESEARCH"
            merged.append(row)
            by_code[code] = row
            if str(research.get("selection_origin") or "") == "EXTERNAL_A_SHARE_NOMINATION":
                stats["external_nomination_routed_count"] += 1
        else:
            row = by_code[code]
            prior = str(row.get("valuation_source_channel") or "")
            if "HARD_LOGIC_PASS" not in prior:
                row["valuation_source_channel"] = (
                    f"{prior}+HARD_LOGIC_PASS" if prior else "HARD_LOGIC_PASS"
                )

        row = by_code[code]
        row["hard_logic_state"] = "PASS"
        row["hard_logic_research_industry"] = research.get("industry") or row.get("industry") or ""
        for field in HARD_LOGIC_FIELDS:
            if field in research:
                row[field] = research.get(field)
        row["formal_signal_eligible"] = False
        row["automatic_promotion_allowed"] = False
        row["no_auto_trade"] = True
        stats["hard_logic_routed_count"] += 1

    return merged, stats


def write_source(
    *,
    valuation_source_dir: Path,
    hard_logic_research_dir: Path,
    raw_all_a_csv: Path,
    output_dir: Path,
) -> list[dict[str, Any]]:
    valuation = _read(valuation_source_dir / "all_a_quant_screen.csv")
    research = _read(hard_logic_research_dir / "hard_logic_research.csv")
    raw = _read(raw_all_a_csv)
    if not valuation:
        raise FileNotFoundError("valuation source is empty")
    if not research:
        raise FileNotFoundError("hard-logic research map is empty")
    if not raw:
        raise FileNotFoundError("raw All-A universe is empty")

    rows, stats = merge_hard_logic_into_valuation(valuation, research, raw)
    output_dir.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with (output_dir / "all_a_quant_screen.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    for name in (
        "long_term_valuation_source_summary.json",
        "run_summary.json",
        "quant_screen_summary.json",
    ):
        source = valuation_source_dir / name
        if source.exists():
            shutil.copy2(source, output_dir / name)

    summary = {
        "source_count": len(valuation),
        "merged_count": len(rows),
        **stats,
        "hard_logic_precedes_valuation": True,
        "topn_seed_is_answer": False,
        "external_nomination_requires_all_a_membership": True,
        "formal_signal_eligible": False,
        "automatic_promotion_allowed": False,
        "no_auto_trade": True,
    }
    (output_dir / "hard_logic_valuation_source_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--valuation-source-dir", type=Path, required=True)
    parser.add_argument("--hard-logic-research-dir", type=Path, required=True)
    parser.add_argument("--raw-all-a-csv", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    rows = write_source(
        valuation_source_dir=args.valuation_source_dir,
        hard_logic_research_dir=args.hard_logic_research_dir,
        raw_all_a_csv=args.raw_all_a_csv,
        output_dir=args.output_dir,
    )
    print(f"hard_logic_valuation_source={args.output_dir};count={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
