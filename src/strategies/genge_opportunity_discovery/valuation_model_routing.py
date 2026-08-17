"""Attach point-in-time valuation-model routing to the research queue.

This module deliberately does not change candidate ranking, Formal BUY, risk
limits, sizing, entry/exit logic or automatic trading.  It reads the existing
``valuation_research_queue.csv`` and writes an auditable routed sidecar that
answers a narrower question: which valuation/normalization strategy family is
appropriate for each company given information known by the report as-of date?

Company profiles are point-in-time and can expire.  When no eligible profile is
available, the existing conservative industry router may still provide a prior.
A profile's confidence caps a profile-driven route; stale/low-confidence/future
profiles cannot influence routing.

Specialized models are not silently treated as executed.  The output explicitly
distinguishes a generic reverse-earnings diagnostic that is already available
from a route that still requires specialized model inputs or cycle
normalization.  All output remains research-only.
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping

from src.strategies.genge_opportunity_discovery.valuation_company_profiles import (
    CompanyValuationProfileRepository,
    load_company_valuation_profile_repository,
)
from src.strategies.genge_opportunity_discovery.valuation_strategy_registry import (
    StrategyRole,
    route_valuation_strategies,
)


DISCLAIMER = "仅用于公开数据研究排序和人工复核，不构成买入或卖出建议，不应自动交易。"
DEFAULT_PROFILE_CONFIG = Path("config/valuation_company_profiles.yaml")
GENERAL_REVERSE_STRATEGY_ID = "general_reverse_earnings"

ROUTING_COLUMNS = [
    "valuation_profile_status",
    "valuation_profile_id",
    "valuation_profile_confidence",
    "valuation_profile_review_after",
    "valuation_profile_used_for_routing",
    "valuation_profile_business_tags",
    "valuation_profile_archetype_hints",
    "valuation_route_status",
    "valuation_route_archetypes",
    "valuation_strategy_ids",
    "valuation_primary_strategy_id",
    "valuation_alternative_strategy_ids",
    "valuation_disabled_strategy_ids",
    "valuation_routing_confidence",
    "valuation_route_reasons",
    "valuation_model_execution_state",
    "valuation_model_next_action",
]


def _normalize_code(value: Any) -> str:
    text = str(value or "").strip().upper()
    if "." in text:
        base, suffix = text.rsplit(".", 1)
        if suffix in {"SH", "SZ", "BJ"} and base.isdigit():
            text = base
    for prefix in ("SH", "SZ", "BJ"):
        if text.startswith(prefix) and text[len(prefix) :].isdigit():
            text = text[len(prefix) :]
            break
    return text.zfill(6) if text.isdigit() else text


def _join(values: Iterable[Any]) -> str:
    return ";".join(str(item) for item in values if str(item))


def _execution_state(
    *,
    primary_strategy_id: str,
    strategy_ids: tuple[str, ...],
    valuation_diagnostic_status: str,
    blocked: bool,
) -> tuple[str, str]:
    if blocked:
        return (
            "ROUTING_BLOCKED",
            "review_profile_disabled_strategies_before_valuation",
        )

    has_normalizer = any(
        strategy_id.endswith("_normalizer") for strategy_id in strategy_ids
    )
    if primary_strategy_id == GENERAL_REVERSE_STRATEGY_ID:
        if has_normalizer:
            return (
                "NORMALIZATION_REQUIRED_BEFORE_GENERIC_VALUATION",
                "run_selected_normalizer_then_reverse_earnings_review",
            )
        if valuation_diagnostic_status == "OK":
            return (
                "GENERIC_REVERSE_DIAGNOSTIC_READY",
                "review_reverse_earnings_expectation_gap",
            )
        return (
            "GENERIC_REVERSE_INPUTS_INCOMPLETE",
            "complete_generic_valuation_inputs_or_use_non_PE_review",
        )

    return (
        "SPECIALIZED_MODEL_SELECTED_INPUTS_REQUIRED",
        f"run_specialized_model:{primary_strategy_id}",
    )


def annotate_valuation_routes(
    rows: Iterable[Mapping[str, Any]],
    *,
    as_of: date,
    profile_repository: CompanyValuationProfileRepository,
) -> list[dict[str, Any]]:
    """Attach an auditable valuation route to each existing research row."""

    routed: list[dict[str, Any]] = []
    for raw in rows:
        row = dict(raw)
        code = _normalize_code(row.get("code"))
        row["code"] = code
        profile_resolution = profile_repository.resolve(code, as_of=as_of)
        profile = profile_resolution.profile
        profile_used = profile_resolution.routing_eligible and bool(
            profile_resolution.routing_business_tags
            or profile_resolution.routing_archetype_hints
        )

        decision = route_valuation_strategies(
            industry=row.get("industry"),
            business_tags=profile_resolution.routing_business_tags,
            archetype_hints=profile_resolution.routing_archetype_hints,
        )

        disabled = set(profile_resolution.routing_disabled_strategy_ids)
        kept_selections = tuple(
            selection
            for selection in decision.selections
            if selection.strategy_id not in disabled
        )
        strategy_ids = tuple(item.strategy_id for item in kept_selections)
        valuation_ids = tuple(
            item.strategy_id
            for item in kept_selections
            if item.role == StrategyRole.VALUATION
        )
        blocked = not valuation_ids
        primary = valuation_ids[0] if valuation_ids else ""
        alternatives = tuple(item for item in valuation_ids if item != primary)

        route_confidence = decision.routing_confidence
        if profile_used:
            route_confidence = min(
                route_confidence,
                profile_resolution.routing_confidence_cap,
            )
        if blocked:
            route_confidence = 0.0

        execution_state, next_action = _execution_state(
            primary_strategy_id=primary,
            strategy_ids=strategy_ids,
            valuation_diagnostic_status=str(
                row.get("valuation_diagnostic_status") or ""
            ),
            blocked=blocked,
        )

        route_status = (
            "PROFILE_DISABLED_ALL_VALUATION_STRATEGIES"
            if blocked
            else decision.status
        )
        reasons = list(decision.reasons)
        if profile_used:
            reasons.append("point_in_time_company_profile_applied")
        elif profile_resolution.status not in {"NOT_FOUND", "FOUND"}:
            reasons.append(
                f"company_profile_not_used:{profile_resolution.status.lower()}"
            )

        row.update(
            {
                "valuation_profile_status": profile_resolution.status,
                "valuation_profile_id": profile.profile_id if profile else "",
                "valuation_profile_confidence": (
                    profile.confidence if profile else ""
                ),
                "valuation_profile_review_after": (
                    profile.review_after.isoformat() if profile else ""
                ),
                "valuation_profile_used_for_routing": profile_used,
                "valuation_profile_business_tags": _join(
                    profile_resolution.routing_business_tags
                ),
                "valuation_profile_archetype_hints": _join(
                    profile_resolution.routing_archetype_hints
                ),
                "valuation_route_status": route_status,
                "valuation_route_archetypes": _join(
                    item.value for item in decision.archetypes
                ),
                "valuation_strategy_ids": _join(strategy_ids),
                "valuation_primary_strategy_id": primary,
                "valuation_alternative_strategy_ids": _join(alternatives),
                "valuation_disabled_strategy_ids": _join(sorted(disabled)),
                "valuation_routing_confidence": route_confidence,
                "valuation_route_reasons": _join(reasons),
                "valuation_model_execution_state": execution_state,
                "valuation_model_next_action": next_action,
                "formal_signal_eligible": False,
                "automatic_promotion_allowed": False,
                "no_auto_trade": True,
            }
        )
        routed.append(row)
    return routed


def _read_queue(path: Path) -> tuple[list[str], list[dict[str, Any]]]:
    if not path.exists():
        raise FileNotFoundError(f"valuation research queue not found: {path}")
    with path.open(encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        rows = list(reader)
        fields = list(reader.fieldnames or [])
    return fields, rows


def _read_as_of(report_dir: Path) -> date:
    summary_path = report_dir / "valuation_research_summary.json"
    if not summary_path.exists():
        raise FileNotFoundError(f"valuation research summary not found: {summary_path}")
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    text = str(payload.get("as_of_date") or "").strip()
    if not text:
        raise ValueError("valuation research as_of_date is unavailable")
    return date.fromisoformat(text)


def find_latest_routing_source(report_root: Path) -> Path:
    if (report_root / "valuation_research_queue.csv").exists():
        return report_root
    candidates = sorted(
        path.parent
        for path in report_root.glob("**/valuation_research_queue.csv")
        if path.is_file()
    )
    if not candidates:
        raise FileNotFoundError(
            f"no valuation research queue found under {report_root}"
        )
    return candidates[-1]


def write_routing_sidecar(
    report_dir: Path,
    *,
    profile_config: Path = DEFAULT_PROFILE_CONFIG,
) -> list[dict[str, Any]]:
    as_of = _read_as_of(report_dir)
    source_fields, source_rows = _read_queue(
        report_dir / "valuation_research_queue.csv"
    )
    repository = load_company_valuation_profile_repository(profile_config)
    rows = annotate_valuation_routes(
        source_rows,
        as_of=as_of,
        profile_repository=repository,
    )

    fields = list(source_fields)
    for field in ROUTING_COLUMNS:
        if field not in fields:
            fields.append(field)

    with (report_dir / "valuation_research_routed.csv").open(
        "w", encoding="utf-8", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in fields} for row in rows)

    lines = [
        "# Valuation Model Routing",
        "",
        DISCLAIMER,
        "",
        f"- as_of_date: {as_of.isoformat()}",
        f"- routed_count: {len(rows)}",
        "- ranking_changed: False",
        "- formal_signal_eligible: False",
        "",
    ]
    for row in rows[:30]:
        lines.extend(
            [
                f"## {row.get('valuation_research_rank')}. {row.get('code')} {row.get('stock_name')}",
                f"- route: {row.get('valuation_route_status')}",
                f"- strategies: {row.get('valuation_strategy_ids')}",
                f"- primary: {row.get('valuation_primary_strategy_id')}",
                f"- confidence: {row.get('valuation_routing_confidence')}",
                f"- execution: {row.get('valuation_model_execution_state')}",
                f"- next: {row.get('valuation_model_next_action')}",
                "",
            ]
        )
    (report_dir / "valuation_research_routed.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )

    summary = {
        "as_of_date": as_of.isoformat(),
        "routed_count": len(rows),
        "profile_routed_count": sum(
            bool(row.get("valuation_profile_used_for_routing")) for row in rows
        ),
        "specialized_route_count": sum(
            row.get("valuation_primary_strategy_id")
            not in {"", GENERAL_REVERSE_STRATEGY_ID}
            for row in rows
        ),
        "normalization_required_count": sum(
            row.get("valuation_model_execution_state")
            == "NORMALIZATION_REQUIRED_BEFORE_GENERIC_VALUATION"
            for row in rows
        ),
        "generic_ready_count": sum(
            row.get("valuation_model_execution_state")
            == "GENERIC_REVERSE_DIAGNOSTIC_READY"
            for row in rows
        ),
        "blocked_route_count": sum(
            row.get("valuation_model_execution_state") == "ROUTING_BLOCKED"
            for row in rows
        ),
        "ranking_changed": False,
        "formal_signal_eligible": False,
        "automatic_promotion_allowed": False,
        "no_auto_trade": True,
        "disclaimer": DISCLAIMER,
    }
    (report_dir / "valuation_routing_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--report-dir", type=Path)
    source.add_argument("--report-root", type=Path)
    parser.add_argument(
        "--profile-config",
        type=Path,
        default=DEFAULT_PROFILE_CONFIG,
    )
    args = parser.parse_args(argv)

    report_dir = args.report_dir or find_latest_routing_source(args.report_root)
    rows = write_routing_sidecar(
        report_dir,
        profile_config=args.profile_config,
    )
    print(f"valuation_model_routing={report_dir};count={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
