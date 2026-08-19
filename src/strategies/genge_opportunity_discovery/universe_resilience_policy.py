"""Resilient Shanghai/Shenzhen A-share universe construction.

The authoritative exchange listing endpoints remain first choice and the core
scanner's recent repository snapshot remains second choice.  This policy adds a
last-resort public-provider fallback only when both are unavailable, which is a
common failure mode on hosted CI runners when an exchange endpoint returns 403.

The fallback is intentionally narrow: Baostock stock-basic rows must be current
listed stocks, must be Shanghai or Shenzhen, must map to a known A-share board,
and the resulting universe must pass a minimum-size completeness check.  It
never substitutes for price, financial, announcement, valuation or event-risk
evidence later in the pipeline.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

import baostock as bs

from src.strategies.genge_opportunity_discovery import all_a_full_scan as core


RULE_VERSION = "all_a_universe_resilience_v1"
MIN_FALLBACK_ROWS = 3000

_ORIGINAL_BUILD_ALL_A_UNIVERSE = core.build_all_a_universe


def _board_text(exchange: str, code: str) -> str | None:
    code = str(code).zfill(6)
    if exchange == "SSE":
        if code.startswith(("688", "689")):
            return "STAR"
        if code.startswith(("600", "601", "603", "605")):
            return "SSE_MAIN"
        return None
    if exchange == "SZSE":
        if code.startswith(("300", "301")):
            return "创业板"
        if code.startswith(("000", "001", "002", "003")):
            return "主板"
        return None
    return None


def _result_error(result: Any) -> tuple[str, str]:
    return (
        str(getattr(result, "error_code", "") or ""),
        str(getattr(result, "error_msg", "") or ""),
    )


def fetch_baostock_universe(as_of: date) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return a completeness-checked current Shanghai/Shenzhen stock universe."""

    login = bs.login()
    login_code, login_message = _result_error(login)
    if login_code != "0":
        raise RuntimeError(
            f"baostock login failed: {login_code or 'unknown'} {login_message}".strip()
        )

    rows: list[dict[str, Any]] = []
    skipped_unresolved = 0
    try:
        result = bs.query_stock_basic()
        error_code, error_message = _result_error(result)
        if error_code != "0":
            raise RuntimeError(
                f"baostock stock-basic query failed: "
                f"{error_code or 'unknown'} {error_message}".strip()
            )
        fields = list(getattr(result, "fields", []) or [])
        while result.next():
            values = result.get_row_data()
            item = dict(zip(fields, values))
            provider_code = str(item.get("code") or "").strip().lower()
            if not provider_code.startswith(("sh.", "sz.")):
                continue
            if str(item.get("type") or "").strip() != "1":
                continue
            if str(item.get("status") or "").strip() != "1":
                continue
            exchange = "SSE" if provider_code.startswith("sh.") else "SZSE"
            code = provider_code.split(".", 1)[1]
            board = _board_text(exchange, code)
            if board is None:
                skipped_unresolved += 1
                continue
            row = core._listing_row(
                code=code,
                name=item.get("code_name") or "",
                exchange=exchange,
                board=board,
                listing_date=item.get("ipoDate") or "",
                universe_source="Baostock query_stock_basic public-provider fallback",
            )
            rows.append(row)
    finally:
        try:
            bs.logout()
        except Exception:
            pass

    rows = core.mark_listings_after_as_of(rows, as_of=as_of)
    rows = sorted(
        {row["code"]: row for row in rows if row.get("code")}.values(),
        key=lambda row: row["code"],
    )
    if len(rows) < MIN_FALLBACK_ROWS:
        raise RuntimeError(
            f"baostock universe incomplete: {len(rows)} < {MIN_FALLBACK_ROWS}"
        )
    return rows, {
        "status": "PUBLIC_PROVIDER_FALLBACK",
        "snapshot_date": as_of.isoformat(),
        "fallback_age_days": 0,
        "sources": [
            {
                "provider": "Baostock",
                "method": "query_stock_basic",
                "status": "PUBLIC_PROVIDER_FALLBACK",
                "row_count": len(rows),
                "skipped_unresolved": skipped_unresolved,
            }
        ],
        "raw_security_count": len(rows),
        "universe_rule_version": RULE_VERSION,
    }


def build_all_a_universe(
    *,
    as_of: date,
    stock_pool_dir: Path = Path("stock_pools"),
    fetcher: Callable[[date], tuple[list[dict[str, Any]], dict[str, Any]]] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Use existing official/snapshot logic first, then a strict public fallback."""

    if fetcher is not None:
        return _ORIGINAL_BUILD_ALL_A_UNIVERSE(
            as_of=as_of,
            stock_pool_dir=stock_pool_dir,
            fetcher=fetcher,
        )
    try:
        return _ORIGINAL_BUILD_ALL_A_UNIVERSE(
            as_of=as_of,
            stock_pool_dir=stock_pool_dir,
        )
    except Exception as primary_error:
        try:
            rows, audit = fetch_baostock_universe(as_of)
        except Exception as fallback_error:
            raise RuntimeError(
                "all-A universe sources exhausted: "
                f"official/snapshot={type(primary_error).__name__}: {primary_error}; "
                f"baostock={type(fallback_error).__name__}: {fallback_error}"
            ) from fallback_error
        audit["fetch_error"] = (
            f"{type(primary_error).__name__}: {primary_error}"
        )
        return rows, audit


def install() -> None:
    """Install into the risk-capped production process; safe to call repeatedly."""

    core.build_all_a_universe = build_all_a_universe
