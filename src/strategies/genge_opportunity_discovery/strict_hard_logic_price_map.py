"""Production adapter: strict Hard Logic Engine -> existing price valuation map.

The valuation machinery in ``hard_logic_price_map`` remains reusable, but its
legacy compatibility gate is intentionally replaced for this production path by
``hard_logic_engine.hard_logic_assessment``.  This prevents Quant ranking,
valuation readiness, or earnings quality alone from being promoted to HARD_LOGIC_PASS.

``hard_logic_research.csv`` is merged back into the researched-company rows so
that the final price map contains the *reason* a company passed, not merely a
PASS label.  The research sidecar cannot create an unrelated security here; a
company must already have entered the postscan/valuation research union.

Sector opportunity context is carried through for visibility only.  Sector
rank/strength never participates in the deterministic hard-logic gate and never
creates fair value or a buy decision.

Executed specialized valuation evidence is also consumed here.  Only an
auditable unit conversion supported by ``specialized_scenario_bridge`` may add a
specialized fair price.  Route selection, reverse-implied diagnostics, or
incomplete model inputs never create a target price.
"""
from __future__ import annotations

import argparse
import csv
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping

from . import hard_logic_price_map as price_map
from .hard_logic_engine import hard_logic_assessment
from .specialized_scenario_postscan import overlay_specialized_scenarios


SECTOR_CONTEXT_COLUMNS = [
    "sector_rank",
    "sector_opportunity_state",
    "sector_research_action",
    "sector_opportunity_score",
    "sector_advance_ratio",
    "sector_excess_return_1d_pct",
    "sector_excess_return_5d_pct",
    "sector_expanding_activity_ratio",
    "sector_overheated",
]
EVIDENCE_COLUMNS = [
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
    "hard_logic_research_summary",
    "hard_logic_selection_origin",
    *SECTOR_CONTEXT_COLUMNS,
]
SPECIALIZED_AUDIT_COLUMNS = [
    "specialized_scenario_bridge_status",
    "specialized_scenario_strategy_id",
    "specialized_scenario_basis",
]


def _normalize_code(value: Any) -> str:
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


def _read_csv(path: Path | None) -> list[dict[str, Any]]:
    if path is None or not path.exists():
        return []
    with path.open(encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _choose_path(root: Path, filename: str, preferred_token: str = "") -> Path | None:
    candidates = sorted(
        (path for path in root.glob(f"**/{filename}") if path.is_file()),
        key=str,
    )
    if not candidates:
        return None
    if preferred_token:
        preferred = [path for path in candidates if preferred_token in str(path)]
        if preferred:
            return preferred[-1]
    return candidates[-1]


def _hard_logic_sidecar_path(root: Path) -> Path | None:
    return _choose_path(root, "hard_logic_research.csv")


def _research_by_code(root: Path) -> dict[str, dict[str, Any]]:
    path = _hard_logic_sidecar_path(root)
    if path is None:
        return {}
    output: dict[str, dict[str, Any]] = {}
    for row in _read_csv(path):
        code = _normalize_code(row.get("selected_code") or row.get("code"))
        if not code:
            continue
        output[code] = row
    return output


def _merge_research_into_company_rows(
    rows: list[dict[str, Any]],
    research: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    for raw in rows:
        row = dict(raw)
        code = _normalize_code(row.get("code"))
        evidence = research.get(code)
        if evidence:
            # Research evidence is allowed to strengthen or downgrade the strict
            # gate, but never to overwrite security identity or market data.
            for field in (
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
                *SECTOR_CONTEXT_COLUMNS,
            ):
                value = evidence.get(field)
                if value not in (None, ""):
                    row[field] = value
            row["hard_logic_research_summary"] = evidence.get("research_summary") or ""
            row["hard_logic_selection_origin"] = evidence.get("selection_origin") or ""
        merged.append(row)
    return merged


def _merge_executed_specialized_scenarios(
    root: Path,
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    specialized_path = _choose_path(
        root,
        "valuation_research_specialized.csv",
        "valuation_research_queue",
    )
    raw_path = _choose_path(
        root,
        "raw_all_a_universe.csv",
        "hard_logic_valuation_source",
    )
    specialized = _read_csv(specialized_path)
    raw = _read_csv(raw_path)
    if not specialized or not raw:
        return rows
    merged, _stats = overlay_specialized_scenarios(rows, specialized, raw)
    return merged


@contextmanager
def _strict_gate_installed(artifact_root: Path | None = None) -> Iterator[None]:
    original_gate = price_map.hard_logic_assessment
    original_loader = price_map.load_artifact_company_rows
    price_map.hard_logic_assessment = hard_logic_assessment

    if artifact_root is not None:
        research = _research_by_code(artifact_root)

        def strict_loader(root: Path) -> list[dict[str, Any]]:
            rows = original_loader(root)
            rows = _merge_research_into_company_rows(rows, research)
            return _merge_executed_specialized_scenarios(root, rows)

        price_map.load_artifact_company_rows = strict_loader
    try:
        yield
    finally:
        price_map.hard_logic_assessment = original_gate
        price_map.load_artifact_company_rows = original_loader


def build_strict_price_expectation_rows(
    rows: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    with _strict_gate_installed():
        return price_map.build_price_expectation_rows(rows)


def _enrich_written_csv(
    output_dir: Path,
    research: Mapping[str, Mapping[str, Any]],
    *,
    artifact_root: Path,
) -> None:
    path = output_dir / "hard_logic_price_map.csv"
    rows = _read_csv(path)
    if not rows:
        return

    specialized_rows = _read_csv(
        _choose_path(
            artifact_root,
            "valuation_research_specialized.csv",
            "valuation_research_queue",
        )
    )
    specialized_by_code = {
        _normalize_code(row.get("code")): row
        for row in specialized_rows
        if _normalize_code(row.get("code"))
    }
    raw_rows = _read_csv(
        _choose_path(
            artifact_root,
            "raw_all_a_universe.csv",
            "hard_logic_valuation_source",
        )
    )
    # Re-run only the pure specialized bridge over the written price-map rows so
    # its audit status/basis is visible in the final CSV. Fair-value decisions
    # were already made with the same bridge inside the strict loader.
    audit_rows, _stats = overlay_specialized_scenarios(
        rows,
        list(specialized_by_code.values()),
        raw_rows,
    ) if specialized_by_code and raw_rows else (rows, {})

    for row in audit_rows:
        evidence = research.get(_normalize_code(row.get("code")))
        if not evidence:
            continue
        row["hard_logic_score"] = evidence.get("hard_logic_score") or ""
        row["hard_logic_missing_evidence"] = evidence.get("hard_logic_missing_evidence") or ""
        row["hard_logic_structural_driver"] = evidence.get("hard_logic_structural_driver") or ""
        row["hard_logic_supply_constraint"] = evidence.get("hard_logic_supply_constraint") or ""
        row["hard_logic_company_edge"] = evidence.get("hard_logic_company_edge") or ""
        row["hard_logic_profit_transmission"] = evidence.get("hard_logic_profit_transmission") or ""
        row["hard_logic_invalidation"] = evidence.get("hard_logic_invalidation") or ""
        row["hard_logic_duration_years"] = evidence.get("hard_logic_duration_years") or ""
        row["hard_logic_persistence"] = evidence.get("hard_logic_persistence") or ""
        row["hard_logic_evidence_sources"] = evidence.get("hard_logic_evidence_sources") or ""
        row["hard_logic_research_summary"] = evidence.get("research_summary") or ""
        row["hard_logic_selection_origin"] = evidence.get("selection_origin") or ""
        for field in SECTOR_CONTEXT_COLUMNS:
            row[field] = evidence.get(field) or ""

    fields = list(audit_rows[0].keys())
    for field in EVIDENCE_COLUMNS + SPECIALIZED_AUDIT_COLUMNS:
        if field not in fields:
            fields.append(field)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(audit_rows)


def _append_evidence_markdown(output_dir: Path, research: Mapping[str, Mapping[str, Any]]) -> None:
    path = output_dir / "hard_logic_price_map.md"
    if not path.exists() or not research:
        return
    lines = ["", "## Structural hard-logic evidence", ""]
    for code, evidence in sorted(research.items()):
        state = str(evidence.get("hard_logic_state") or "REVIEW")
        name = str(evidence.get("selected_name") or "")
        industry = str(evidence.get("industry") or "")
        sector_state = str(evidence.get("sector_opportunity_state") or "")
        sector_rank = str(evidence.get("sector_rank") or "")
        lines.extend(
            [
                f"### {code} {name} | {industry} | {state}",
                f"- sector context: rank={sector_rank or 'N/A'} | state={sector_state or 'N/A'} (discovery-only, not hard-logic evidence)",
                f"- structural driver: {evidence.get('hard_logic_structural_driver') or 'MISSING'}",
                f"- company edge: {evidence.get('hard_logic_company_edge') or 'MISSING'}",
                f"- profit transmission: {evidence.get('hard_logic_profit_transmission') or 'MISSING'}",
                f"- invalidation: {evidence.get('hard_logic_invalidation') or 'MISSING'}",
                f"- duration: {evidence.get('hard_logic_duration_years') or 'MISSING'} years",
                f"- evidence: {evidence.get('hard_logic_evidence_sources') or 'MISSING'}",
                "",
            ]
        )
    with path.open("a", encoding="utf-8") as stream:
        stream.write("\n".join(lines))


def write_price_map(artifact_root: Path, output_dir: Path) -> list[dict[str, Any]]:
    research = _research_by_code(artifact_root)
    with _strict_gate_installed(artifact_root):
        rows = price_map.write_price_map(artifact_root, output_dir)
    _enrich_written_csv(
        output_dir,
        research,
        artifact_root=artifact_root,
    )
    _append_evidence_markdown(output_dir, research)
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    rows = write_price_map(args.artifact_root, args.output_dir)
    print(f"strict_hard_logic_price_map={args.output_dir};count={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
