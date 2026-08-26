# V3.1 Round-4 decision record

Date: 2026-08-26

Status: **Do not promote the typed valuation router to production.**

## What round 4 tested

Round 4 was an untouched out-of-sample valuation/execution-layer test on 12 Shanghai/Shenzhen main-board A shares not used in rounds 1 or 2. The economic router was committed before results:

- RESOURCE_ASSET -> PB-relative proxy
- STABLE_CASHFLOW -> existing PE/PB geometric mean
- GROWTH_TECH_CONSENSUS -> PE and PB must agree in direction before valuation changes position size

The BUY/SELL thresholds, 756-trading-day past-only anchor, month-end cadence, 0.10% one-way friction and cost-basis-independent SELL contract were unchanged.

## Headline evidence

### Combined 12-stock portfolio

- Typed router CAGR: 13.06%
- Universal PE/PB proxy CAGR: 12.86%
- Literal buy-and-hold CAGR: 27.16%
- Typed max drawdown: -23.12%
- Universal max drawdown: -27.82%
- Literal buy-and-hold max drawdown: -38.72%
- Typed Sharpe: 1.056
- Universal Sharpe: 0.964
- Literal buy-and-hold Sharpe: 0.949

Interpretation: typing improved risk-adjusted behavior modestly, but did not repair the large absolute-return gap.

### Resource-asset group

- Typed CAGR 18.05% vs universal 18.31% vs buy-and-hold 17.23%.
- Typed max drawdown -23.08% vs universal -31.62% vs buy-and-hold -46.52%.
- Typed Sharpe 1.065 vs universal 0.877 vs buy-and-hold 0.631.

Interpretation: the asset-style proxy is plausible for risk control, but it did not improve CAGR versus the universal proxy. This is supportive evidence for business-type-specific valuation, not enough to promote PB-only as a production intrinsic-value engine. Production resource valuation should ultimately use NAV, resource life, cost curve and normalized cycle earnings.

### Stable-cashflow group

The typed rule was intentionally identical to the universal rule. CAGR was 9.61% versus literal buy-and-hold 10.60%, while max drawdown improved from -26.09% to -11.85%.

Interpretation: V3.1 is trading return for materially lower drawdown. No evidence here justifies changing the existing stable-company proxy.

### Growth-tech group

- Typed CAGR: 9.01%
- Universal CAGR: 9.16%
- Literal buy-and-hold CAGR: 39.37%
- Typed average cash: 54.57%
- Universal average cash: 52.37%
- Typed trades: 51 vs universal 73

Interpretation: the PE/PB direction-consensus router reduced activity but **did not solve the growth-company valuation problem**. The failure is too large to explain with the old normalization bug or a small SELL-threshold adjustment.

## Falsified hypothesis

The hypothesis "the main growth-tech problem is PE/PB disagreement, so a direction-consensus router should materially repair performance" is **not supported** by round 4.

The typed and universal growth-tech CAGRs differ by only about -0.14 percentage points despite a large reduction in trade count. Therefore the main issue is deeper than simply averaging inconsistent PE/PB signals.

## Current diagnosis

The evidence now points to the historical-relative-multiple proxy itself as the wrong abstraction for structural compounders/growth technology.

For a high-quality growth company, intrinsic value should be refreshed from economically normalized earning power and reinvestment runway. A stock can remain above its own historical PE/PB median for years while normalized earnings and intrinsic value rise rapidly. A historical-multiple anchor can therefore create two structural errors:

1. **under-entry**: large cash balances while the business compounds;
2. **premature de-risking**: position cuts because the historical multiple looks expensive even though refreshed earning power has risen.

Round 4 growth-tech average cash above 54% is direct evidence of persistent underexposure in the tested implementation.

## What must NOT be done

Do not respond to round 4 by tuning 1.20 / 1.40 / 1.70 upward, selecting PB-only because it looked better in one prior sample, or relaxing BUY bands until the historical chart looks attractive. Those changes would be post-result optimization.

## Next research gate

Build a separate **PIT normalized-earnings neutral-value engine** for structural compounders/growth technology.

Required principles:

- use only financial reports publicly available by each historical decision date;
- normalize multi-year earning power rather than use raw TTM PE alone;
- include dilution/share-count effects where data permit;
- distinguish earnings growth funded by high incremental returns from low-quality balance-sheet expansion;
- derive neutral value from normalized per-share earning power and a defensible long-term valuation range;
- use the existing V3.1 BUY/SELL bands only after neutral value is independently estimated;
- keep SELL independent of personal cost basis;
- test on a new untouched OOS universe before any production promotion.

Until that engine passes an untouched test, production V3.1 remains unchanged.
