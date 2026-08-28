"""Persist a read-only hourly price/value overlay over one authorized V3.1.1 canonical.

This module deliberately cannot create or mutate Formal BUY/ADD/REDUCE/EXIT actions.
It consumes the Finalizer's authorized hourly workset, refreshes public prices for
Shanghai/Shenzhen main-board names, and records price/value evidence as a durable,
auditable time series.
"""
from __future__ import annotations

import argparse
import json
import re
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping
from zoneinfo import ZoneInfo

CONTRACT_VERSION = "GEN_GE_V3_1_1_HOURLY_DEEP_OVERLAY_V1"
PRODUCTION_VERSION = "GEN_GE_V3_1_1_PRODUCTION"
BEIJING = ZoneInfo("Asia/Shanghai")

MAINBOARD_PATTERNS = (
    re.compile(r"^(600|601|603|605)\d{3}$"),
    re.compile(r"^(000|001|002|003)\d{3}$"),
)

ANCHOR_KEYS = (
    "neutral_value",
    "neutral_price",
    "base_value",
    "base_price",
    "v311_neutral_value",
    "intrinsic_value_neutral",
    "valuation_neutral",
)
PRICE_KEYS = (
    "current_price",
    "price",
    "market_price",
    "v311_price",
    "decision_price",
)
ACTION_KEYS = ("formal_action", "action", "production_action", "decision")
NAME_KEYS = ("name", "stock_name", "company_name")


class OverlayContractError(RuntimeError):
    pass


@dataclass(frozen=True)
class Quote:
    code: str
    name: str
    price: float | None
    previous_close: float | None
    change_pct: float | None
    observed_at: str
    provider: str
    status: str = "OK"


def _read_json(path: Path) -> Any:
    if not path.is_file():
        raise OverlayContractError(f"missing required authoritative file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _first(mapping: Mapping[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        value = mapping.get(key)
        if value not in (None, ""):
            return value
    return None


def _as_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def is_tradeable_mainboard(code: str) -> bool:
    code = str(code or "").strip().zfill(6)
    return any(pattern.fullmatch(code) for pattern in MAINBOARD_PATTERNS)


def _identity(payload: Mapping[str, Any]) -> tuple[str | None, str | None]:
    sid = _first(payload, ("canonical_snapshot_id", "snapshot_id"))
    source = _first(payload, ("canonical_source_run_id", "source_run_id"))
    return (str(sid) if sid is not None else None, str(source) if source is not None else None)


def load_authoritative_bundle(root: Path) -> dict[str, Any]:
    authority = _read_json(root / "production_authority.json")
    canonical = _read_json(root / "canonical_snapshot" / "latest.json")
    hourly = _read_json(root / "operating_views" / "hourly.json")
    holdings = _read_json(root / "holdings_reconciliation.json")
    lifecycle_state = _read_json(root / "candidate_lifecycle" / "candidate_lifecycle_state.json")
    lifecycle_summary = _read_json(root / "candidate_lifecycle" / "summary.json")

    if authority.get("authorized") is not True:
        raise OverlayContractError("production authority is not authorized")
    version = _first(authority, ("production_version", "production_model_version")) or _first(
        canonical, ("production_version", "production_model_version")
    )
    if version != PRODUCTION_VERSION:
        raise OverlayContractError(f"unexpected production version: {version!r}")

    authority_sid, authority_run = _identity(authority)
    canonical_sid, canonical_run = _identity(canonical)
    hourly_sid, hourly_run = _identity(hourly)
    holdings_sid, holdings_run = _identity(holdings)
    summary_sid, summary_run = _identity(lifecycle_summary)
    state_sid = lifecycle_state.get("latest_applied_snapshot_id")
    state_run = lifecycle_state.get("last_persisted_source_run_id")

    sid_values = {x for x in (authority_sid, canonical_sid, hourly_sid, holdings_sid, summary_sid, str(state_sid) if state_sid else None) if x}
    run_values = {x for x in (authority_run, canonical_run, hourly_run, holdings_run, summary_run, str(state_run) if state_run else None) if x}
    if len(sid_values) != 1:
        raise OverlayContractError(f"canonical snapshot identity conflict: {sorted(sid_values)}")
    if len(run_values) != 1:
        raise OverlayContractError(f"canonical source run identity conflict: {sorted(run_values)}")
    if not sid_values or not run_values:
        raise OverlayContractError("canonical snapshot/source identity missing")

    latest_trade_date = _first(authority, ("latest_trade_date",)) or _first(canonical, ("latest_trade_date",))
    research_as_of = _first(authority, ("research_as_of",)) or _first(canonical, ("research_as_of",))
    if not latest_trade_date or not research_as_of:
        raise OverlayContractError("latest_trade_date/research_as_of missing")

    return {
        "authority": authority,
        "canonical": canonical,
        "hourly": hourly,
        "holdings": holdings,
        "lifecycle_state": lifecycle_state,
        "lifecycle_summary": lifecycle_summary,
        "snapshot_id": next(iter(sid_values)),
        "source_run_id": next(iter(run_values)),
        "latest_trade_date": str(latest_trade_date),
        "research_as_of": str(research_as_of),
    }


def _iter_rows(node: Any, path: tuple[str, ...] = ()) -> Iterable[tuple[tuple[str, ...], Mapping[str, Any]]]:
    if isinstance(node, Mapping):
        code = node.get("code") or node.get("stock_code") or node.get("symbol")
        if code is not None:
            yield path, node
        for key, value in node.items():
            yield from _iter_rows(value, path + (str(key),))
    elif isinstance(node, list):
        for idx, value in enumerate(node):
            yield from _iter_rows(value, path + (str(idx),))


def _recursive_numeric(mapping: Mapping[str, Any], keys: Iterable[str]) -> float | None:
    direct = _as_float(_first(mapping, keys))
    if direct is not None:
        return direct
    for value in mapping.values():
        if isinstance(value, Mapping):
            found = _recursive_numeric(value, keys)
            if found is not None:
                return found
    return None


def extract_workset(hourly: Mapping[str, Any]) -> list[dict[str, Any]]:
    by_code: dict[str, dict[str, Any]] = {}
    for path, row in _iter_rows(hourly):
        raw_code = row.get("code") or row.get("stock_code") or row.get("symbol")
        code = re.sub(r"\D", "", str(raw_code or ""))[-6:].zfill(6)
        if not is_tradeable_mainboard(code):
            continue
        joined = "/".join(path).lower()
        explicit_scope = str(row.get("scope") or row.get("observed_scope") or "").upper()
        if "holding" in joined or "HOLDING" in explicit_scope:
            scope = "HOLDING"
        elif "deep" in joined or "focus" in joined or "candidate" in joined:
            scope = "DEEP_REVIEW_FOCUS"
        else:
            scope = explicit_scope or "CANONICAL_HOURLY_WORKSET"

        item = by_code.setdefault(
            code,
            {
                "code": code,
                "name": str(_first(row, NAME_KEYS) or ""),
                "scope": scope,
                "formal_action": str(_first(row, ACTION_KEYS) or ""),
                "canonical_price": _recursive_numeric(row, PRICE_KEYS),
                "validated_value_anchor": _recursive_numeric(row, ANCHOR_KEYS),
            },
        )
        if scope == "HOLDING":
            item["scope"] = "HOLDING"
        if not item["name"]:
            item["name"] = str(_first(row, NAME_KEYS) or "")
        if not item["formal_action"]:
            item["formal_action"] = str(_first(row, ACTION_KEYS) or "")
        if item["canonical_price"] is None:
            item["canonical_price"] = _recursive_numeric(row, PRICE_KEYS)
        if item["validated_value_anchor"] is None:
            item["validated_value_anchor"] = _recursive_numeric(row, ANCHOR_KEYS)
    return sorted(by_code.values(), key=lambda x: (x["scope"] != "HOLDING", x["code"]))


def _market_symbol(code: str) -> str:
    return ("sh" if code.startswith(("600", "601", "603", "605")) else "sz") + code


def fetch_tencent_quotes(codes: Iterable[str]) -> dict[str, Quote]:
    codes = list(dict.fromkeys(codes))
    if not codes:
        return {}
    url = "https://qt.gtimg.cn/q=" + ",".join(_market_symbol(code) for code in codes)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 GenGe-V3.1.1-hourly-overlay"})
    now = datetime.now(timezone.utc).isoformat()
    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            text = response.read().decode("gb18030", errors="replace")
    except Exception as exc:  # public-data failure must remain research-only and explicit
        return {
            code: Quote(code, "", None, None, None, now, "tencent_quote", f"FETCH_ERROR:{type(exc).__name__}")
            for code in codes
        }

    result: dict[str, Quote] = {}
    for line in text.splitlines():
        if "=\"" not in line:
            continue
        body = line.split('="', 1)[1].rsplit('"', 1)[0]
        fields = body.split("~")
        if len(fields) < 6:
            continue
        code = re.sub(r"\D", "", fields[2])[-6:].zfill(6)
        price = _as_float(fields[3])
        prev = _as_float(fields[4])
        pct = ((price / prev - 1.0) * 100.0) if price is not None and prev not in (None, 0) else None
        observed = now
        if len(fields) > 30 and re.fullmatch(r"\d{14}", fields[30] or ""):
            dt = datetime.strptime(fields[30], "%Y%m%d%H%M%S").replace(tzinfo=BEIJING)
            observed = dt.isoformat()
        result[code] = Quote(code, fields[1], price, prev, pct, observed, "tencent_quote")
    for code in codes:
        result.setdefault(code, Quote(code, "", None, None, None, now, "tencent_quote", "MISSING_QUOTE"))
    return result


def _margin_direction(current: float | None, canonical: float | None) -> str:
    if current is None or canonical in (None, 0):
        return "UNKNOWN"
    move = current / canonical - 1.0
    if move <= -0.005:
        return "EXPANDING"
    if move >= 0.005:
        return "SHRINKING"
    return "STABLE"


def _priority(scope: str, action: str, ratio: float | None, change_pct: float | None) -> str:
    action = action.upper()
    if action in {"REDUCE_25", "REDUCE_50", "CORE_ONLY", "EXIT"}:
        return "RAISE"
    if ratio is not None and ratio <= 0.80:
        return "RAISE"
    if change_pct is not None and abs(change_pct) >= 3.0:
        return "RAISE"
    if scope == "HOLDING" or action == "HOLD_REVIEW":
        return "KEEP"
    return "KEEP"


def build_overlay(
    bundle: Mapping[str, Any],
    *,
    quote_provider: Callable[[Iterable[str]], Mapping[str, Quote]] = fetch_tencent_quotes,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or datetime.now(timezone.utc)
    workset = extract_workset(bundle["hourly"])
    quotes = quote_provider(item["code"] for item in workset)
    rows: list[dict[str, Any]] = []

    for item in workset:
        quote = quotes.get(item["code"])
        current = quote.price if quote else None
        anchor = item["validated_value_anchor"]
        ratio = current / anchor if current is not None and anchor not in (None, 0) else None
        margin = 1.0 - ratio if ratio is not None else None
        if ratio is None:
            price_status = "VALUE_ANCHOR_UNAVAILABLE"
        elif ratio <= 0.80:
            price_status = "PRICE_GATE_PASS_RESEARCH_ONLY"
        elif ratio <= 0.90:
            price_status = "NEAR_PRICE_GATE"
        else:
            price_status = "PRICE_GATE_NOT_MET"

        rows.append(
            {
                **item,
                "latest_price": current,
                "latest_price_observed_at": quote.observed_at if quote else None,
                "latest_price_provider": quote.provider if quote else None,
                "latest_price_status": quote.status if quote else "MISSING_QUOTE",
                "latest_change_pct": round(quote.change_pct, 4) if quote and quote.change_pct is not None else None,
                "price_to_value": round(ratio, 6) if ratio is not None else None,
                "margin_of_safety": round(margin, 6) if margin is not None else None,
                "safety_margin_direction": _margin_direction(current, item["canonical_price"]),
                "price_evidence_status": price_status,
                "new_sell_evidence": "UNASSESSED_BY_NUMERIC_OVERLAY",
                "thesis_status": "UNCHANGED_UNLESS_EXTERNAL_EVIDENCE_ATTACHED",
                "deep_review_priority": _priority(
                    item["scope"], item["formal_action"], ratio, quote.change_pct if quote else None
                ),
                "hourly_research_conclusion": (
                    "PRICE_ATTRACTIVE_RESEARCH_LEAD" if price_status == "PRICE_GATE_PASS_RESEARCH_ONLY" and item["scope"] != "HOLDING"
                    else "FORMAL_ACTION_UNCHANGED"
                ),
            }
        )

    return {
        "contract_version": CONTRACT_VERSION,
        "production_version": PRODUCTION_VERSION,
        "generated_at": generated_at.isoformat(),
        "generated_at_beijing": generated_at.astimezone(BEIJING).isoformat(),
        "canonical_snapshot_id": bundle["snapshot_id"],
        "canonical_source_run_id": bundle["source_run_id"],
        "latest_trade_date": bundle["latest_trade_date"],
        "research_as_of": bundle["research_as_of"],
        "formal_action_source": "FINALIZED_CANONICAL_ONLY",
        "formal_action_recomputed": False,
        "overlay_may_overwrite_formal_action": False,
        "price_overlay_is_formal_buy": False,
        "tradeable_scope": "SHANGHAI_SHENZHEN_MAINBOARD_ONLY",
        "workset_count": len(rows),
        "holding_count": sum(row["scope"] == "HOLDING" for row in rows),
        "price_attractive_research_lead_count": sum(
            row["hourly_research_conclusion"] == "PRICE_ATTRACTIVE_RESEARCH_LEAD" for row in rows
        ),
        "rows": rows,
    }


def persist_overlay(payload: Mapping[str, Any], output_root: Path) -> tuple[Path, Path]:
    stamp = datetime.fromisoformat(str(payload["generated_at"])).astimezone(BEIJING)
    history = output_root / stamp.strftime("%Y-%m-%d") / f"{stamp:%H}.json"
    latest = output_root / "latest.json"
    history.parent.mkdir(parents=True, exist_ok=True)
    output_root.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    history.write_text(text, encoding="utf-8")
    latest.write_text(text, encoding="utf-8")
    return latest, history


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authoritative-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=Path("data/hourly_deep_overlay"))
    args = parser.parse_args()
    bundle = load_authoritative_bundle(args.authoritative_root)
    payload = build_overlay(bundle)
    latest, history = persist_overlay(payload, args.output_root)
    print(json.dumps({
        "canonical_snapshot_id": payload["canonical_snapshot_id"],
        "workset_count": payload["workset_count"],
        "holding_count": payload["holding_count"],
        "price_attractive_research_lead_count": payload["price_attractive_research_lead_count"],
        "latest": str(latest),
        "history": str(history),
        "formal_action_recomputed": False,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
