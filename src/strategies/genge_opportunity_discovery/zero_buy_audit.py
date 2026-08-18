"""Audit zero-Formal-BUY outcomes so the production funnel cannot silently collapse.

This module never manufactures a BUY.  It distinguishes a legitimate defensive
zero (for example a RED market regime) from a zero that requires a second-pass
review of near-ready and soft-blocked candidates.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

ALLOWED_ZERO_MARKET_STATES = {"RED", "CRISIS", "RISK_OFF", "EXTREME_RISK"}
SOFT_BLOCKER_TOKENS = {
    "exit_profile",
    "trend_unconfirmed",
    "condition_watch",
    "entry_trigger",
    "entry_pending",
    "breakout_confirmation",
    "state_continuity",
    "history_coverage",
    "profile_sample",
}


def _read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def find_latest_report(root: Path) -> Path:
    if (root / "run_summary.json").exists():
        return root
    candidates = sorted(
        {path.parent for path in root.glob("**/run_summary.json") if path.is_file()},
        key=str,
    )
    if not candidates:
        raise FileNotFoundError(f"no run_summary.json under {root}")
    return candidates[-1]


def _formal_buy_rows(report_dir: Path) -> list[dict[str, Any]]:
    for name in ("buy_ready.csv", "formal_buy_candidates.csv", "top5_candidates.csv"):
        rows = _read_csv(report_dir / name)
        if not rows:
            continue
        if name == "buy_ready.csv":
            return rows
        filtered = [
            row for row in rows
            if str(row.get("formal_buy_eligible") or row.get("formal_signal_eligible") or "").lower()
            in {"true", "1", "yes"}
            or str(row.get("classification") or "").upper() == "BUY_READY"
            or str(row.get("user_visible_level") or "").upper() == "STRICT_REVIEW_READY"
        ]
        if filtered:
            return filtered
    return []


def _candidate_rows(report_dir: Path) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for name in (
        "near_ready.csv",
        "deep_watch.csv",
        "top30_deep_review.csv",
        "top80_evidence_queue.csv",
        "all_a_quant_screen.csv",
    ):
        for row in _read_csv(report_dir / name):
            code = str(row.get("code") or "").strip()
            if not code or code in seen:
                continue
            result.append(row)
            seen.add(code)
    return result


def _blocker_text(row: Mapping[str, Any]) -> str:
    values = [
        row.get("strict_gate_failed"),
        row.get("missing_conditions"),
        row.get("classification_missing_conditions"),
        row.get("hard_blockers"),
        row.get("hard_reject_blockers"),
        row.get("exit_profile_blocker_detail"),
    ]
    return ";".join(str(value or "") for value in values if str(value or "").strip())


def _soft_only(row: Mapping[str, Any]) -> bool:
    hard = str(row.get("hard_blockers") or row.get("hard_reject_blockers") or "").strip()
    if hard:
        return False
    text = _blocker_text(row).lower()
    return bool(text) and any(token in text for token in SOFT_BLOCKER_TOKENS)


def audit_zero_buy(report_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    summary = _read_json(report_dir / "run_summary.json")
    formal = _formal_buy_rows(report_dir)
    market = str(summary.get("market_regime_status") or "UNKNOWN").upper()
    candidates = _candidate_rows(report_dir)
    soft_only = [row for row in candidates if _soft_only(row)]

    if formal:
        status = "FORMAL_BUY_PRESENT"
        requires_second_pass = False
    elif market in ALLOWED_ZERO_MARKET_STATES:
        status = "ZERO_BUY_DEFENSIVE_MARKET_ALLOWED"
        requires_second_pass = False
    else:
        status = "ZERO_BUY_REQUIRES_SECOND_PASS"
        requires_second_pass = True

    blocker_counter: Counter[str] = Counter()
    for row in candidates[:200]:
        text = _blocker_text(row)
        for token in (piece.strip() for piece in text.split(";") if piece.strip()):
            blocker_counter[token] += 1

    audit = {
        "status": status,
        "market_regime_status": market,
        "formal_buy_count": len(formal),
        "candidate_count_examined": len(candidates),
        "soft_only_candidate_count": len(soft_only),
        "requires_second_pass": requires_second_pass,
        "zero_buy_allowed": not requires_second_pass,
        "top_blockers": blocker_counter.most_common(20),
        "invariant": (
            "zero Formal BUY must not be silently accepted outside an explicitly defensive market; "
            "run a second-pass review without bypassing hard safety gates"
        ),
        "no_auto_trade": True,
    }
    return audit, soft_only[:30]


def write_audit(report_dir: Path, output_dir: Path) -> dict[str, Any]:
    audit, second_pass = audit_zero_buy(report_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "zero_buy_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    fields = [
        "code", "stock_name", "industry", "classification", "user_visible_level",
        "quant_score", "missing_conditions", "strict_gate_failed",
        "exit_profile_blocker_detail", "hard_blockers",
    ]
    with (output_dir / "zero_buy_second_pass_candidates.csv").open(
        "w", encoding="utf-8", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(second_pass)

    lines = [
        "# Zero Formal BUY Audit",
        "",
        f"- status: {audit['status']}",
        f"- market_regime_status: {audit['market_regime_status']}",
        f"- formal_buy_count: {audit['formal_buy_count']}",
        f"- second_pass_required: {audit['requires_second_pass']}",
        f"- soft_only_candidate_count: {audit['soft_only_candidate_count']}",
        "",
        "This audit never promotes a stock by itself and never bypasses hard safety gates.",
    ]
    (output_dir / "zero_buy_audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return audit


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--fail-on-unexplained-zero", action="store_true")
    args = parser.parse_args(argv)
    report_dir = find_latest_report(args.report_root)
    audit = write_audit(report_dir, args.output_dir)
    print(json.dumps(audit, ensure_ascii=False, indent=2))
    if args.fail_on_unexplained_zero and audit["requires_second_pass"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
