# Market Research Log — 2026-08-16 — Batch 10

> Storage / memory-cycle comparison: 德明利, 香农芯创, 北京君正, 普冉股份, 大普微.

## Analysis snapshot

```text
analysis_as_of: 2026-08-16
latest_a_share_trading_day: 2026-08-14
market_regime: YELLOW
market_position_multiplier: 0.5
price_source: repository production artifact for 001309/300475/300223/688766
price_freshness: FRESH for those four
301666_price_freshness: UNVERIFIED for 2026-08-14 (latest independently found quote was 2026-07-28)
fundamental_freshness: ACCEPTABLE (latest H1 previews)
formal_buy: NO
```

## 001309 德明利

### Price / market cap

```text
2026-08-14 close: 406.19
MA20: 404.02
MA60: 619.68
MA120: 527.24
MA250: 354.57
1y percentile: 70.8%
5y percentile: 92.71%
shares: ~2.27 亿
market cap: ~922 亿 RMB
```

### Latest earnings

2026Q1 preview:

```text
Revenue: 73-78 亿
Headline profit: 31.5-36.5 亿
Recurring profit: 31.4-36.4 亿
```

2026H1 preview:

```text
Revenue: 160-180 亿
Headline profit: 57-65 亿
Recurring profit: 56.4902-64.4902 亿
Non-recurring items: ~0.5098 亿
Share-based payment expense: ~1.6 亿
```

Current-period earnings quality is very high. The company attributed the surge to AI/storage demand, tight supply, rising prices, supply-chain access, enterprise SSD/controller progress and product mix.

However, 2025 attributable profit was only about 6.9 亿. This is therefore an extraordinary cycle expansion rather than a normal year-on-year growth path.

### Consensus-quality warning

Public forecast aggregation was extremely dispersed:

```text
2026E net profit: ~9.39 to 143.10 亿, average ~80.44 亿
2027E: ~13.91 to 97.21 亿, average ~67.72 亿
```

The dispersion itself is information: simple consensus average is not a reliable normalized-profit anchor in an extreme memory cycle.

### Working cycle scenarios

```text
forward-cycle 2026 profit:
Bear 75 亿
Base 90 亿
Bull 105 亿

through-cycle normalized profit:
Bear 15 亿
Base 25 亿
Bull 35 亿
```

Forward-cycle PE at current market cap:

```text
75 亿 -> ~12.3x
90 亿 -> ~10.2x
105 亿 -> ~8.8x
```

This looks cheap if 2026 peak profits are treated as permanent.

Through-cycle fair value:

```text
Bear: 15 亿 @ 18x -> 270 亿 -> ~119/share
Base: 25 亿 @ 25x -> 625 亿 -> ~275/share
Bull: 35 亿 @ 30x -> 1050 亿 -> ~463/share
```

At 406.19 the stock is already between the working Base and Bull through-cycle cases.

Status:

```text
current_cycle_earnings: A+
earnings_quality: A
cycle_risk: EXTREME
valuation_on_peak_profit: APPARENTLY_CHEAP
valuation_on_through_cycle_profit: C-/D+
status: CYCLE_VALUE_CANDIDATE / WAIT_FOR_PRICE / HIGH_CYCLE_SENSITIVITY
formal_buy: NO
```

## 300475 香农芯创

### Price / market cap

```text
close: 161.03
MA20: 155.14
MA60: 202.45
MA120: 180.46
MA250: 146.78
1y percentile: 62.4%
5y percentile: 92.48%
shares: ~4.6954 亿
market cap: ~756 亿 RMB
```

### Latest earnings

2026H1 preview:

```text
Headline profit: 35-40 亿
Recurring profit: 33.9-38.9 亿
Estimated non-recurring impact: ~1.1 亿
```

The company attributed the surge to enterprise-storage demand, rising memory prices, better distribution gross margin and the scale-up of its own-brand `海普存储` enterprise-storage business.

The earnings quality is strong in the current period, but the business remains heavily exposed to memory pricing and distribution economics.

Public consensus forecasts were extremely dispersed and partly stale relative to the H1 preview, so the simple average is not used as the primary valuation anchor.

### Working cycle scenarios

```text
forward-cycle profit:
Bear 50 亿
Base 60 亿
Bull 70 亿

through-cycle normalized profit:
Bear 10 亿
Base 16 亿
Bull 22 亿
```

Forward-cycle PE at current market cap:

```text
~15.1x / 12.6x / 10.8x
```

Through-cycle valuation:

```text
Bear: 10 亿 @ 14x -> 140 亿 -> ~29.8/share
Base: 16 亿 @ 18x -> 288 亿 -> ~61.3/share
Bull: 22 亿 @ 22x -> 484 亿 -> ~103.1/share
```

Current 161.03 remains well above the working Bull through-cycle value. The own-brand enterprise-storage business may raise the future normalized profit/multiple, but that optionality is already being priced aggressively.

Status:

```text
current_cycle_earnings: A+
core_earnings_quality: A
business_model_quality: B (distribution-heavy but improving through own brand)
cycle_risk: EXTREME
status: CYCLE_PEAK_REVIEW / EXPECTATION_HIGH / WAIT_FOR_PRICE
formal_buy: NO
```

## 300223 北京君正

> Canonical company name is `北京君正`. The production artifact incorrectly labels code 300223 as `君正股份`; this is a separate security-master data defect.

### Price / market cap

```text
close: 143.62
MA20: 138.65
MA60: 170.12
MA120: 146.63
MA250: 119.57
1y percentile: 80.8%
5y percentile: 92.96%
shares: ~4.8366 亿
market cap: ~694.6 亿 RMB
```

### Latest earnings

2026H1 preview:

```text
Headline profit: 10.786-12.824 亿
Recurring profit: 10.491-12.529 亿
```

The company attributed the surge to the memory super-cycle: tight DRAM supply and significant price increases, stronger Flash demand from AI server / optical-module applications, plus price increases in computing-chip products due to KGD shortages/cost inflation.

Unlike pure memory distributors, 北京君正 combines memory with computing / MCU / analog / automotive-related platforms. Therefore company-level cycle normalization should use segment-aware treatment, not a uniform cycle haircut.

### Working cycle scenarios

```text
forward-cycle profit:
Bear 20 亿
Base 24 亿
Bull 28 亿

through-cycle normalized profit:
Bear 9 亿
Base 12.5 亿
Bull 16 亿
```

Forward-cycle PE at current market cap:

```text
~34.7x / 28.9x / 24.8x
```

Through-cycle fair value:

```text
Bear: 9 亿 @ 22x -> 198 亿 -> ~40.9/share
Base: 12.5 亿 @ 28x -> 350 亿 -> ~72.4/share
Bull: 16 亿 @ 32x -> 512 亿 -> ~105.9/share
```

At 143.62 the stock is above the working Bull through-cycle value despite a much lower apparent PE on 2026 peak profits.

Status:

```text
platform_quality: A-
current_cycle_earnings: A+
cycle_risk: HIGH
through_cycle_valuation: D
status: HIGH_QUALITY_CYCLE / EXPECTATION_HIGH / WAIT_FOR_PRICE
formal_buy: NO
```

## 688766 普冉股份

### Price / market cap

```text
close: 411.00
MA20: 378.47
MA60: 499.54
MA120: 391.05
MA250: 257.06
1y percentile: 86.4%
5y percentile: 97.16%
10d return: +15.81%
shares: 1.4870 亿
market cap: ~611.2 亿 RMB
```

### Latest earnings

2026H1 preview:

```text
Revenue: ~39.5 亿, +335.65%
Headline profit: ~8.25 亿, +1925.36%
Recurring profit: ~8.20 亿, +2976.99%
```

Current-period earnings quality is extremely clean. Drivers include memory price/volume gains plus `存储+` expansion in MCU/Driver/industrial-control/AIoT and consolidation effects from acquired businesses.

A late-April analyst forecast of 2026 profit ~10.74 亿 is already stale relative to H1 recurring profit of ~8.2 亿, so consensus must be refreshed rather than used mechanically.

### Working cycle scenarios

```text
forward-cycle profit:
Bear 14 亿
Base 17 亿
Bull 20 亿

through-cycle normalized profit:
Bear 7 亿
Base 10 亿
Bull 13 亿
```

Forward-cycle PE:

```text
~43.7x / 35.9x / 30.6x
```

Through-cycle fair value:

```text
Bear: 7 亿 @ 25x -> 175 亿 -> ~117.7/share
Base: 10 亿 @ 32x -> 320 亿 -> ~215.2/share
Bull: 13 亿 @ 38x -> 494 亿 -> ~332.2/share
```

At 411 the stock is above the working Bull through-cycle case. The platform expansion is real, but a large amount of successful execution is already priced.

Status:

```text
current_core_growth: A+
earnings_quality: A+
platform_optionalilty: A-
valuation: D
status: QUALITY_CYCLE_GROWTH / EXPECTATION_HIGH / WAIT_FOR_PRICE
formal_buy: NO
```

## 301666 大普微

### Price freshness

The stock listed on 2026-04-16 and is not present in the repository's 2026-08-14 production artifact. The latest quote independently verified in this batch was:

```text
2026-07-28 close: 438.66
shares: 4.3622 亿
reference market cap: ~1914 亿 RMB
```

Therefore:

```text
2026-08-14 price: UNVERIFIED
current precise margin_of_safety: DISABLED
formal_buy: DISABLED
```

### Latest earnings

2026H1 preview:

```text
Revenue: 43-48 亿, +474.7% to +541.6%
Headline profit: 12.0-13.5 亿
Recurring profit: 11.95-13.45 亿
```

The company attributed the turnaround to AI data-center enterprise SSD demand, PCIe SSD shortages, KV-cache / inference growth and product iteration.

The current-period profit is very clean, but the company is a newly listed enterprise-storage name with high cycle exposure and a very high valuation reference even after the H1 earnings surge.

Using the stale 2026-07-28 reference market cap only for context, a 22-30 亿 forward-cycle profit range would still imply roughly 64-87x PE. Therefore the stock does not screen as a low-expectation memory-cycle opportunity even before through-cycle normalization.

Status:

```text
PRICE_UNVERIFIED
current_cycle_growth: A+
cycle_risk: VERY HIGH
valuation_reference: HIGH
status: PRIORITY_RESEARCH / PRICE_UNVERIFIED / EXPECTATION_HIGH
formal_buy: NO
```

## Batch 10 ranking

By current risk-adjusted valuation, not raw H1 growth:

```text
1. 德明利 — strongest apparent current-cycle valuation compression, but still between Base/Bull through-cycle valuation
2. 北京君正 — better platform durability than pure memory names, but current price still above working through-cycle Bull
3. 普冉股份 — excellent clean growth and platform expansion, but high expectation burden
4. 香农芯创 — earnings surge is real, but distribution/cycle exposure makes through-cycle valuation particularly stretched
5. 大普微 — exceptional growth, but latest 8/14 price is unverified and even the latest verified reference remained very expensive
```

Main lesson:

> A memory stock can show a single-digit or low-teens forward PE during a super-cycle and still be expensive on sustainable earnings. The system must always show both `forward_cycle_PE` and `through_cycle_PE` for these names.

No new valuation primitive was required: segment-aware cycle normalization and existing earnings-quality logic were sufficient.

## Next continuous queue

```text
300502 新易盛
300308 中际旭创
300394 天孚通信
300476 胜宏科技
002463 沪电股份
002916 深南电路
002837 英维克
then revisit 002270 华明装备 after latest H1 data
```
