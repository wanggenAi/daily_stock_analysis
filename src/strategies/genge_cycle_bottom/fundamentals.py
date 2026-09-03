"""Public-data valuation and financial loaders for GenGe research.

The helpers in this module are deliberately fail-open: they return partial
public data when available and explicit provider errors when not available.
They never synthesize PE/PB/financial values.
"""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
import io
from pathlib import Path
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd


VALUATION_COLUMNS = ("date", "pe", "pb", "ps", "market_cap")
FINANCIAL_COLUMNS = (
    "report_date",
    "disclosure_date",
    "debt_ratio",
    "net_profit",
    "recurring_profit",
    "operating_cash_flow",
    "operating_cash_flow_per_share",
    "cash_conversion_ratio",
    "cash_conversion_ratio_basis",
    "roe",
    "gross_margin",
)
# Earlier financial caches could contain AkShare's per-share operating cash
# flow in the total-cash-flow field, omit the direct ratio, or divide Sina's
# already dimensionless OCF/net-profit ratio by 100. Never reuse them.
FINANCIAL_CACHE_KIND = "financial_v4_cashflow_units_ratio_semantics"
PROVIDER_RETRY_ATTEMPTS = 3
PROVIDER_RETRY_BACKOFF_SECONDS = 0.25


@dataclass
class FundamentalFetchResult:
    valuation_df: Optional[pd.DataFrame] = None
    financial_df: Optional[pd.DataFrame] = None
    valuation_provider: str = "none"
    financial_provider: str = "none"
    provider_errors: Dict[str, List[str]] = field(default_factory=dict)
    cache_hits: Dict[str, bool] = field(default_factory=dict)


def normalize_code(code: Any) -> str:
    text = str(code).strip().upper()
    if "." in text:
        base, suffix = text.rsplit(".", 1)
        if suffix in {"SH", "SZ", "BJ"} and base.isdigit():
            text = base
    for prefix in ("SH", "SZ", "BJ"):
        if text.startswith(prefix) and text[len(prefix):].isdigit():
            text = text[len(prefix):]
            break
    return text.zfill(6) if text.isdigit() else text


def market_symbol(code: str) -> str:
    normalized = normalize_code(code)
    if normalized.startswith(("6", "9")):
        return f"SH{normalized}"
    if normalized.startswith(("0", "2", "3")):
        return f"SZ{normalized}"
    if normalized.startswith(("4", "8")):
        return f"BJ{normalized}"
    return normalized


def _period_for_years(years: int) -> str:
    if years >= 10:
        return "近十年"
    if years >= 5:
        return "近五年"
    if years >= 3:
        return "近三年"
    return "近一年"


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    text = str(value).strip().replace(",", "").replace("%", "")
    if not text or text.lower() in {"nan", "none", "null", "-"}:
        return None
    try:
        number = float(text)
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return number


def _first_column(
    columns: Iterable[Any],
    includes: Iterable[str],
    excludes: Iterable[str] = (),
) -> Optional[str]:
    include_tokens = tuple(includes)
    exclude_tokens = tuple(excludes)
    for column in columns:
        text = str(column)
        if include_tokens and not any(token in text for token in include_tokens):
            continue
        if exclude_tokens and any(token in text for token in exclude_tokens):
            continue
        return str(column)
    return None


def _cache_path(cache_dir: Path, kind: str, code: str) -> Path:
    return cache_dir / kind / f"{normalize_code(code)}.csv"


def _read_cache(cache_dir: Path, kind: str, code: str) -> Optional[pd.DataFrame]:
    path = _cache_path(cache_dir, kind, code)
    if not path.exists():
        return None
    try:
        df = pd.read_csv(path)
    except Exception:
        return None
    return df if not df.empty else None


def _write_cache(cache_dir: Path, kind: str, code: str, df: pd.DataFrame) -> None:
    if df is None or df.empty:
        return
    path = _cache_path(cache_dir, kind, code)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def _quiet_call(fn):
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        return fn()


def _retry_frame_call(
    fn,
    normalizer,
    *,
    label: str,
    errors: List[str],
    attempts: int = PROVIDER_RETRY_ATTEMPTS,
) -> pd.DataFrame:
    """Return the first non-empty normalized provider frame after bounded retries."""

    last = pd.DataFrame()
    total_attempts = max(1, int(attempts))
    for attempt in range(1, total_attempts + 1):
        try:
            raw = _quiet_call(fn)
            normalized = normalizer(raw)
        except Exception as exc:
            errors.append(f"{label}:attempt_{attempt}:{type(exc).__name__}")
        else:
            if normalized is not None and not normalized.empty:
                return normalized
            last = normalized if isinstance(normalized, pd.DataFrame) else pd.DataFrame()
            errors.append(f"{label}:attempt_{attempt}:field_unavailable")
        if attempt < total_attempts:
            time.sleep(PROVIDER_RETRY_BACKOFF_SECONDS * attempt)
    return last


def _financial_frame_has_core_amounts(frame: Optional[pd.DataFrame]) -> bool:
    if frame is None or frame.empty:
        return False
    if "net_profit" not in frame.columns or "operating_cash_flow" not in frame.columns:
        return False
    local = frame.copy()
    local["report_date"] = pd.to_datetime(local.get("report_date"), errors="coerce")
    local = local.dropna(subset=["report_date"]).sort_values("report_date")
    if local.empty:
        return False
    latest = local.iloc[-1]
    return bool(
        _safe_float(latest.get("net_profit")) is not None
        and _safe_float(latest.get("operating_cash_flow")) is not None
    )


def _merge_financial_frames(*frames: Optional[pd.DataFrame]) -> pd.DataFrame:
    """Merge reported financial evidence without fabricating missing values.

    Source order is authoritative for ordinary fields. Disclosure date is the
    maximum known date across the components used for a report period so PIT
    selection cannot use a combined row before every contributing statement was
    public.
    """

    parts: List[pd.DataFrame] = []
    for priority, frame in enumerate(frames):
        normalized = _normalize_financial_frame(frame)
        if normalized.empty:
            continue
        local = normalized.copy()
        local["_source_priority"] = priority
        local = local.dropna(axis="columns", how="all")
        parts.append(local)
    if not parts:
        return pd.DataFrame(columns=FINANCIAL_COLUMNS)

    combined = pd.concat(parts, ignore_index=True).reindex(
        columns=[*FINANCIAL_COLUMNS, "_source_priority"]
    )
    rows: List[Dict[str, Any]] = []
    numeric_columns = (
        "debt_ratio",
        "net_profit",
        "recurring_profit",
        "operating_cash_flow",
        "operating_cash_flow_per_share",
        "roe",
        "gross_margin",
    )
    for report_date, group in combined.groupby("report_date", sort=True):
        group = group.sort_values("_source_priority", kind="stable")
        row: Dict[str, Any] = {"report_date": report_date}
        disclosures = pd.to_datetime(group["disclosure_date"], errors="coerce").dropna()
        row["disclosure_date"] = disclosures.max().date() if not disclosures.empty else None
        for column in numeric_columns:
            value = None
            for candidate in group[column].tolist():
                parsed = _safe_float(candidate)
                if parsed is not None:
                    value = parsed
                    break
            row[column] = value

        row["cash_conversion_ratio"] = None
        row["cash_conversion_ratio_basis"] = ""
        for _, source_row in group.iterrows():
            parsed_ratio = _safe_float(source_row.get("cash_conversion_ratio"))
            if parsed_ratio is None:
                continue
            row["cash_conversion_ratio"] = parsed_ratio
            row["cash_conversion_ratio_basis"] = str(
                source_row.get("cash_conversion_ratio_basis") or ""
            )
            break
        rows.append(row)

    return pd.DataFrame(rows, columns=FINANCIAL_COLUMNS).reset_index(drop=True)


class PublicFundamentalLoader:
    """Load public A-share valuation/financial frames with optional cache."""

    def __init__(self, cache_dir: str | Path = "data/cache/genge_fundamentals"):
        self.cache_dir = Path(cache_dir)

    def load(
        self,
        code: str,
        *,
        years: int,
        fetch_valuation: bool,
        fetch_financial: bool,
    ) -> FundamentalFetchResult:
        result = FundamentalFetchResult()
        normalized = normalize_code(code)
        if fetch_valuation:
            result.valuation_df, result.valuation_provider, errors, cache_hit = self.load_valuation(normalized, years=years)
            result.cache_hits["valuation"] = cache_hit
            if errors:
                result.provider_errors["valuation"] = errors
        if fetch_financial:
            result.financial_df, result.financial_provider, errors, cache_hit = self.load_financial(normalized, years=years)
            result.cache_hits["financial"] = cache_hit
            if errors:
                result.provider_errors["financial"] = errors
        return result

    def load_valuation(self, code: str, *, years: int) -> Tuple[Optional[pd.DataFrame], str, List[str], bool]:
        cached = _read_cache(self.cache_dir, "valuation", code)
        if cached is not None:
            return _normalize_valuation_frame(cached), "cache", [], True

        errors: List[str] = []
        try:
            import akshare as ak
        except Exception as exc:
            return None, "none", [f"import_akshare:{type(exc).__name__}"], False

        frames: List[pd.DataFrame] = []
        period = _period_for_years(years)
        indicator_map = {
            "市盈率(TTM)": "pe",
            "市净率": "pb",
            "总市值": "market_cap",
        }
        for indicator, target_column in indicator_map.items():
            normalized = _retry_frame_call(
                lambda indicator=indicator: ak.stock_zh_valuation_baidu(
                    symbol=normalize_code(code),
                    indicator=indicator,
                    period=period,
                ),
                lambda raw, target_column=target_column: _normalize_baidu_valuation(
                    raw, target_column
                ),
                label=f"stock_zh_valuation_baidu:{indicator}",
                errors=errors,
            )
            if not normalized.empty:
                frames.append(normalized)

        if not frames:
            return None, "none", errors or ["valuation_provider_unavailable"], False

        merged = frames[0]
        for frame in frames[1:]:
            merged = merged.merge(frame, on="date", how="outer")
        merged = _normalize_valuation_frame(merged)
        if merged.empty:
            return None, "none", errors or ["valuation_field_unavailable"], False
        _write_cache(self.cache_dir, "valuation", code, merged)
        return merged, "akshare.stock_zh_valuation_baidu", errors, False

    def load_financial(self, code: str, *, years: int) -> Tuple[Optional[pd.DataFrame], str, List[str], bool]:
        cached = _read_cache(self.cache_dir, FINANCIAL_CACHE_KIND, code)
        if cached is not None:
            normalized_cache = _normalize_financial_frame(cached)
            if _financial_frame_has_core_amounts(normalized_cache):
                return normalized_cache, "cache", [], True

        errors: List[str] = []
        try:
            import akshare as ak
        except Exception as exc:
            return None, "none", [f"import_akshare:{type(exc).__name__}"], False

        start_year = max(1990, pd.Timestamp.today().year - int(years) - 2)
        primary = _retry_frame_call(
            lambda: ak.stock_financial_analysis_indicator(
                symbol=normalize_code(code),
                start_year=str(start_year),
            ),
            _normalize_financial_frame,
            label="stock_financial_analysis_indicator",
            errors=errors,
        )
        provider = "akshare.stock_financial_analysis_indicator" if not primary.empty else "none"

        # The indicator endpoint can be non-empty while containing only ratios or
        # per-share cash flow. If it lacks reported net-profit and total OCF
        # amounts, recover them from the separate Eastmoney income/cash-flow
        # statements. These are public reported values, not synthesized values.
        statement_bundle = pd.DataFrame(columns=FINANCIAL_COLUMNS)
        if not _financial_frame_has_core_amounts(primary):
            symbol = market_symbol(code)
            statement_frames: List[pd.DataFrame] = []
            for function_name in (
                "stock_profit_sheet_by_report_em",
                "stock_cash_flow_sheet_by_report_em",
            ):
                function = getattr(ak, function_name, None)
                if function is None:
                    errors.append(f"{function_name}:provider_function_unavailable")
                    continue
                statement = _retry_frame_call(
                    lambda function=function: function(symbol=symbol),
                    _normalize_financial_frame,
                    label=function_name,
                    errors=errors,
                )
                if not statement.empty:
                    statement_frames.append(statement)
            statement_bundle = _merge_financial_frames(*statement_frames)

        normalized = _merge_financial_frames(primary, statement_bundle)
        if normalized.empty:
            return None, "none", errors or ["financial_provider_unavailable"], False
        if not statement_bundle.empty:
            provider = (
                "akshare.stock_financial_analysis_indicator+akshare.eastmoney_statements"
                if not primary.empty
                else "akshare.eastmoney_statements"
            )
        # A ratios-only/one-statement partial result remains useful evidence for
        # this cycle, but must not become a sticky cache hit that suppresses
        # recovery in the next cycle.
        if _financial_frame_has_core_amounts(normalized):
            _write_cache(self.cache_dir, FINANCIAL_CACHE_KIND, code, normalized)
        else:
            errors.append("financial_core_amounts_incomplete_after_recovery")
        return normalized, provider, errors, False


def _normalize_baidu_valuation(raw_df: Any, target_column: str) -> Optional[pd.DataFrame]:
    if not isinstance(raw_df, pd.DataFrame) or raw_df.empty:
        return None
    if "date" not in raw_df.columns or "value" not in raw_df.columns:
        return None
    local = raw_df[["date", "value"]].copy()
    local["date"] = pd.to_datetime(local["date"], errors="coerce").dt.date
    local[target_column] = local["value"].map(_safe_float)
    local = local.dropna(subset=["date", target_column])
    return local[["date", target_column]]


def _normalize_valuation_frame(df: Optional[pd.DataFrame]) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=VALUATION_COLUMNS)
    local = df.copy()
    if "date" not in local.columns:
        return pd.DataFrame(columns=VALUATION_COLUMNS)
    local["date"] = pd.to_datetime(local["date"], errors="coerce").dt.date
    for column in VALUATION_COLUMNS:
        if column == "date":
            continue
        if column not in local.columns:
            local[column] = None
        local[column] = local[column].map(_safe_float)
    local = local.dropna(subset=["date"]).sort_values("date").drop_duplicates("date", keep="last")
    return local[list(VALUATION_COLUMNS)].reset_index(drop=True)


def _normalize_financial_frame(df: Optional[pd.DataFrame]) -> pd.DataFrame:
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame(columns=FINANCIAL_COLUMNS)
    local = df.copy()
    report_col = (
        _first_column(local.columns, ("日期", "报告期", "报告日", "REPORT_DATE", "report_date"))
        or _first_column(local.columns, ("date",))
    )
    if report_col is None:
        return pd.DataFrame(columns=FINANCIAL_COLUMNS)

    disclosure_col = _first_column(
        local.columns,
        ("NOTICE_DATE", "公告日期", "披露日期", "更新日期", "disclosure_date"),
    )
    debt_col = _first_column(local.columns, ("资产负债率", "DEBT", "debt_ratio"))
    net_profit_col = _first_column(
        local.columns,
        ("净利润", "归母净利润", "PARENT_NETPROFIT", "NETPROFIT", "net_profit"),
        ("率", "同比", "增长率", "每股", "扣除非经常性", "扣非"),
    )
    recurring_profit_col = _first_column(
        local.columns,
        ("扣除非经常性损益后的净利润", "扣非净利润", "recurring_profit"),
        ("同比", "增长率", "增长", "增速", "每股"),
    )

    # Unit contract: only a true total cash-flow amount may populate
    # operating_cash_flow. AkShare's 每股经营性现金流 is yuan/share and is kept
    # separately for audit; it must never be divided by a total RMB profit.
    operating_cash_col = _first_column(
        local.columns,
        (
            "经营活动产生的现金流量净额",
            "经营活动现金流量净额",
            "NETCASH_OPERATE",
            "total_operating_cash_flow",
            "operating_cash_flow",
        ),
        ("每股", "PER_SHARE", "per_share", "比率", "比例", "率", "%"),
    )
    operating_cash_per_share_col = _first_column(
        local.columns,
        ("每股经营性现金流", "operating_cash_flow_per_share"),
        ("比率", "比例"),
    )

    # Sina labels this field with "(%)" but publishes it as the direct
    # dimensionless OCF/net-profit multiple: e.g. 2026Q1 今世缘 is 1.5263,
    # matching 2.1138bn / 1.3849bn. AKShare passes the value through unchanged.
    normalized_cash_ratio_col = (
        "cash_conversion_ratio" if "cash_conversion_ratio" in local.columns else None
    )
    provider_cash_ratio_col = None
    if normalized_cash_ratio_col is None:
        provider_cash_ratio_col = _first_column(
            local.columns,
            (
                "经营现金净流量与净利润的比率",
                "经营现金流量净额与净利润的比率",
                "经营活动现金流量净额与净利润的比率",
                "operating_cash_flow_to_net_profit",
            ),
            ("同比", "增长"),
        )

    roe_col = _first_column(local.columns, ("净资产收益率", "加权净资产收益率", "ROE"), ("同比",))
    gross_margin_col = _first_column(local.columns, ("销售毛利率", "毛利率", "GROSSPROFIT_MARGIN"), ("同比",))

    result = pd.DataFrame()
    result["report_date"] = pd.to_datetime(local[report_col], errors="coerce").dt.date
    if disclosure_col is not None:
        result["disclosure_date"] = pd.to_datetime(local[disclosure_col], errors="coerce").dt.date
    else:
        result["disclosure_date"] = None
    result["debt_ratio"] = local[debt_col].map(_safe_float) if debt_col else None
    result["net_profit"] = local[net_profit_col].map(_safe_float) if net_profit_col else None
    result["recurring_profit"] = local[recurring_profit_col].map(_safe_float) if recurring_profit_col else None
    result["operating_cash_flow"] = local[operating_cash_col].map(_safe_float) if operating_cash_col else None
    result["operating_cash_flow_per_share"] = (
        local[operating_cash_per_share_col].map(_safe_float)
        if operating_cash_per_share_col
        else None
    )
    if normalized_cash_ratio_col is not None:
        result["cash_conversion_ratio"] = local[normalized_cash_ratio_col].map(_safe_float)
        if "cash_conversion_ratio_basis" in local.columns:
            result["cash_conversion_ratio_basis"] = local["cash_conversion_ratio_basis"].fillna("")
        else:
            result["cash_conversion_ratio_basis"] = "NORMALIZED_CACHED_RATIO"
    elif provider_cash_ratio_col is not None:
        result["cash_conversion_ratio"] = local[provider_cash_ratio_col].map(_safe_float)
        result["cash_conversion_ratio_basis"] = "PROVIDER_OCF_TO_NET_PROFIT_RATIO"
    else:
        result["cash_conversion_ratio"] = None
        result["cash_conversion_ratio_basis"] = ""
    result["roe"] = local[roe_col].map(_safe_float) if roe_col else None
    result["gross_margin"] = local[gross_margin_col].map(_safe_float) if gross_margin_col else None
    result = result.dropna(subset=["report_date"]).sort_values("report_date").drop_duplicates("report_date", keep="last")
    return result[list(FINANCIAL_COLUMNS)].reset_index(drop=True)
