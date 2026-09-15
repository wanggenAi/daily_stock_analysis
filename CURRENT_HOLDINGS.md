# CURRENT_HOLDINGS

> Durable source of truth for the user's manually confirmed A-share holdings used by daily GenGe V3.1.1 holding review. This file does **not** connect to a broker and must only be updated from explicit user confirmation or user-provided transaction/position evidence.

## Confirmed holdings

Snapshot basis: user-provided CITIC Securities broker position evidence at approximately **2026-09-15 10:32:50 CST**. The screenshot shows the same four positions and explicitly shows **today executed quantity = 0** for all four holdings, so no new transaction is inferred. All shares are available. Minor broker-displayed average-cost drift versus the prior durable values is treated as display/fee precision drift, not as a trade.

| Code | Name | Quantity | Average cost (CNY) | Status | Evidence date |
| --- | --- | ---: | ---: | --- | --- |
| 601318 | 中国平安 | 400 | 55.9658 | HELD | 2026-09-15 |
| 603993 | 洛阳钼业 | 1000 | 18.70980 | HELD | 2026-09-15 |
| 001316 | 润贝航科 | 200 | 25.7450 | HELD | 2026-09-15 |
| 600406 | 国电南瑞 | 200 | 23.1253 | HELD | 2026-09-15 |

## Recently closed positions

| Code | Name | Previous quantity | Previous average cost (CNY) | Exit evidence | Status | Evidence date |
| --- | --- | ---: | ---: | --- | --- | --- |
| 603369 | 今世缘 | 300 | 29.5003 | User explicitly confirmed on 2026-09-01 that the entire remaining position was sold and provided broker transaction evidence | CLOSED | 2026-09-01 |
| 600276 | 恒瑞医药 | 100 | 46.4105 | Broker position screenshot showed quantity 0 and user explicitly confirmed the sale | CLOSED | 2026-08-31 |

> Closed positions are not current holdings. Historical canonical decisions remain historical facts only and must not be projected onto the current portfolio.

## Daily review contract

Every trading-day holding review must refresh price, filings/material events, industry drivers, hard-logic status and valuation evidence. Production version `GEN_GE_V3_1_1_PRODUCTION` requires LOW/INVALID valuation confidence to return HOLD_REVIEW and keeps Hard Gate FAIL -> EXIT. Never infer a transaction from price movement or a prior plan.

## Latest manual holdings update — 2026-09-15 10:32:50 CST

Latest broker position evidence confirms:

- `603993 洛阳钼业`: **1,000 shares**, all **1,000 available**, broker-displayed average cost **18.7097 CNY**, displayed price **17.7400 CNY**, market value **17,740.00 CNY**, floating P/L **-983.81 CNY (-5.180%)**, and **today executed quantity 0**. Durable average cost remains **18.7098 CNY** because the 0.0001 difference is immaterial display/fee precision drift and there is explicit evidence of no trade today.
- `601318 中国平安`: **400 shares**, all **400 available**, broker-displayed average cost **55.9656 CNY**, displayed price **54.2500 CNY**, market value **21,700.00 CNY**, floating P/L **-703.49 CNY (-3.070%)**, and **today executed quantity 0**. Durable average cost remains **55.9658 CNY** because the 0.0002 difference is immaterial display/fee precision drift and there is explicit evidence of no trade today.
- `001316 润贝航科`: **200 shares**, all **200 available**, broker-displayed average cost **25.7450 CNY**, displayed price **28.4600 CNY**, market value **5,692.00 CNY**, floating P/L **+535.15 CNY (+10.550%)**, and **today executed quantity 0**.
- `600406 国电南瑞`: **200 shares**, all **200 available**, broker-displayed average cost **23.1253 CNY**, displayed price **22.0800 CNY**, market value **4,416.00 CNY**, floating P/L **-216.30 CNY (-4.520%)**, and **today executed quantity 0**.
- `603369 今世缘`: remains **0 shares / CLOSED**.
- `600276 恒瑞医药`: remains **0 shares / CLOSED**.

Account references displayed at approximately 10:32:50 CST are informational evidence only and must not be reused as fresh prices in later production decisions:

- Combined displayed stock market value: **49,548.00 CNY**.
- Available cash: **59,019.49 CNY**.
- Approximate account assets from displayed stock value plus cash: **108,567.49 CNY**.
- Approximate stock exposure: **45.64%**.

Current confirmed A-share holdings remain exactly **4 names / 1,800 shares total**: `601318 中国平安` 400, `603993 洛阳钼业` 1,000, `001316 润贝航科` 200, and `600406 国电南瑞` 200.

This manual portfolio update confirms state only. It records **no new transaction** and therefore must **not** consume, create, expand, or otherwise mutate any staged-add authorization or Formal/Canonical trading action. Any current `603993` staged-add authorization remains governed solely by the current finalized Canonical/production state and explicit later execution evidence.

## Prior confirmed snapshots

- **2026-09-11 11:00 CST:** `603993` increased from 900 to **1,000 shares** after a new 100-share buy. Broker-displayed average cost was **18.7098 CNY** and only 900 shares were available intraday, consistent with T+1. Available cash was **59,019.39 CNY**. Portfolio total: 4 names / 1,800 shares.
- **2026-09-10 10:56 CST:** `601318` increased from 300 to 400 shares after a fully filled 100-share buy at 55.2500 CNY; `603993` remained 900 shares at broker-displayed average cost 18.8163 CNY. Portfolio total: 4 names / 1,700 shares.
- **2026-09-07 14:49 CST:** `603993` increased from 800 to 900 shares after a 100-share add; broker-displayed average cost 18.9114 CNY. Portfolio total: 4 names / 1,600 shares.
- **2026-09-03 13:38 CST:** `603993` increased from 600 to 800 shares after a 200-share add; broker-displayed average cost 18.9753 CNY. Portfolio total: 4 names / 1,500 shares.
- **2026-09-01 13:33 CST:** current four-name portfolio was established with `601318` 300 shares and `603993` 600 shares, alongside `001316` 200 and `600406` 200. Portfolio total: 1,300 shares.
- **2026-09-01:** `603369 今世缘` fully closed.
- **2026-08-31:** `600276 恒瑞医药` fully closed.

Full historical screenshot-level detail remains available in Git history and in `data/manual_broker_snapshots/`; this file keeps the current durable state and transaction lineage compact so production parsers do not consume stale display prices as current inputs.

## Change history

- 2026-09-15 10:32:50 CST: refreshed from latest CITIC Securities broker-position evidence. Holdings remain **4 names / 1,800 shares** and all four rows show **today executed quantity 0**. `603993 洛阳钼业` remains **1,000 shares**; no new add is recorded. Available cash is **59,019.49 CNY**. This is state confirmation only and does not consume or create trading authority.
- 2026-09-11 11:00 CST: updated from CITIC Securities broker-position evidence. `603993 洛阳钼业` increased from **900 to 1,000 shares** after a new **100-share buy**; broker-displayed average cost became **18.7098 CNY** and only 900 shares were available intraday, consistent with T+1. Available cash was **59,019.39 CNY**. Current confirmed portfolio remained 4 names and totaled **1,800 shares**. This was holdings-state / transaction-evidence update only; the then-prior one-lot staged-add authorization was consumed.
- 2026-09-10 10:56 CST: `601318 中国平安` increased from 300 to 400 shares after a fully filled 100-share buy at 55.2500 CNY; broker-displayed average cost became 55.9658 CNY. Current portfolio totaled 1,700 shares.
- 2026-09-07 14:49 CST: `603993 洛阳钼业` increased from 800 to 900 shares after a 100-share add; broker-displayed average cost became 18.9114 CNY. Current portfolio totaled 1,600 shares.
- 2026-09-03 13:38 CST: `603993 洛阳钼业` increased from 600 to 800 shares after a 200-share add; broker-displayed average cost became 18.9753 CNY. Current portfolio totaled 1,500 shares.
- 2026-09-01 13:33 CST: added `601318 中国平安` 300 shares and `603993 洛阳钼业` 600 shares to the current portfolio; total 1,300 shares.
- 2026-09-01: `603369 今世缘` fully closed.
- 2026-08-31: `600276 恒瑞医药` fully closed.
