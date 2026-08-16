# Market Research Log — 2026-08-16 — Batch 5

> Read with `CURRENT_MARKET_RESEARCH.md`, `MODEL_EVOLUTION_LOG.md`, and prior batch logs.
>
> This batch completes `300666 江丰电子` using the repository's 2026-08-14 production market snapshot plus the latest available company filings and public industry data. Formal BUY remains separate from research ranking.

## Analysis snapshot

```text
analysis_as_of: 2026-08-16
latest_a_share_trading_day: 2026-08-14
market_regime: YELLOW
market_position_multiplier: 0.5
price_source: repository production artifact / tencent_raw
qfq_source: akshare_sina_qfq
price_freshness: FRESH
fundamental_freshness: ACCEPTABLE (2025 annual + 2026Q1 + 2026H1 preview)
formal_buy: DISABLED unless all existing entry/risk gates pass
```

## 300666 江丰电子

### Price / technical snapshot — 2026-08-14

```text
close: 255.90
open: 256.07
high: 257.50
low: 248.80
MA20: 229.87
MA60: 261.71
MA120: 210.15
MA250: 148.95
price_percentile_1y: 0.896
price_percentile_5y: 0.9792
return_1d_pct: +1.9441%
return_5d_pct: +1.3305%
return_10d_pct: +25.7988%
relative_strength_20d: +11.0212%
relative_strength_60d: +39.3332%
legacy_quant_status: HARD_REJECT
legacy_hard_blocker: price_too_high
legacy_soft_blocker: trend_unconfirmed
```

Under the upgraded architecture, the legacy `price_too_high` hard reject is not enough to remove the name from the broad Research Pool. It remains strong evidence of expectation/entry risk.

### Share count / market cap

The June 2026 private placement added:

```text
10,650,400 shares
issue price: 181.01 RMB/share
gross proceeds: ~19.2783 亿 RMB
net proceeds: ~19.0535 亿 RMB
```

After the new shares listed on 2026-06-23:

```text
total shares: 275,971,083
```

At `255.90`, simple equity market cap is approximately:

```text
~706.21 亿 RMB
```

### 2025 full-year basis

```text
Revenue: ~46.041 亿 RMB, +27.72% YoY
Attributable net profit: ~4.995 亿 RMB, +24.70%
Recurring attributable profit: ~3.604 亿 RMB, +18.74%
Operating cash flow: ~4.700 亿 RMB
ROE: ~10.58%
R&D: ~2.621 亿 RMB, 5.69% of revenue
R&D capitalization: 0
```

Product mix / margin:

```text
Ultra-high-purity sputtering targets revenue: ~28.499 亿, +22.13%; gross margin ~34.24%, +2.89ppt
Precision semiconductor components revenue: ~10.839 亿, +22.24%; gross margin ~14.88%, -9.39ppt
Overall gross margin: ~27.17%, -1.00ppt
```

Precision-component unit volume grew rapidly, but the segment's margin deterioration is a material profitability watch item. The second growth curve is real in volume, but not yet proven to carry target-material economics.

### 2026Q1 basis

```text
Revenue: ~13.055 亿 RMB, +30.49%
Attributable net profit: ~2.097 亿 RMB, +33.42%
Recurring attributable profit: ~1.254 亿 RMB, +37.07%
Operating cash flow: ~1.855 亿 RMB, +206.80%
```

### 2026H1 preview — key quality split

Company preview:

```text
Revenue: ~27 亿 RMB, ~+30% YoY
Attributable net profit: 4.8-5.6 亿 RMB, +89.99% to +121.65%
Recurring attributable profit: 1.8-2.3 亿 RMB, +2.37% to +30.81%
Expected non-recurring gains: ~3.0-3.3 亿 RMB
```

Major non-recurring sources disclosed by the company include:

```text
fair-value change of strategic investment in 芯联集成
partial transfer of associate equity
flat-panel target business integration
fair-value remeasurement of long-term equity investments
share of investee non-recurring items
government grants
```

Interpretation:

> headline profit acceleration is not representative of sustainable operating earnings.

Using the midpoint only as a diagnostic:

```text
headline H1 profit midpoint: ~5.20 亿
recurring H1 profit midpoint: ~2.05 亿
recurring / headline: ~39%
non-recurring share: ~61%
```

Therefore:

```text
H1 headline profit x 2 = INVALID
headline forward PE = misleading without quality adjustment
```

The upgraded `earnings_quality` model correctly routes this case to recurring/core profit.

### Industry / thesis

Core positive drivers:

```text
advanced-node logic and memory fab expansion
AI/HBM-related advanced-process demand
higher target consumption / process complexity
localization of high-purity Al/Ti/Ta/Cu/W target materials
Korea advanced-process target factory
second curve in precision semiconductor components
new capacity in electrostatic chucks / brittle materials / precision components
```

The company stated that ultra-high-purity target revenue continued to grow and that gas-distribution plates, vacuum valves, heaters and other precision parts were scaling. Domestic and overseas customer orders continued to increase.

China's advanced-chip output / fab-capacity expansion remains an industry tailwind, but target-material demand is still exposed to fab-capex cycles, raw-material prices and qualification timing.

### Consensus reference

Third-party consensus aggregation observed as of 2026-07-31:

```text
2026E attributable profit: ~8.26 亿 RMB
2027E attributable profit: ~11.14 亿 RMB
2028E attributable profit: ~15.12 亿 RMB
```

At the 2026-08-14 market cap:

```text
2026E headline PE: ~85.5x
2027E headline PE: ~63.4x
2028E headline PE: ~46.7x
```

Because 2026 headline profit contains very large non-recurring gains, the `85.5x` figure is already generous to the stock: a PE on sustainable 2026 core profit would be substantially higher.

### Core-profit normalization

The formal H1 report is scheduled for 2026-08-25. Until the detailed H2/cash-flow/segment information is available, do not create fake precision.

Working research ranges for **sustainable attributable core profit**, not reported headline profit:

```text
2026 core Bear: ~4.0 亿 RMB
2026 core Base: ~4.7 亿 RMB
2026 core Bull: ~5.5 亿 RMB
```

These ranges are based on the 2025 recurring base, the 2026H1 recurring preview and a non-linear H2 recovery assumption. They are not company guidance and must be replaced after H1 details.

### Reverse implied sustainable profit

At current equity market cap `~706.2 亿`, if the market ultimately assigns a high-quality semiconductor-material multiple of:

```text
55x -> implied sustainable profit ~12.84 亿
50x -> ~14.12 亿
45x -> ~15.69 亿
40x -> ~17.66 亿
```

This calculation is intentionally shown on the current equity market cap without adding net cash again.

Interpretation:

- current valuation requires a sustainable profit level far above the current 2026 recurring-profit run rate;
- at a still-premium `55x`, implied sustainable profit is already above the current 2027 consensus headline profit and approaches the 2028 consensus range;
- therefore the stock price is paying today for successful multi-year execution of target-material share gains + precision-component margin improvement + new capacity/overseas expansion.

### 2027-oriented scenario valuation

Because 2026 headline earnings are distorted, scenarios are based on sustainable/core earnings rather than reported headline earnings.

Working research scenarios:

```text
Bear: 7.5 亿 core profit @ 35x -> 262.5 亿 -> ~95 RMB/share
Base: 9.5 亿 core profit @ 45x -> 427.5 亿 -> ~155 RMB/share
Bull: 12.0 亿 core profit @ 55x -> 660.0 亿 -> ~239 RMB/share
```

At `255.90`, current price is already above this working 2027 Bull case.

This is not a claim that 255.90 can never be justified. It means the current price requires either:

```text
higher sustainable profit than the working Bull case
or
higher long-run multiple than 55x
or
a longer valuation horizon (e.g. 2028+) with successful execution
```

### Financing treatment

The June private placement raised verified net proceeds of about `19.05 亿 RMB`. The latest post-financing H1 balance sheet is not yet published.

Therefore:

- do not treat the newly issued shares as denominator-only dilution;
- do not assume the full 19.05 亿 is idle net cash;
- do not add the entire proceeds to fair value without checking deployment / replacement / project spending;
- after the H1 report, rebuild the post-financing balance-sheet bridge using actual cash, borrowings, restricted funds and construction-in-progress.

### Key risks / watch items

```text
1. Very large headline-vs-recurring profit gap in 2026H1.
2. Precision-component gross margin fell to ~14.88% in 2025 despite strong volume growth.
3. Inventory was large at 2025 year-end; inventory value was a key audit matter.
4. Advanced-node / memory / AI demand must continue translating into customer qualification and revenue.
5. Raw-material price changes (including tantalum/tungsten etc.) may support ASP but can also pressure cost/margins if pass-through lags.
6. Korea/new-project capex execution and utilization need validation.
7. The 10.65m placement shares are scheduled to unlock on 2026-12-23.
8. Current price is in a very high historical percentile and had risen ~25.8% over 10 sessions by 2026-08-14.
```

### Current status

```text
industry_logic: A
strategic_scarcity / localization: A
headline_earnings_growth: A+
core_earnings_growth: B
headline_vs_recurring_quality: C-/D
cash_conversion: B+
second_curve_revenue_growth: A
second_curve_margin_quality: C
valuation: D
expectation_risk: VERY HIGH
entry_readiness: NOT CONFIRMED
status: PRIORITY_RESEARCH / LOW_HEADLINE_EARNINGS_QUALITY / EXPECTATION_HIGH / WAIT_FOR_PRICE
formal_buy: NO
```

### Research price zones

Given the current uncertainty around sustainable core earnings, price zones must remain broad and be recomputed after the H1 report.

```text
>230: still demanding a very strong Bull / long-horizon outcome
190-220: begin re-running valuation if H1 recurring profit / component margin improves
155-185: closer to the working 2027 Base-to-upper-Base value region
<155: potentially meaningful valuation reset, but only if business quality remains intact
```

These are research zones, not Formal BUY levels.

### Model calibration outcome

No new valuation feature was added from this case. The existing fundamental-reverse-valuation core already contains the necessary concepts:

```text
normalized_core_operating_profit
recurring_profit_ratio
non_recurring_profit_share
non_operating_asset_value
financial-asset bridge
financing-proceeds bridge
```

Instead of adding another indicator, PR #25 received a **real-world regression calibration test** using the 2026H1 Jiangfeng midpoint. The test ensures future refactors cannot annualize headline profit when recurring profit is only ~39% of headline earnings.

This follows the model-evolution rule: improve reliability, not indicator count.

## Near-term checkpoint

```text
300666 江丰电子 H1 report scheduled: 2026-08-25
```

Re-run after disclosure with:

```text
actual H1 recurring/core profit
segment gross margins
inventory / receivables
operating cash flow
post-placement cash/debt/CIP
precision-component profitability
new target / component capacity utilization
```

## Next research queue

Refresh the market/fundamental snapshot and continue:

```text
603986 兆易创新
```
