"""Build an auditable Runbei + V3.1 multidimensional candidate comparison.

This is a research presentation layer.  It never creates Formal/Canonical BUY
authority and never turns missing evidence into PASS.  The input is the exact
``success_archetype_scored.csv`` produced by Success Archetype Recall, so the
five Runbei feature contributions that were previously buried in JSON strings
become explicit columns in the persisted comparison artifact.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping

CONTRACT_VERSION = "GEN_GE_RUNBEI_MULTIDIM_COMPARISON_V1"
AUTHORITY = "RESEARCH_ONLY"
DEFAULT_ARCHETYPE = Path("data/research_archetypes/runbei_v1.json")
DEFAULT_SCORECARD = Path("data/research_models/v31_multidim_scorecard.json")

_GATE_ALIASES: dict[str, tuple[str, ...]] = {
    "predictability": (
        "predictability_status",
        "predictability_gate_status",
        "gate_predictability_status",
    ),
    "financial_safety": (
        "financial_safety_status",
        "financial_safety_gate_status",
        "gate_financial_safety_status",
    ),
    "earnings_authenticity": (
        "earnings_authenticity_status",
        "earnings_authenticity_gate_status",
        "gate_earnings_authenticity_status",
    ),
    "long_term_demand": (
        "long_term_demand_status",
        "long_term_demand_gate_status",
        "gate_long_term_demand_status",
    ),
    "moat": (
        "moat_status",
        "moat_gate_status",
        "gate_moat_status",
    ),
}

_DIMENSION_ALIASES: dict[str, tuple[str, ...]] = {
    "long_term_demand": ("long_term_demand_score", "long_term_demand_points"),
    "moat_and_direction": ("moat_and_direction_score", "moat_direction_points"),
    "earnings_quality": ("earnings_quality_points", "earnings_quality_dimension_score"),
    "roic_incremental_roic": ("roic_incremental_roic_score", "roic_points"),
    "management_capital_allocation": (
        "management_capital_allocation_score",
        "capital_allocation_points",
    ),
    "growth_runway": ("growth_runway_score", "growth_space_points"),
    "normalized_earnings_certainty": (
        "normalized_earnings_certainty_score",
        "earnings_certainty_points",
    ),
    "market_expectation_gap": ("market_expectation_gap_score", "expectation_gap_points"),
    "valuation_margin_of_safety": (
        "valuation_margin_of_safety_score",
        "margin_of_safety_points",
    ),
    "market_position": ("market_position_score", "market_position_points"),
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _num(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _code(value: Any) -> str:
    text = _text(value).upper()
    if "." in text:
        base, suffix = text.rsplit(".", 1)
        if suffix in {"SH", "SZ", "BJ"}:
            text = base
    for prefix in ("SH", "SZ", "BJ"):
        if text.startswith(prefix) and text[len(prefix) :].isdigit():
            text = text[len(prefix) :]
            break
    return text.zfill(6) if text.isdigit() else text


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    text = _text(value)
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return dict(parsed) if isinstance(parsed, Mapping) else {}


def _tokens(value: Any) -> list[str]:
    return [x.strip() for x in _text(value).replace(",", ";").split(";") if x.strip()]


def _first(row: Mapping[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def validate_contracts(archetype: Mapping[str, Any], scorecard: Mapping[str, Any]) -> None:
    features = archetype.get("features") or []
    if not features or not archetype.get("archetype_id"):
        raise ValueError("invalid Runbei archetype")
    feature_weight = sum(float(item["weight"]) for item in features)
    if not math.isclose(feature_weight, 100.0, abs_tol=1e-6):
        raise ValueError(f"Runbei feature weights must sum to 100, got {feature_weight}")

    dimensions = scorecard.get("dimensions") or []
    dimension_weight = sum(float(item["weight"]) for item in dimensions)
    if not math.isclose(dimension_weight, 100.0, abs_tol=1e-6):
        raise ValueError(f"V3.1 dimension weights must sum to 100, got {dimension_weight}")
    rules = scorecard.get("rules") or {}
    if rules.get("unknown_is_pass") is not False:
        raise ValueError("scorecard must preserve UNKNOWN != PASS")
    if rules.get("similarity_can_create_formal_buy") is not False:
        raise ValueError("similarity must not create Formal BUY")
    if rules.get("no_auto_trade") is not True:
        raise ValueError("scorecard must preserve no-auto-trade")


def _gate_status(row: Mapping[str, Any], gate: str) -> str:
    explicit = _text(_first(row, _GATE_ALIASES.get(gate, ()))).upper()
    if explicit in {"PASS", "FAIL", "UNKNOWN"}:
        return explicit

    failures = {token.lower() for token in _tokens(row.get("v31_hard_gate_failures"))}
    if gate.lower() in failures or any(gate.lower() in token for token in failures):
        return "FAIL"

    # Absence of a failure marker is deliberately not interpreted as PASS.
    return "UNKNOWN"


def _dimension_points(
    row: Mapping[str, Any], dimension_id: str, weight: float
) -> tuple[float | None, str]:
    aggregate = _json_object(
        row.get("v31_multidim_scores_json") or row.get("multidim_scores_json")
    )
    if dimension_id in aggregate:
        value = _num(aggregate[dimension_id])
        if value is not None and 0.0 <= value <= weight:
            return value, "PERSISTED_JSON"
    value = _num(_first(row, _DIMENSION_ALIASES.get(dimension_id, ())))
    if value is not None and 0.0 <= value <= weight:
        return value, "PERSISTED_COLUMN"
    return None, "UNKNOWN_NOT_PERSISTED"


def _feature_detail(
    row: Mapping[str, Any], feature: Mapping[str, Any]
) -> dict[str, Any]:
    feature_id = str(feature["id"])
    scores = _json_object(row.get("success_archetype_feature_scores_json"))
    sources = _json_object(row.get("success_archetype_feature_sources_json"))
    source_field = _text(sources.get(feature_id))
    raw_value = _num(row.get(source_field)) if source_field else None
    if raw_value is None:
        aliases = [str(x) for x in (feature.get("aliases") or [feature_id])]
        source_field = next((key for key in aliases if row.get(key) not in (None, "")), "")
        raw_value = _num(row.get(source_field)) if source_field else None
    points = _num(scores.get(feature_id))
    return {
        "id": feature_id,
        "weight": float(feature["weight"]),
        "mode": _text(feature.get("mode") or "proximity"),
        "reference_value": _num(feature.get("reference_value")),
        "tolerance": _num(feature.get("tolerance")),
        "source_field": source_field,
        "raw_value": raw_value,
        "points": points,
        "status": "OBSERVED" if points is not None and raw_value is not None else "UNKNOWN_NOT_PERSISTED",
    }


def _comparison_row(
    row: Mapping[str, Any],
    *,
    archetype: Mapping[str, Any],
    scorecard: Mapping[str, Any],
) -> dict[str, Any]:
    feature_details = [_feature_detail(row, feature) for feature in archetype["features"]]
    feature_map = {item["id"]: item for item in feature_details}

    gate_ids = list(dict.fromkeys([
        *(scorecard.get("hard_gates") or []),
        "long_term_demand",
        "moat",
    ]))
    gates = {gate: _gate_status(row, str(gate)) for gate in gate_ids}
    hard_gate_failed = any(status == "FAIL" for status in gates.values())
    hard_gate_unknown = any(status == "UNKNOWN" for status in gates.values())

    dimensions: list[dict[str, Any]] = []
    for dimension in scorecard.get("dimensions") or []:
        dimension_id = str(dimension["id"])
        weight = float(dimension["weight"])
        points, provenance = _dimension_points(row, dimension_id, weight)
        dimensions.append(
            {
                "id": dimension_id,
                "label": _text(dimension.get("label") or dimension_id),
                "weight": weight,
                "points": points,
                "provenance": provenance,
            }
        )
    multidim_complete = bool(dimensions) and all(item["points"] is not None for item in dimensions)
    multidim_score = (
        round(sum(float(item["points"]) for item in dimensions), 4)
        if multidim_complete
        else None
    )

    similarity = _num(row.get("success_archetype_similarity_score"))
    coverage = _num(row.get("success_archetype_evidence_coverage"))
    return {
        "code": _code(row.get("code")),
        "name": _text(row.get("stock_name") or row.get("name")),
        "industry": _text(row.get("industry") or row.get("industry_name")),
        "is_reference": _code(row.get("code"))
        == _code((archetype.get("reference") or {}).get("code")),
        "runbei_archetype_id": _text(archetype.get("archetype_id")),
        "runbei_state": _text(row.get("success_archetype_state") or "NONE"),
        "runbei_similarity_score": similarity,
        "runbei_evidence_coverage": coverage,
        "runbei_missing_features": _tokens(row.get("success_archetype_missing_features")),
        "runbei_features": feature_details,
        "runbei_feature_points": {
            key: feature_map[key]["points"] for key in feature_map
        },
        "runbei_feature_raw_values": {
            key: feature_map[key]["raw_value"] for key in feature_map
        },
        "hard_gates": gates,
        "hard_gate_failed": hard_gate_failed,
        "hard_gate_unknown": hard_gate_unknown,
        "v31_dimensions": dimensions,
        "v31_multidim_score": multidim_score,
        "v31_multidim_complete": multidim_complete,
        "quant_status": _text(row.get("quant_status")),
        "quant_rank": _num(row.get("quant_rank")),
        "quant_score": _num(row.get("quant_score")),
        "financial_review_status": _text(row.get("financial_review_status")),
        "terminal_decision": _text(row.get("terminal_decision")),
        "terminal_reason_class": _text(row.get("terminal_reason_class")),
        "current_price": _num(row.get("terminal_current_price") or row.get("current_price")),
        "wait_price_max": _num(row.get("wait_price_max")),
        "neutral_value": _num(row.get("neutral_value")),
        "valuation_confidence": _text(row.get("valuation_confidence")),
        "formal_action_eligible": False,
        "formal_action_recomputed": False,
        "similarity_changes_research_order_only": True,
        "unknown_is_pass": False,
        "no_auto_trade": True,
    }


def build_comparison(
    rows: Iterable[Mapping[str, Any]],
    *,
    archetype: Mapping[str, Any],
    scorecard: Mapping[str, Any],
    source_recall_run_id: str = "",
) -> dict[str, Any]:
    validate_contracts(archetype, scorecard)
    output_rows = [
        _comparison_row(row, archetype=archetype, scorecard=scorecard) for row in rows
    ]
    output_rows.sort(
        key=lambda item: (
            item["is_reference"],
            item["runbei_state"] != "ARCHETYPE_MATCH",
            item["hard_gate_failed"],
            -(item["runbei_similarity_score"] or 0.0),
            -(item["runbei_evidence_coverage"] or 0.0),
            item["code"],
        )
    )
    for index, item in enumerate(output_rows, start=1):
        item["comparison_rank"] = index

    return {
        "contract_version": CONTRACT_VERSION,
        "authority": AUTHORITY,
        "source_recall_run_id": _text(source_recall_run_id),
        "archetype_id": archetype["archetype_id"],
        "reference_code": _code((archetype.get("reference") or {}).get("code")),
        "row_count": len(output_rows),
        "matched_count": sum(row["runbei_state"] == "ARCHETYPE_MATCH" for row in output_rows),
        "feature_schema": [
            {
                "id": feature["id"],
                "weight": float(feature["weight"]),
                "mode": feature.get("mode") or "proximity",
                "reference_value": feature.get("reference_value"),
                "tolerance": feature.get("tolerance"),
            }
            for feature in archetype["features"]
        ],
        "v31_scorecard": scorecard,
        "rows": output_rows,
        "ranking_rule": (
            "comparison_rank is an audit/display ordering only: non-reference archetype matches first, "
            "then no confirmed hard-gate failure, Runbei similarity, evidence coverage, code. "
            "It does not create BUY or Formal authority."
        ),
        "formal_action_eligible": False,
        "formal_action_recomputed": False,
        "unknown_is_pass": False,
        "no_auto_trade": True,
    }


def _fmt(value: Any, digits: int = 2) -> str:
    number = _num(value)
    return "—" if number is None else f"{number:.{digits}f}"


def render_markdown(payload: Mapping[str, Any]) -> str:
    feature_schema = payload.get("feature_schema") or []
    headers = [
        "Rank",
        "代码",
        "股票",
        "润贝相似度",
        "覆盖率",
        *[str(item["id"]) for item in feature_schema],
        "Hard Gate",
        "100分多维",
        "Terminal",
        "现价",
        "等待价上限",
        "中性价值",
    ]
    lines = [
        "# Runbei + V3.1 多维候选比较",
        "",
        "> 这是研究比较矩阵，不是 Formal BUY 清单。相似度高只代表更像成功原型；Hard Gate、基本面多维评分、估值与价格仍需独立通过。",
        "",
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in payload.get("rows") or []:
        feature_points = row.get("runbei_feature_points") or {}
        gate_values = list((row.get("hard_gates") or {}).values())
        if "FAIL" in gate_values:
            gate = "FAIL"
        elif gate_values and all(value == "PASS" for value in gate_values):
            gate = "PASS"
        else:
            gate = "UNKNOWN"
        multidim = _fmt(row.get("v31_multidim_score")) if row.get("v31_multidim_complete") else "UNKNOWN"
        values = [
            str(row.get("comparison_rank") or ""),
            str(row.get("code") or ""),
            str(row.get("name") or ""),
            _fmt(row.get("runbei_similarity_score")),
            _fmt((row.get("runbei_evidence_coverage") or 0) * 100) + "%",
            *[_fmt(feature_points.get(str(item["id"]))) for item in feature_schema],
            gate,
            multidim,
            str(row.get("terminal_decision") or "—"),
            _fmt(row.get("current_price")),
            _fmt(row.get("wait_price_max")),
            _fmt(row.get("neutral_value")),
        ]
        lines.append("| " + " | ".join(values) + " |")
    lines.extend(
        [
            "",
            "## 解释规则",
            "",
            "- Runbei 五项分数来自同一次 Success Archetype Recall 的逐项打分，不再只保留总相似度。",
            "- V3.1 100分多维评分只在上游真实持久化全部十个维度时计算；缺列保持 UNKNOWN，不补造分数。",
            "- Hard Gate 缺证据保持 UNKNOWN；UNKNOWN != PASS。",
            "- similarity / comparison_rank 只改变研究顺序，不产生 Formal BUY，也不自动交易。",
            "",
        ]
    )
    return "\n".join(lines)


def _flatten_csv_row(row: Mapping[str, Any], feature_ids: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "comparison_rank": row.get("comparison_rank"),
        "code": row.get("code"),
        "name": row.get("name"),
        "industry": row.get("industry"),
        "runbei_state": row.get("runbei_state"),
        "runbei_similarity_score": row.get("runbei_similarity_score"),
        "runbei_evidence_coverage": row.get("runbei_evidence_coverage"),
        "hard_gate_failed": row.get("hard_gate_failed"),
        "hard_gate_unknown": row.get("hard_gate_unknown"),
        "v31_multidim_score": row.get("v31_multidim_score"),
        "v31_multidim_complete": row.get("v31_multidim_complete"),
        "quant_status": row.get("quant_status"),
        "quant_rank": row.get("quant_rank"),
        "quant_score": row.get("quant_score"),
        "financial_review_status": row.get("financial_review_status"),
        "terminal_decision": row.get("terminal_decision"),
        "current_price": row.get("current_price"),
        "wait_price_max": row.get("wait_price_max"),
        "neutral_value": row.get("neutral_value"),
        "valuation_confidence": row.get("valuation_confidence"),
        "formal_action_eligible": False,
        "unknown_is_pass": False,
        "no_auto_trade": True,
    }
    points = row.get("runbei_feature_points") or {}
    raw = row.get("runbei_feature_raw_values") or {}
    for feature_id in feature_ids:
        out[f"runbei_{feature_id}_raw"] = raw.get(feature_id)
        out[f"runbei_{feature_id}_points"] = points.get(feature_id)
    for gate, status in (row.get("hard_gates") or {}).items():
        out[f"gate_{gate}"] = status
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scored-csv", type=Path, required=True)
    parser.add_argument("--archetype", type=Path, default=DEFAULT_ARCHETYPE)
    parser.add_argument("--scorecard", type=Path, default=DEFAULT_SCORECARD)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-recall-run-id", default="")
    args = parser.parse_args(argv)

    archetype = _load_json(args.archetype)
    scorecard = _load_json(args.scorecard)
    with args.scored_csv.open(encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError("success_archetype_scored.csv is empty")

    payload = build_comparison(
        rows,
        archetype=archetype,
        scorecard=scorecard,
        source_recall_run_id=args.source_recall_run_id,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "runbei_multidim_comparison.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (args.output_dir / "runbei_multidim_comparison.md").write_text(
        render_markdown(payload), encoding="utf-8"
    )

    feature_ids = [str(item["id"]) for item in payload["feature_schema"]]
    flat_rows = [_flatten_csv_row(row, feature_ids) for row in payload["rows"]]
    fields = list(dict.fromkeys(key for row in flat_rows for key in row.keys()))
    with (args.output_dir / "runbei_multidim_comparison.csv").open(
        "w", encoding="utf-8", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(flat_rows)

    print(
        json.dumps(
            {
                "row_count": payload["row_count"],
                "matched_count": payload["matched_count"],
                "archetype_id": payload["archetype_id"],
                "formal_action_eligible": False,
                "unknown_is_pass": False,
                "no_auto_trade": True,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
