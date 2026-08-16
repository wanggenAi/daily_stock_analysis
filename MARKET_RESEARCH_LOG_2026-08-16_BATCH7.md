# Market Research Log — 2026-08-16 — Batch 7

> Cross-sector valuation comparison: tungsten resource vs grid automation/software vs grid core platform.
>
> Read with `CURRENT_MARKET_RESEARCH.md`, `MODEL_EVOLUTION_LOG.md`, and prior batch logs.

## Analysis snapshot

```text
analysis_as_of: 2026-08-16
latest_a_share_trading_day: 2026-08-14
market_regime: YELLOW
market_position_multiplier: 0.5
price_source: repository production artifact / tencent_raw
price_freshness: FRESH for all three names
fundamental_freshness: ACCEPTABLE
formal_buy: NO unless all downstream gates separately pass
```

## 1) 002378 章源钨业

### Price snapshot

```text
close: 26.25
MA20: 24.11
MA60: 28.93
MA120: 31.45
MA250: 22.66
price_percentile_1y: 0.584
price_percentile_5y: 0.9168
return_10d_pct: +18.14%
```

Current shares used: `1,201,417,666`.
Approximate equity market cap at 26.25: `~315.4 亿 RMB`.

### Latest fundamentals

2025 reported attributable profit: roughly `2.90 亿 RMB` from quarterly aggregation.

2026Q1:

```text
Revenue: ~26.31 亿, +121.76%
Attributable net profit: ~3.813 亿, +795.78%
Recurring attributable profit: ~3.784 亿, +824.73%
```

2026H1 preview:

```text
Attributable net profit: 6.3-7.5 亿
Recurring attributable profit: 6.2-7.4 亿
```

Headline and recurring profit are very close -> current-period earnings quality is high.

### Commodity driver / cycle warning

The H1 earnings boom occurred during an extraordinary tungsten-price phase. By July the company's long-contract reference prices had already fallen materially:

```text
July first half:
55% black tungsten concentrate: 44.8 万/标吨
APT: 66.0 万/吨

July second half:
55% black tungsten concentrate: 41.1 万/标吨
APT: 60.5 万/吨
```

The July second-half prices were down roughly 8% from the first-half July quote. Earlier June quotes were higher still.

This makes simple `H1 × 2` invalid.

### Forward-cycle vs through-cycle earnings

Working research assumptions:

```text
forward-cycle 2026 profit:
Bear 10 亿
Base 12 亿
Bull 14 亿

through-cycle normalized profit:
Bear 4.5 亿
Base 6.5 亿
Bull 9.0 亿
```

The forward-cycle range acknowledges strong H1 realized profit while the through-cycle range reflects normalization from extraordinary tungsten pricing.

### Valuation

Current market cap / forward-cycle profit:

```text
10 亿 -> ~31.5x
12 亿 -> ~26.3x
14 亿 -> ~22.5x
```

Current market cap / through-cycle Base profit (6.5 亿): `~48.5x`.

Through-cycle scenario fair value:

```text
Bear: 4.5 亿 @ 18x -> 81 亿 -> ~6.74/share
Base: 6.5 亿 @ 24x -> 156 亿 -> ~12.98/share
Bull: 9.0 亿 @ 30x -> 270 亿 -> ~22.47/share
```

At 26.25 the stock is above this working Bull through-cycle value.

Reverse implied profit:

```text
At 24x fair PE, current market cap implies ~13.1 亿 sustainable profit.
At 30x fair PE, it still implies ~10.5 亿 sustainable profit.
```

### Status

```text
industry_logic: A
strategic_scarcity: A
current_cycle_earnings: A+
earnings_quality: A
cycle_risk: VERY HIGH
through_cycle_valuation: D
status: PRIORITY_RESEARCH / CYCLE_PEAK_REVIEW / EXPECTATION_HIGH / WAIT_FOR_PRICE
formal_buy: NO
```

Scheduled 2026H1 report: 2026-08-25.

---

## 2) 000682 东方电子

### Price snapshot

```text
close: 11.88
MA20: 12.00
MA60: 12.54
MA120: 12.91
MA250: 12.45
price_percentile_1y: 0.332
price_percentile_5y: 0.86
return_10d_pct: -0.83%
```

Shares: `1,340,727,007`.
Approximate market cap: `~159.3 亿 RMB`.

### Latest fundamentals

2025:

```text
Revenue: ~83.77 亿, +11.04%
Attributable net profit: ~9.12 亿, +33.35%
Recurring attributable profit: ~7.30 亿, +12.69%
```

2026Q1:

```text
Revenue: ~15.19 亿, +8.05%
Attributable net profit: ~2.358 亿, +95.06%
Recurring attributable profit: ~1.254 亿, +9.66%
```

The Q1 headline/core divergence is material. The main source was approximately `1.239 亿 RMB` of fair-value gain, mainly from the company's holding in 南网数字. Q1 total non-recurring profit was about `1.104 亿 RMB` after tax/minority effects.

Therefore the correct operating signal is closer to `+9.7%` recurring-profit growth, not `+95%` headline growth.

### Structural positives

- grid automation / distribution / digital-energy software exposure;
- high cash balance and recurring service/software characteristics in parts of the portfolio;
- State Grid H1 2026 fixed-asset investment exceeded `3100 亿 RMB`, +12.6% YoY;
- company plans a `24.7 亿 RMB` smart-energy innovation industrial park, creating long-term capacity/technology optionality but also execution/capital-allocation risk.

### Consensus reference

Public forecast aggregation around late July 2026:

```text
2026E headline net profit: ~10.30 亿
2027E: ~12.03 亿
2028E: ~13.80 亿
```

The model does not use the 2026 headline consensus directly as normalized core profit because Q1 already contains a large fair-value gain.

### Working normalized-core scenarios

```text
Bear: 7.5 亿
Base: 8.8 亿
Bull: 10.5 亿
```

Scenario fair value using plain equity-profit PE (no separate net-cash add-back):

```text
Bear: 7.5 亿 @ 18x -> ~10.07/share
Base: 8.8 亿 @ 22x -> ~14.44/share
Bull: 10.5 亿 @ 26x -> ~20.36/share
```

At 11.88 the stock is below the working Base fair value by roughly 18%, but only modestly above Bear.

### Reverse pricing

Current market cap implies:

```text
at 20x -> ~7.96 亿 sustainable profit
at 22x -> ~7.24 亿
at 24x -> ~6.64 亿
```

Those requirements are not obviously aggressive relative to 2025 recurring profit (7.30 亿), which is why the stock qualifies as a valuation candidate despite weak technical confirmation.

### Status

```text
industry_logic: A-
headline_earnings_quality_Q1: LOW
core_earnings_quality: A-
valuation: B+
expectation_risk: LOW-MEDIUM
entry_readiness: NOT CONFIRMED
status: VALUE_CANDIDATE / WATCH_FOR_H1 / WATCH_FOR_ENTRY
formal_buy: NO
```

Scheduled 2026H1 report: 2026-08-20.

---

## 3) 600406 国电南瑞

### Price snapshot

```text
close: 23.23
MA20: 24.05
MA60: 23.39
MA120: 25.05
MA250: 23.86
price_percentile_1y: 0.488
price_percentile_5y: 0.7632
return_10d_pct: -4.60%
```

2025 total shares: `8,031,756,156`.
Approximate equity market cap at 23.23: `~1865.8 亿 RMB`.

### Latest fundamentals

2025:

```text
Revenue: ~662.29 亿, +14.53%
Attributable net profit: ~82.79 亿, +8.79%
Recurring attributable profit: ~79.83 亿, +8.04%
Operating cash flow: ~127.69 亿, +15.17%
ROE: ~16.26%
```

2026Q1:

```text
Revenue: ~95.64 亿, +7.52%
Attributable net profit: ~7.21 亿, +6.04%
Recurring attributable profit: ~6.42 亿, +5.39%
```

Q1 is seasonally weak for this business; annual cash conversion and earnings quality remain strong in the latest full-year data.

### Industry driver

State Grid reported more than `3100 亿 RMB` of H1 2026 fixed-asset investment, +12.6% YoY, with UHV, clean-energy transmission, interprovincial flexibility and grid reinforcement accelerating.

### Consensus reference

Late-July 2026 aggregation:

```text
2026E net profit: ~93.15 亿
2027E: ~103.23 亿
2028E: ~115.98 亿
```

At current market cap, approximate forward PE:

```text
2026E: ~20.0x
2027E: ~18.1x
2028E: ~16.1x
```

### Working scenario valuation

```text
Bear: 88 亿 @ 18x -> ~19.72/share
Base: 95 亿 @ 22x -> ~26.02/share
Bull: 105 亿 @ 25x -> ~32.68/share
```

At 23.23, current price is about 12% below the working Base value and clearly below the Bull value.

Reverse implied profit:

```text
20x -> ~93.3 亿
22x -> ~84.8 亿
24x -> ~77.7 亿
```

The current price does not require an aggressive long-term profit assumption if a low-20s fair multiple is justified by franchise quality, cash conversion and grid-investment visibility.

### Status

```text
industry_logic: A
business_quality: A+
earnings_quality: A+
cycle_risk: LOW
valuation: B+
expectation_risk: LOW-MEDIUM
entry_readiness: NOT CONFIRMED
market_regime: YELLOW
status: VALUE_CANDIDATE / HIGH_QUALITY / WATCH_FOR_ENTRY
formal_buy: NO
```

Scheduled 2026H1 report: 2026-08-27.

---

# Cross-sector ranking after Batch 7

This ranking is based on current valuation balance + earnings durability, not raw growth rate:

```text
1. 国电南瑞 600406 — best durability/valuation balance; lower growth but low expectation burden
2. 东方电子 000682 — more valuation upside, but Q1 headline quality is poor and H1 is imminent
3. 章源钨业 002378 — strongest cycle/scarcity elasticity, but current price still requires unusually high sustainable profit
```

Important lesson:

> The sector with the strongest current profit growth is not automatically the highest-odds stock. Through-cycle earnings and expectations matter more than headline YoY growth.

## Model-code decision from this batch

No new production metric was added merely for novelty.

Existing PR #25 primitives already handle the main failure modes:

- `002378`: forward-cycle vs through-cycle profit;
- `000682`: recurring/core profit vs fair-value gain;
- `600406`: plain recurring-equity PE without double-counting net cash.

The correct optimization decision for this batch is to **reuse validated primitives rather than add redundant indicators**.

## Next continuous queue

Continue without waiting for a new chat message:

```text
601020 华钰矿业
600497 驰宏锌锗
002428 云南锗业
000962 东方钽业
300054 鼎龙股份
000400 许继电气
600312 平高电气
601567 三星医疗
001309 德明利
300475 香农芯创
300223 北京君正
688766 普冉股份
301666 大普微
300502 新易盛
300308 中际旭创
300394 天孚通信
300476 胜宏科技
002463 沪电股份
002916 深南电路
002837 英维克
```

`002270 华明装备` remains a revisit item after fresh 2026H1 data because the prior session found no reliable H1 confirmation.
