# Market Research Log — 2026-08-16 — Batch 6

> Read with `CURRENT_MARKET_RESEARCH.md`, `MODEL_EVOLUTION_LOG.md`, and prior batch logs.
>
> This batch completes `603986 兆易创新` and closes the initial semiconductor equipment/material/storage comparison sequence. Formal BUY remains separate from Research Pool ranking.

## Analysis snapshot

```text
analysis_as_of: 2026-08-16
latest_a_share_trading_day: 2026-08-14
market_regime: YELLOW
market_position_multiplier: 0.5
A_share_price_source: repository production artifact / tencent_raw
A_share_price_freshness: FRESH
fundamental_freshness: ACCEPTABLE (2025 annual + 2026Q1 + 2026H1 preview)
industry_driver_freshness: ACCEPTABLE (Jul-2026 memory pricing research)
formal_buy: NO
```

## 603986 兆易创新

### A-share price / technical snapshot — 2026-08-14

```text
close: 417.48
open: 419.00
high: 421.18
low: 406.55
MA20: 407.50
MA60: 524.66
MA120: 413.29
MA250: 308.23
price_percentile_1y: 0.808
price_percentile_5y: 0.9616
return_1d_pct: +3.2089%
return_5d_pct: +0.1031%
return_10d_pct: +10.2694%
relative_strength_20d: -16.2034%
relative_strength_60d: +1.9036%
legacy_quant_status: HARD_REJECT
legacy_blocker: price_too_high / trend_unconfirmed
```

Interpretation: the stock has corrected materially from the mid-year peak, but a large drawdown does **not** make it historically low-priced; it remained around the 96th percentile of its five-year price range in the production snapshot.

### Share classes / market-cap caveat

By July 2026 the company had both A and H shares outstanding. Public share-structure data used in this batch indicated roughly:

```text
A shares: ~6.68 亿
H shares: ~3325.31 万
Total economic shares: ~7.01-7.02 亿
```

Therefore:

```text
A price × all company shares
```

must **not** be labelled the actual consolidated market cap. It is only the total equity value *implied by the A-share price* if all economic shares were valued at the A quote.

At the 2026-08-14 A close, that A-price-implied total equity value is approximately:

```text
~2928 亿 RMB
```

Actual consolidated market cap requires the H-share quote and explicit HKD→RMB conversion. Those inputs were not reliably verified in this batch, so:

```text
consolidated_market_cap: UNVERIFIED
```

For A-share intrinsic-value comparison, per-share fair value can still be compared against the A quote using the full economic share-count denominator, provided the distinction above stays explicit.

### 2025 fundamental mix

2025 full year:

```text
Revenue: ~92.03 亿 RMB, +25.12% YoY
Attributable net profit: ~16.48 亿 RMB, +49.47%
Recurring attributable profit: ~14.69 亿 RMB, +42.57%
Operating cash flow: ~21.29 亿 RMB
```

2025 product revenue / gross margin:

```text
Memory: ~65.66 亿 revenue, ~42.84% GM
MCU: ~19.10 亿 revenue, ~35.82% GM
Sensors: ~3.89 亿 revenue, ~19.57% GM
Analog: ~3.33 亿 revenue, ~36.96% GM
```

Memory represented roughly 71% of product revenue and about 76% of disclosed product gross profit in 2025. This is why the company should not be valued as a fully non-cyclical semiconductor platform despite meaningful MCU/analog diversification.

### 2026Q1

```text
Revenue: ~41.88 亿 RMB, +119.38% YoY
Attributable net profit: ~14.61 亿 RMB, +522.79%
Recurring attributable profit: ~14.10 亿 RMB, +529.90%
Operating cash flow: ~17.83 亿 RMB, +430.91%
```

Q1 headline/recurring profit quality was high.

### 2026H1 preview

```text
Revenue: ~115 亿 RMB, +177% YoY
Attributable net profit: ~69 亿 RMB, +1099%
Recurring attributable profit: ~48.5 亿 RMB, +791%
```

The company explicitly attributed the core earnings surge to tight memory supply, memory product volume/price gains, and MCU demand, while a large securities fair-value gain further boosted headline profit.

H1 quality bridge:

```text
recurring / headline profit: ~70.3%
H1 non-recurring difference: ~20.5 亿 RMB
```

Implied Q2 from H1 minus Q1:

```text
Q2 headline profit: ~54.39 亿 RMB
Q2 recurring profit: ~34.40 亿 RMB
```

Critical interpretation: the spectacular H1 headline figure is materially inflated by non-recurring gains, **but the core operating acceleration is also genuinely enormous**. The model must avoid both errors: capitalizing 69 亿 as clean recurring earnings, or dismissing the entire surge as non-operating.

### Industry cycle driver

Memory pricing research reviewed in this batch showed an extreme 2026 upcycle:

```text
1Q26 conventional DRAM contract prices: roughly +90% to +95% QoQ forecast
2Q26 conventional DRAM: roughly +58% to +63% QoQ forecast
2Q26 NAND Flash: roughly +70% to +75% QoQ forecast
3Q26 general DRAM: roughly +13% to +18% QoQ forecast
3Q26 NAND Flash: roughly +10% to +15% QoQ forecast
```

The key signal is not that the cycle is already over; pricing was still expected to rise in Q3. The signal is that the *rate* of price acceleration had begun to moderate from an extraordinary base. Specialty/legacy memory shortages remained structurally tight.

### Why simple PE is misleading

A first-pass 2026 current-cycle core-profit range used for research:

```text
Bear forward-cycle profit: ~90 亿
Base forward-cycle profit: ~105 亿
Bull forward-cycle profit: ~125 亿
```

Using the A-share price-implied total equity value (~2928 亿), forward-cycle PE would look approximately:

```text
Bear: ~32.5x
Base: ~27.9x
Bull: ~23.4x
```

That does **not** look obviously expensive for a strong semiconductor platform.

However, these profits are being earned during an extraordinary memory-price regime. They cannot automatically become the permanent valuation denominator.

### Segment-aware through-cycle normalization

A company-wide `is_cyclical=True` haircut is also too crude because MCU/analog/sensor businesses should not be normalized identically to memory.

Working research scenarios therefore separate current-cycle profit from through-cycle profit:

```text
Bear:
  forward-cycle profit: 90 亿
  through-cycle normalized profit: 42 亿
  fair multiple: 30x

Base:
  forward-cycle profit: 105 亿
  through-cycle normalized profit: 58 亿
  fair multiple: 36x

Bull:
  forward-cycle profit: 125 亿
  through-cycle normalized profit: 78 亿
  fair multiple: 42x
```

These through-cycle values are research assumptions, not company guidance. They reflect the 2025 business mix, the dominance of memory in gross profit, platform diversification, and the current exceptional memory-price environment.

### Scenario fair value

Using approximately 7.0125 亿 total economic shares:

```text
Bear: 42 亿 × 30x = 1260 亿 -> ~179.7 RMB/share
Base: 58 亿 × 36x = 2088 亿 -> ~297.8 RMB/share
Bull: 78 亿 × 42x = 3276 亿 -> ~467.2 RMB/share
```

At the 2026-08-14 A close of `417.48`, the stock traded:

- materially above the working Base through-cycle value;
- below but relatively close to the working Bull value;
- while looking much cheaper if judged only on peak/current-cycle 2026 profit.

This difference is the central valuation issue.

### Consensus warning

Public analyst-consensus aggregations observed during the batch were internally stale/dispersed relative to the July H1 preview: average 2026 profit estimates in some aggregators were already below the company's H1 headline guidance, while individual forecasts ranged extremely widely.

Therefore:

```text
consensus_profit_freshness: STALE / HIGH_DISPERSION
```

The model should not use the simple consensus average as the primary 2026 normalized-profit anchor after a material company earnings update.

### Current research status

```text
business_quality: A
platform_diversification: A-
current_core_earnings_momentum: A+
headline_earnings_quality_H1: B- (large fair-value gain)
core_earnings_quality: A-
cycle_risk: VERY HIGH
through_cycle_confidence: MEDIUM-LOW
valuation_on_current_cycle_profit: C+ / seemingly reasonable
valuation_on_through_cycle_profit: D+ / expectation-heavy
entry_readiness: NOT CONFIRMED
status: CYCLE_VALUE_CANDIDATE / HIGH_CYCLE_SENSITIVITY / WAIT_FOR_PRICE
formal_buy: NO
```

### Research price zones

These are valuation-research zones, not Formal BUY triggers:

```text
>380: still requires a long/strong cycle or near-Bull through-cycle outcome
320-360: improving, but still contains meaningful cycle optimism
280-310: close to current Base through-cycle fair-value region
240-275: materially better margin of safety if H1/H2 core logic stays intact
```

All zones must be recomputed after the scheduled 2026H1 report and fresh memory pricing data.

### Near-term checkpoint

2026H1 report was scheduled for:

```text
2026-08-19
```

The report should supersede the preview, especially for:

```text
memory-vs-MCU revenue mix
gross-margin expansion
inventory / purchase commitments
cash conversion
securities fair-value gains
DRAM/NOR/SLC NAND product mix
H-share / capital structure details
```

## Model refinement #1 — segment-aware cycle normalization

The existing company-level cycle primitive was too binary for a company such as GigaDevice, where memory is highly cyclical but MCU/analog/sensor businesses have different earnings durability.

PR #25 now contains:

```text
src/strategies/genge_opportunity_discovery/segment_cycle_blend.py
tests/test_genge_segment_cycle_blend.py
```

Safety behavior:

- cyclical segments require explicit through-cycle profit or explicit normalization ratio;
- non-cyclical segments can remain at forward profit unless explicitly normalized;
- missing cyclical assumptions fail closed;
- no segment profit is inferred automatically from revenue/gross profit by the primitive.

## Model refinement #2 — multi-share-class market-cap bridge

A/H dual listing exposed that one listed class's price multiplied by total company shares is not actual consolidated market cap.

PR #25 now contains:

```text
src/strategies/genge_opportunity_discovery/share_class_market_cap.py
tests/test_genge_share_class_market_cap.py
```

Safety behavior:

- each share class requires explicit shares, quote and FX-to-reporting-currency;
- incomplete H/A pricing returns `INCOMPLETE_SHARE_CLASS_PRICING`;
- a reference-class price may still produce a separately labelled `reference_class_implied_total_equity_value`;
- that implied value is never labelled actual consolidated market cap.

## Relative view — initial semiconductor batch complete

Current research/valuation balance, not Formal BUY ranking:

```text
1. 688019 安集科技 — closest to Base fair value; strong quality and lower cycle exposure
2. 603986 兆易创新 — strongest current-cycle earnings compression, but very high cycle sensitivity
3. 688120 华海清科 — high-quality platform, price previously near Bull case
4. 300604 长川科技 — exceptional growth, high expectation + R&D-capitalization comparability issue
5. 300666 江丰电子 — strategic material logic strong, but H1 headline profit heavily non-recurring and valuation high
```

Storage pure plays `301308 江波龙` and `688525 佰维存储` remain high-priority cycle research names but require H1 inventory/cash-flow normalization before a durable through-cycle ranking.

## Next cross-sector comparison queue

Refresh all data before continuing:

```text
002378 章源钨业
000682 东方电子
600406 国电南瑞
```

Purpose: compare strategic-resource cyclicals and grid-quality names against the semiconductor opportunity set on one common expectation-gap / margin-of-safety framework.
