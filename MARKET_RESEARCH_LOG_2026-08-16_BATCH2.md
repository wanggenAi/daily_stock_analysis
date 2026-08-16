# Market Research Log — 2026-08-16 — Batch 2

> Read together with `CURRENT_MARKET_RESEARCH.md`.
>
> This file records the second live-test batch of the fundamental/reverse-valuation framework. It **supersedes the old `Next deep-valuation batch` section** in `CURRENT_MARKET_RESEARCH.md` for continuation purposes.
>
> Hard rule: all price-sensitive conclusions must be recomputed from a fresh market snapshot in the next session. Exact 2026-08-14 closes were not reliably verified from the public web sources available in this session, so no new Formal BUY / exact MOS / exact entry-price output is authorized from this log.

## Analysis snapshot

```text
analysis_as_of: 2026-08-16
latest_a_share_trading_day: 2026-08-14
fundamental_freshness: FRESH / ACCEPTABLE
industry_freshness: ACCEPTABLE
price_freshness: UNVERIFIED for exact 2026-08-14 closes
formal_buy_from_this_batch: DISABLED until fresh price verification
```

## Batch objective

Test five high-growth semiconductor / storage names against the upgraded framework:

```text
002371 北方华创
688012 中微公司
688072 拓荆科技
301308 江波龙
688525 佰维存储
```

The main questions were:

1. Is a high static PE genuinely expensive, or can forward/core earnings justify it?
2. Are headline profits recurring operating earnings or distorted by investment/fair-value gains?
3. For memory-cycle names, what is current-cycle forward profit versus sustainable through-cycle profit?
4. Can the system avoid promoting a stock simply because sector momentum or headline YoY growth is spectacular?

---

## 1. 002371 北方华创

### Latest fundamental basis used

2025 annual report:

```text
Revenue: ~393.53 亿 RMB, +30.85% YoY
Attributable net profit: ~55.22 亿 RMB, -1.77% YoY
Recurring attributable profit: ~53.36 亿 RMB, -4.22% YoY
Operating cash flow: ~21.33 亿 RMB, +37.48% YoY
```

2026Q1:

```text
Revenue: ~103.23 亿 RMB, +25.80% YoY
Attributable net profit: ~16.35 亿 RMB, +3.42% YoY
Recurring attributable profit: ~16.27 亿 RMB, +3.60% YoY
Operating cash flow: ~+7.48 亿 RMB
R&D expense: ~14.02 亿 RMB, +36.64% YoY
```

The 2026H1 formal report was not yet available at this analysis time; scheduled disclosure date observed in public calendar data: 2026-08-26.

### Interpretation

- Revenue growth remains strong.
- Headline and recurring profit are almost identical -> **high earnings quality**.
- Profit growth is much slower than revenue growth, but R&D intensity is an important reason; do not mistake heavy current R&D for an automatic deterioration in franchise quality.
- This is exactly the type of company that must **not** be removed merely because static PE is high.

### Provisional normalized-core-profit working range

**Inference only; revalidate after H1:**

```text
Bear: ~60 亿 RMB
Base: ~66 亿 RMB
Bull: ~72 亿 RMB
```

### Current research state

```text
research_priority: P0
status: PRIORITY_RESEARCH / EXPECTATION_CHECK
headline_earnings_quality: HIGH
valuation_confidence: MEDIUM until H1 + fresh price
formal_buy: NO (price freshness not verified)
```

### What to calculate next

- Fetch current price / market cap.
- Fetch H1 report once disclosed.
- Reverse solve implied normalized profit at quality-adjusted fair multiples.
- Determine whether current valuation requires a return to very high profit growth or merely sustained revenue/share gains.

---

## 2. 688012 中微公司

### Latest fundamental basis used

2025 annual report:

```text
Revenue: ~123.85 亿 RMB, +36.62% YoY
Attributable net profit: ~21.11 亿 RMB, +30.69% YoY
Recurring attributable profit: ~15.50 亿 RMB, +11.64% YoY
Operating cash flow: ~22.95 亿 RMB, +57.39% YoY
R&D ratio: ~30.23%
```

2026Q1:

```text
Revenue: ~29.15 亿 RMB, +34.13% YoY
Attributable net profit: ~9.30 亿 RMB, +197.2% YoY
Recurring attributable profit: ~4.78 亿 RMB, +60.09% YoY
Investment income: ~4.995 亿 RMB
Fair-value-change gain: ~0.544 亿 RMB
```

The 2026H1 formal report was not yet available at this analysis time; scheduled disclosure date observed: 2026-08-20.

### Interpretation

The headline `9.30 亿` Q1 profit is **not** a clean core-operating number.

The recurring profit `4.78 亿` is a much better starting point for normalized operating earnings, and its +60% growth still shows a strong underlying business inflection.

Therefore:

```text
Q1 headline profit × 4 = INVALID
Q1 recurring profit × 4 = still too simplistic
```

### Provisional normalized-core-profit working range

**Inference only; revalidate after H1:**

```text
Bear: ~20 亿 RMB
Base: ~23 亿 RMB
Bull: ~27 亿 RMB
```

### Current research state

```text
research_priority: P0
status: PRIORITY_RESEARCH / EARNINGS_QUALITY_ADJUSTED
headline_earnings_quality: MEDIUM-LOW
core_earnings_quality: HIGHER than headline metric suggests
valuation_confidence: MEDIUM until H1 + fresh price
formal_buy: NO
```

### Important framework finding

When normalizing operating earnings, we should exclude large investment/fair-value gains from the sustainable profit base — **but not pretend the underlying investment assets have zero economic value**.

This creates a need for a separate valuation adjustment such as:

```text
non_operating_asset_adjustment
investment_asset_value
net_cash_or_investment_adjustment
```

or a lightweight SOTP bridge.

The model should therefore distinguish:

```text
core_operating_value
+
non_operating_asset_value
=
enterprise/equity fair value
```

instead of either capitalizing one-off gains forever or deleting the assets entirely.

---

## 3. 688072 拓荆科技

### Latest fundamental basis used

2025 annual report:

```text
Revenue: ~65.19 亿 RMB, +58.87% YoY
Attributable net profit: ~9.27 亿 RMB, +34.67% YoY
Recurring attributable profit: ~7.23 亿 RMB, +103.05% YoY
Operating cash flow: ~36.33 亿 RMB
```

2026Q1:

```text
Revenue: ~11.12 亿 RMB, +56.97% YoY
Attributable net profit: ~5.71 亿 RMB
Recurring attributable profit: ~1.02 亿 RMB
Fair-value-change gain: ~4.48 亿 RMB
Operating cash flow: ~-5.20 亿 RMB
```

The 2026H1 formal report was not yet available at this analysis time; scheduled disclosure date observed: 2026-08-21.

### Interpretation

This is the cleanest live test so far for `earnings_quality_score`.

A naive model sees:

```text
Q1 attributable profit = 5.71 亿
```

and may conclude earnings exploded.

But roughly `4.48 亿` came from fair-value changes, while recurring profit was only about `1.02 亿`.

Therefore the upgraded system must refuse to annualize headline profit and must explicitly surface the distortion.

At the same time, recurring profit itself improved strongly from the prior-year base, so this is **not** a simple rejection. It is a core-business inflection candidate that needs cleaner H1 confirmation.

### Provisional normalized-core-profit working range

**Low-confidence inference; revalidate after H1:**

```text
Bear: ~10 亿 RMB
Base: ~12 亿 RMB
Bull: ~14 亿 RMB
```

### Current research state

```text
research_priority: P1 pending H1 confirmation
status: VALUATION_REVIEW / LOW_HEADLINE_EARNINGS_QUALITY / CORE_INFLECTION_WATCH
headline_earnings_quality: LOW
core_trend: POSITIVE
valuation_confidence: MEDIUM-LOW
formal_buy: NO
```

---

## 4. 301308 江波龙

### Latest fundamental basis used

2025 annual report:

```text
Revenue: ~227.66 亿 RMB, +30.36% YoY
Attributable net profit: ~14.23 亿 RMB, +185.41% YoY
Recurring attributable profit: ~12.89 亿 RMB, +674.08% YoY
Operating cash flow: ~-12.01 亿 RMB
```

2026Q1:

```text
Revenue: ~99.09 亿 RMB, +132.79% YoY
Attributable net profit: ~38.62 亿 RMB
Recurring attributable profit: ~39.43 亿 RMB
Operating cash flow: ~-28.75 亿 RMB
```

2026H1 earnings preview:

```text
Revenue: ~220-250 亿 RMB
Attributable net profit: ~92-110 亿 RMB
Recurring attributable profit: ~90-105 亿 RMB
```

Implied Q2 attributable profit from the preview is roughly `53.4-71.4 亿 RMB`, meaning the earnings acceleration continued beyond Q1.

The 2026H1 formal report was not yet available at this analysis time; scheduled disclosure date observed: 2026-08-27.

### Industry driver checked in this session

Latest industry material checked indicated that 3Q26 memory pricing was still expected to rise, but at a slower rate than the earlier phase of the cycle:

```text
General DRAM contract price: expected +13% to +18% QoQ in 3Q26
NAND Flash: expected +10% to +15% QoQ in 3Q26
```

AI/data-center demand remains a major support, while the high base and consumer-demand pressure increase the risk of treating current profitability as permanently sustainable.

### Interpretation

This is **not** a normal growth-stock PE problem. It is a cycle-normalization problem.

The framework needs two separate earnings concepts:

```text
forward_cycle_profit
through_cycle_normalized_profit
```

For 2026, forward profit may be extraordinarily high. That does **not** mean the same level should be capitalized indefinitely at a normal growth-stock multiple.

Also note the weak cash conversion in Q1 despite huge accounting profit. Inventory, procurement commitments, working capital and cash conversion must be inspected in the H1 report.

### Current research state

```text
research_priority: P0
status: PRIORITY_RESEARCH / CYCLE_PEAK_REVIEW / VALUATION_UNCERTAIN
current_cycle_earnings: EXTREMELY STRONG
through_cycle_confidence: LOW-MEDIUM
cash_conversion_watch: HIGH PRIORITY
formal_buy: NO
```

No precise sustainable normalized-profit range is locked in yet. Doing so before H1 cash-flow/inventory detail would create false precision.

---

## 5. 688525 佰维存储

### Latest fundamental basis used

2025 earnings basis used in-session:

```text
Attributable net profit: ~8.67 亿 RMB
```

2026Q1:

```text
Revenue: ~68.14 亿 RMB, +341.53% YoY
Attributable net profit: ~28.99 亿 RMB
Recurring attributable profit: ~28.16 亿 RMB
Operating cash flow: ~-27.06 亿 RMB
```

2026H1 earnings preview:

```text
Revenue: ~150-160 亿 RMB
Attributable net profit: ~70-75 亿 RMB
Recurring attributable profit: ~62-70 亿 RMB
```

Implied Q2 attributable profit is roughly `41.0-46.0 亿 RMB`, again showing continued acceleration.

The 2026H1 formal report was not yet available at this analysis time; scheduled disclosure date observed: 2026-08-25.

### Interpretation

Headline versus recurring profit quality is much cleaner than in the semiconductor-equipment fair-value examples.

However, this does **not** make the profit automatically sustainable:

- memory pricing is cyclical;
- the current AI/storage demand cycle is unusually strong;
- Q1 operating cash flow was materially negative;
- working capital / inventory / procurement structure needs H1 verification.

Therefore it belongs in a high-priority research pool but must receive a `peak_earnings_discount` / cycle-normalization treatment.

### Current research state

```text
research_priority: P0
status: PRIORITY_RESEARCH / CYCLE_PEAK_REVIEW
headline_earnings_quality: HIGH
cycle_risk: VERY HIGH
through_cycle_valuation_confidence: LOW-MEDIUM
cash_conversion_watch: HIGH PRIORITY
formal_buy: NO
```

---

# Cross-stock preliminary research ranking

This is **not a cheapness ranking** because fresh current prices were not verified.

## Quality / durability orientation

```text
1. 北方华创 — very strong franchise + clean earnings; growth investment suppresses near-term profit expansion
2. 中微公司 — strong core growth, but headline profit requires investment-gain adjustment
3. 拓荆科技 — core inflection is interesting, but headline Q1 profit is heavily distorted
4. 佰维存储 — exceptional current earnings momentum, but high cycle and cash-conversion risk
5. 江波龙 — exceptional absolute profit acceleration, but highest need for cycle normalization / working-capital review
```

## Research priority orientation

```text
P0: 北方华创
P0: 中微公司
P0: 江波龙
P0: 佰维存储
P1 pending H1: 拓荆科技
```

Again: P0 means **research first**, not BUY.

---

# Two framework refinements discovered by live testing

These are not extra decorative indicators. They close concrete model failure modes found during the batch.

## A. Separate current-cycle profit from through-cycle sustainable profit

For cyclical industries such as memory, tungsten, shipping, panels, hogs, chemicals, etc., add or formalize:

```text
forward_cycle_profit_bear/base/bull
through_cycle_normalized_profit_bear/base/bull
peak_earnings_discount
cycle_profit_gap
```

Use `forward_cycle_profit` to answer:

> What can the company plausibly earn in the current 12-month cycle?

Use `through_cycle_normalized_profit` to answer:

> What earnings level is safe enough to capitalize at a sustainable multiple?

Do not let an extraordinary boom-year profit automatically become the permanent valuation base.

## B. Separate recurring earnings normalization from non-operating asset value

For companies with material investment income / fair-value gains:

```text
normalized_core_operating_profit
non_operating_asset_value
net_cash_or_investment_adjustment
```

The model should:

1. remove one-off/non-operating gains from sustainable operating profit;
2. avoid capitalizing those gains as recurring earnings;
3. still recognize the economic value of the underlying financial/investment assets where reliable data exists;
4. lower confidence rather than invent asset values when data is insufficient.

This prevents both overvaluation and undervaluation.

---

# Next continuation plan

## Immediate next research batch

After refreshing the full market snapshot and current prices, continue with:

```text
688120 华海清科
300604 长川科技
688019 安集科技
300666 江丰电子
603986 兆易创新
```

## Near-term report checkpoints

Revisit the second batch when formal H1 reports become available:

```text
688012 中微公司 — scheduled 2026-08-20
688072 拓荆科技 — scheduled 2026-08-21
688525 佰维存储 — scheduled 2026-08-25
002371 北方华创 — scheduled 2026-08-26
301308 江波龙 — scheduled 2026-08-27
```

A new session should **not** wait for these dates if current analysis is requested; use the latest available data at that time and label its freshness. When a new report is available, it supersedes the preview/Q1 assumptions above.

## Resume protocol

A new session should:

1. Read `AGENTS.md`.
2. Read `CURRENT_MARKET_RESEARCH.md`.
3. Read this file `MARKET_RESEARCH_LOG_2026-08-16_BATCH2.md`.
4. Inspect current `main` and latest commit.
5. Pull a fresh market snapshot; do not inherit old prices.
6. Run the next five names above.
7. Update GitHub with the next durable research log / current handoff.
8. Keep `Research Pool = broad`, `Formal BUY = strict`.
