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
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd


VALUATION_COLUMNS = ("date", "pe", "pb", "ps", "market_cap")
FINANCIAL_COLUMNS = (
    "report_date",
    "disclosure_date",
    "debt_ratio",
    "net_profit",
    "operating_cash_flow",
    "roe",
    "gross_margin",
)


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
            try:
                raw_df = _quiet_call(
                    lambda indicator=indicator: ak.stock_zh_valuation_baidu(
                        symbol=normalize_code(code),
                        indicator=indicator,
                        period=period,
                    )
                )
            except Exception as exc:
                errors.append(f"stock_zh_valuation_baidu:{indicator}:{type(exc).__name__}")
                continue
            normalized = _normalize_baidu_valuation(raw_df, target_column)
            if normalized is not None and not normalized.empty:
                frames.append(normalized)
            else:
                errors.append(f"stock_zh_valuation_baidu:{indicator}:field_unavailable")

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
        cached = _read_cache(self.cache_dir, "financial", code)
        if cached is not None:
            return _normalize_financial_frame(cached), "cache", [], True

        errors: List[str] = []
        try:
            import akshare as ak
        except Exception as exc:
            return None, "none", [f"import_akshare:{type(exc).__name__}"], False

        start_year = max(1990, pd.Timestamp.today().year - int(years) - 2)
        raw_df = None
        provider = "none"
        try:
            raw_df = _quiet_call(
                lambda: ak.stock_financial_analysis_indicator(
                    symbol=normalize_code(code),
                    start_year=str(start_year),
                )
            )
            provider = "akshare.stock_financial_analysis_indicator"
        except Exception as exc:
            errors.append(f"stock_financial_analysis_indicator:{type(exc).__name__}")

        normalized = _normalize_financial_frame(raw_df)
        if normalized.empty:
            return None, "none", errors or ["financial_provider_unavailable"], False
        _write_cache(self.cache_dir, "financial", code, normalized)
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
        _first_column(local.columns, ("日期", "报告期", "REPORT_DATE", "report_date"))
        or _first_column(local.columns, ("date",))
    )
    if report_col is None:
        return pd.DataFrame(columns=FINANCIAL_COLUMNS)

    disclosure_col = _first_column(local.columns, ("NOTICE_DATE", "公告日期", "披露日期", "disclosure_date"))
    debt_col = _first_column(local.columns, ("资产负债率", "DEBT", "debt_ratio"))
    net_profit_col = _first_column(
        local.columns,
        ("净利润", "归母净利润", "PARENT_NETPROFIT", "NETPROFIT"),
        ("率", "同比", "增长率", "每股"),
    )
    operating_cash_col = _first_column(
        local.columns,
        ("经营活动产生的现金流量净额", "每股经营性现金流", "经营性现金流", "经营现金流", "NETCASH_OPERATE"),
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
    result["operating_cash_flow"] = local[operating_cash_col].map(_safe_float) if operating_cash_col else None
    result["roe"] = local[roe_col].map(_safe_float) if roe_col else None
    result["gross_margin"] = local[gross_margin_col].map(_safe_float) if gross_margin_col else None
    result = result.dropna(subset=["report_date"]).sort_values("report_date").drop_duplicates("report_date", keep="last")
    return result[list(FINANCIAL_COLUMNS)].reset_index(drop=True)
