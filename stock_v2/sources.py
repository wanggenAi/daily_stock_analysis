from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any, Iterable


_CODE_RE = re.compile(r"(?<!\d)([036]\d{5})(?!\d)")
_GLOBAL_FACTOR_IDS = (
    "SP500", "NASDAQ", "NASDAQ100", "SOX", "VIX", "US10Y", "DXY", "USDCNH",
    "HANGSENG", "HANGSENGTECH", "COPPER", "GOLD", "SILVER", "CRUDE_OIL", "BTC", "ETH",
)


def _latest(paths: Iterable[Path]) -> Path | None:
    paths = [p for p in paths if p.exists() and p.is_file()]
    if not paths:
        return None
    return max(paths, key=lambda p: (p.stat().st_mtime_ns, str(p)))


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def latest_scan_file(root: Path) -> Path | None:
    scan_root = root / "reports" / "all_a_full_scan"
    preferred = [
        "top30_deep_review.csv",
        "daily_candidate_top5.csv",
        "near_ready.csv",
        "buy_ready.csv",
        "all_a_quant_screen.csv",
    ]
    for name in preferred:
        found = _latest(scan_root.glob(f"**/{name}"))
        if found:
            return found
    return None


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def parse_markdown_table(path: Path, required_columns: set[str] | None = None) -> list[dict[str, str]]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    rows: list[dict[str, str]] = []
    i = 0
    required_columns = required_columns or set()
    while i + 1 < len(lines):
        header = lines[i].strip()
        sep = lines[i + 1].strip()
        if not (header.startswith("|") and sep.startswith("|") and "---" in sep):
            i += 1
            continue
        cols = [c.strip() for c in header.strip("|").split("|")]
        if required_columns and not required_columns.issubset(set(cols)):
            i += 1
            continue
        j = i + 2
        while j < len(lines) and lines[j].strip().startswith("|"):
            vals = [v.strip() for v in lines[j].strip().strip("|").split("|")]
            if len(vals) == len(cols):
                rows.append(dict(zip(cols, vals)))
            j += 1
        i = j
    return rows


def load_radar_rows(root: Path) -> list[dict[str, str]]:
    path = root / "LATEST_RESEARCH_RADAR.md"
    rows = parse_markdown_table(path, {"Code", "Name"})
    out: list[dict[str, str]] = []
    for row in rows:
        if _CODE_RE.fullmatch(row.get("Code", "")):
            out.append({
                "code": row.get("Code", ""),
                "stock_name": row.get("Name", ""),
                "industry": row.get("Industry", "UNKNOWN"),
                "actionability_score": row.get("Quant", ""),
                "source_tier": row.get("Tier", ""),
                "pass_count": row.get("PASS", ""),
                "unknown_count": row.get("UNKNOWN", ""),
                "follow_up": row.get("Follow-up", ""),
                "_source": str(path.name),
            })
    return out


def load_ledger_rows(root: Path, limit: int = 100) -> list[dict[str, str]]:
    path = root / "V31_CANDIDATE_LEDGER.md"
    if not path.exists():
        return []
    rows = parse_markdown_table(path)
    out: list[dict[str, str]] = []
    for row in rows:
        code = next((row.get(k, "") for k in ("Code", "code", "代码") if row.get(k)), "")
        m = _CODE_RE.search(str(code))
        if not m:
            continue
        decision = next((row.get(k, "") for k in ("Decision", "State", "Action", "decision") if row.get(k)), "")
        if any(x in decision.upper() for x in ("REJECT", "HARD_FAIL", "HARD REJECT")):
            continue
        out.append({
            "code": m.group(1),
            "stock_name": next((row.get(k, "") for k in ("Name", "stock_name", "名称") if row.get(k)), m.group(1)),
            "industry": next((row.get(k, "") for k in ("Industry", "industry", "行业") if row.get(k)), "UNKNOWN"),
            "actionability_score": next((row.get(k, "") for k in ("Score", "Quant", "actionability_score", "Confidence") if row.get(k)), ""),
            "source_tier": decision or "LEGACY_LEDGER",
            "_source": path.name,
        })
        if len(out) >= limit:
            break
    return out


def load_candidates(root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    scan = latest_scan_file(root)
    if scan:
        rows = load_csv_rows(scan)
        if rows:
            return rows, {
                "mode": "LIVE_SCAN",
                "source": str(scan.relative_to(root)),
                "degraded": False,
            }

    radar = load_radar_rows(root)
    ledger = load_ledger_rows(root)
    combined: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in [*radar, *ledger]:
        code = str(row.get("code") or "")
        if code and code not in seen:
            combined.append(row)
            seen.add(code)
    return combined, {
        "mode": "COMMITTED_SNAPSHOT_FALLBACK" if combined else "NO_DATA",
        "source": "LATEST_RESEARCH_RADAR.md + V31_CANDIDATE_LEDGER.md" if combined else "",
        "degraded": True,
    }


def load_holdings(root: Path) -> set[str]:
    holdings: set[str] = set()
    for name in ("CURRENT_HOLDINGS.md", "CURRENT_EXECUTION_STATE.json"):
        path = root / name
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        holdings.update(_CODE_RE.findall(text))
    return holdings


def _global_context(root: Path) -> dict[str, Any]:
    path = root / "data" / "global_market_pulse" / "latest.json"
    payload = _load_json(path)
    if not payload:
        return {
            "available": False,
            "source": "",
            "generated_at": None,
            "coverage": {},
            "risk_regime": {},
            "pre_open": {},
            "factors": {},
            "security_transmission": {},
        }

    series = payload.get("series") or {}
    factors: dict[str, dict[str, Any]] = {}
    if isinstance(series, dict):
        for factor_id in _GLOBAL_FACTOR_IDS:
            row = series.get(factor_id)
            if not isinstance(row, dict) or row.get("status") != "OK":
                continue
            factors[factor_id] = {
                "label": row.get("label") or factor_id,
                "latest": row.get("latest"),
                "market_date": row.get("market_date"),
                "freshness": row.get("freshness"),
                "change_24h_pct": row.get("change_24h_pct") if row.get("change_24h_pct") is not None else row.get("change_1d_pct"),
                "change_5d_pct": row.get("change_5d_pct"),
                "since_last_a_share_close_pct": row.get("since_last_a_share_close_pct"),
            }

    transmission: dict[str, dict[str, Any]] = {}
    for row in payload.get("security_transmission") or []:
        if not isinstance(row, dict):
            continue
        code_match = _CODE_RE.search(str(row.get("code") or ""))
        if not code_match:
            continue
        code = code_match.group(1)
        transmission[code] = {
            "direction": row.get("direction") or row.get("signal") or "NEUTRAL",
            "signal": row.get("signal") or row.get("direction") or "NEUTRAL",
            "magnitude": row.get("magnitude") or "LOW",
            "confidence": row.get("confidence"),
            "factors": list(row.get("relevant_global_factors") or []),
            "evidence_refs": list(row.get("evidence_refs") or []),
            "research_implication": row.get("research_implication"),
            "freshness": row.get("freshness"),
        }

    return {
        "available": True,
        "source": str(path.relative_to(root)),
        "generated_at": payload.get("generated_at"),
        "coverage": payload.get("coverage") or {},
        "risk_regime": payload.get("risk_regime") or {},
        "pre_open": payload.get("pre_open_intelligence") or {},
        "factors": factors,
        "security_transmission": transmission,
    }


def load_market_context(root: Path) -> dict[str, Any]:
    global_context = _global_context(root)
    result: dict[str, Any] = {
        "status": "DEGRADED",
        "score": None,
        "external_risk": "UNKNOWN",
        "reasons": ["live market_regime.json unavailable"],
        "source": "",
        "global": global_context,
    }

    candidates = list((root / "reports" / "all_a_full_scan").glob("**/market_regime.json"))
    latest = _latest(candidates)
    if latest:
        payload = _load_json(latest)
        if payload:
            result.update({
                "status": str(payload.get("market_regime_status") or payload.get("status") or "AVAILABLE"),
                "score": payload.get("market_regime_score") if payload.get("market_regime_score") is not None else payload.get("score"),
                "external_risk": payload.get("external_risk_level") or payload.get("external_risk") or "UNKNOWN",
                "reasons": payload.get("market_regime_risk_reasons") or payload.get("risk_reasons") or [],
                "source": str(latest.relative_to(root)),
            })
    elif global_context.get("available"):
        regime = global_context.get("risk_regime") or {}
        pre_open = global_context.get("pre_open") or {}
        result.update({
            "status": str(regime.get("status") or "GLOBAL_ONLY"),
            "score": regime.get("score"),
            "external_risk": pre_open.get("holiday_gap_risk") or "GLOBAL_CONTEXT_AVAILABLE",
            "reasons": list(pre_open.get("next_a_share_open_watch") or []),
            "source": global_context.get("source") or "",
        })
    return result
