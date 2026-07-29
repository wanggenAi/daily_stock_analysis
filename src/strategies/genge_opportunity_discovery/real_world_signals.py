"""Deterministic market, industry, price-volume and event-risk signals.

The opportunity pipeline deliberately avoids using vendor-labelled "main fund
flow" as a buy/sell truth source. Every executed trade has both a buyer and a
seller; this module instead scores observable price/volume behaviour, market
breadth, index stress, industry participation and dated evidence.
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import date
from typing import Any, Iterable, Mapping

import pandas as pd

from src.strategies.genge_cycle_bottom.features import coerce_date, prepare_price_frame


CRITICAL_EVENT_TERMS = (
    "立案", "退市", "处罚", "违规", "审计非标", "债务违约", "逾期",
    "冻结", "安全事故", "停产", "业绩预亏", "大额减持", "控制权变更",
)
RESOLVED_EVENT_TERMS = (
    "解除冻结", "股份解冻", "终止减持", "减持完毕", "实施完毕", "撤销处罚",
    "撤回立案", "终止调查", "不存在逾期", "无逾期", "恢复生产", "复工复产",
    "风险消除", "不予处罚",
)


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _mean(values: Iterable[float | None]) -> float | None:
    clean = [value for value in values if value is not None and math.isfinite(value)]
    return None if not clean else sum(clean) / len(clean)


def _median(values: Iterable[float | None]) -> float | None:
    clean = pd.Series([value for value in values if value is not None], dtype="float64").dropna()
    return None if clean.empty else float(clean.median())


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def history_snapshot(history: pd.DataFrame, *, as_of: date) -> dict[str, Any]:
    """Return point-in-time daily features for one security or index."""

    frame = prepare_price_frame(history)
    frame = frame[frame["date"] <= as_of].copy().reset_index(drop=True)
    if len(frame) < 2:
        return {"available": False}
    latest = frame.iloc[-1]
    previous = frame.iloc[-2]
    close = _number(latest.get("close"))
    previous_close = _number(previous.get("close"))
    if close is None or previous_close in (None, 0.0):
        return {"available": False, "trade_date": coerce_date(latest.get("date")).isoformat()}
    open_price = _number(latest.get("open"))
    high = _number(latest.get("high"))
    low = _number(latest.get("low"))
    volume = _number(latest.get("volume"))
    amount = _number(latest.get("amount"))
    prior = frame.iloc[-21:-1]
    volume_values = prior["volume"] if "volume" in prior else pd.Series(dtype="float64")
    amount_values = prior["amount"] if "amount" in prior else pd.Series(dtype="float64")
    avg_volume = _mean(_number(value) for value in volume_values)
    avg_amount = _mean(_number(value) for value in amount_values)
    return_1d = None if close is None or not previous_close else (close / previous_close - 1.0) * 100.0
    return_5d = None
    if len(frame) >= 6:
        base = _number(frame.iloc[-6].get("close"))
        return_5d = None if close is None or not base else (close / base - 1.0) * 100.0
    ma20 = _mean(_number(value) for value in frame.tail(20)["close"])
    ma60 = _mean(_number(value) for value in frame.tail(60)["close"])
    close_location = None
    if close is not None and high is not None and low is not None and high > low:
        close_location = (close - low) / (high - low)
    return {
        "available": True,
        "trade_date": coerce_date(latest.get("date")).isoformat(),
        "return_1d_pct": None if return_1d is None else round(return_1d, 4),
        "return_5d_pct": None if return_5d is None else round(return_5d, 4),
        "gap_open_pct": None if open_price is None or not previous_close else round((open_price / previous_close - 1.0) * 100.0, 4),
        "volume_ratio_20": None if volume is None or not avg_volume else round(volume / avg_volume, 4),
        "amount_ratio_20": None if amount is None or not avg_amount else round(amount / avg_amount, 4),
        "close_location": None if close_location is None else round(close_location, 4),
        "above_ma20": bool(close is not None and ma20 is not None and close >= ma20),
        "above_ma60": bool(close is not None and ma60 is not None and close >= ma60),
    }


def price_volume_state(row: Mapping[str, Any]) -> dict[str, Any]:
    """Classify observable price/volume behaviour without inferring trade ownership."""

    daily_return = _number(row.get("return_1d_pct"))
    volume_ratio = _number(row.get("volume_ratio_20"))
    amount_ratio = _number(row.get("amount_ratio_20"))
    close_location = _number(row.get("close_location"))
    gap = _number(row.get("gap_open_pct"))
    activity = max(value for value in (volume_ratio, amount_ratio, 0.0) if value is not None)
    state = "NEUTRAL"
    score = 55.0
    reasons: list[str] = []
    if daily_return is not None and daily_return <= -4.5 and activity >= 1.5:
        state, score = "CAPITULATION_RISK", 10.0
        reasons.append("large_drop_on_expanding_activity")
    elif daily_return is not None and daily_return <= -2.0 and activity >= 1.2:
        state, score = "DISTRIBUTION", 20.0
        reasons.append("decline_on_expanding_activity")
    elif daily_return is not None and daily_return >= 2.0 and activity >= 1.2 and (close_location or 0.0) >= 0.65:
        state, score = "ACCUMULATION", 85.0
        reasons.append("advance_on_expanding_activity")
    elif daily_return is not None and daily_return < 0 and activity < 0.85:
        state, score = "WEAK_DEMAND", 40.0
        reasons.append("decline_with_thin_demand")
    if gap is not None and gap <= -4.0:
        score = min(score, 20.0)
        reasons.append("large_negative_gap")
    if close_location is not None and close_location <= 0.2 and activity >= 1.2:
        score = min(score, 25.0)
        reasons.append("closed_near_low_on_activity")
    return {
        "price_volume_state": state,
        "price_volume_score": round(score, 2),
        "price_volume_reasons": ";".join(reasons),
    }


def build_market_regime(
    rows: list[Mapping[str, Any]], *, index_histories: Mapping[str, pd.DataFrame], as_of: date,
    external_histories: Mapping[str, pd.DataFrame] | None = None,
    external_as_of: date | None = None,
) -> dict[str, Any]:
    """Score the effective A-share universe plus major-index and external stress."""

    valid_returns = [_number(row.get("return_1d_pct")) for row in rows]
    valid_returns = [value for value in valid_returns if value is not None]
    total = len(valid_returns)
    advance_ratio = 0.5 if not total else sum(value > 0 for value in valid_returns) / total
    decline_ratio = 0.5 if not total else sum(value < 0 for value in valid_returns) / total
    median_return = _median(valid_returns) or 0.0
    above_ma20_ratio = 0.0 if not rows else sum(bool(row.get("above_ma20")) for row in rows) / len(rows)
    above_ma60_ratio = 0.0 if not rows else sum(bool(row.get("above_ma60")) for row in rows) / len(rows)
    distribution_ratio = 0.0 if not rows else sum(
        str(row.get("price_volume_state")) in {"DISTRIBUTION", "CAPITULATION_RISK"} for row in rows
    ) / len(rows)
    limit_up_count = 0
    limit_down_count = 0
    for row in rows:
        daily_return = _number(row.get("return_1d_pct"))
        if daily_return is None:
            continue
        threshold = 19.0 if str(row.get("board")) in {"STAR", "CHINEXT"} else 9.5
        limit_up_count += daily_return >= threshold
        limit_down_count += daily_return <= -threshold

    index_rows: list[dict[str, Any]] = []
    for name, history in index_histories.items():
        snapshot = history_snapshot(history, as_of=as_of)
        current = bool(snapshot.get("available")) and snapshot.get("trade_date") == as_of.isoformat()
        index_rows.append({"name": name, **snapshot, "current_for_as_of": current})
    index_available_count = sum(bool(row.get("current_for_as_of")) for row in index_rows)
    index_returns = [_number(row.get("return_1d_pct")) for row in index_rows if row.get("current_for_as_of")]
    worst_index_return = min((value for value in index_returns if value is not None), default=0.0)
    average_index_return = _mean(index_returns) or 0.0

    external_rows: list[dict[str, Any]] = []
    external_context_date = external_as_of or as_of
    for name, history in (external_histories or {}).items():
        snapshot = history_snapshot(history, as_of=external_context_date)
        try:
            age_days = (external_context_date - coerce_date(snapshot.get("trade_date"))).days
        except Exception:
            age_days = None
        current = bool(snapshot.get("available")) and age_days is not None and 0 <= age_days <= 4
        external_rows.append({
            "name": name, **snapshot, "age_days": age_days,
            "current_for_context": current,
        })
    external_returns = [
        _number(row.get("return_1d_pct")) for row in external_rows if row.get("current_for_context")
    ]
    external_available_count = sum(bool(row.get("current_for_context")) for row in external_rows)
    worst_external_return = min((value for value in external_returns if value is not None), default=0.0)
    external_risk = (
        "UNKNOWN" if not any(value is not None for value in external_returns)
        else "HIGH" if worst_external_return <= -2.5
        else "MEDIUM" if worst_external_return <= -1.0
        else "LOW"
    )

    breadth_score = advance_ratio * 55.0 + above_ma20_ratio * 25.0 + above_ma60_ratio * 20.0
    return_score = _clamp(50.0 + median_return * 12.0)
    index_score = _clamp(55.0 + average_index_return * 12.0 + worst_index_return * 5.0)
    participation_score = _clamp(100.0 - distribution_ratio * 180.0)
    score = breadth_score * 0.35 + return_score * 0.20 + index_score * 0.30 + participation_score * 0.15
    if external_risk == "HIGH":
        score -= 8.0
    elif external_risk == "MEDIUM":
        score -= 3.0
    score = _clamp(score)
    reasons: list[str] = []
    if worst_index_return <= -5.0:
        reasons.append("major_index_crash")
    if advance_ratio < 0.30:
        reasons.append("weak_market_breadth")
    if median_return <= -1.5:
        reasons.append("negative_median_return")
    if distribution_ratio >= 0.25:
        reasons.append("broad_price_volume_distribution")
    if limit_down_count >= max(30, limit_up_count * 2):
        reasons.append("limit_down_imbalance")
    if external_risk in {"MEDIUM", "HIGH"}:
        reasons.append(f"external_market_risk_{external_risk.lower()}")
    if external_available_count < 2:
        reasons.append("external_market_data_partial")
    data_quality = "OK" if total >= 100 and index_available_count >= 3 else "PARTIAL"
    if data_quality != "OK":
        reasons.append("market_signal_data_partial")
    forced_red = index_available_count == 0 or worst_index_return <= -5.0 or (
        advance_ratio < 0.28 and median_return <= -1.5
    ) or limit_down_count >= max(60, limit_up_count * 3)
    if index_available_count == 0:
        reasons.append("major_index_data_unavailable")
    status = "RED" if forced_red or score < 35.0 else "YELLOW" if score < 58.0 else "GREEN"
    if status == "GREEN" and (
        data_quality != "OK"
        or external_risk in {"HIGH", "UNKNOWN"}
        or external_available_count < 2
    ):
        status = "YELLOW"
    return {
        "as_of_date": as_of.isoformat(),
        "status": status,
        "score": round(score, 2),
        "allow_new_buy": status != "RED",
        "position_multiplier": {"RED": 0.0, "YELLOW": 0.5, "GREEN": 1.0}[status],
        "effective_sample_count": total,
        "advance_count": sum(value > 0 for value in valid_returns),
        "decline_count": sum(value < 0 for value in valid_returns),
        "advance_ratio": round(advance_ratio, 4),
        "decline_ratio": round(decline_ratio, 4),
        "median_return_1d_pct": round(median_return, 4),
        "above_ma20_ratio": round(above_ma20_ratio, 4),
        "above_ma60_ratio": round(above_ma60_ratio, 4),
        "distribution_ratio": round(distribution_ratio, 4),
        "limit_up_count": limit_up_count,
        "limit_down_count": limit_down_count,
        "index_available_count": index_available_count,
        "average_index_return_1d_pct": round(average_index_return, 4),
        "worst_index_return_1d_pct": round(worst_index_return, 4),
        "external_context_date": external_context_date.isoformat(),
        "external_available_count": external_available_count,
        "external_data_quality": "OK" if external_available_count >= 2 else "PARTIAL",
        "external_risk_level": external_risk,
        "worst_external_return_1d_pct": round(worst_external_return, 4),
        "risk_reasons": reasons,
        "index_snapshots": index_rows,
        "external_snapshots": external_rows,
        "data_quality": data_quality,
    }


def build_industry_regimes(rows: list[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        industry = str(row.get("industry") or "").strip()
        if industry:
            grouped[industry].append(row)
    result: dict[str, dict[str, Any]] = {}
    for industry, members in grouped.items():
        returns = [_number(row.get("return_1d_pct")) for row in members]
        returns = [value for value in returns if value is not None]
        count = len(returns)
        advance_ratio = 0.5 if not count else sum(value > 0 for value in returns) / count
        median_return = _median(returns) or 0.0
        above_ma20 = sum(bool(row.get("above_ma20")) for row in members) / len(members)
        distribution = sum(
            str(row.get("price_volume_state")) in {"DISTRIBUTION", "CAPITULATION_RISK"}
            for row in members
        ) / len(members)
        score = (
            advance_ratio * 30.0
            + _clamp(50.0 + median_return * 12.0) * 0.25
            + above_ma20 * 25.0
            + _clamp(100.0 - distribution * 180.0) * 0.20
        )
        crisis = count >= 5 and (
            (advance_ratio < 0.25 and median_return <= -2.0) or distribution >= 0.35
        )
        status = "CRISIS" if crisis else "WEAK" if score < 45.0 else "STRONG" if score >= 62.0 else "NEUTRAL"
        result[industry] = {
            "industry": industry,
            "status": status,
            "score": round(_clamp(score), 2),
            "sample_count": count,
            "advance_ratio": round(advance_ratio, 4),
            "median_return_1d_pct": round(median_return, 4),
            "above_ma20_ratio": round(above_ma20, 4),
            "distribution_ratio": round(distribution, 4),
        }
    return result


def event_risk(
    evidence_rows: Iterable[Mapping[str, Any]], row: Mapping[str, Any], *, as_of: date,
    event_scan_rows: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Aggregate only recent, verified candidate-matching event evidence."""

    code = str(row.get("code") or "").strip()
    if code.endswith(".0"):
        code = code[:-2]
    code = code.zfill(6) if code.isdigit() else code
    industry = str(row.get("normalized_industry") or row.get("industry") or "").strip()
    scan_status = "UNKNOWN"
    scan_status_priority = {"UNKNOWN": 0, "OK": 1, "PARTIAL": 2, "FAILED": 3}
    for audit in event_scan_rows:
        audit_code = str(audit.get("code") or "").strip()
        if audit_code.endswith(".0"):
            audit_code = audit_code[:-2]
        audit_code = audit_code.zfill(6) if audit_code.isdigit() else audit_code
        collector = str(audit.get("collector") or "").strip().lower()
        if (
            not code
            or audit_code != code
            or not (collector == "official_material_event_scan" or collector.endswith("_material_event"))
        ):
            continue
        status = str(audit.get("status") or "").strip().upper()
        issue = str(audit.get("issue") or "").strip()
        if status == "OK" and issue != "material_event_scan_complete":
            continue
        if status in scan_status_priority and scan_status_priority[status] > scan_status_priority[scan_status]:
            scan_status = status

    material_by_type: dict[str, list[tuple[date, Mapping[str, Any]]]] = defaultdict(list)
    material_conflict_types: set[str] = set()
    legacy_critical_terms: set[str] = set()
    for evidence in evidence_rows:
        scope = str(evidence.get("scope") or "").strip().lower()
        evidence_code = str(evidence.get("code") or "").strip()
        if evidence_code.endswith(".0"):
            evidence_code = evidence_code[:-2]
        evidence_code = evidence_code.zfill(6) if evidence_code.isdigit() else evidence_code
        evidence_industry = str(evidence.get("industry") or "").strip()
        matches = (
            scope == "company" and bool(code) and evidence_code == code
        ) or (scope == "industry" and bool(industry) and evidence_industry == industry)
        if not matches:
            continue
        try:
            evidence_date = coerce_date(evidence.get("evidence_date") or evidence.get("date"))
        except Exception:
            continue
        freshness = (as_of - evidence_date).days
        if freshness < 0:
            continue
        evidence_kind = str(evidence.get("evidence_kind") or "").strip().lower()
        is_material_event = evidence_kind == "material_event"
        if freshness > (730 if is_material_event else 45):
            continue
        status = str(evidence.get("evidence_status") or "").strip().upper()
        if is_material_event:
            event_type = str(evidence.get("event_type") or "material_event").strip()
            if status == "CONFLICTING" or "conflicting_evidence" in str(evidence.get("warning_flags") or "").lower():
                material_conflict_types.add(event_type)
            if status in {"VERIFIED", "PARTIALLY_VERIFIED"}:
                material_by_type[event_type].append((evidence_date, evidence))
            continue
        # Ordinary financial or industry evidence belongs to the corresponding
        # fundamental/regime scores.  Only explicit, company-scoped legacy risk
        # evidence with a critical term participates in event risk.
        if (
            scope != "company"
            or evidence_kind not in {"risk_event", "material_risk", "critical_event"}
            or status not in {"VERIFIED", "PARTIALLY_VERIFIED"}
        ):
            continue
        direction = str(evidence.get("direction") or evidence.get("evidence_direction") or "").strip().upper()
        if direction != "NEGATIVE":
            continue
        content = " ".join(str(evidence.get(key) or "") for key in (
            "indicator", "title", "normalized_summary", "raw_excerpt",
        ))
        if any(term in content for term in RESOLVED_EVENT_TERMS):
            continue
        legacy_critical_terms.update(term for term in CRITICAL_EVENT_TERMS if term in content)

    negative_count = 0
    critical_count = 0
    reasons: list[str] = []
    for event_type, typed_rows in material_by_type.items():
        deduped: list[tuple[date, Mapping[str, Any]]] = []
        seen_within_type: set[str] = set()
        for evidence_date, evidence in sorted(typed_rows, key=lambda item: item[0]):
            dedup_key = str(evidence.get("content_hash") or "").strip() or "|".join((
                str(evidence.get("original_url") or evidence.get("source") or "").strip(),
                evidence_date.isoformat(), str(evidence.get("indicator") or "").strip(),
            ))
            if dedup_key in seen_within_type:
                continue
            seen_within_type.add(dedup_key)
            deduped.append((evidence_date, evidence))

        full_resolution_dates = [
            evidence_date for evidence_date, evidence in deduped
            if str(evidence.get("event_status") or "").strip().upper() == "RESOLVED"
            and str(evidence.get("event_resolution_scope") or "").strip().upper() == "FULL"
        ]
        last_full_resolution = max(full_resolution_dates) if full_resolution_dates else None
        active_rows: list[tuple[date, Mapping[str, Any]]] = []
        for evidence_date, evidence in deduped:
            if str(evidence.get("event_status") or "ACTIVE").strip().upper() != "ACTIVE":
                continue
            if last_full_resolution is not None and evidence_date <= last_full_resolution:
                continue
            valid_until = evidence.get("risk_valid_until")
            if valid_until:
                try:
                    if as_of > coerce_date(valid_until):
                        continue
                except Exception:
                    pass
            active_rows.append((evidence_date, evidence))
        if not active_rows:
            continue
        latest_active = max(active_rows, key=lambda item: item[0])[1]
        negative_count += 1
        if str(latest_active.get("event_severity") or "HIGH").strip().upper() == "HIGH":
            critical_count += 1
        reasons.append(event_type)

    for term in sorted(legacy_critical_terms):
        negative_count += 1
        critical_count += 1
        reasons.append(term)
    conflict_count = len(material_conflict_types)
    level = (
        "HIGH" if critical_count or negative_count >= 2
        else "MEDIUM" if negative_count or conflict_count
        else "LOW" if scan_status == "OK"
        else "UNKNOWN"
    )
    return {
        "event_risk_level": level,
        "event_scan_status": scan_status,
        "event_negative_evidence_count": negative_count,
        "event_critical_evidence_count": critical_count,
        "event_conflict_count": conflict_count,
        "event_risk_reasons": ";".join(dict.fromkeys(reasons)),
    }


def enrich_real_world_signals(
    row: Mapping[str, Any], *, market_regime: Mapping[str, Any],
    industry_regimes: Mapping[str, Mapping[str, Any]], evidence_rows: Iterable[Mapping[str, Any]],
    event_scan_rows: Iterable[Mapping[str, Any]] = (),
    as_of: date,
) -> dict[str, Any]:
    industry = str(
        row.get("industry_regime_key") or row.get("normalized_industry") or row.get("industry") or ""
    )
    industry_regime = dict(industry_regimes.get(industry) or {
        "status": "UNKNOWN", "score": 50.0, "sample_count": 0,
    })
    event = event_risk(evidence_rows, row, as_of=as_of, event_scan_rows=event_scan_rows)
    price_volume = price_volume_state(row)
    market_status = str(market_regime.get("status") or "UNKNOWN")
    industry_status = str(industry_regime.get("status") or "UNKNOWN")
    industry_sample_count = int(_number(industry_regime.get("sample_count")) or 0)
    event_level = str(event.get("event_risk_level") or "LOW")
    price_state = str(price_volume.get("price_volume_state") or "NEUTRAL")
    flags: list[str] = []
    if market_status == "RED":
        flags.append("market_regime_red")
    if industry_status == "CRISIS":
        flags.append("industry_regime_crisis")
    if industry_status == "UNKNOWN" or industry_sample_count < 5:
        flags.append("industry_regime_unavailable")
    if event_level == "HIGH":
        flags.append("critical_event_risk")
    if event_level == "UNKNOWN":
        flags.append("event_risk_unknown")
    if price_state in {"DISTRIBUTION", "CAPITULATION_RISK"}:
        flags.append(f"price_volume_{price_state.lower()}")
    market_score = _number(market_regime.get("score"))
    industry_score = _number(industry_regime.get("score"))
    price_score = _number(price_volume.get("price_volume_score"))
    market_score = 50.0 if market_score is None else market_score
    industry_score = 50.0 if industry_score is None else industry_score
    price_score = 50.0 if price_score is None else price_score
    event_score = {"LOW": 80.0, "MEDIUM": 50.0, "HIGH": 0.0, "UNKNOWN": 25.0}.get(event_level, 25.0)
    composite = market_score * 0.30 + industry_score * 0.30 + price_score * 0.25 + event_score * 0.15
    multiplier = _number(market_regime.get("position_multiplier"))
    return {
        "market_regime_status": market_status,
        "market_regime_score": round(market_score, 2),
        "market_position_multiplier": 1.0 if multiplier is None else multiplier,
        "external_risk_level": market_regime.get("external_risk_level") or "UNKNOWN",
        "industry_regime_status": industry_status,
        "industry_regime_score": round(industry_score, 2),
        "industry_regime_sample_count": industry_sample_count,
        **price_volume,
        **event,
        "real_world_score": round(_clamp(composite), 2),
        "real_world_gate_passed": not flags,
        "real_world_risk_flags": ";".join(flags),
    }
