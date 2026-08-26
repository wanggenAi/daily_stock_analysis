from __future__ import annotations

"""Probe public historical A-share financial-statement metadata for strict PIT use.

Research utility only. It does not compute a strategy result and does not modify
V3.1. The purpose is to determine whether public statement sources expose a
reliable report-publication/update timestamp that can gate historical normalized-
earnings calculations without look-ahead.
"""

from pathlib import Path
import json
import time

import akshare as ak
import pandas as pd

OUT = Path("artifacts/v31_pit_financial_probe")
PROBE = {
    "002463": "沪电股份",
    "603160": "汇顶科技",
}


def market_symbol(code: str) -> str:
    return ("sh" if code.startswith("6") else "sz") + code


def em_symbol(code: str) -> str:
    return ("SH" if code.startswith("6") else "SZ") + code


def summarize(df: pd.DataFrame, source: str, code: str, statement: str) -> dict:
    cols = [str(c) for c in df.columns]
    date_like = [c for c in cols if any(k.lower() in c.lower() for k in ["date", "日期", "报告日", "更新"])]
    earnings_like = [c for c in cols if any(k in c for k in ["净利润", "利润总额", "营业收入", "每股收益", "EPS", "BASIC_EPS", "PARENT_NETPROFIT"])]
    cash_like = [c for c in cols if any(k in c for k in ["经营活动", "现金流", "NETCASH", "经营现金"])]
    return {
        "source": source,
        "code": code,
        "name": PROBE[code],
        "statement": statement,
        "rows": len(df),
        "columns": cols,
        "date_like_columns": date_like,
        "earnings_like_columns": earnings_like,
        "cash_like_columns": cash_like,
    }


def save_sample(df: pd.DataFrame, path: Path) -> None:
    sample = df.head(12).copy()
    # Make object/date fields safe for CSV audit output.
    sample.to_csv(path, index=False)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    metadata: list[dict] = []
    errors: list[dict] = []

    for code, name in PROBE.items():
        print(f"PROBE {code} {name}", flush=True)

        # Sina three statements expose an `更新日期` field in current AKShare docs.
        for statement in ["利润表", "现金流量表", "资产负债表"]:
            try:
                df = ak.stock_financial_report_sina(stock=market_symbol(code), symbol=statement)
                metadata.append(summarize(df, "sina_financial_report", code, statement))
                save_sample(df, OUT / f"sina_{code}_{statement}.csv")
            except Exception as exc:
                errors.append({"source": "sina_financial_report", "code": code, "statement": statement, "error": f"{type(exc).__name__}: {exc}"})
            time.sleep(0.5)

        # Eastmoney report-period statements may expose NOTICE_DATE or equivalent.
        em_calls = [
            ("利润表", ak.stock_profit_sheet_by_report_em),
            ("现金流量表", ak.stock_cash_flow_sheet_by_report_em),
            ("资产负债表", ak.stock_balance_sheet_by_report_em),
        ]
        for statement, func in em_calls:
            try:
                df = func(symbol=em_symbol(code))
                metadata.append(summarize(df, "eastmoney_report_period", code, statement))
                save_sample(df, OUT / f"eastmoney_{code}_{statement}.csv")
            except Exception as exc:
                errors.append({"source": "eastmoney_report_period", "code": code, "statement": statement, "error": f"{type(exc).__name__}: {exc}"})
            time.sleep(0.5)

    (OUT / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (OUT / "errors.json").write_text(json.dumps(errors, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    rows = []
    for item in metadata:
        rows.append({
            "source": item["source"],
            "code": item["code"],
            "name": item["name"],
            "statement": item["statement"],
            "rows": item["rows"],
            "date_like_columns": " | ".join(item["date_like_columns"]),
            "earnings_like_columns": " | ".join(item["earnings_like_columns"]),
            "cash_like_columns": " | ".join(item["cash_like_columns"][:20]),
        })
    pd.DataFrame(rows).to_csv(OUT / "probe_summary.csv", index=False)

    report = [
        "# V3.1 PIT financial-data probe",
        "",
        "> Data plumbing audit only. No strategy or valuation threshold is tested here.",
        "",
        "The probe checks whether Sina/Eastmoney historical statement endpoints expose report/publication/update timestamps that can support strict point-in-time normalized-earnings reconstruction.",
        "",
        "## Source/field summary",
        "",
        pd.DataFrame(rows).to_markdown(index=False) if rows else "No successful statement source.",
        "",
        "## Errors",
        "",
        pd.DataFrame(errors).to_markdown(index=False) if errors else "None.",
        "",
        "## Gate",
        "",
        "A normalized-earnings backtest must not proceed unless each historical financial observation can be assigned a defensible availability timestamp. Report period alone is insufficient.",
    ]
    (OUT / "REPORT.md").write_text("\n".join(report), encoding="utf-8")
    print("\n".join(report), flush=True)


if __name__ == "__main__":
    main()
