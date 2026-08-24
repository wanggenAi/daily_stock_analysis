# V3.1 Execution Contract

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

When the hard logic remains intact, valuation drives staged de-risking rather than all-or-nothing liquidation:

- below neutral value: `HOLD`
- `price / neutral >= 1.00`: `HOLD_NO_ADD`
- `>= 1.20`: `REDUCE_25`, target position 75% of the reference full position
- `>= 1.40`: `REDUCE_50`, target position 50%
- `>= 1.70`: `CORE_ONLY`, target position 25%

If any V3.1 hard logic gate changes to FAIL, valuation no longer protects the position: the contract emits `EXIT` with target position 0 and requires human review/execution.

Unknown or incomplete valuation emits `HOLD_REVIEW`; it must not fabricate a sell signal.

## Human execution only

V3.1 is a research and decision-support contract. It does not connect to a broker and does not automatically place orders. `BUY`, `REDUCE` and `EXIT` outputs remain subject to human confirmation and current-data review.

## New-session handoff

A new AI session working on this repository should read this document and the authoritative Python contract before issuing actual BUY recommendations. If chat instructions and old research notes disagree with the frozen code contract, the current frozen contract wins unless the user explicitly changes it.
