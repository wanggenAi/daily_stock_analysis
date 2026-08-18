"""Long-term second pass for candidates blocked only by exit-profile validation.

A 60-day/medium-horizon exit-profile sample limitation is not allowed to erase a
candidate that passed every non-exit-profile hard gate.  This module surfaces
those names for valuation/fundamental review.  It never manufactures Formal BUY
eligibility and never bypasses non-exit hard gates.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

EXIT_PROFILE_GATE_PREFIXES = (
    "exit_profile_",
    "profile_validation_",
    "profile_data_",
)


def _read(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _split(value: Any) -> set[str]:
    return {x.strip() for x in str(value or "").split(";") if x.strip()}


def _failed_gates(row: Mapping[str, Any]) -> set[str]:
    for key in ("strict_gate_failed", "missing_conditions", "classification_missing_conditions"):
        values = _split(row.get(key))
        if values:
            return values
    return set()


def _is_exit_profile_gate(name: str) -> bool:
    return name.startswith(EXIT_PROFILE_GATE_PREFIXES)


def passes_all_non_exit_hard_gates(row: Mapping[str, Any]) -> bool:
    hard = str(row.get("hard_blockers") or row.get("hard_reject_blockers") or "").strip()
    if hard:
        return False
    failed = _failed_gates(row)
    return bool(failed) and all(_is_exit_profile_gate(name) for name in failed)


def select_long_term_second_pass(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in rows:
        code = str(raw.get("code") or "").strip()
        if not code or code in seen or not passes_all_non_exit_hard_gates(raw):
            continue
        row = dict(raw)
        row.update(
            {
                "long_term_second_pass_status": "PASSED_ALL_NON_EXIT_PROFILE_HARD_GATES",
                "formal_signal_eligible": False,
                "automatic_promotion_allowed": False,
                "requires_valuation_review": True,
                "requires_fundamental_review": True,
                "medium_horizon_exit_profile_limitation": True,
                "no_auto_trade": True,
            }
        )
        selected.append(row)
        seen.add(code)
    selected.sort(
        key=lambda r: (
            -float(r.get("actionability_score") or 0),
            -float(r.get("quant_score") or 0),
            str(r.get("code") or ""),
        )
    )
    return selected


def find_latest_report(root: Path) -> Path:
    if (root / "run_summary.json").exists():
        return root
    dirs = sorted({p.parent for p in root.glob("**/run_summary.json") if p.is_file()}, key=str)
    if not dirs:
        raise FileNotFoundError(f"no All-A report under {root}")
    return dirs[-1]


def load_candidates(report_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for name in ("condition_watch.csv", "research_watch.csv", "top30_deep_review.csv", "tomorrow_watchlist.csv"):
        for row in _read(report_dir / name):
            code = str(row.get("code") or "").strip()
            if code and code not in seen:
                rows.append(row)
                seen.add(code)
    return rows


def write_report(report_dir: Path, output_dir: Path) -> list[dict[str, Any]]:
    rows = select_long_term_second_pass(load_candidates(report_dir))
    output_dir.mkdir(parents=True, exist_ok=True)
    fields = [
        "code", "stock_name", "industry", "classification", "user_visible_level",
        "quant_score", "actionability_score", "real_reward_risk_ratio",
        "strict_gate_failed", "missing_conditions", "exit_profile_status",
        "long_term_second_pass_status", "requires_valuation_review",
        "requires_fundamental_review", "medium_horizon_exit_profile_limitation",
        "formal_signal_eligible", "automatic_promotion_allowed", "no_auto_trade",
    ]
    with (output_dir / "long_term_second_pass_candidates.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader(); w.writerows(rows)
    summary = {
        "candidate_count": len(rows),
        "codes": [r.get("code") for r in rows],
        "semantics": "passed all non-exit-profile hard gates; exit-profile limitation is medium-horizon validation only",
        "formal_signal_eligible": False,
        "automatic_promotion_allowed": False,
        "requires_valuation_review": True if rows else False,
        "no_auto_trade": True,
    }
    (output_dir / "long_term_second_pass_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# Long-Term Second Pass",
        "",
        "Candidates here passed all non-exit-profile hard gates. Exit-profile sample limitations remain visible but do not erase long-term research visibility.",
        "",
    ]
    for i, row in enumerate(rows, 1):
        lines.append(
            f"{i}. {row.get('code','')} {row.get('stock_name','')} | industry={row.get('industry','')} | "
            f"actionability={row.get('actionability_score','')} | rr={row.get('real_reward_risk_ratio','')} | "
            f"exit_profile={row.get('exit_profile_status','')}"
        )
    (output_dir / "long_term_second_pass.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return rows


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--report-root", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    args = p.parse_args(argv)
    report = find_latest_report(args.report_root)
    rows = write_report(report, args.output_dir)
    print(f"long_term_second_pass={args.output_dir};count={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
