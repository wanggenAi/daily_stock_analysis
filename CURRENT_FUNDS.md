# CURRENT_FUNDS

> Durable source of truth for manually confirmed fund holdings used by the Investor Decision Dashboard. This file is independent from stock holdings and must only be updated from explicit user confirmation or user-provided fund position / transaction evidence.

## Confirmed funds

| Code | Name | Units | Average cost (CNY) | Status | Evidence date |
| --- | --- | ---: | ---: | --- | --- |

## Current status

As of 2026-09-02, the repository does not yet contain a sufficiently current, complete and explicitly confirmed fund-position snapshot that is safe to use as production decision input.

The dashboard must therefore show `LATEST_HOLDINGS_NOT_PERSISTED` for funds instead of guessing from old conversations, historical screenshots, watchlists or remembered positions.

When newer user-confirmed fund evidence is supplied, record each currently held fund in the table above. A fund that has been fully sold must be removed from `Confirmed funds` and retained only in change history if audit history is needed.

## Decision contract

- Fund holdings are a first-class part of the investor-facing portfolio review.
- Every daily investor brief should review confirmed funds together with confirmed stocks.
- Missing fund evidence must be visible; it must never silently become “no fund holdings”.
- No BUY / ADD / REDUCE / SELL instruction may be invented from an old or incomplete fund snapshot.
- This file does not connect to a broker and never enables auto-trading.
