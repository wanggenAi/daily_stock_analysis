# CURRENT_HOLDINGS

> Durable source of truth for the user's manually confirmed A-share holdings used by daily GenGe V3.1.1 holding review. This file does **not** connect to a broker and must only be updated from explicit user confirmation or user-provided transaction/position evidence.

## Confirmed holdings

Snapshot basis: user-provided CITIC Securities broker position evidence at approximately **2026-09-11 11:00 CST**. The screenshot confirms `603993 洛阳钼业` increased from 900 to **1,000 shares** after a new 100-share buy. Broker-displayed average cost is **18.7098 CNY** and only 900 shares are available intraday, consistent with the newly purchased 100 shares being T+1 unavailable. Other holding quantities remain unchanged.

| Code | Name | Quantity | Average cost (CNY) | Status | Evidence date |
| --- | --- | ---: | ---: | --- | --- |
| 601318 | 中国平安 | 400 | 55.9658 | HELD | 2026-09-11 |
| 603993 | 洛阳钼业 | 1000 | 18.70980 | HELD | 2026-09-11 |
| 001316 | 润贝航科 | 200 | 25.7450 | HELD | 2026-09-11 |
| 600406 | 国电南瑞 | 200 | 23.1253 | HELD | 2026-09-11 |

## Recently closed positions

| Code | Name | Previous quantity | Previous average cost (CNY) | Exit evidence | Status | Evidence date |
| --- | --- | ---: | ---: | --- | --- | --- |
| 603369 | 今世缘 | 300 | 29.5003 | User explicitly confirmed on 2026-09-01 that the entire remaining position was sold and provided broker transaction evidence | CLOSED | 2026-09-01 |
| 600276 | 恒瑞医药 | 100 | 46.4105 | Broker position screenshot showed quantity 0 and user explicitly confirmed the sale | CLOSED | 2026-08-31 |

> Closed positions are not current holdings. Historical canonical decisions remain historical facts only and must not be projected onto the current portfolio.

## Daily review contract

Every trading-day holding review must refresh price, filings/material events, industry drivers, hard-logic status and valuation evidence. Production version `GEN_GE_V3_1_1_PRODUCTION` requires LOW/INVALID valuation confidence to return HOLD_REVIEW and keeps Hard Gate FAIL -> EXIT. Never infer a transaction from price movement or a prior plan.

## Latest manual holdings update — 2026-09-11 11:00 CST

Latest broker position evidence confirms:

- `603993 洛阳钼业`: **1,000 shares**, broker-displayed average cost **18.7098 CNY**; **900 shares available**. The previous balance is 900 shares and the reference holding is 1,000 shares, confirming a **new 100-share buy today** that is T+1 unavailable intraday.
- `601318 中国平安`: **400 shares**, prior durable average cost **55.9658 CNY**, all 400 shares available. The current broker screen displays 55.9656 CNY; the durable source keeps the previously confirmed 55.9658 CNY because the 0.0002 difference is immaterial broker-display/rounding drift rather than a new transaction.
- `001316 润贝航科`: **200 shares**, broker-displayed average cost **25.7450 CNY**, all 200 shares available.
- `600406 国电南瑞`: **200 shares**, broker-displayed average cost **23.1253 CNY**, all 200 shares available.
- `603369 今世缘`: remains **0 shares / CLOSED**.
- `600276 恒瑞医药`: remains **0 shares / CLOSED**.

Displayed portfolio and market references at approximately 11:00 CST are informational evidence only and must not be reused as fresh prices in later production decisions:

- `603993 洛阳钼业`: displayed price **17.6900 CNY**, market value **17,690.00 CNY**, floating P/L **-1,033.88 CNY (-5.45%)**.
- `601318 中国平安`: displayed price **55.2000 CNY**, market value **22,080.00 CNY**, floating P/L **-323.79 CNY (-1.37%)**.
- `001316 润贝航科`: displayed price **29.1900 CNY**, market value **5,838.00 CNY**, floating P/L **+681.08 CNY (+13.38%)**.
- `600406 国电南瑞`: displayed price **22.2900 CNY**, market value **4,458.00 CNY**, floating P/L **-174.32 CNY (-3.61%)**.
- Combined displayed stock market value: **50,066.00 CNY**.
- Available cash: **59,019.39 CNY**.
- Approximate account assets from displayed stock value plus cash: **109,085.39 CNY**.
- Approximate stock exposure: **45.90%**.

Current confirmed A-share holdings are exactly **4 names / 1,800 shares total**: `601318 中国平安` 400, `603993 洛阳钼业` 1,000, `001316 润贝航科` 200, and `600406 国电南瑞` 200.

This manual portfolio update changes holdings state only. It records the user's 100-share `603993` purchase as transaction evidence but does **not** retroactively convert it into a new canonical Formal ADD, does not authorize another add, and does not alter the GenGe V3.1.1 frozen production contract, Confidence Gate, Hard Gate, BUY/SELL thresholds, SELL rationale gate, canonical authority, or no-auto-trade policy. Any finalized canonical produced before this holdings update is stale for current-portfolio holdings reconciliation until a new authorized production cycle consumes the 1,000-share `603993` state.

## Prior confirmed snapshots

- **2026-09-10 10:56 CST:** `601318` increased from 300 to 400 shares after a fully filled 100-share buy at 55.2500 CNY; `603993` remained 900 shares at broker-displayed average cost 18.8163 CNY. Portfolio total: 4 names / 1,700 shares.
- **2026-09-07 14:49 CST:** `603993` increased from 800 to 900 shares after a 100-share add; broker-displayed average cost 18.9114 CNY. Portfolio total: 4 names / 1,600 shares.
- **2026-09-03 13:38 CST:** `603993` increased from 600 to 800 shares after a 200-share add; broker-displayed average cost 18.9753 CNY. Portfolio total: 4 names / 1,500 shares.
- **2026-09-01 13:33 CST:** current four-name portfolio was established with `601318` 300, `603993` 600, `001316` 200, `600406` 200. Portfolio total: 1,300 shares.
- **2026-09-01:** `603369 今世缘` fully closed.
- **2026-08-31:** `600276 恒瑞医药` fully closed.

Full historical screenshot-level detail remains available in Git history; this file keeps the current durable state and transaction lineage compact so production parsers do not consume stale display prices as current inputs.

## Change history

- 2026-09-11 11:00 CST: updated from latest CITIC Securities broker-position evidence. `603993 洛阳钼业` increased from **900 to 1,000 shares** after a new **100-share buy**; broker-displayed average cost is now **18.7098 CNY** and only 900 shares are available intraday, consistent with T+1. Available cash is **59,019.39 CNY**. Current confirmed portfolio remains 4 names and now totals **1,800 shares**. This is a holdings-state / transaction-evidence update only; the prior one-lot staged-add authorization is consumed and no second add is created by this file.
- 2026-09-10 10:56 CST: `601318 中国平安` increased from 300 to 400 shares after a fully filled 100-share buy at 55.2500 CNY; broker-displayed average cost became 55.9658 CNY. Current portfolio totaled 1,700 shares.
- 2026-09-07 14:49 CST: `603993 洛阳钼业` increased from 800 to 900 shares after a 100-share add; broker-displayed average cost became 18.9114 CNY. Current portfolio totaled 1,600 shares.
- 2026-09-03 13:38 CST: `603993 洛阳钼业` increased from 600 to 800 shares after a 200-share add; broker-displayed average cost became 18.9753 CNY. Current portfolio totaled 1,500 shares.
- 2026-09-01 13:33 CST: added `601318 中国平安` 300 shares and `603993 洛阳钼业` 600 shares to the current portfolio; total 1,300 shares.
- 2026-09-01: `603369 今世缘` fully closed.
- 2026-08-31: `600276 恒瑞医药` fully closed.
