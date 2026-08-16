# Market Research Log — 2026-08-16 — Batch 12

> Completes the initial core research queue with `002270 华明装备`.

## Analysis snapshot

```text
analysis_as_of: 2026-08-16
latest_a_share_trading_day: 2026-08-14
market_regime: YELLOW
market_position_multiplier: 0.5
price_source: repository production artifact / tencent_raw
price_freshness: FRESH
fundamental_freshness: ACCEPTABLE (2025 annual + 2026Q1)
2026H1_status: NOT YET DISCLOSED / NO RELIABLE PREVIEW FOUND
formal_buy: NO
```

## 002270 华明装备

### Price snapshot

```text
close: 20.11
MA20: 19.74
MA60: 19.95
MA120: 24.26
MA250: 24.12
1y percentile: 28.0%
5y percentile: 84.0%
10d return: -1.57%
shares: ~8.96 亿
market cap: ~180 亿 RMB
```

The production legacy quant system still flags `price_too_high`, but under the upgraded architecture that is not a valid reason to remove the stock from the broad Research Pool.

### Latest verified fundamentals

2025:

```text
Revenue: ~24.27 亿, +4.5%
Headline attributable profit: ~7.10 亿, +15.5%
Recurring attributable profit: ~6.71 亿, +15.3%
ROE: ~22.04%
```

2026Q1:

```text
Revenue: ~5.30 亿, +4.07%
Headline profit: ~1.63 亿, -4.85%
Recurring profit: ~1.43 亿, -9.51%
OCF: ~0.924 亿, +50.30%
```

The company explicitly attributed the reported profit decline mainly to share-based-payment expense, lower FX gains and greater overseas investment.

After removing the disclosed share-based-payment effect:

```text
adjusted headline profit: ~1.78 亿, +3.6%
adjusted recurring profit: ~1.58 亿, -0.34%
```

Therefore Q1 is better described as `core profit roughly flat after incentive-cost adjustment`, not a clear earnings acceleration.

### Business driver

- core product: transformer tap changers / lifecycle maintenance;
- domestic leadership and high margin;
- global grid capex / transformer demand supports overseas growth;
- UHV and service/maintenance offer structural optionality;
- Q1 electric-equipment revenue was affected by lower new-energy-project shipments and customer delivery timing;
- the company has an H-share listing process underway, creating future financing/share-count uncertainty that must be bridged only once final terms are known.

### H1 data-quality resolution

No 2026H1 formal report or reliable H1 earnings preview was found as of 2026-08-16.

The scheduled 2026H1 report date is:

```text
2026-08-29
```

Earlier web-search material that appeared to show `2026H1 ~3.68 亿 +17%` was not accepted because it was inconsistent with disclosure chronology / appeared to refer to prior-year data. This batch preserves the fresh-data fail-closed rule rather than forcing an H1 number.

### Consensus reference

Late-July public aggregation:

```text
2026E net profit: ~8.50 亿
2027E: ~10.33 亿
2028E: ~12.71 亿
```

At the 2026-08-14 market cap:

```text
2026E PE: ~21.2x
2027E PE: ~17.4x
2028E PE: ~14.2x
```

The valuation is therefore materially less demanding than many high-growth AI/semiconductor-equipment candidates.

### Working scenarios

Plain equity-profit PE, with no separate net-cash add-back:

```text
Bear: 7.5 亿 @ 18x -> 135 亿 -> ~15.1/share
Base: 8.5 亿 @ 22x -> 187 亿 -> ~20.9/share
Bull: 10.5 亿 @ 26x -> 273 亿 -> ~30.5/share
```

At 20.11 the stock is close to the working Base value.

### Reverse pricing

Approximate current market cap implies sustainable profit of:

```text
18x -> ~10.0 亿
20x -> ~9.0 亿
22x -> ~8.2 亿
24x -> ~7.5 亿
```

A low-20s fair multiple therefore does not require an implausible earnings assumption relative to current consensus, but the latest operating data have not yet confirmed acceleration.

### Current status

```text
business_quality: A-
industry_logic: A
valuation: B / near Base
current_fundamental_momentum: C
expectation_risk: LOW-MEDIUM
H1_confirmation: REQUIRED
status: VALUE_CANDIDATE / FUNDAMENTAL_CONFIRMATION_REQUIRED / WATCH_FOR_H1
formal_buy: NO
```

## Core-queue completion

With this batch the initial deep-research universe defined during the 2026-08-16 session is complete, aside from future scheduled-report refreshes and exact-price gaps already marked `UNVERIFIED`.

Next step is not to stop or add random names. Build a **fresh-data master cross-sector ranking** from all completed cases, separated into:

```text
Fundamental / Mispricing Candidates
High-Quality Fair-Value Watch
Cycle Candidates Requiring Normalization
Expectation Too High / Wait for Price
Fundamental Recovery Required
Data/Price Unverified
```

The master ranking must preserve each stock's valuation semantics (cycle, terminal-duration, plain PE, A/H share-class caveat) rather than forcing one identical metric across all business models.
