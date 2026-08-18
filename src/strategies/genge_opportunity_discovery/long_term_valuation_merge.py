"""Merge long-term second-pass names into an industry-aware valuation source.

This module guarantees that candidates which passed every non-exit-profile hard
gate are actually sent through reverse valuation. It remains research-only and
does not grant Formal BUY eligibility.
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
from pathlib import Path
from typing import Any, Mapping


def _read(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _code(row: Mapping[str, Any]) -> str:
    text = str(row.get("code") or "").strip().upper()
    if "." in text:
        base, suffix = text.rsplit(".", 1)
        if suffix in {"SH", "SZ", "BJ"}:
            text = base
    for prefix in ("SH", "SZ", "BJ"):
        if text.startswith(prefix) and text[len(prefix):].isdigit():
            text = text[len(prefix):]
            break
    return text.zfill(6) if text.isdigit() else text


def merge_long_term_into_valuation(
    valuation_rows: list[Mapping[str, Any]],
    long_term_rows: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    by_code: dict[str, dict[str, Any]] = {}
    for raw in valuation_rows:
        code = _code(raw)
        if not code or code in by_code:
            continue
        row = dict(raw)
        row["code"] = code
        merged.append(row)
        by_code[code] = row

    for raw in long_term_rows:
        code = _code(raw)
        if not code:
            continue
        hard = str(raw.get("hard_blockers") or raw.get("hard_reject_blockers") or "").strip()
        status = str(raw.get("long_term_second_pass_status") or "").strip()
        if hard or status != "PASSED_ALL_NON_EXIT_PROFILE_HARD_GATES":
            continue
        if code in by_code:
            prior = str(by_code[code].get("valuation_source_channel") or "")
            if "LONG_TERM_SECOND_PASS" not in prior:
                by_code[code]["valuation_source_channel"] = (
                    f"{prior}+LONG_TERM_SECOND_PASS" if prior else "LONG_TERM_SECOND_PASS"
                )
            by_code[code]["long_term_second_pass_status"] = status
            by_code[code]["medium_horizon_exit_profile_limitation"] = True
            continue
        row = dict(raw)
        row["code"] = code
        row["valuation_source_channel"] = "LONG_TERM_SECOND_PASS"
        row["wide_recall_reason"] = "LONG_TERM_NON_EXIT_HARD_GATES_PASSED"
        row["quant_status"] = row.get("quant_status") or "SECONDARY_RESEARCH"
        row["formal_signal_eligible"] = False
        row["automatic_promotion_allowed"] = False
        row["no_auto_trade"] = True
        merged.append(row)
        by_code[code] = row
    return merged


def write_source(
    valuation_source_dir: Path,
    long_term_dir: Path,
    output_dir: Path,
) -> list[dict[str, Any]]:
    base = _read(valuation_source_dir / "all_a_quant_screen.csv")
    long_term = _read(long_term_dir / "long_term_second_pass_candidates.csv")
    if not base:
        raise FileNotFoundError("industry-aware valuation source is empty")
    rows = merge_long_term_into_valuation(base, long_term)
    output_dir.mkdir(parents=True, exist_ok=True)
    fields = sorted({k for row in rows for k in row})
    with (output_dir / "all_a_quant_screen.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader(); w.writerows(rows)
    for name in ("run_summary.json", "quant_screen_summary.json"):
        src = valuation_source_dir / name
        if src.exists():
            shutil.copy2(src, output_dir / name)
            break
    summary = {
        "source_count": len(base),
        "long_term_second_pass_input_count": len(long_term),
        "merged_count": len(rows),
        "long_term_routed_count": sum(
            "LONG_TERM_SECOND_PASS" in str(r.get("valuation_source_channel") or "")
            for r in rows
        ),
        "formal_signal_eligible": False,
        "automatic_promotion_allowed": False,
        "no_auto_trade": True,
    }
    (output_dir / "long_term_valuation_source_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return rows


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--valuation-source-dir", type=Path, required=True)
    p.add_argument("--long-term-dir", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    args = p.parse_args(argv)
    rows = write_source(args.valuation_source_dir, args.long_term_dir, args.output_dir)
    print(f"long_term_valuation_source={args.output_dir};count={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
