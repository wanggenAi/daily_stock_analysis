# CURRENT_HOLDINGS

> Durable source of truth for the user's manually confirmed A-share holdings used by daily V3.1 holding review. This file does **not** connect to a broker and must only be updated from explicit user confirmation or user-provided transaction/position evidence.

## Confirmed holdings

Snapshot basis: user-provided broker position screenshots from 2026-08-25. Quantities and average costs below are treated as confirmed until the user reports a new buy/sell or provides a newer position screenshot.

| Code | Name | Quantity | Average cost (CNY) | Status | Evidence date |
| --- | --- | ---: | ---: | --- | --- |
| 603369 | 今世缘 | 300 | 29.5003 | HELD | 2026-08-25 |
| 001316 | 润贝航科 | 200 | 26.0955 | HELD | 2026-08-25 |
| 600276 | 恒瑞医药 | 100 | 46.4115 | HELD | 2026-08-25 |
| 600406 | 国电南瑞 | 200 | 23.1258 | HELD | 2026-08-25 |

## Daily review contract

Every trading-day pre-open holding review should read this file first and then refresh the latest verifiable market price, filings/material events, industry drivers, V3.1 hard-logic status and valuation evidence.

For each held security, output:

- `HOLD / ADD / REDUCE / EXIT`
- latest verified price and trade date
- unrealized P/L versus confirmed average cost when data is fresh
- long-term demand / moat / earnings-quality status
- current valuation and expectation gap
- add conditions
- reduce / exit / thesis-invalidation conditions
- confidence and any missing evidence

Never infer a transaction from price movement or a prior plan. A holding is changed only by explicit user confirmation or new position/transaction evidence.

## Change history

- 2026-08-26: initialized from the latest recoverable broker-position evidence supplied by the user on 2026-08-25.
