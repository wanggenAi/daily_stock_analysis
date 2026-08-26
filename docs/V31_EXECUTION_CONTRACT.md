# V3.1 Execution Contract

> Production note: this BUY/SELL contract remains the base of
> `GEN_GE_V3_1_1_PRODUCTION`, but production now applies the promoted Valuation
> Confidence Gate documented in `docs/GEN_GE_PRODUCTION_MODEL.md`. LOW/INVALID
> confidence returns HOLD_REVIEW; all ratios and Hard Gate FAIL -> EXIT remain
> unchanged.

This document records the frozen execution semantics for the GenGe V3.1 research pipeline. The authoritative executable implementation is `src/strategies/genge_opportunity_discovery/selection_framework_v31.py`.

## Research universe vs execution universe

Research may cover the broader A-share market so that sector and company comparisons are not artificially narrowed.

Actual V3.1 BUY eligibility is restricted to the user's executable Shanghai/Shenzhen main-board universe:

- Shanghai: `600*`, `601*`, `603*`, `605*`
- Shenzhen: `000*`, `001*`, `002*`, `003*`

STAR Market, ChiNext, Beijing Stock Exchange and any other prefixes are research-only. They may appear in comparative research, but `v31_buy_ready` must remain false for them.

## Frozen qualification order

The execution order is:

1. predictability hard gate
2. long-term demand hard gate
3. moat / substitution difficulty hard gate
4. financial safety hard gate
5. earnings authenticity hard gate
6. A1/A2/A3 qualification and scoring completeness
7. normalized earnings
8. pessimistic / neutral / optimistic / extreme-stress valuation
9. market-implied growth vs realistic growth and expectation gap
10. risk-adjusted three-year CAGR and downside analysis
11. falsification / strongest bear-case review
12. margin of safety, portfolio exposure and market-position checks
13. execution-universe eligibility
14. only then may `v31_buy_ready` become true

Cheap valuation, technical position, popularity, legacy Tier-A labels or high quant scores can never bypass these gates.

## Price discipline

The neutral-value ratio is a reference diagnostic, not a substitute for industry-specific valuation work:

- `price / neutral <= 0.65`: extreme margin reference
- `<= 0.75`: A-level reference
- `<= 0.85`: staged-buy reference
- `<= 1.00`: wait / no-chase reference
- `<= 1.20`: overvalued reference
- `> 1.20`: severely priced-in reference

Formal BUY still requires every explicit V3.1 buy condition to pass.

## Frozen SELL / REDUCE discipline

### The sell basis is intrinsic value, never the holder's profit percentage

V3.1 MUST NOT issue `REDUCE` or `EXIT` merely because a position is up 20%, 40%, 80% or any other percentage from its purchase price. Entry cost, unrealized P/L, historical return since purchase and the psychological desire to "take profit" are not valuation inputs.

Before a valuation-driven sell decision, the research process must refresh the company's normalized earnings and the pessimistic / neutral / optimistic / extreme-stress valuation using the latest available financial and industry evidence. The decision basis is then:

`latest tradable market price / refreshed V3.1 neutral intrinsic value`

The denominator is therefore dynamic. If earnings, ROIC, asset value, commodity assumptions, competitive position or other model inputs improve, neutral value may rise and a stock can remain `HOLD` even after a large gain from the original entry price. Conversely, if normalized earnings or intrinsic value falls, a stock can require reduction even when the holder is not in profit.

Example: a position bought at 10 has a former neutral value of 15 and trades at 18. With a still-valid neutral value of 15, `18 / 15 = 1.20`, which reaches the first reduction band. If new evidence raises refreshed neutral value to 25, the same market price gives `18 / 25 = 0.72`; V3.1 must not reduce merely because the position is +80% versus cost.

### Valuation-driven de-risking ladder

When the hard logic remains intact and the valuation inputs are current and reviewable, staged de-risking is based on the latest `price / refreshed neutral value` ratio:

- below neutral value: `HOLD`
- `price / neutral >= 1.00`: `HOLD_NO_ADD`
- `>= 1.20`: `REDUCE_25`, target position 75% of the reference full position
- `>= 1.40`: `REDUCE_50`, target position 50%
- `>= 1.70`: `CORE_ONLY`, target position 25%

These thresholds are valuation ratios, not gains from cost basis.

### Reverse-implied expectation check

The neutral-value ladder is not the only analytical input. Every serious reduce review should also re-check the market-implied profit CAGR against realistic normalized profit growth and the V3.1 expectation-gap thesis. A price that requires implausibly high future earnings, margins, ROIC, commodity prices or market share strengthens a reduction case; a realistic implied expectation weakens it.

Market position, momentum and sentiment are secondary risk controls. They may affect timing or position sizing, but they cannot replace the refreshed valuation and expectation-gap analysis.

### Fundamental falsification overrides valuation

If any V3.1 hard logic gate changes to FAIL, valuation no longer protects the position: the contract emits `EXIT` with target position 0 and requires human review/execution. This can happen even below the original purchase price.

If valuation evidence is missing, stale or cannot be refreshed reliably, the safe semantic is `HOLD_REVIEW` / valuation refresh required. The system must not fabricate a mechanical profit-taking signal from the purchase price or recent涨幅.

## Explicit anti-patterns

A new session or implementation must reject all of the following as standalone SELL rules:

- "up 20% from my cost, therefore sell"
- "I have recovered my loss, therefore sell"
- "the stock doubled, therefore it must be expensive"
- "the chart is overbought, therefore intrinsic value no longer matters"
- "the old neutral value is still valid even though new financial/industry evidence materially changed"

The correct sequence is always: refresh fundamentals -> refresh normalized earnings -> refresh scenario valuation -> reverse-solve market expectations -> compare price with refreshed value -> decide `HOLD / REDUCE / CORE_ONLY / EXIT`.

## Human execution only

V3.1 is a research and decision-support contract. It does not connect to a broker and does not automatically place orders. `BUY`, `REDUCE` and `EXIT` outputs remain subject to human confirmation and current-data review.

## New-session handoff

A new AI session working on this repository should read this document and the authoritative Python contract before issuing actual BUY or SELL recommendations. It must never substitute purchase-cost return for intrinsic-value analysis. If chat instructions and old research notes disagree with the frozen code contract, the current frozen contract wins unless the user explicitly changes it.
