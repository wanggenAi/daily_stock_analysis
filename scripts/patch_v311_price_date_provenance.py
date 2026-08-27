"""One-time guarded migration for V3.1.1 price-date provenance.

The migration is deliberately structural and fail-closed: every target block must
match exactly once, otherwise this script exits without writing the source file.
It exists only to land the production fix safely without replacing the large
valuation module wholesale.
"""
from __future__ import annotations

import re
from pathlib import Path

TARGET = Path("src/strategies/genge_opportunity_discovery/v311_current_expectation_inputs.py")


def _replace_once(text: str, pattern: str, replacement: str, label: str) -> str:
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.S)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one source block, matched {count}")
    return updated


def main() -> int:
    original = TARGET.read_text(encoding="utf-8")
    text = original

    helper = '''def _parse_observed_trade_date(value: Any) -> date | None:
    """Normalize a provider/source observation date without inventing one."""
    if value is None:
        return None
    if isinstance(value, pd.Timestamp):
        if pd.isna(value):
            return None
        return value.date()
    if isinstance(value, date):
        return value
    raw = str(value).strip()
    if not raw or raw.lower() in {"nan", "nat", "none"}:
        return None
    # Common vendor integer/string format: YYYYMMDD.
    digits = raw.split(".", 1)[0]
    if len(digits) == 8 and digits.isdigit():
        try:
            return date(int(digits[:4]), int(digits[4:6]), int(digits[6:8]))
        except ValueError:
            return None
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    try:
        return pd.Timestamp(parsed).date()
    except (TypeError, ValueError, OverflowError):
        return None


'''
    marker = "def _normalize_code(value: Any) -> str:\n"
    if "def _parse_observed_trade_date(" not in text:
        if text.count(marker) != 1:
            raise SystemExit("date helper insertion point is not unique")
        text = text.replace(marker, helper + marker, 1)

    current_inputs = '''def current_inputs_from_panel(
    code: str,
    panel: pd.DataFrame,
    *,
    current_price: float | None,
    as_of: date,
    price_source: str,
    price_date: Any = None,
) -> dict[str, Any]:
    code = _normalize_code(code)
    observed_price_date = _parse_observed_trade_date(price_date)
    as_of_ts = pd.Timestamp(as_of)
    if panel is None or panel.empty:
        return _invalid_row(
            code,
            current_price,
            as_of,
            price_source,
            "FINANCIAL_DATA_UNAVAILABLE",
            price_date=observed_price_date,
        )
    local = panel.copy()
    local["available_date"] = pd.to_datetime(local["available_date"], errors="coerce").dt.normalize()
    local = local[local["available_date"].notna() & (local["available_date"] <= as_of_ts)]
    if local.empty:
        return _invalid_row(
            code,
            current_price,
            as_of,
            price_source,
            "NO_FINANCIAL_REPORT_AVAILABLE_AS_OF_DATE",
            price_date=observed_price_date,
        )
    latest = local.sort_values(["available_date", "report_date"]).iloc[-1]
    normalized = _finite(latest.get("normalized_eps_round6"))
    realistic = _finite(latest.get("realistic_growth_round6"))
    neutral = _finite(latest.get("neutral_value_round6"))
    price = _finite(current_price)
    if price is None or price <= 0:
        implied, implied_status = np.nan, "INPUT_INCOMPLETE"
    else:
        implied, implied_status = solve_market_implied_growth(
            float(price), float(normalized) if normalized is not None else np.nan
        )
    expectation_gap = (
        float(realistic - implied)
        if realistic is not None and np.isfinite(implied)
        else np.nan
    )
    ratio = (
        float(price / neutral)
        if price is not None and neutral is not None and price > 0 and neutral > 0
        else np.nan
    )
    report_date = pd.to_datetime(latest.get("report_date"), errors="coerce")
    available_date = pd.to_datetime(latest.get("available_date"), errors="coerce")

    price_error = ""
    if observed_price_date is None:
        price_error = "PRICE_DATE_UNVERIFIED"
    elif observed_price_date > as_of:
        price_error = "PRICE_DATE_AFTER_DECISION_DATE"
    elif price is None or price <= 0:
        price_error = "PRICE_INPUT_INCOMPLETE"

    numeric_ready = (
        all(value is not None for value in (price, normalized, realistic, neutral))
        and np.isfinite(implied)
    )
    input_error = price_error
    if not input_error and implied_status == "INPUT_INCOMPLETE":
        input_error = "IMPLIED_GROWTH_INPUT_INCOMPLETE"
    ready = numeric_ready and not input_error

    return {
        "code": code,
        "v311_expectation_input_status": "READY" if ready else "HOLD_REVIEW_INPUT_INCOMPLETE",
        "v311_expectation_policy_source": POLICY_SOURCE,
        "decision_date": as_of.isoformat(),
        # Price freshness is evidence, not an alias for the decision date.
        "price_date": observed_price_date.isoformat() if observed_price_date is not None else "",
        "fund_available_date": available_date.date().isoformat()
        if not pd.isna(available_date)
        else "",
        "financial_report_date": report_date.date().isoformat()
        if not pd.isna(report_date)
        else "",
        "current_price_source": price_source,
        "v31_current_price": price,
        "v31_normalized_profit": normalized,
        "v31_normalized_profit_method": "STRICT_PIT_NORMALIZED_CLEAN_EPS_ROUND6",
        "v31_neutral_value": neutral,
        "v31_realistic_profit_cagr": realistic,
        "v31_market_implied_profit_cagr": implied if np.isfinite(implied) else None,
        "v31_expectation_gap_pct": expectation_gap if np.isfinite(expectation_gap) else None,
        "normalized_earnings": normalized,
        "realistic_growth": realistic,
        "market_implied_growth": implied if np.isfinite(implied) else None,
        "expectation_gap": expectation_gap if np.isfinite(expectation_gap) else None,
        "neutral_value": neutral,
        "price_to_neutral": ratio if np.isfinite(ratio) else None,
        "normalized_earnings_observation_count": _finite(
            latest.get("normalized_earnings_observation_count")
        ),
        "deduct_profit_quality_factor": _finite(latest.get("deduct_factor_round6")),
        "cash_conversion_ratio": _finite(latest.get("cash_conversion")),
        "realistic_growth_four_report_range": _finite(
            latest.get("realistic_growth_four_report_range")
        ),
        "implied_growth_status": implied_status,
        "eps_growth_3y_round6": _finite(latest.get("eps_growth_3y_round6")),
        "revenue_growth_3y_round6": _finite(latest.get("revenue_growth_3y_round6")),
        "v311_input_error": input_error,
    }


'''
    text = _replace_once(
        text,
        r"def current_inputs_from_panel\(.*?\n\ndef _invalid_row\(",
        current_inputs + "def _invalid_row(",
        "current_inputs_from_panel",
    )

    invalid_row = '''def _invalid_row(
    code: str,
    current_price: float | None,
    as_of: date,
    price_source: str,
    error: str,
    *,
    price_date: Any = None,
) -> dict[str, Any]:
    observed_price_date = _parse_observed_trade_date(price_date)
    return {
        "code": _normalize_code(code),
        "v311_expectation_input_status": "HOLD_REVIEW_INPUT_INCOMPLETE",
        "v311_expectation_policy_source": POLICY_SOURCE,
        "decision_date": as_of.isoformat(),
        "price_date": observed_price_date.isoformat() if observed_price_date is not None else "",
        "fund_available_date": "",
        "financial_report_date": "",
        "current_price_source": price_source,
        "v31_current_price": current_price,
        "v31_normalized_profit": None,
        "v31_normalized_profit_method": "",
        "v31_neutral_value": None,
        "v31_realistic_profit_cagr": None,
        "v31_market_implied_profit_cagr": None,
        "v31_expectation_gap_pct": None,
        "normalized_earnings": None,
        "realistic_growth": None,
        "market_implied_growth": None,
        "expectation_gap": None,
        "neutral_value": None,
        "price_to_neutral": None,
        "normalized_earnings_observation_count": None,
        "deduct_profit_quality_factor": None,
        "cash_conversion_ratio": None,
        "realistic_growth_four_report_range": None,
        "implied_growth_status": "INPUT_INCOMPLETE",
        "eps_growth_3y_round6": None,
        "revenue_growth_3y_round6": None,
        "v311_input_error": error,
    }


'''
    text = _replace_once(
        text,
        r"def _invalid_row\(.*?\n\ndef _fetch_with_retry\(",
        invalid_row + "def _fetch_with_retry(",
        "_invalid_row",
    )

    latest_close = '''def fetch_latest_close(code: str, *, as_of: date) -> tuple[float | None, str, str]:
    import akshare as ak

    start = (as_of - timedelta(days=30)).strftime("%Y%m%d")
    end = as_of.strftime("%Y%m%d")
    try:
        frame = ak.stock_zh_a_hist(
            symbol=_normalize_code(code),
            period="daily",
            start_date=start,
            end_date=end,
            adjust="qfq",
        )
        if frame is None or frame.empty:
            return None, "AKSHARE_QFQ_EMPTY", ""
        date_column = "日期" if "日期" in frame.columns else "date"
        close_column = "收盘" if "收盘" in frame.columns else "close"
        if date_column not in frame.columns or close_column not in frame.columns:
            return None, "AKSHARE_QFQ_SCHEMA_MISMATCH", ""
        local = frame[[date_column, close_column]].copy()
        local[date_column] = pd.to_datetime(local[date_column], errors="coerce").dt.date
        local[close_column] = pd.to_numeric(local[close_column], errors="coerce")
        local = local.dropna().loc[lambda x: x[date_column] <= as_of]
        if local.empty:
            return None, "AKSHARE_QFQ_NO_ASOF_PRICE", ""
        latest = local.sort_values(date_column).iloc[-1]
        observed = _parse_observed_trade_date(latest[date_column])
        return (
            float(latest[close_column]),
            "AKSHARE_QFQ_DAILY",
            observed.isoformat() if observed is not None else "",
        )
    except Exception as exc:  # network/provider boundary
        return None, f"AKSHARE_QFQ_ERROR:{type(exc).__name__}", ""


'''
    text = _replace_once(
        text,
        r"def fetch_latest_close\(.*?\n\ndef _source_price_map\(",
        latest_close + "def _source_price_map(",
        "fetch_latest_close",
    )

    source_map = '''def _source_price_map(rows: Iterable[Mapping[str, Any]]) -> dict[str, tuple[float, str]]:
    price_fields = (
        ("raw_latest_close", ("raw_latest_trade_date", "latest_trade_date", "price_date")),
        ("v31_current_price", ("price_date", "latest_trade_date", "raw_latest_trade_date")),
        ("current_price", ("price_date", "latest_trade_date", "raw_latest_trade_date")),
        ("close", ("trade_date", "price_date", "latest_trade_date")),
        ("latest_close", ("latest_trade_date", "price_date", "trade_date")),
    )
    result: dict[str, tuple[float, str]] = {}
    for row in rows:
        code = _normalize_code(row.get("code"))
        if not code:
            continue
        for price_field, date_fields in price_fields:
            value = _finite(row.get(price_field))
            if value is None or value <= 0:
                continue
            observed: date | None = None
            for date_field in date_fields:
                observed = _parse_observed_trade_date(row.get(date_field))
                if observed is not None:
                    break
            result[code] = (value, observed.isoformat() if observed is not None else "")
            break
    return result


def _normalize_price_loader_result(value: Any) -> tuple[float | None, str, str]:
    """Accept legacy 2-tuples but never infer a missing observation date."""
    if not isinstance(value, (tuple, list)):
        raise ValueError("price loader must return (price, source[, observed_date])")
    if len(value) == 2:
        price, source = value
        observed = ""
    elif len(value) == 3:
        price, source, observed = value
    else:
        raise ValueError("price loader must return 2 or 3 values")
    numeric = _finite(price)
    parsed = _parse_observed_trade_date(observed)
    return numeric, _text(source), parsed.isoformat() if parsed is not None else ""


'''
    text = _replace_once(
        text,
        r"def _source_price_map\(.*?\n\ndef build_current_expectation_rows\(",
        source_map + "def build_current_expectation_rows(",
        "_source_price_map",
    )

    build_rows = '''def build_current_expectation_rows(
    codes: Iterable[str],
    *,
    source_rows: Iterable[Mapping[str, Any]] = (),
    as_of: date,
    financial_loader=fetch_financial_panel,
    price_loader=fetch_latest_close,
) -> list[dict[str, Any]]:
    source_rows = list(source_rows)
    price_map = _source_price_map(source_rows)
    rows: list[dict[str, Any]] = []
    for code in dict.fromkeys(_normalize_code(value) for value in codes if _normalize_code(value)):
        upstream_price = price_map.get(code)
        price: float | None = upstream_price[0] if upstream_price is not None else None
        price_date = upstream_price[1] if upstream_price is not None else ""
        price_source = "UPSTREAM_RAW_LATEST_CLOSE" if price is not None else ""

        # An upstream price without an observed trade date is not production-safe.
        # Prefer an independently dated provider observation when available.
        if price is None or not price_date:
            try:
                fetched_price, fetched_source, fetched_date = _normalize_price_loader_result(
                    price_loader(code, as_of=as_of)
                )
                if fetched_price is not None and fetched_price > 0:
                    price = fetched_price
                    price_source = fetched_source
                    price_date = fetched_date
                elif price is None:
                    price_source = fetched_source
            except Exception as exc:
                if price is None:
                    price_source = f"PRICE_FETCH_ERROR:{type(exc).__name__}"

        try:
            panel = financial_loader(code)
            row = current_inputs_from_panel(
                code,
                panel,
                current_price=price,
                as_of=as_of,
                price_source=price_source,
                price_date=price_date,
            )
        except Exception as exc:  # provider failures are safe HOLD_REVIEW inputs
            row = _invalid_row(
                code,
                price,
                as_of,
                price_source,
                f"FINANCIAL_FETCH_ERROR:{type(exc).__name__}:{exc}",
                price_date=price_date,
            )
        rows.append(row)
    return rows


'''
    text = _replace_once(
        text,
        r"def build_current_expectation_rows\(.*?\n\ndef write_current_expectation_inputs\(",
        build_rows + "def write_current_expectation_inputs(",
        "build_current_expectation_rows",
    )

    forbidden = '"price_date": as_of.isoformat()'
    if forbidden in text:
        raise SystemExit("unsafe fabricated price_date assignment remains after migration")
    for required in (
        "PRICE_DATE_UNVERIFIED",
        "PRICE_DATE_AFTER_DECISION_DATE",
        "def _parse_observed_trade_date(",
        "def _normalize_price_loader_result(",
    ):
        if required not in text:
            raise SystemExit(f"migration invariant missing: {required}")

    if text == original:
        raise SystemExit("migration made no change")
    TARGET.write_text(text, encoding="utf-8")
    print(f"patched {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
