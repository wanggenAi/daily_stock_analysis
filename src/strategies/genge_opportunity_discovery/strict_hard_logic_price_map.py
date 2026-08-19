"""Production adapter: strict Hard Logic Engine -> existing price valuation map.

The valuation machinery in ``hard_logic_price_map`` remains reusable, but its
legacy compatibility gate is intentionally replaced for this production path by
``hard_logic_engine.hard_logic_assessment``.  This prevents Quant ranking,
valuation readiness, or earnings quality alone from being promoted to HARD_LOGIC_PASS.

``hard_logic_research.csv`` is merged back into the researched-company rows so
that the final price map contains the *reason* a company passed, not merely a
PASS label.  The research sidecar cannot create an unrelated security here; a
company must already have entered the postscan/valuation research union.
"""
from __future__ import annotations

import argparse
import csv
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping

from . import hard_logic_price_map as price_map
from .hard_logic_engine import hard_logic_assessment


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


def _read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _hard_logic_sidecar_path(root: Path) -> Path | None:
    candidates = sorted(
        (path for path in root.glob("**/hard_logic_research.csv") if path.is_file()),
        key=str,
    )
    return candidates[-1] if candidates else None


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
            ):
                value = evidence.get(field)
                if value not in (None, ""):
                    row[field] = value
            row["hard_logic_research_summary"] = evidence.get("research_summary") or ""
            row["hard_logic_selection_origin"] = evidence.get("selection_origin") or ""
        merged.append(row)
    return merged


@contextmanager
def _strict_gate_installed(artifact_root: Path | None = None) -> Iterator[None]:
    original_gate = price_map.hard_logic_assessment
    original_loader = price_map.load_artifact_company_rows
    price_map.hard_logic_assessment = hard_logic_assessment

    if artifact_root is not None:
        research = _research_by_code(artifact_root)

        def strict_loader(root: Path) -> list[dict[str, Any]]:
            return _merge_research_into_company_rows(original_loader(root), research)

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


def _enrich_written_csv(output_dir: Path, research: Mapping[str, Mapping[str, Any]]) -> None:
    path = output_dir / "hard_logic_price_map.csv"
    rows = _read_csv(path)
    if not rows:
        return
    for row in rows:
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

    fields = list(rows[0].keys())
    for field in EVIDENCE_COLUMNS:
        if field not in fields:
            fields.append(field)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _append_evidence_markdown(output_dir: Path, research: Mapping[str, Mapping[str, Any]]) -> None:
    path = output_dir / "hard_logic_price_map.md"
    if not path.exists() or not research:
        return
    lines = ["", "## Structural hard-logic evidence", ""]
    for code, evidence in sorted(research.items()):
        state = str(evidence.get("hard_logic_state") or "REVIEW")
        name = str(evidence.get("selected_name") or "")
        industry = str(evidence.get("industry") or "")
        lines.extend(
            [
                f"### {code} {name} | {industry} | {state}",
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
    _enrich_written_csv(output_dir, research)
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
