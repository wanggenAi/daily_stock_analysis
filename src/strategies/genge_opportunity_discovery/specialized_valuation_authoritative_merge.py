"""Merge specialized valuation sidecars back into the authoritative research CSV.

Each executor is intentionally research-only and fail-closed.  This bridge makes
its evidence/model/anchor/completion facts visible to downstream V3.1 review,
Canonical snapshots and holding/candidate lifecycle without changing ranking or
Formal decision thresholds.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Mapping

SIDE_CARS = (
    ("valuation_research_specialized.csv", ("specialized_",)),
    ("bank_valuation_execution.csv", ("bank_",)),
    (
        "insurance_valuation_execution.csv",
        (
            "insurance_",
            "valuation_evidence_status",
            "valuation_model_status",
            "valuation_anchor_status",
            "valuation_completion_status",
            "valuation_reference_anchor_",
        ),
    ),
    ("valuation_research_resource_nav.csv", ("resource_nav_",)),
)


def _code(value: Any) -> str:
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


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def _present(value: Any) -> bool:
    return str(value or "").strip() not in {"", "none", "nan", "null"}


def _read(path: Path) -> tuple[list[str], list[dict[str, Any]]]:
    with path.open(encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        return list(reader.fieldnames or []), list(reader)


def _merge_allowed(target: dict[str, Any], source: Mapping[str, Any], prefixes: tuple[str, ...]) -> None:
    for key, value in source.items():
        if key in {"code", "stock_name"}:
            continue
        if any(key == prefix or key.startswith(prefix) for prefix in prefixes):
            target[key] = value


def _normalize_completion(row: dict[str, Any]) -> None:
    strategy = str(row.get("valuation_primary_strategy_id") or "").strip()
    evidence = "NOT_APPLICABLE"
    model = "NOT_APPLICABLE"
    anchor = "NOT_APPLICABLE"
    completion = "NOT_APPLICABLE"
    followup = ""

    if strategy == "insurance_embedded_value":
        evidence = str(row.get("valuation_evidence_status") or "INVALID")
        model = str(row.get("valuation_model_status") or "NOT_EXECUTED")
        anchor = str(row.get("valuation_anchor_status") or "UNAVAILABLE")
        completion = str(row.get("valuation_completion_status") or "UNFINISHED")
        if completion == "UNFINISHED":
            followup = "VALUATION_STRATEGY_UNFINISHED"
        elif completion == "COMPLETED_NO_ANCHOR":
            followup = "VALUATION_STRATEGY_COMPLETED_NO_ANCHOR"
    elif strategy == "resource_asset_nav":
        status = str(row.get("resource_nav_status") or "")
        executed = _truthy(row.get("resource_nav_executed"))
        has_anchor = _present(row.get("resource_nav_base_per_share")) or _present(row.get("resource_nav_base_value"))
        evidence = "VALID" if executed else ("STALE" if status == "RESOURCE_INPUT_STALE" else "MISSING")
        model = "EXECUTED" if executed else "NOT_EXECUTED"
        anchor = "REFERENCE_AVAILABLE" if has_anchor else "UNAVAILABLE"
        completion = (
            "COMPLETED_WITH_REFERENCE_ANCHOR" if executed and has_anchor
            else "COMPLETED_NO_ANCHOR" if executed
            else "UNFINISHED"
        )
        followup = (
            "VALUATION_STRATEGY_UNFINISHED" if completion == "UNFINISHED"
            else "VALUATION_STRATEGY_COMPLETED_NO_ANCHOR" if completion == "COMPLETED_NO_ANCHOR"
            else ""
        )
    elif strategy == "bank_book_value":
        executed = _truthy(row.get("bank_model_executed"))
        has_anchor = _present(row.get("bank_fair_pb"))
        evidence = "VALID" if executed else "INCOMPLETE"
        model = "EXECUTED" if executed else "NOT_EXECUTED"
        anchor = "REFERENCE_AVAILABLE" if has_anchor else "UNAVAILABLE"
        completion = (
            "COMPLETED_WITH_REFERENCE_ANCHOR" if executed and has_anchor
            else "COMPLETED_NO_ANCHOR" if executed
            else "UNFINISHED"
        )
        followup = (
            "VALUATION_STRATEGY_UNFINISHED" if completion == "UNFINISHED"
            else "VALUATION_STRATEGY_COMPLETED_NO_ANCHOR" if completion == "COMPLETED_NO_ANCHOR"
            else ""
        )
    elif strategy == "capital_markets_cycle":
        executed = _truthy(row.get("specialized_model_executed"))
        has_anchor = _present(row.get("specialized_fair_pb"))
        evidence = "VALID" if executed else "INCOMPLETE"
        model = "EXECUTED" if executed else "NOT_EXECUTED"
        anchor = "REFERENCE_AVAILABLE" if has_anchor else "UNAVAILABLE"
        completion = (
            "COMPLETED_WITH_REFERENCE_ANCHOR" if executed and has_anchor
            else "COMPLETED_NO_ANCHOR" if executed
            else "UNFINISHED"
        )
        followup = (
            "VALUATION_STRATEGY_UNFINISHED" if completion == "UNFINISHED"
            else "VALUATION_STRATEGY_COMPLETED_NO_ANCHOR" if completion == "COMPLETED_NO_ANCHOR"
            else ""
        )

    row.update(
        {
            "valuation_strategy_evidence_status": evidence,
            "valuation_strategy_model_status": model,
            "valuation_strategy_anchor_status": anchor,
            "valuation_strategy_completion_status": completion,
            "valuation_strategy_followup_reason": followup,
            "valuation_strategy_merge_authoritative": True,
        }
    )


def merge_report(report_root: Path) -> dict[str, Any]:
    routed_candidates = sorted(
        {p.parent for p in report_root.glob("**/valuation_research_routed.csv") if p.is_file()},
        key=str,
    )
    if (report_root / "valuation_research_routed.csv").exists():
        report_dir = report_root
    elif routed_candidates:
        report_dir = routed_candidates[-1]
    else:
        raise FileNotFoundError(f"no valuation_research_routed.csv under {report_root}")

    routed_path = report_dir / "valuation_research_routed.csv"
    base_fields, base_rows = _read(routed_path)
    by_code = {_code(row.get("code")): row for row in base_rows if _code(row.get("code"))}
    sidecars_used: list[str] = []

    for filename, prefixes in SIDE_CARS:
        path = report_dir / filename
        if not path.exists():
            continue
        _, rows = _read(path)
        sidecars_used.append(filename)
        for source in rows:
            code = _code(source.get("code"))
            target = by_code.get(code)
            if target is not None:
                _merge_allowed(target, source, prefixes)

    for row in base_rows:
        _normalize_completion(row)
        row["formal_signal_eligible"] = False
        row["automatic_promotion_allowed"] = False
        row["no_auto_trade"] = True

    fields = list(base_fields)
    for row in base_rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with routed_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(base_rows)

    summary = {
        "row_count": len(base_rows),
        "sidecars_used": sidecars_used,
        "unfinished_count": sum(
            row.get("valuation_strategy_completion_status") == "UNFINISHED" for row in base_rows
        ),
        "completed_with_anchor_count": sum(
            row.get("valuation_strategy_completion_status") == "COMPLETED_WITH_REFERENCE_ANCHOR"
            for row in base_rows
        ),
        "completed_no_anchor_count": sum(
            row.get("valuation_strategy_completion_status") == "COMPLETED_NO_ANCHOR" for row in base_rows
        ),
        "formal_signal_eligible": False,
        "automatic_promotion_allowed": False,
        "no_auto_trade": True,
    }
    (report_dir / "specialized_valuation_authoritative_merge_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-root", type=Path, required=True)
    args = parser.parse_args(argv)
    merge_report(args.report_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
