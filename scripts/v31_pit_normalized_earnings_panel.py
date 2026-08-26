from __future__ import annotations

"""Build strict-PIT historical earnings/cash-flow panels gated by NOTICE_DATE.

Research infrastructure only. No valuation multiple or BUY/SELL rule is changed.
The purpose is to reconstruct what normalized-earnings inputs were actually public
at each historical point in time before designing a new growth-company neutral-
value engine.
"""

from pathlib import Path
import json
import time

import akshare as ak
import numpy as np
import pandas as pd

OUT = Path("artifacts/v31_pit_normalized_earnings_panel")
UNIVERSE = {
    "600183": "生益科技",
    "002463": "沪电股份",
    "002916": "深南电路",
    "603160": "汇顶科技",
}


def em_symbol(code: str) -> str:
    return ("SH" if code.startswith("6") else "SZ") + code


def fetch_with_retry(func, *, symbol: str, tries: int = 3) -> pd.DataFrame:
    errors = []
    for i in range(tries):
        try:
            df = func(symbol=symbol)
            if df is None or df.empty:
                raise RuntimeError("empty dataframe")
            return df
        except Exception as exc:
            errors.append(f"{type(exc).__name__}: {exc}")
            time.sleep(1 + i)
    raise RuntimeError(" | ".join(errors))


def numeric(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df.columns:
        return pd.Series(np.nan, index=df.index, dtype=float)
    return pd.to_numeric(df[col], errors="coerce")


def prepare_statement(df: pd.DataFrame, value_cols: list[str], prefix: str) -> pd.DataFrame:
    need = ["REPORT_DATE", "NOTICE_DATE"] + [c for c in value_cols if c in df.columns]
    x = df[need].copy()
    x["REPORT_DATE"] = pd.to_datetime(x["REPORT_DATE"], errors="coerce").dt.normalize()
    x["NOTICE_DATE"] = pd.to_datetime(x["NOTICE_DATE"], errors="coerce").dt.normalize()
    x = x.dropna(subset=["REPORT_DATE", "NOTICE_DATE"]).sort_values(["REPORT_DATE", "NOTICE_DATE"])
    # If a source contains revised duplicates for one report period, the original
    # earliest notice is the defensible PIT availability boundary.
    x = x.drop_duplicates("REPORT_DATE", keep="first")
    rename = {c: f"{prefix}{c}" for c in value_cols if c in x.columns}
    x = x.rename(columns=rename)
    for c in rename.values():
        x[c] = pd.to_numeric(x[c], errors="coerce")
    return x


def ttm_from_cumulative(df: pd.DataFrame, col: str) -> pd.Series:
    """Convert Chinese cumulative report-period values to TTM without look-ahead.

    Annual: current annual cumulative value.
    Q1/H1/Q3: current cumulative + previous FY - previous-year same-period cumulative.
    All source rows are already historical reports; availability is handled separately
    by the max NOTICE_DATE across required statements.
    """
    by_date = {pd.Timestamp(d): v for d, v in zip(df["report_date"], df[col])}
    out = []
    for d, cur in zip(df["report_date"], df[col]):
        d = pd.Timestamp(d)
        if pd.isna(cur):
            out.append(np.nan)
            continue
        if d.month == 12 and d.day == 31:
            out.append(float(cur))
            continue
        prev_fy = pd.Timestamp(year=d.year - 1, month=12, day=31)
        prev_same = pd.Timestamp(year=d.year - 1, month=d.month, day=d.day)
        fy_val = by_date.get(prev_fy, np.nan)
        same_val = by_date.get(prev_same, np.nan)
        if pd.isna(fy_val) or pd.isna(same_val):
            out.append(np.nan)
        else:
            out.append(float(cur) + float(fy_val) - float(same_val))
    return pd.Series(out, index=df.index, dtype=float)


def build_company(code: str) -> pd.DataFrame:
    symbol = em_symbol(code)
    profit_raw = fetch_with_retry(ak.stock_profit_sheet_by_report_em, symbol=symbol)
    cash_raw = fetch_with_retry(ak.stock_cash_flow_sheet_by_report_em, symbol=symbol)

    profit_cols = ["PARENT_NETPROFIT", "DEDUCT_PARENT_NETPROFIT", "BASIC_EPS", "TOTAL_OPERATE_INCOME", "RESEARCH_EXPENSE"]
    cash_cols = ["NETCASH_OPERATE"]
    p = prepare_statement(profit_raw, profit_cols, "p_")
    c = prepare_statement(cash_raw, cash_cols, "c_")

    x = p.merge(c, on="REPORT_DATE", how="outer", suffixes=("_profit", "_cash")).sort_values("REPORT_DATE")
    x["profit_notice_date"] = pd.to_datetime(x.get("NOTICE_DATE_profit"), errors="coerce").dt.normalize()
    x["cash_notice_date"] = pd.to_datetime(x.get("NOTICE_DATE_cash"), errors="coerce").dt.normalize()
    # Strict availability requires both profit and cash-flow statements when both
    # are used. Use the later of the two notice dates.
    x["available_date"] = x[["profit_notice_date", "cash_notice_date"]].max(axis=1)
    x = x.rename(columns={"REPORT_DATE": "report_date"})

    for col in ["p_PARENT_NETPROFIT", "p_DEDUCT_PARENT_NETPROFIT", "p_BASIC_EPS", "p_TOTAL_OPERATE_INCOME", "p_RESEARCH_EXPENSE", "c_NETCASH_OPERATE"]:
        if col not in x.columns:
            x[col] = np.nan
        else:
            x[col] = pd.to_numeric(x[col], errors="coerce")

    x["ttm_parent_netprofit"] = ttm_from_cumulative(x, "p_PARENT_NETPROFIT")
    x["ttm_deduct_netprofit"] = ttm_from_cumulative(x, "p_DEDUCT_PARENT_NETPROFIT")
    x["ttm_basic_eps_approx"] = ttm_from_cumulative(x, "p_BASIC_EPS")
    x["ttm_revenue"] = ttm_from_cumulative(x, "p_TOTAL_OPERATE_INCOME")
    x["ttm_research_expense"] = ttm_from_cumulative(x, "p_RESEARCH_EXPENSE")
    x["ttm_operating_cashflow"] = ttm_from_cumulative(x, "c_NETCASH_OPERATE")

    x["cash_conversion"] = x["ttm_operating_cashflow"] / x["ttm_parent_netprofit"].replace(0, np.nan)
    x["deduct_quality"] = x["ttm_deduct_netprofit"] / x["ttm_parent_netprofit"].replace(0, np.nan)
    x["rd_intensity"] = x["ttm_research_expense"] / x["ttm_revenue"].replace(0, np.nan)

    # Slow-moving historical normalization diagnostics only; no valuation yet.
    x["normalized_eps_4q_median"] = x["ttm_basic_eps_approx"].rolling(4, min_periods=2).median()
    x["normalized_deduct_np_4q_median"] = x["ttm_deduct_netprofit"].rolling(4, min_periods=2).median()
    x["normalized_cfo_4q_median"] = x["ttm_operating_cashflow"].rolling(4, min_periods=2).median()

    x["code"] = code
    # The helper is reusable by later untouched OOS universes. A missing display
    # name must never block the financial calculations themselves.
    x["name"] = UNIVERSE.get(code, code)
    keep = [
        "code", "name", "report_date", "profit_notice_date", "cash_notice_date", "available_date",
        "p_PARENT_NETPROFIT", "p_DEDUCT_PARENT_NETPROFIT", "p_BASIC_EPS", "p_TOTAL_OPERATE_INCOME", "p_RESEARCH_EXPENSE", "c_NETCASH_OPERATE",
        "ttm_parent_netprofit", "ttm_deduct_netprofit", "ttm_basic_eps_approx", "ttm_revenue", "ttm_research_expense", "ttm_operating_cashflow",
        "cash_conversion", "deduct_quality", "rd_intensity",
        "normalized_eps_4q_median", "normalized_deduct_np_4q_median", "normalized_cfo_4q_median",
    ]
    return x[keep].sort_values("report_date").reset_index(drop=True)


def audit_panel(df: pd.DataFrame) -> dict:
    valid = df.dropna(subset=["available_date", "report_date"])
    bad_availability = valid[valid["available_date"] < valid["report_date"]]
    return {
        "code": str(df["code"].iloc[0]),
        "name": str(df["name"].iloc[0]),
        "rows": int(len(df)),
        "first_report": str(df["report_date"].min().date()) if df["report_date"].notna().any() else None,
        "last_report": str(df["report_date"].max().date()) if df["report_date"].notna().any() else None,
        "first_available": str(valid["available_date"].min().date()) if not valid.empty else None,
        "ttm_eps_ready": int(df["ttm_basic_eps_approx"].notna().sum()),
        "ttm_np_ready": int(df["ttm_parent_netprofit"].notna().sum()),
        "ttm_cfo_ready": int(df["ttm_operating_cashflow"].notna().sum()),
        "availability_before_report_errors": int(len(bad_availability)),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    audits = []
    errors = []
    panels = []
    for code, name in UNIVERSE.items():
        print(f"BUILD PIT FINANCIAL PANEL {code} {name}", flush=True)
        try:
            df = build_company(code)
            df.to_csv(OUT / f"financial_panel_{code}.csv", index=False)
            audits.append(audit_panel(df))
            panels.append(df)
        except Exception as exc:
            errors.append({"code": code, "name": name, "error": f"{type(exc).__name__}: {exc}"})

    audit_df = pd.DataFrame(audits)
    audit_df.to_csv(OUT / "audit_summary.csv", index=False)
    (OUT / "errors.json").write_text(json.dumps(errors, ensure_ascii=False, indent=2), encoding="utf-8")
    if panels:
        pd.concat(panels, ignore_index=True).to_csv(OUT / "all_financial_panels.csv", index=False)

    report = [
        "# Strict-PIT normalized-earnings input panel",
        "",
        "> Infrastructure only. No neutral-value formula and no BUY/SELL result is produced.",
        "",
        "## Availability contract",
        "",
        "- Historical observations are keyed by report period but become usable only on `available_date`.",
        "- `available_date = max(profit NOTICE_DATE, cash-flow NOTICE_DATE)` for metrics that combine both statements.",
        "- `UPDATE_DATE` is deliberately ignored because later database revisions can rewrite it.",
        "- Q1/H1/Q3 TTM values use current cumulative + previous FY - previous-year same-period cumulative.",
        "- TTM basic EPS is labelled approximate because weighted-average shares can change across periods.",
        "",
        "## Audit",
        "",
        audit_df.to_markdown(index=False) if not audit_df.empty else "No successful panels.",
        "",
        "## Errors",
        "",
        pd.DataFrame(errors).to_markdown(index=False) if errors else "None.",
        "",
        "## Next gate",
        "",
        "Only after these PIT inputs are validated should a normalized-earnings neutral-value formula be frozen. The formula must be specified before its next untouched OOS result is observed.",
    ]
    (OUT / "REPORT.md").write_text("\n".join(report), encoding="utf-8")
    print("\n".join(report), flush=True)


if __name__ == "__main__":
    main()
