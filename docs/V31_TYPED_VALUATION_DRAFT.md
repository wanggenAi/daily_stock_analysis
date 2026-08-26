# V3.1 typed valuation engine — falsifiable draft

Status: **research only / not production V3.1**.

This draft is frozen before round-4 out-of-sample results are observed. It exists because round-3 diagnosis showed that one universal PE/PB geometric-mean neutral-value proxy is economically fragile across business types, especially growth technology. It does **not** change the V3.1 moat/hard-gate contract, BUY ladder, SELL ladder, transaction cost, or rebalance cadence.

## Frozen execution thresholds

- BUY_STAGED: price/neutral <= 0.85 -> up to 50% of name cap
- BUY_A_LEVEL: <= 0.75 -> up to 75% of name cap
- BUY_FULL_MARGIN: <= 0.65 -> up to 100% of name cap
- HOLD_NO_ADD: >= 1.00
- REDUCE_25: >= 1.20 -> max 75% of name cap
- REDUCE_50: >= 1.40 -> max 50% of name cap
- CORE_ONLY: >= 1.70 -> max 25% of name cap
- One-way cost: 0.10%
- Rebalance: month-end
- Historical anchor: trailing 756 trading-day median, shifted one day, minimum 252 observations
- Entry cost basis is never used by SELL.

## Economic valuation types

### 1. RESOURCE_ASSET

Use PB-relative-to-past-only-median as the historical proxy.

Reason: commodity/resource earnings are strongly cycle-dependent; a high or low TTM PE can be driven primarily by the commodity-profit cycle rather than by a durable change in asset value. In production, this type should ultimately be replaced by normalized earnings + NAV/resource-life/cost-curve work. PB is only a historical public-data proxy for the OOS falsification test.

### 2. STABLE_CASHFLOW

Use the existing geometric mean of positive PE-relative and PB-relative signals.

Reason: for mature, persistently profitable businesses, both earnings power and balance-sheet capital can contain information. If only one positive component is available, use the available component, matching the existing V3.1 historical proxy behavior.

### 3. GROWTH_TECH_CONSENSUS

PE and PB must agree in direction before valuation changes position size.

Let `pe_rel = PE(TTM) / past-only PE median` and `pb_rel = PB / past-only PB median`.

- If both are below 1.0, use `max(pe_rel, pb_rel)`. This means a BUY requires **both** signals to be cheap enough.
- If both are above 1.0, use `min(pe_rel, pb_rel)`. This means a SELL requires **both** signals to be expensive enough.
- If they straddle 1.0, set the effective ratio to 1.0 (HOLD / no valuation de-risking).
- If either required component is unavailable/non-positive, return no valuation signal (`HOLD_REVIEW`) rather than manufacturing a price target.

Reason: growth technology can experience structural changes in margin, product mix, R&D payoff and valuation regime. A PE/PB disagreement is therefore treated as uncertainty, not averaged away. This is a direction-consensus rule, not a fitted numeric threshold.

## Execution-engine correction

Round 4 uses the cash-constrained execution method diagnosed in round 3:

1. Execute stock-level de-risking requests first.
2. Calculate remaining cash.
3. If BUY requests exceed cash, scale **only the incremental BUY requests** pro-rata.
4. Never sell an unrelated HOLD/BUY-labelled position just because another stock requests capital.

The old all-target normalization engine is retained only as historical evidence; it is not used for the typed OOS headline.

## Round-4 anti-overfit contract

The round-4 universe is written into code before any round-4 output is observed. It contains only Shanghai/Shenzhen main-board A shares and none of the securities used in round 1 or round 2.

The typed router is compared with:

- the frozen universal V3.1 PE/PB geometric-mean proxy on the same fresh universe;
- literal initial-equal-dollar, zero-rebalance buy-and-hold;
- CSI 300.

No threshold or valuation type may be changed after observing round-4 results. Any later change requires another untouched OOS universe.

## Important limitation

This remains an execution/valuation-layer PIT test conditional on a fixed research universe. It is **not** a historical reconstruction of qualitative moat, predictability, demand, financial-safety, or earnings-authenticity gates.
