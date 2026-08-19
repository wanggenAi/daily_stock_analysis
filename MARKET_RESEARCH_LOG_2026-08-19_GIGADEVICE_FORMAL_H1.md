# Market Research Log — 2026-08-19 — 603986 兆易创新 Formal H1 Revaluation

> Event-driven recheck triggered by the formal 2026 interim report. This supersedes the preview-based H1 assumptions in `MARKET_RESEARCH_LOG_2026-08-16_BATCH6.md`. Formal BUY remains separate from Research Pool valuation.

## Analysis snapshot

```text
analysis_as_of: 2026-08-19
formal_report_status: DISCLOSED
formal_report_release: 2026-08-18 22:49 HKT via HKEX
fundamental_freshness: FRESH / FORMAL_H1
industry_driver_freshness: FRESH_ENOUGH (TrendForce Jul/Aug 2026)
A_share_price_basis: 2026-08-14 repository production close 417.48 RMB
A_share_price_freshness: STALE_3_TRADING_DAYS / latest source not independently verified at this run
share_structure_freshness: 2026-07-31 monthly return
formal_buy: NO
```

The valuation intentionally remains anchored to the latest **repository-validated** A-share close available to this research run. No unverified 2026-08-19 quote is substituted merely to claim freshness. Recompute the market-cap-dependent outputs when the next production price snapshot is available.

## Formal H1 headline / core / cash-flow bridge

Formal 2026H1 reported:

```text
Revenue: 115.6576 亿 RMB, +178.67% YoY
Gross profit: 73.0152 亿 RMB
Overall gross margin: ~63.13%
Attributable net profit: 68.5679 亿 RMB, +1091.50% YoY
Recurring attributable profit: 48.83 亿 RMB, +796.90% YoY
Operating cash flow: 60.4834 亿 RMB, +531.47% YoY
```

Quality diagnostics:

```text
recurring / headline profit: ~71.21%
non-recurring share of headline: ~28.79%
OCF / recurring profit: ~123.87%
OCF / headline profit: ~88.21%
```

The formal report therefore confirms the preview's key conclusion: headline profit contains a large non-operating component, but the core operating result is itself exceptionally strong. The model must use the reported recurring profit as the core starting point rather than capitalizing the full headline profit.

Implied Q2 recurring profit from formal H1 less 2026Q1 recurring profit (~14.10 亿):

```text
~34.73 亿 RMB
```

This is a real core acceleration, not merely a fair-value-gain artifact.

## Product mix / gross-margin evidence

Formal H1 disaggregated operating revenue and cost:

| Segment | Revenue (亿 RMB) | Cost (亿 RMB) | Gross margin | Revenue share | Gross-profit share |
|---|---:|---:|---:|---:|---:|
| Memory chips | 98.2748 | 31.8696 | ~67.57% | ~84.97% | ~90.95% |
| MCUs | 14.2976 | 8.7952 | ~38.49% | ~12.36% | ~7.54% |
| Sensors | 1.0025 | 0.8061 | ~19.60% | ~0.87% | ~0.27% |
| Analog | 1.9064 | 1.1343 | ~40.50% | ~1.65% | ~1.06% |
| Technical/other | 0.1763 | 0.0373 | ~78.84% | ~0.15% | ~0.19% |

Key change versus 2025:

```text
2025 memory revenue share: ~71%
2025 memory gross-profit share: ~76%
2026H1 memory revenue share: ~85%
2026H1 memory gross-profit share: ~91%
```

The platform businesses remain strategically meaningful, but the *current earnings engine* is much more memory-dominated than the prior preview-based valuation assumed. This increases through-cycle sensitivity and is the main reason the normalized-profit scenarios are revised down modestly despite stronger H1 earnings.

Formal operating commentary also confirms:

```text
Memory revenue: +245.44% YoY
MCU revenue: +49.07% YoY
niche DRAM: volume + price growth, sharply improved GM
SLC NAND: volume + price growth, sharply improved GM
NOR Flash: broad volume growth + moderate price increase
MCU: industrial largest revenue source; prices began moderate rise in Q2
```

## Inventory / working capital

At 2026-06-30:

```text
Inventory net book value: 41.8422 亿 RMB
2025-12-31 inventory: 30.6597 亿 RMB
Increase: +36.47%
```

Inventory composition / provision:

```text
Gross inventory: 44.6695 亿
Inventory provision: 2.8273 亿
Provision / gross inventory: ~6.33%
2025 year-end provision / gross inventory: ~8.89%
```

Inventory growth is material and must be watched through the down-cycle, but it grew far slower than H1 revenue. The provision ratio also declined rather than expanding. This is not currently an inventory-stress signal, though it remains a high-priority cycle checkpoint.

## R&D capitalization diagnostic

Formal report provides complete R&D reconciliation:

```text
Total R&D expenditure: 9.6571 亿 RMB
Expensed R&D: 7.6482 亿
Capitalized R&D: 2.0090 亿
Capitalization rate: ~20.80%
Prior H1 capitalization rate: ~17.28%
Change: +3.53ppt
```

The increase is visible but not remotely comparable to the previously identified sharp Longsys/长川-style comparability case. Existing `rnd_capitalization.py` already models this failure mode, so this case does **not** justify a new valuation metric or new code path.

## A/H share structure

Latest verified monthly return at 2026-07-31:

```text
A shares: 668,491,934
H shares: 33,253,100
Total economic shares: 701,745,034
Treasury shares: 0
```

The July cancellation reduced A shares by only 4,565. H shares were unchanged.

As established in PR #25, `A price × total A+H shares` is only a **reference-class-implied total equity value**, not actual consolidated market cap. Actual consolidated market cap still requires a same-date H quote and explicit HKD→RMB FX.

At the repository-validated 2026-08-14 A close of 417.48:

```text
A-price-implied total equity value: ~2929.65 亿 RMB
```

## Industry driver refresh

TrendForce's latest available 3Q26 work still indicates rising memory prices, but at a sharply slower rate than the extraordinary H1 move:

```text
3Q26 conventional DRAM contract prices: +13% to +18% QoQ forecast
3Q26 NAND Flash contract prices: +10% to +15% QoQ forecast
3Q26 mobile DRAM: +8% to +13% QoQ forecast
4Q26: price increases expected to converge further under weak end demand / high inventory,
       while server/HBM capacity reallocation continues to support supply tightness
```

This supports a strong H2 operating environment but argues against treating H1 margin expansion as a permanent steady-state floor.

## Revised forward-cycle profit

Formal H1 recurring profit is already 48.83 亿 and implied Q2 recurring profit is ~34.73 亿. The prior forward-cycle range (90/105/125 亿) is therefore revised upward modestly:

```text
Bear forward_cycle_profit: 100 亿
Base forward_cycle_profit: 115 亿
Bull forward_cycle_profit: 130 亿
```

These are research scenarios, not company guidance.

At the 2026-08-14 A-price-implied total equity value (~2929.65 亿), this produces current-cycle PE of roughly:

```text
Bear: ~29.3x
Base: ~25.5x
Bull: ~22.5x
```

Again, this is why current-cycle PE alone can make the stock look deceptively inexpensive.

## Revised through-cycle normalization

The formal segment data materially raises the measured dependence on memory gross profit. Therefore prior through-cycle assumptions of 42/58/78 亿 are revised to:

```text
Bear through_cycle_normalized_profit: 40 亿
Base through_cycle_normalized_profit: 55 亿
Bull through_cycle_normalized_profit: 75 亿
```

Retain the same explicit research multiples:

```text
Bear: 30x
Base: 36x
Bull: 42x
```

Rationale:

- memory now contributes ~91% of H1 gross profit, so current peak economics require a larger normalization discount;
- MCU/analog still support a higher long-run multiple than a pure commodity-memory company;
- automotive, industrial and product-breadth progress improve the structural floor;
- exact segment operating profit is not disclosed, so through-cycle confidence cannot be HIGH.

## Bear / Base / Bull fair value

Using 701,745,034 total economic shares:

```text
Bear: 40 亿 × 30x = 1200 亿 -> ~171.0 RMB/share
Base: 55 亿 × 36x = 1980 亿 -> ~282.2 RMB/share
Bull: 75 亿 × 42x = 3150 亿 -> ~448.9 RMB/share
```

Versus the validated 417.48 reference A price:

```text
Bear return: -59.0%
Base margin of safety / return: -32.4%
Bull return: +7.5%
Upside potential: +7.5%
Downside risk: 59.0%
Scenario upside/downside ratio: ~0.13x
```

No scenario probabilities are invented.

## Reverse implied expectation / Expectation Gap

At current A-price-implied total equity value and the Base 36x through-cycle multiple:

```text
implied sustainable profit: ~81.38 亿 RMB
Base through-cycle normalized profit: 55 亿 RMB
Expectation Gap: ~+47.96%
```

Interpretation: the A-share reference price requires sustainable normalized profit roughly 48% above the current Base through-cycle assumption.

At the same time, the current price only represents about 25.5x the Base **forward-cycle** 2026 profit assumption. This divergence is the key valuation fact:

```text
current-cycle valuation: looks reasonable / even superficially cheap
through-cycle valuation: expectation-heavy
```

## Safety-margin zones

Base through-cycle fair price is ~282.2 RMB.

Research discount zones:

```text
10% below Base: ~253.9
15% below Base: ~239.8
20% below Base: ~225.7
25% below Base: ~211.6
```

These are valuation research zones, not Formal BUY triggers.

## Valuation confidence / status

```text
business_quality: A
platform_diversification: A-
current_core_earnings_momentum: A+
headline_earnings_quality: B (large non-recurring contribution)
core_cash_conversion: A
memory_cycle_exposure: VERY HIGH
inventory_risk: MEDIUM / WATCH
R&D_capitalization_risk: LOW-MEDIUM / existing diagnostic sufficient
forward_cycle_profit_confidence: MEDIUM-HIGH
through_cycle_profit_confidence: MEDIUM-LOW
valuation_on_forward_cycle_profit: C+ / apparently reasonable
valuation_on_through_cycle_profit: D / expectation-heavy
scenario_odds: POOR_AT_REFERENCE_PRICE
entry_readiness: NOT_CONFIRMED
status: CYCLE_VALUE_CANDIDATE / HIGH_CYCLE_SENSITIVITY / EXPECTATION_HEAVY / WAIT_FOR_PRICE
formal_buy: NO
```

## Model-defect review

The formal report does **not** expose a new reproducible valuation defect.

Existing PR #25 primitives already cover the observed issues:

```text
earnings-quality normalization -> strips headline fair-value distortion
segment_cycle_blend -> prevents one company-wide cycle haircut
share_class_market_cap -> prevents A quote × A+H shares from being mislabeled consolidated market cap
rnd_capitalization -> audits moderate capitalization-rate changes
financial_asset_bridge -> prevents double counting financial income / assets
scenario_odds -> compares Bear/Base/Bull asymmetry without invented probabilities
valuation_horizon -> prevents future terminal values from being treated as present values
```

Therefore no new code/metric is added from this event. Avoid model bloat.

## Delta versus 2026-08-16 preview-based revaluation

```text
Formal H1 core profit: slightly stronger than preview (~48.83 vs ~48.5 亿)
Formal H1 cash conversion: much stronger / now verified
Memory concentration: materially higher than prior model basis
Through-cycle Base profit: revised 58 -> 55 亿
Base fair price: revised ~297.8 -> ~282.2 RMB
Bull fair price: revised ~467.2 -> ~448.9 RMB
Research conclusion: slightly more cautious on normalized valuation despite stronger headline/core H1
```

The formal report strengthens the near-term earnings thesis but weakens the argument that the current H1 profit level is durable through a normal memory cycle.
