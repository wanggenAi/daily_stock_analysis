# Market Research Log — 2026-08-16 — Batch 11

> AI hardware / optical / PCB / thermal-management comparison. This batch introduces explicit valuation-horizon semantics so future terminal values are not silently compared with today's market cap without discounting.

## Analysis snapshot

```text
analysis_as_of: 2026-08-16
latest_a_share_trading_day: 2026-08-14
market_regime: YELLOW
market_position_multiplier: 0.5
price_source: repository production artifact / tencent_raw
price_freshness: FRESH
fundamental_freshness: ACCEPTABLE
formal_buy: NO
```

## Valuation-horizon stress-test convention

This batch uses two explicitly different multiple semantics:

```text
CURRENT_FORWARD_PE:
  today's market price / future-year earnings estimate
  -> do NOT discount again

TERMINAL_PE:
  a PE assumed to apply at a future terminal date
  -> terminal equity value MUST be discounted back to today
```

For a common cross-stock duration stress test only, this batch uses:

```text
analysis date: 2026-08-16
terminal horizon: approximately 2.37 years to end-2028
required return: 12% annualized
```

Terminal PE assumptions are research assumptions, not company guidance and not universal fair multiples:

```text
新易盛 25x
中际旭创 25x
天孚通信 35x
胜宏科技 22x
沪电股份 25x
深南电路 25x
英维克 30x
```

The purpose is not to create authoritative target prices. The purpose is to ask:

> If today's price is to earn 12% annually and the company exits 2028 at the assumed terminal multiple, how much 2028 profit must it produce?

This is a duration/expectation test.

---

## 300502 新易盛

### Price / market cap

```text
close: 448.08
MA20: 443.02
MA60: 503.76
MA120: 425.14
MA250: 336.22
1y percentile: 81.6%
5y percentile: 96.32%
shares: ~13.9426 亿
market cap: ~6247 亿 RMB
```

### Latest fundamental checkpoint

2026H1 preview:

```text
Headline attributable profit: 70-80 亿
Recurring attributable profit: 69.81-79.81 亿
Non-recurring impact: ~0.19 亿
```

The H1 surge is therefore extremely clean. The company attributed growth to continued AI-compute investment and product-mix optimization.

Q1 headline profit was ~27.8 亿, implying Q2 headline profit of roughly 42.2-52.2 亿. The core operating trend therefore accelerated sequentially.

Public consensus reference observed during this batch:

```text
2026E: ~188.47 亿
2027E: ~297.65 亿
2028E: ~485.72 亿
```

These are third-party estimates with dispersion, not company guidance.

Current forward PE:

```text
2026E ~33.1x
2027E ~21.0x
2028E ~12.9x
```

### Reverse duration test

At a 25x end-2028 terminal PE and 12% required return, today's market cap requires approximately:

```text
required 2028 terminal profit: ~326.9 亿
required CAGR from 2026E 188.5 亿: ~26.2%/yr
```

This required terminal profit is materially below the current third-party 2028 consensus (~485.7 亿).

If the 2028 consensus were achieved and a 25x terminal multiple were still justified, the discounted present-equity-value stress test would imply roughly `665.8 RMB/share`, about 49% above the 2026-08-14 A-share price.

This is **not** a target price. It is evidence that static high-PE/high-price screens can miss a stock when forward earnings are growing fast enough.

Risks:

- AI/CSP capex duration and customer concentration;
- optical-module ASP declines / technology transitions;
- supply bottlenecks and execution;
- very high absolute expectations and five-year price percentile;
- planned H-share process can alter future share count/capital structure and must be bridged once final terms are known.

Status:

```text
current_core_growth: A+
earnings_quality: A+
expectation_test: POSITIVE under stated horizon assumptions
duration_risk: HIGH
crowding_risk: HIGH
status: GROWTH_VALUE_CANDIDATE / HIGH_DURATION_RISK / WATCH_FOR_ENTRY
formal_buy: NO
```

Scheduled H1 report checkpoint: 2026-08-25.

---

## 300308 中际旭创

### Price / share-class caveat

```text
A-share close: 943.00
MA20: 965.30
MA60: 1111.75
MA120: 917.41
MA250: 686.90
1y percentile: 76.8%
5y percentile: 95.36%
```

The company is now A+H dual listed. Total economic shares used for an **A-price-implied total equity value** are roughly 11.697 亿, which gives approximately `11031 亿 RMB` if all shares were marked at the A price.

This is **not** actual consolidated market cap. Actual consolidated market cap requires class-specific A/H prices and FX.

### Latest fundamentals

2026Q1:

```text
Revenue: ~194.96 亿, +192.12%
Headline profit: ~57.35 亿, +262.28%
Recurring profit: ~57.18 亿, +264.56%
OCF: ~33.68 亿, +55.58%
```

The latest company investor communication reviewed in the batch said:

- overall industry demand remains very strong;
- almost all customer orders cover full-year 2026 and some extend into 2027;
- 800G / 1.6T / 2.4T / NPO demand for 2027 has high visibility;
- some major customers have already provided 2028 new-product indications;
- management rejected market rumors of destructive 1.6T price competition.

Public consensus reference:

```text
2026E: ~300.92 亿
2027E: ~527.21 亿
2028E: ~775.57 亿
```

Using the A-price-implied total equity value, approximate forward PE:

```text
2026E ~36.7x
2027E ~20.9x
2028E ~14.2x
```

### Reverse duration test

At 25x terminal PE / 12% required return:

```text
required 2028 profit: ~577.2 亿
required CAGR from 2026E: ~31.6%/yr
```

Current third-party 2028 consensus (~775.6 亿) is above the required-profit threshold.

If that consensus were achieved, the discounted A-equivalent value stress test is around `1267 RMB/share`, about 34% above the 2026-08-14 A quote.

Again, this is not a formal target because:

- 2026H1 formal financial results are not yet in hand;
- consensus can change materially;
- A/H share-class valuation must be handled explicitly;
- terminal multiple and required return are assumptions.

Status:

```text
business_quality: A+
current_core_growth: A+
order_visibility: A+
earnings_quality_Q1: A+
expectation_test: POSITIVE under stated assumptions
duration_risk: HIGH
share_class_market_cap: CONSOLIDATED_UNVERIFIED
status: GROWTH_VALUE_CANDIDATE / HIGH_DURATION_RISK / H1_PENDING
formal_buy: NO
```

Scheduled H1 report: 2026-08-24.

---

## 300394 天孚通信

### Price / market cap

```text
close: 267.71
MA20: 212.87
MA60: 266.78
MA120: 253.07
MA250: 189.07
1y percentile: 86.0%
5y percentile: 97.2%
10d return: +56.55%
shares: ~10.9083 亿
market cap: ~2920 亿 RMB
```

Legacy technical system also identified abnormal short-term extension; this is entry/crowding evidence, not a fundamental rejection.

### Latest fundamentals

2026H1 preview:

```text
Headline profit: ~11.24-13.04 亿, +25%-45%
Recurring profit: ~10.89-12.84 亿, +25.56%-48.02%
Non-recurring impact: ~0.20-0.35 亿
```

Current earnings quality is clean. AI/data-center optical-component demand remains strong, while management also cited material shortages and FX losses as constraints.

Consensus reference:

```text
2026E: ~33.74 亿
2027E: ~45.15 亿
2028E: ~62.56 亿
```

Current forward PE:

```text
2026E ~86.6x
2027E ~64.7x
2028E ~46.7x
```

### Reverse duration test

Even using a relatively rich 35x terminal PE, current market cap requires:

```text
2028 terminal profit: ~109.1 亿
required CAGR from 2026E: ~64.1%/yr
```

That required profit is far above current third-party 2028 consensus (~62.6 亿).

Discounting the current 2028 consensus at a 35x terminal multiple produces an illustrative present-value equivalent of only about `153.4 RMB/share`, far below 267.71.

Status:

```text
business_quality: A
core_growth: A
valuation: F under duration stress test
crowding: EXTREME
expectation_risk: EXTREME
status: EXPECTATION_TOO_HIGH / CROWDING_EXTREME / WAIT_FOR_PRICE
formal_buy: NO
```

---

## 300476 胜宏科技

### Price / share-class caveat

```text
A-share close: 269.33
MA20: 236.66
MA60: 298.80
MA120: 299.88
MA250: 287.29
1y percentile: 33.2%
5y percentile: 86.64%
10d return: +41.45%
```

The company is A+H dual listed. Using roughly 9.828 亿 total economic shares gives an **A-price-implied total equity value** of about `2647 亿 RMB`; this is not actual consolidated market cap.

### Latest fundamentals

2026Q1:

```text
Revenue: ~55.19 亿, +27.99%
Headline profit: ~12.88 亿, +39.95%
Recurring profit: ~12.57 亿, +36.07%
OCF: ~21.17 亿, +399.38%
```

Current operating quality is good, though capex and debt expansion require monitoring. No reliable 2026H1 preview was found in this batch.

Consensus reference:

```text
2026E: ~87.5 亿
2027E: ~148.9 亿
2028E: ~225.3 亿
```

A-price-implied forward PE:

```text
2026E ~30.3x
2027E ~17.8x
2028E ~11.8x
```

### Reverse duration test

At a 22x terminal PE / 12% hurdle:

```text
required 2028 profit: ~157.4 亿
required CAGR from 2026E: ~28.1%/yr
```

This is below current 2028 consensus (~225.3 亿). If the consensus were achieved, the A-equivalent discounted-value stress test would be around `385.5 RMB/share`, about 43% above the A quote.

Confidence is lower than 新易盛 because H1 financial confirmation is missing and because actual consolidated A/H market cap is not used.

Status:

```text
business_quality: A
Q1_core_growth: A
cash_conversion_Q1: A
expectation_test: POSITIVE but lower-confidence
duration_risk: HIGH
crowding: HIGH
share_class_market_cap: CONSOLIDATED_UNVERIFIED
status: GROWTH_VALUE_CANDIDATE / H1_CONFIRMATION_REQUIRED / CROWDING_HIGH
formal_buy: NO
```

---

## 002463 沪电股份

### Price / market cap

```text
close: 121.27
MA20: 114.46
MA60: 128.18
MA120: 108.80
MA250: 87.54
1y percentile: 82.8%
5y percentile: 96.56%
10d return: +16.89%
shares: ~19.24 亿
market cap: ~2333 亿 RMB
```

### Latest fundamentals

2026H1 preview:

```text
Headline profit: 28.3-30.0 亿, +68.17% to +78.28%
Recurring profit: 27.3-28.8 亿, +66.08% to +75.20%
```

Q1 headline profit was ~12.42 亿 and recurring profit ~11.63 亿, implying Q2 sequential acceleration. Drivers include high-speed switches, AI servers, HPC, automotive electronics and product-mix improvement. The Thailand subsidiary turned profitable in Q2.

Consensus reference:

```text
2026E: ~57.64 亿
2027E: ~87.99 亿
2028E: ~131.0 亿
```

Current forward PE:

```text
2026E ~40.5x
2027E ~26.5x
2028E ~17.8x
```

### Reverse duration test

At 25x terminal PE / 12% hurdle:

```text
required 2028 profit: ~122.1 亿
required CAGR from 2026E: ~37.3%/yr
```

This requirement is close to, but slightly below, current 2028 consensus (~131 亿).

The discounted consensus stress-test value is roughly `130.1 RMB/share`, only about 7% above the current quote. Thus the stock looks approximately fair to slightly attractive rather than deeply mispriced.

Status:

```text
business_quality: A
current_core_growth: A+
earnings_quality: A+
expectation_risk: MEDIUM
valuation: FAIR_TO_SLIGHT_VALUE
status: QUALITY_GROWTH / FAIR_TO_SLIGHT_VALUE / WATCH_FOR_ENTRY
formal_buy: NO
```

---

## 002916 深南电路

### Price / market cap

```text
close: 378.00
MA20: 343.91
MA60: 387.09
MA120: 330.98
MA250: 264.79
1y percentile: 85.6%
5y percentile: 97.12%
10d return: +22.73%
shares: ~6.81 亿
market cap: ~2574 亿 RMB
```

### Latest fundamentals

2026H1 preview:

```text
Headline profit: 21-23 亿, +54.41% to +69.12%
Recurring profit: 20.8-22.8 亿, +64.36% to +80.17%
```

The company cited AI-driven storage and compute demand, Guangzhou capacity ramp, product-mix optimization and efficiency improvement. PCB data-center/communications exposure and package-substrate memory exposure also improved.

Consensus reference:

```text
2026E: ~53.56 亿
2027E: ~73.95 亿
2028E: ~100.82 亿
```

Current forward PE:

```text
2026E ~48.1x
2027E ~34.8x
2028E ~25.5x
```

### Reverse duration test

At 25x terminal PE / 12% hurdle:

```text
required 2028 profit: ~134.7 亿
required CAGR from 2026E: ~47.6%/yr
```

This required terminal profit is materially above current 2028 consensus (~100.8 亿).

Under the same assumptions, discounted consensus value is about `282.9 RMB/share`, roughly 25% below the current A quote.

The company remains high quality; the issue is price/expectation, not fundamentals.

Current private-placement plans also create potential future financing dilution/proceeds that must be bridged once final issuance terms are known.

Status:

```text
business_quality: A
current_core_growth: A+
earnings_quality: A+
expectation_risk: HIGH
status: QUALITY_GROWTH / EXPECTATION_HIGH / WAIT_FOR_PRICE
formal_buy: NO
```

---

## 002837 英维克

### Price / market cap

```text
close: 57.09
MA20: 54.73
MA60: 66.69
MA120: 71.97
MA250: 66.85
1y percentile: 28.4%
5y percentile: 85.68%
10d return: +20.32%
shares: ~12.7435 亿
market cap: ~727.5 亿 RMB
```

### Latest fundamentals

2025:

```text
Revenue: ~60.68 亿, +32.23%
Headline profit: ~5.22 亿, +15.30%
```

2026Q1:

```text
Revenue: ~11.75 亿, +26.03%
Headline profit: ~0.0866 亿, -81.97%
Recurring profit: ~0.0539 亿, -87.10%
OCF: ~-3.86 亿
```

This is not a clean current-growth case. Revenue expanded while profit collapsed, with margin/expense/FX/credit effects requiring H1 confirmation.

Consensus reference:

```text
2026E: ~11.94 亿
2027E: ~20.36 亿
2028E: ~30.24 亿
```

Current forward PE:

```text
2026E ~60.9x
2027E ~35.7x
2028E ~24.1x
```

### Reverse duration test

At 30x terminal PE / 12% hurdle:

```text
required 2028 profit: ~31.7 亿
required CAGR from 2026E: ~51.0%/yr
```

That is close to the current 2028 consensus (~30.24 亿), so the stock can look roughly fair **only if** a very large earnings recovery actually occurs.

Discounted consensus value is about `54.4 RMB/share`, close to the 57.09 market price. Because Q1 fundamentals are currently poor, this is not a value signal yet.

Status:

```text
valuation_if_recovery_executes: FAIR
current_fundamental_momentum: D
expectation_risk: MEDIUM-HIGH
status: FUNDAMENTAL_RECOVERY_REQUIRED / WATCH_FOR_H1 / WAIT_FOR_ENTRY
formal_buy: NO
```

Scheduled H1 report: 2026-08-25.

---

# Batch 11 ranking

By risk-adjusted current valuation versus required future execution:

```text
1. 新易盛 — strongest combination of confirmed H1 core acceleration and positive reverse-duration gap
2. 中际旭创 — positive duration gap and exceptional order visibility, but H1 formal confirmation + A/H market-cap precision still pending
3. 沪电股份 — clean H1 acceleration; current price roughly fair/slightly attractive rather than deeply cheap
4. 胜宏科技 — reverse-duration gap looks attractive, but lower confidence due no H1 preview, A/H market-cap caveat and sharp short-term move
5. 英维克 — valuation roughly fair only if a major profit recovery occurs; fundamentals do not yet confirm it
6. 深南电路 — excellent company/earnings, but current price requires profit above current 2028 consensus under the stated terminal assumptions
7. 天孚通信 — quality remains high, but duration/expectation burden and short-term crowding are extreme
```

## Main model lesson

The batch validates the reason to loosen static valuation filters:

> A stock with a high current PE can still be a fundamental-value candidate if the market price requires a future profit level below a credible forward earnings path.

But a second rule is equally important:

> Future-year profit × future terminal PE is not today's fair value. Terminal values must be discounted to the analysis date with an explicit required return.

PR #25 now contains valuation-horizon primitives to enforce this distinction and reverse-solve required terminal profit / required CAGR.

## Remaining core queue

```text
002270 华明装备 — revisit latest available H1 data / current price
```

After that, create a fresh-data master ranking across all completed sectors.
