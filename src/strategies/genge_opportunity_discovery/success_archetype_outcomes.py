"""Observe forward outcomes of research-only success-archetype recall cohorts.

This module is learning/audit only. It never changes Formal/Canonical actions,
thresholds, sizing, or trading instructions. Missing prices remain pending.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Mapping

from src.strategies.genge_opportunity_discovery.formal_decision_outcomes import (
    load_daily_prices,
)

CONTRACT_VERSION = "GEN_GE_SUCCESS_ARCHETYPE_OUTCOMES_V3_LEGACY_ARTIFACT_COMPAT"
HORIZONS = (5, 20, 60)
MIN_HUMAN_REVIEW_SAMPLE = 20
LEGACY_RECALL_CONTRACTS_WITHOUT_COHORT_DATE = {
    "GEN_GE_SUCCESS_ARCHETYPE_RECALL_V1",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _code(value: Any) -> str:
    text = _text(value).upper()
    if "." in text:
        base, suffix = text.rsplit(".", 1)
        if suffix in {"SH", "SZ", "BJ"}:
            text = base
    for prefix in ("SH", "SZ", "BJ"):
        if text.startswith(prefix) and text[len(prefix):].isdigit():
            text = text[len(prefix):]
            break
    return text.zfill(6) if text.isdigit() else text


def _dec(value: Any) -> Decimal | None:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return number if number > 0 else None


def _similarity(value: Any) -> Decimal | None:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return number if number.is_finite() else None


def _bucket(value: Any) -> str:
    score = _similarity(value)
    if score is None:
        return "UNKNOWN"
    if score >= Decimal("80"):
        return "S80_PLUS"
    if score >= Decimal("70"):
        return "S70_79"
    if score >= Decimal("60"):
        return "S60_69"
    return "S52_59"


def load_history(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _record_id(
    *,
    archetype_id: str,
    source_terminal_run_id: str,
    cohort_date: str,
    code: str,
) -> str:
    raw = "|".join((archetype_id, source_terminal_run_id, cohort_date, code))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def _baseline(
    code: str,
    cohort_date: str,
    daily_prices: Mapping[str, Mapping[str, Decimal]],
) -> tuple[str, Decimal | None]:
    available = sorted(
        day for day in daily_prices.get(code, {}) if day <= cohort_date
    )
    if not available:
        return "", None
    day = available[-1]
    return day, daily_prices[code][day]


def _cohort_baseline(
    item: Mapping[str, Any],
    *,
    code: str,
    cohort_date: str,
    daily_prices: Mapping[str, Mapping[str, Decimal]],
) -> tuple[str, Decimal | None, str]:
    # The Terminal Review price is already known before recall is emitted and
    # is therefore the cleanest frozen cohort baseline. Using it prevents a
    # newly recalled security from becoming permanently unobservable merely
    # because it had not yet entered hourly_deep_overlay on the same day.
    source_price = _dec(item.get("source_price"))
    if source_price is not None and item.get("source_price_known_by_recall") is True:
        field = _text(item.get("source_price_field")) or "terminal_price"
        return cohort_date, source_price, f"SUCCESS_ARCHETYPE_{field.upper()}"
    baseline_date, baseline_price = _baseline(code, cohort_date, daily_prices)
    return baseline_date, baseline_price, (
        "HOURLY_DEEP_OVERLAY" if baseline_price is not None else "UNAVAILABLE"
    )


def validate_priority_payload(payload: Mapping[str, Any]) -> None:
    if payload.get("changes_research_order_only") is not True:
        raise ValueError("success-archetype payload must remain research-order only")
    if payload.get("changes_thresholds") is not False:
        raise ValueError("success-archetype payload cannot change thresholds")
    if payload.get("formal_action_eligible") is not False:
        raise ValueError("success-archetype payload cannot gain Formal authority")
    if payload.get("formal_action_recomputed") is not False:
        raise ValueError("success-archetype payload cannot recompute Formal actions")
    if payload.get("canonical_authority_unchanged") is not True:
        raise ValueError("Canonical authority must remain unchanged")
    if payload.get("automatic_promotion_allowed") is not False:
        raise ValueError("automatic promotion must remain disabled")
    if payload.get("starter_position_allowed") is not False:
        raise ValueError("starter position authority must remain disabled")
    if payload.get("no_auto_trade") is not True:
        raise ValueError("no_auto_trade must remain true")


def append_cohort(
    existing: Iterable[Mapping[str, Any]],
    priority_payload: Mapping[str, Any] | None,
    daily_prices: Mapping[str, Mapping[str, Decimal]],
) -> list[dict[str, Any]]:
    records = [dict(row) for row in existing if isinstance(row, Mapping)]
    if not priority_payload:
        return records
    validate_priority_payload(priority_payload)

    cohort_date = _text(priority_payload.get("as_of"))[:10]
    source_terminal_run_id = _text(
        priority_payload.get("source_terminal_run_id")
    )
    archetype_id = _text(priority_payload.get("archetype_id"))
    recall_contract = _text(priority_payload.get("contract_version"))
    if not cohort_date or not archetype_id:
        legacy_without_date = (
            recall_contract in LEGACY_RECALL_CONTRACTS_WITHOUT_COHORT_DATE
            and bool(archetype_id)
            and not cohort_date
        )
        if legacy_without_date:
            # V1 artifacts predate outcome observation and never persisted a
            # point-in-time cohort date. They remain valid research-priority
            # evidence, but inventing a cohort date would create hindsight
            # leakage. Preserve existing history and wait for a dated V2+
            # artifact instead of failing the whole Research Learning run.
            return records
        raise ValueError("archetype outcome cohort requires as_of and archetype_id")

    seen = {_text(row.get("record_id")) for row in records}
    for item in priority_payload.get("queue") or []:
        if not isinstance(item, Mapping):
            continue
        code = _code(item.get("code"))
        if not code:
            continue
        record_id = _record_id(
            archetype_id=archetype_id,
            source_terminal_run_id=source_terminal_run_id,
            cohort_date=cohort_date,
            code=code,
        )
        if record_id in seen:
            continue
        baseline_date, baseline_price, baseline_source = _cohort_baseline(
            item,
            code=code,
            cohort_date=cohort_date,
            daily_prices=daily_prices,
        )
        records.append(
            {
                "record_id": record_id,
                "archetype_id": archetype_id,
                "source_terminal_run_id": source_terminal_run_id,
                "cohort_date": cohort_date,
                "code": code,
                "name": item.get("name"),
                "similarity_score": item.get("similarity_score"),
                "similarity_bucket": _bucket(item.get("similarity_score")),
                "evidence_coverage": item.get("evidence_coverage"),
                "source_quant_status": item.get("source_quant_status"),
                "source_financial_review_status": item.get(
                    "source_financial_review_status"
                ),
                "financial_evidence_origin": item.get(
                    "financial_evidence_origin"
                ),
                "baseline_date": baseline_date,
                "baseline_price": (
                    str(baseline_price) if baseline_price is not None else None
                ),
                "baseline_source": baseline_source,
                "source_price_field": item.get("source_price_field"),
            }
        )
        seen.add(record_id)
    records.sort(
        key=lambda row: (
            _text(row.get("cohort_date")),
            _text(row.get("archetype_id")),
            _code(row.get("code")),
            _text(row.get("record_id")),
        )
    )
    return records


def _group_statistics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    buckets: dict[tuple[str, str], list[Decimal]] = defaultdict(list)
    quant_buckets: dict[tuple[str, str], list[Decimal]] = defaultdict(list)
    for row in rows:
        similarity_bucket = _text(row.get("similarity_bucket")) or "UNKNOWN"
        quant_status = _text(row.get("source_quant_status")) or "UNKNOWN"
        for horizon, value in (row.get("horizons") or {}).items():
            if not isinstance(value, Mapping) or value.get("status") != "OBSERVED":
                continue
            try:
                ret = Decimal(str(value.get("return")))
            except (InvalidOperation, ValueError, TypeError):
                continue
            buckets[(similarity_bucket, horizon)].append(ret)
            quant_buckets[(quant_status, horizon)].append(ret)

    def summarize(
        grouped: Mapping[tuple[str, str], list[Decimal]]
    ) -> tuple[dict[str, Any], int]:
        result: dict[str, Any] = {}
        ready = 0
        for (group, horizon), values in sorted(grouped.items()):
            sample_count = len(values)
            mean_value = sum(values, Decimal("0")) / Decimal(sample_count)
            median_value = Decimal(str(median(values)))
            positive = sum(value > 0 for value in values)
            status = (
                "READY_FOR_HUMAN_REVIEW"
                if sample_count >= MIN_HUMAN_REVIEW_SAMPLE
                else "INSUFFICIENT_SAMPLE"
            )
            if status == "READY_FOR_HUMAN_REVIEW":
                ready += 1
            result.setdefault(group, {})[horizon] = {
                "sample_count": sample_count,
                "mean_return": str(
                    mean_value.quantize(Decimal("0.000001"))
                ),
                "median_return": str(
                    median_value.quantize(Decimal("0.000001"))
                ),
                "positive_return_rate": str(
                    (
                        Decimal(positive) / Decimal(sample_count)
                    ).quantize(Decimal("0.000001"))
                ),
                "review_readiness": status,
                "minimum_sample_for_human_review": MIN_HUMAN_REVIEW_SAMPLE,
            }
        return result, ready

    by_similarity, ready_similarity = summarize(buckets)
    by_quant_status, ready_quant = summarize(quant_buckets)
    return {
        "by_similarity_bucket": by_similarity,
        "by_source_quant_status": by_quant_status,
        "ready_bucket_count": ready_similarity + ready_quant,
    }


def evaluate(
    records: Iterable[Mapping[str, Any]],
    daily_prices: Mapping[str, Mapping[str, Decimal]],
) -> dict[str, Any]:
    out: list[dict[str, Any]] = []
    for raw in records:
        row = dict(raw)
        code = _code(row.get("code"))
        baseline_date = _text(row.get("baseline_date"))[:10]
        entry = _dec(row.get("baseline_price"))
        dates = sorted(
            day
            for day in daily_prices.get(code, {})
            if baseline_date and day > baseline_date
        )
        horizons: dict[str, Any] = {}
        for horizon in HORIZONS:
            key = f"d{horizon}"
            if entry is None or not baseline_date or len(dates) < horizon:
                horizons[key] = {
                    "status": "PENDING",
                    "observed_trading_days": len(dates),
                }
                continue
            target_date = dates[horizon - 1]
            price = daily_prices[code][target_date]
            ret = price / entry - Decimal("1")
            horizons[key] = {
                "status": "OBSERVED",
                "target_date": target_date,
                "price": str(price),
                "return": str(ret.quantize(Decimal("0.000001"))),
            }
        row["code"] = code
        row["horizons"] = horizons
        out.append(row)

    grouped = _group_statistics(out)
    observed = sum(
        value.get("status") == "OBSERVED"
        for row in out
        for value in row["horizons"].values()
    )
    pending = sum(
        value.get("status") == "PENDING"
        for row in out
        for value in row["horizons"].values()
    )
    return {
        "contract_version": CONTRACT_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "horizons_trading_days": list(HORIZONS),
        "record_count": len(out),
        "observed_horizon_count": observed,
        "pending_horizon_count": pending,
        "group_statistics": {
            "by_similarity_bucket": grouped["by_similarity_bucket"],
            "by_source_quant_status": grouped["by_source_quant_status"],
        },
        "human_review_ready_bucket_count": grouped["ready_bucket_count"],
        "minimum_sample_for_human_review": MIN_HUMAN_REVIEW_SAMPLE,
        "human_parameter_review_allowed_when_sample_ready": True,
        "formal_action_recomputed": False,
        "formal_action_eligible": False,
        "parameter_tuning_allowed": False,
        "automatic_parameter_tuning_allowed": False,
        "changes_thresholds": False,
        "no_auto_trade": True,
        "records": out,
    }


def persist_history(path: Path, records: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps(dict(row), ensure_ascii=False, sort_keys=True)
        for row in records
    ]
    path.write_text(("\n".join(lines) + "\n") if lines else "", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--priority", type=Path)
    parser.add_argument(
        "--history",
        type=Path,
        default=Path("data/success_archetype_outcomes/history.jsonl"),
    )
    parser.add_argument(
        "--price-history-root",
        type=Path,
        default=Path("data/hourly_deep_overlay"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/success_archetype_outcomes/latest.json"),
    )
    args = parser.parse_args(argv)

    prices = load_daily_prices(args.price_history_root)
    priority = None
    if args.priority and args.priority.exists():
        priority = json.loads(args.priority.read_text(encoding="utf-8"))
    records = append_cohort(load_history(args.history), priority, prices)
    persist_history(args.history, records)
    payload = evaluate(records, prices)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "record_count": payload["record_count"],
                "observed_horizon_count": payload[
                    "observed_horizon_count"
                ],
                "pending_horizon_count": payload["pending_horizon_count"],
                "human_review_ready_bucket_count": payload[
                    "human_review_ready_bucket_count"
                ],
                "parameter_tuning_allowed": False,
                "formal_action_eligible": False,
                "no_auto_trade": True,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
