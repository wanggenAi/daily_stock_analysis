from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any, Iterable, Mapping

from .models import Candidate


CODE_KEYS = ("code", "symbol", "stock_code", "证券代码", "Code")
NAME_KEYS = ("stock_name", "name", "stock", "证券简称", "Name")
INDUSTRY_KEYS = ("industry", "normalized_industry", "raw_industry", "Industry")
SCORE_KEYS = ("actionability_score", "quant_score", "real_world_score", "score", "Quant")
PRICE_KEYS = ("raw_latest_close", "price_current_price", "current_price", "price", "close")
BUY_LOW_KEYS = ("pullback_entry_low", "buy_low", "entry_low", "price_pullback_level")
BUY_HIGH_KEYS = ("pullback_entry_high", "buy_high", "entry_high", "breakout_max_chase_price")
EVIDENCE_KEYS = ("evidence_urls", "evidence", "official_evidence_urls")
RISK_KEYS = ("top_risks", "real_world_risk_flags", "hard_blockers", "soft_blockers")
REASON_KEYS = ("hard_logic_level", "upgrade_conditions", "follow_up", "classification_missing_conditions")


def _first(row: dict[str, Any], keys: Iterable[str], default: Any = "") -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return default


def _float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            f = float(value)
            return f if math.isfinite(f) else None
        except Exception:
            return None
    text = str(value).strip().replace(",", "").replace("%", "")
    m = re.search(r"-?\d+(?:\.\d+)?", text)
    if not m:
        return None
    try:
        f = float(m.group())
        return f if math.isfinite(f) else None
    except Exception:
        return None


def _clean_code(value: Any) -> str:
    text = str(value or "")
    m = re.search(r"(?<!\d)([036]\d{5})(?!\d)", text)
    return m.group(1) if m else text.strip()


def _split(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    parts = re.split(r"[;\n|]+", str(value))
    return [p.strip() for p in parts if p.strip() and p.strip().lower() not in {"none", "nan"}]


def _score(row: dict[str, Any]) -> float:
    raw = _float(_first(row, SCORE_KEYS))
    if raw is not None:
        if 0 <= raw <= 1:
            raw *= 100
        return round(max(0.0, min(100.0, raw)), 2)
    passed = _float(row.get("pass_count"))
    unknown = _float(row.get("unknown_count"))
    if passed is not None:
        total = max(1.0, passed + (unknown or 0.0))
        return round(45.0 + 45.0 * passed / total, 2)
    tier = str(row.get("source_tier") or row.get("user_visible_level") or "").upper()
    if "FULL_EVIDENCE" in tier or "STRICT_REVIEW_READY" in tier:
        return 72.0
    if "NEAR" in tier or "CONDITION" in tier:
        return 62.0
    return 52.0


def _price_zone(row: dict[str, Any]) -> tuple[float | None, float | None]:
    low = _float(_first(row, BUY_LOW_KEYS))
    high = _float(_first(row, BUY_HIGH_KEYS))
    preferred = str(row.get("preferred_plan") or "").lower()
    if preferred == "breakout":
        low = _float(row.get("breakout_trigger_price")) or low
        high = _float(row.get("breakout_max_chase_price")) or high
    elif preferred == "pullback":
        low = _float(row.get("pullback_entry_low")) or low
        high = _float(row.get("pullback_entry_high")) or high
    if low is not None and high is not None and low > high:
        low, high = high, low
    return low, high


def _distance(price: float | None, low: float | None, high: float | None) -> float | None:
    if price is None or low is None or high is None or price <= 0:
        return None
    if low <= price <= high:
        return 0.0
    target = high if price > high else low
    return round(abs(price - target) / price * 100.0, 2)


def _hard_reject(row: dict[str, Any]) -> bool:
    fields = " ".join(str(row.get(k) or "") for k in ("quant_status", "classification", "user_visible_level", "hard_blockers")).upper()
    return "HARD_REJECT" in fields or "HARD REJECT" in fields


def _source_hint(row: dict[str, Any], source_name: str) -> str:
    explicit = str(row.get("source_tier") or row.get("user_visible_level") or row.get("classification") or "")
    return explicit or source_name


def _global_score_delta(transmission: Mapping[str, Any]) -> float:
    direction = str(transmission.get("direction") or transmission.get("signal") or "NEUTRAL").upper()
    magnitude = str(transmission.get("magnitude") or "LOW").upper()
    base = {"LOW": 1.0, "MEDIUM": 2.5, "HIGH": 4.0}.get(magnitude, 1.0)
    if any(token in direction for token in ("POSITIVE", "BENEFICIAL", "FAVORABLE", "BULLISH")):
        return base
    if any(token in direction for token in ("NEGATIVE", "ADVERSE", "UNFAVORABLE", "BEARISH")):
        return -base
    return 0.0


def _apply_global_transmission(candidate: Candidate, transmission: Mapping[str, Any] | None) -> None:
    if not transmission:
        return
    delta = _global_score_delta(transmission)
    candidate.score = round(max(0.0, min(100.0, candidate.score + delta)), 2)
    factors = [str(v) for v in transmission.get("factors") or [] if str(v)]
    direction = str(transmission.get("direction") or transmission.get("signal") or "NEUTRAL")
    magnitude = str(transmission.get("magnitude") or "LOW")
    factor_text = ",".join(factors) if factors else "GLOBAL"
    candidate.reasons = list(dict.fromkeys([
        *candidate.reasons,
        f"global={factor_text}:{direction}/{magnitude}",
    ]))[:8]
    refs = [str(v) for v in transmission.get("evidence_refs") or [] if str(v)]
    candidate.evidence = list(dict.fromkeys([*candidate.evidence, *refs]))[:10]
    if delta < 0:
        candidate.risks = list(dict.fromkeys([
            *candidate.risks,
            f"explicit_global_transmission={direction}/{magnitude}",
        ]))[:8]


def build_candidate(row: dict[str, Any], source_name: str, holdings: set[str], global_transmission: Mapping[str, Any] | None = None) -> Candidate | None:
    code = _clean_code(_first(row, CODE_KEYS))
    if not re.fullmatch(r"[036]\d{5}", code):
        return None
    base_score = _score(row)
    current = _float(_first(row, PRICE_KEYS))
    buy_low, buy_high = _price_zone(row)
    distance = _distance(current, buy_low, buy_high)
    source_hint = _source_hint(row, source_name)
    source_lower = source_name.lower()
    state = "WATCH"
    if _hard_reject(row):
        state = "REJECT"
    elif "buy_ready" in source_lower:
        state = "BUY"
    elif "near_ready" in source_lower:
        state = "NEAR_BUY"
    elif distance == 0 and base_score >= 65:
        state = "BUY"
    elif distance is not None and distance <= 6 and base_score >= 55:
        state = "NEAR_BUY"

    evidence: list[str] = []
    for key in EVIDENCE_KEYS:
        evidence.extend(_split(row.get(key)))
    evidence = list(dict.fromkeys(evidence))[:8]
    risks: list[str] = []
    for key in RISK_KEYS:
        risks.extend(_split(row.get(key)))
    risks = list(dict.fromkeys(risks))[:6]
    reasons: list[str] = []
    for key in REASON_KEYS:
        reasons.extend(_split(row.get(key)))
    if row.get("industry_regime_status"):
        reasons.append(f"industry={row.get('industry_regime_status')}")
    if row.get("market_regime_status"):
        reasons.append(f"market={row.get('market_regime_status')}")
    reasons = list(dict.fromkeys(reasons))[:6]

    completeness = sum([
        bool(current),
        bool(buy_low is not None and buy_high is not None),
        str(_first(row, INDUSTRY_KEYS, "UNKNOWN")) not in ("", "UNKNOWN"),
        bool(evidence),
        bool(reasons or risks),
    ])
    confidence = "HIGH" if base_score >= 70 and completeness >= 4 else "MEDIUM" if base_score >= 55 and completeness >= 2 else "LOW"

    candidate = Candidate(
        code=code,
        name=str(_first(row, NAME_KEYS, code)).strip() or code,
        industry=str(_first(row, INDUSTRY_KEYS, "UNKNOWN")).strip() or "UNKNOWN",
        score=base_score,
        state=state,
        confidence=confidence,
        current_price=current,
        buy_low=buy_low,
        buy_high=buy_high,
        distance_to_buy_pct=distance,
        source=source_name,
        source_tier=source_hint,
        reasons=reasons,
        risks=risks,
        evidence=evidence,
        holding=code in holdings,
    )
    _apply_global_transmission(candidate, global_transmission)
    return candidate


def rank_candidates(raw_rows: list[dict[str, Any]], source_name: str, holdings: set[str], *, top_n: int = 30, industry_cap: int = 3, global_transmission: Mapping[str, Mapping[str, Any]] | None = None) -> tuple[list[Candidate], list[Candidate]]:
    candidates: list[Candidate] = []
    seen: set[str] = set()
    global_transmission = global_transmission or {}
    for row in raw_rows:
        code = _clean_code(_first(row, CODE_KEYS))
        candidate = build_candidate(row, source_name, holdings, global_transmission.get(code))
        if candidate and candidate.code not in seen:
            candidates.append(candidate)
            seen.add(candidate.code)

    state_weight = {"BUY": 4, "NEAR_BUY": 3, "WATCH": 2, "REJECT": 0}
    candidates.sort(key=lambda c: (state_weight.get(c.state, 1), c.score, c.confidence == "HIGH", c.holding), reverse=True)

    chosen: list[Candidate] = []
    counts: Counter[str] = Counter()
    for c in candidates:
        key = c.industry or "UNKNOWN"
        if key != "UNKNOWN" and counts[key] >= industry_cap:
            continue
        if c.state == "REJECT":
            continue
        chosen.append(c)
        counts[key] += 1
        if len(chosen) >= top_n:
            break

    eligible_count = len([c for c in candidates if c.state != "REJECT"])
    if len(chosen) < min(top_n, eligible_count):
        chosen_codes = {c.code for c in chosen}
        for c in candidates:
            if c.code in chosen_codes or c.state == "REJECT":
                continue
            chosen.append(c)
            chosen_codes.add(c.code)
            if len(chosen) >= top_n:
                break

    for idx, c in enumerate(chosen, 1):
        c.rank = idx
    return chosen, candidates


def apply_changes(candidates: list[Candidate], previous: dict[str, Any] | None) -> list[str]:
    previous = previous or {}
    prev_rows = previous.get("candidates") or []
    prev_rank = {str(row.get("code")): int(row.get("rank") or 0) for row in prev_rows}
    current_codes = {c.code for c in candidates}
    for c in candidates:
        old = prev_rank.get(c.code)
        if old is None:
            c.change = "NEW"
        elif c.rank < old:
            c.change = f"UP {old-c.rank}"
        elif c.rank > old:
            c.change = f"DOWN {c.rank-old}"
        else:
            c.change = "STABLE"
    return [code for code in prev_rank if code not in current_codes]
