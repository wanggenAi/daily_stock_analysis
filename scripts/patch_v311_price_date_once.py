from pathlib import Path
import re

SOURCE = Path("src/strategies/genge_opportunity_discovery/v311_current_expectation_inputs.py")
TEST = Path("tests/test_v311_price_date_provenance.py")

text = SOURCE.read_text(encoding="utf-8")

old_header = '''def current_inputs_from_panel(
    code: str,
    panel: pd.DataFrame,
    *,
    current_price: float | None,
    as_of: date,
    price_source: str,
) -> dict[str, Any]:'''
new_header = '''def current_inputs_from_panel(
    code: str,
    panel: pd.DataFrame,
    *,
    current_price: float | None,
    as_of: date,
    price_source: str,
    price_date: date | None = None,
) -> dict[str, Any]:'''
assert old_header in text
text = text.replace(old_header, new_header, 1)

text = text.replace(
    'return _invalid_row(code, current_price, as_of, price_source, "FINANCIAL_DATA_UNAVAILABLE")',
    'return _invalid_row(code, current_price, as_of, price_source, "FINANCIAL_DATA_UNAVAILABLE", price_date=price_date)',
    1,
)
text = text.replace(
    'return _invalid_row(code, current_price, as_of, price_source, "NO_FINANCIAL_REPORT_AVAILABLE_AS_OF_DATE")',
    'return _invalid_row(code, current_price, as_of, price_source, "NO_FINANCIAL_REPORT_AVAILABLE_AS_OF_DATE", price_date=price_date)',
    1,
)

old_price = '''    price = _finite(current_price)
    if price is None or price <= 0:
        implied, implied_status = np.nan, "INPUT_INCOMPLETE"
    else:
        implied, implied_status = solve_market_implied_growth(
            float(price), float(normalized) if normalized is not None else np.nan
        )'''
new_price = '''    price = _finite(current_price)
    price_date_error = ""
    if price is not None and price > 0:
        if price_date is None:
            price_date_error = "PRICE_DATE_UNVERIFIED"
        elif price_date > as_of:
            price_date_error = "PRICE_DATE_AFTER_DECISION_DATE"
    if price is None or price <= 0 or price_date_error:
        implied, implied_status = np.nan, "INPUT_INCOMPLETE"
    else:
        implied, implied_status = solve_market_implied_growth(
            float(price), float(normalized) if normalized is not None else np.nan
        )'''
assert old_price in text
text = text.replace(old_price, new_price, 1)

assert text.count('"price_date": as_of.isoformat(),') >= 2
text = text.replace(
    '"price_date": as_of.isoformat(),',
    '"price_date": price_date.isoformat() if price_date is not None else "",',
    2,
)

old_error = '"v311_input_error": "" if implied_status != "INPUT_INCOMPLETE" else "IMPLIED_GROWTH_INPUT_INCOMPLETE",'
new_error = '''"v311_input_error": (
            price_date_error
            if price_date_error
            else ("" if implied_status != "INPUT_INCOMPLETE" else "IMPLIED_GROWTH_INPUT_INCOMPLETE")
        ),'''
assert old_error in text
text = text.replace(old_error, new_error, 1)

old_invalid = '''def _invalid_row(
    code: str,
    current_price: float | None,
    as_of: date,
    price_source: str,
    error: str,
) -> dict[str, Any]:'''
new_invalid = '''def _invalid_row(
    code: str,
    current_price: float | None,
    as_of: date,
    price_source: str,
    error: str,
    *,
    price_date: date | None = None,
) -> dict[str, Any]:'''
assert old_invalid in text
text = text.replace(old_invalid, new_invalid, 1)

fetch_pattern = re.compile(
    r"def fetch_latest_close\(code: str, \*, as_of: date\) -> tuple\[float \| None, str\]:\n.*?\n\ndef _source_price_map\(rows: Iterable\[Mapping\[str, Any\]\]\) -> dict\[str, float\]:\n.*?\n    return result",
    re.S,
)
fetch_replacement = '''def fetch_latest_close(code: str, *, as_of: date) -> tuple[float | None, str, date | None]:
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
            return None, "AKSHARE_QFQ_EMPTY", None
        date_column = "日期" if "日期" in frame.columns else "date"
        close_column = "收盘" if "收盘" in frame.columns else "close"
        if date_column not in frame.columns or close_column not in frame.columns:
            return None, "AKSHARE_QFQ_SCHEMA_MISMATCH", None
        local = frame[[date_column, close_column]].copy()
        local[date_column] = pd.to_datetime(local[date_column], errors="coerce").dt.date
        local[close_column] = pd.to_numeric(local[close_column], errors="coerce")
        local = local.dropna().loc[lambda x: x[date_column] <= as_of]
        if local.empty:
            return None, "AKSHARE_QFQ_NO_ASOF_PRICE", None
        latest = local.sort_values(date_column).iloc[-1]
        return float(latest[close_column]), "AKSHARE_QFQ_DAILY", latest[date_column]
    except Exception as exc:  # network/provider boundary
        return None, f"AKSHARE_QFQ_ERROR:{type(exc).__name__}", None


def _parse_price_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.date()


def _source_price_observations(
    rows: Iterable[Mapping[str, Any]], *, as_of: date
) -> dict[str, tuple[float, date, str]]:
    price_fields = ("raw_latest_close", "v31_current_price", "current_price", "close", "latest_close")
    date_fields = ("price_date", "raw_latest_trade_date", "latest_trade_date", "trade_date", "date")
    result: dict[str, tuple[float, date, str]] = {}
    for row in rows:
        code = _normalize_code(row.get("code"))
        if not code:
            continue
        observed_date = next(
            (
                parsed
                for field in date_fields
                if (parsed := _parse_price_date(row.get(field))) is not None
            ),
            None,
        )
        if observed_date is None or observed_date > as_of:
            continue
        for field in price_fields:
            value = _finite(row.get(field))
            if value is not None and value > 0:
                result[code] = (value, observed_date, f"UPSTREAM_{field.upper()}")
                break
    return result'''
text, n = fetch_pattern.subn(fetch_replacement, text, count=1)
assert n == 1, f"fetch/source block replacement count={n}"

old_build = '''    source_rows = list(source_rows)
    price_map = _source_price_map(source_rows)
    rows: list[dict[str, Any]] = []
    for code in dict.fromkeys(_normalize_code(value) for value in codes if _normalize_code(value)):
        price = price_map.get(code)
        price_source = "UPSTREAM_RAW_LATEST_CLOSE" if price is not None else ""
        if price is None:
            price, price_source = price_loader(code, as_of=as_of)'''
new_build = '''    source_rows = list(source_rows)
    price_observations = _source_price_observations(source_rows, as_of=as_of)
    rows: list[dict[str, Any]] = []
    for code in dict.fromkeys(_normalize_code(value) for value in codes if _normalize_code(value)):
        observation = price_observations.get(code)
        if observation is not None:
            price, price_date, price_source = observation
        else:
            price, price_date, price_source = None, None, ""
            loaded = price_loader(code, as_of=as_of)
            if len(loaded) == 3:
                price, price_source, price_date = loaded
            else:
                price, price_source = loaded
                price_date = None'''
assert old_build in text
text = text.replace(old_build, new_build, 1)

old_call = '''            current_price=price,
            as_of=as_of,
            price_source=price_source,
        )'''
new_call = '''            current_price=price,
            as_of=as_of,
            price_source=price_source,
            price_date=price_date,
        )'''
assert old_call in text
text = text.replace(old_call, new_call, 1)

old_invalid_call = '''                price_source,
                f"FINANCIAL_FETCH_ERROR:{type(exc).__name__}:{exc}",
            )'''
new_invalid_call = '''                price_source,
                f"FINANCIAL_FETCH_ERROR:{type(exc).__name__}:{exc}",
                price_date=price_date,
            )'''
assert old_invalid_call in text
text = text.replace(old_invalid_call, new_invalid_call, 1)

SOURCE.write_text(text, encoding="utf-8")

TEST.write_text('''from datetime import date\n\nimport pandas as pd\n\nfrom src.strategies.genge_opportunity_discovery.v311_current_expectation_inputs import (\n    build_current_expectation_rows,\n    current_inputs_from_panel,\n)\n\n\ndef _panel():\n    return pd.DataFrame([{\n        "report_date": pd.Timestamp("2026-06-30"),\n        "available_date": pd.Timestamp("2026-08-20"),\n        "normalized_eps_round6": 1.0,\n        "realistic_growth_round6": 0.05,\n        "neutral_value_round6": 20.0,\n    }])\n\n\ndef test_actual_trade_date_is_not_fabricated_as_decision_date():\n    row = current_inputs_from_panel(\n        "600406", _panel(), current_price=20.0, as_of=date(2026, 8, 27),\n        price_source="TEST", price_date=date(2026, 8, 26),\n    )\n    assert row["decision_date"] == "2026-08-27"\n    assert row["price_date"] == "2026-08-26"\n    assert row["v311_input_error"] != "PRICE_DATE_UNVERIFIED"\n\n\ndef test_price_without_verified_date_fails_closed():\n    row = current_inputs_from_panel(\n        "600406", _panel(), current_price=20.0, as_of=date(2026, 8, 27),\n        price_source="TEST", price_date=None,\n    )\n    assert row["price_date"] == ""\n    assert row["v311_expectation_input_status"] == "HOLD_REVIEW_INPUT_INCOMPLETE"\n    assert row["v311_input_error"] == "PRICE_DATE_UNVERIFIED"\n\n\ndef test_price_after_decision_date_fails_closed():\n    row = current_inputs_from_panel(\n        "600406", _panel(), current_price=20.0, as_of=date(2026, 8, 27),\n        price_source="TEST", price_date=date(2026, 8, 28),\n    )\n    assert row["v311_expectation_input_status"] == "HOLD_REVIEW_INPUT_INCOMPLETE"\n    assert row["v311_input_error"] == "PRICE_DATE_AFTER_DECISION_DATE"\n\n\ndef test_undated_upstream_price_is_not_silently_reused():\n    calls = []\n    def financial_loader(_code):\n        return _panel()\n    def price_loader(code, *, as_of):\n        calls.append((code, as_of))\n        return 19.5, "LOADER", date(2026, 8, 26)\n    rows = build_current_expectation_rows(\n        ["600406"], source_rows=[{"code": "600406", "raw_latest_close": 99.0}],\n        as_of=date(2026, 8, 27), financial_loader=financial_loader, price_loader=price_loader,\n    )\n    assert calls\n    assert rows[0]["v31_current_price"] == 19.5\n    assert rows[0]["price_date"] == "2026-08-26"\n    assert rows[0]["current_price_source"] == "LOADER"\n''', encoding="utf-8")

print("price-date patch staged")
