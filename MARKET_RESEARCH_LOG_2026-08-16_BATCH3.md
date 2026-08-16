# Market Research Log — 2026-08-16 — Batch 3

> Read with `CURRENT_MARKET_RESEARCH.md`, `MODEL_EVOLUTION_LOG.md`, and the prior batch logs.
>
> This batch uses the repository's own 2026-08-14 production artifact for the price snapshot when public web search indexes lagged. Formal BUY remains separate from research ranking.

## Analysis snapshot

```text
analysis_as_of: 2026-08-16
latest_a_share_trading_day: 2026-08-14
market_regime_as_of: 2026-08-14
market_regime: YELLOW
market_regime_score: 56.54
market_position_multiplier: 0.5
price_data_coverage_ratio: 1.0
price_source: repository production artifact / tencent_raw
qfq_source: akshare_sina_qfq
fundamental_freshness: ACCEPTABLE
price_freshness: FRESH for 300604 via production snapshot
```

Repository production snapshot for `300604 长川科技` on 2026-08-14:

```text
close: 283.05
open: 287.01
high: 290.99
low: 278.00
latest_trade_date: 2026-08-14
MA20: 278.60
MA60: 272.97
MA120: 211.98
MA250: 147.24
price_percentile_1y: 0.90
price_percentile_5y: 0.98
return_1d_pct: +0.4828%
return_5d_pct: -0.0565%
return_10d_pct: +9.0163%
relative_strength_20d: -4.8037%
relative_strength_60d: +25.7225%
legacy_quant_status: HARD_REJECT
legacy_hard_blocker: price_too_high
legacy_soft_blocker: trend_unconfirmed
```

Important model interpretation: the legacy hard reject above is **not** sufficient grounds to remove the name from the broad Research Pool under the upgraded architecture. It remains useful evidence that the stock is expensive/extended and not entry-ready.

## 300604 长川科技

### Latest fundamental basis

2025 full year:

```text
Revenue: 52.92 亿 RMB, +45.31% YoY
Attributable net profit: 13.31 亿 RMB, +190.42% YoY
Recurring attributable profit: 12.50 亿 RMB, +201.86% YoY
Operating cash flow: 5.62 亿 RMB
```

2026Q1:

```text
Revenue: 13.78 亿 RMB, +69.09% YoY
Attributable net profit: 3.53 亿 RMB, +217.60% YoY
Recurring attributable profit: 3.25 亿 RMB, +612.27% YoY
Operating cash flow: -2.09 亿 RMB
```

2026H1 preview:

```text
Attributable net profit: 9.0-10.0 亿 RMB, +110.76% to +134.18%
Recurring attributable profit: 8.55-9.55 亿 RMB, +139.38% to +167.38%
Estimated non-recurring items: ~0.45 亿 RMB
```

The company attributed H1 growth to prior R&D成果, high-end downstream demand, strong growth in digital testers and other product lines, and scale effects.

### Business / industry driver

The company's main platform covers testers, handlers, probe stations and AOI. Public research material reviewed in this batch indicated that testing equipment is one of the highest-value portions of advanced packaging / high-end AI chip testing capex, and that long test time / complexity for AI and memory devices supports tester demand.

Research focus:

```text
SoC / digital tester share gains
memory tester second growth curve
advanced packaging / AI test intensity
probe-station / handler cross-selling
customer concentration / capex cycle
```

### Consensus earnings reference

Public forecast aggregation observed in the batch (as of late July 2026):

```text
2026E average attributable profit: ~21.97 亿 RMB
2027E average attributable profit: ~30.95 亿 RMB
2028E average attributable profit: ~40.66 亿 RMB
```

These are third-party consensus references, not company guidance.

### Share-count / financing adjustment

2026Q1 reported share capital was about `632,779,813` shares.

The July 2026 private placement issued:

```text
11,163,580 new shares
issue price: 280.11 RMB/share
net proceeds: ~30.92 亿 RMB
```

A simple post-issuance share-count bridge therefore gives approximately:

```text
~643.94 million shares
```

Future per-share valuation must use an explicit share-count denominator rather than blindly reusing old consensus EPS.

At the 2026-08-14 close of `283.05`, the simple post-issuance equity market-cap estimate is roughly:

```text
~1,823 亿 RMB
```

This estimate should be refreshed from the provider's exact total-share field once the production integration exposes it directly.

### Forward PE reference at 283.05

Using the consensus profit references above and the approximate post-issuance market cap:

```text
2026E PE: ~83x
2027E PE: ~59x
2028E PE: ~45x
```

This is materially expensive even after allowing for very strong earnings growth.

### Reverse implied profit

Ignoring a precise net-cash bridge until the H1 post-financing balance sheet is available, current market cap implies roughly:

```text
at 50x fair PE -> ~36.5 亿 sustainable profit
at 45x fair PE -> ~40.5 亿 sustainable profit
at 40x fair PE -> ~45.6 亿 sustainable profit
at 35x fair PE -> ~52.1 亿 sustainable profit
```

Interpretation:

- at a still-generous `45x`, today's market cap already requires roughly the **current 2028 consensus profit** to be treated as sustainable;
- at `40x`, the market requires profit above current 2028 consensus;
- therefore current price contains a large amount of successful share-gain / AI-memory testing / platform-expansion execution.

### 2027-oriented scenario valuation

Working research scenarios, not company guidance:

```text
Bear: 25 亿 profit @ 35x -> ~875 亿 equity value -> ~136 RMB/share
Base: 31 亿 profit @ 45x -> ~1,395 亿 equity value -> ~217 RMB/share
Bull: 35 亿 profit @ 55x -> ~1,925 亿 equity value -> ~299 RMB/share
```

At `283.05`, the stock is already near the working **Bull** 2027 scenario.

Research status:

```text
industry_logic: A
current_earnings_momentum: A+
headline_vs_recurring_quality: A
cash_conversion_watch: MEDIUM-HIGH
valuation: D
expectation_risk: HIGH
status: PRIORITY_RESEARCH / EXPECTATION_HIGH / WAIT_FOR_PRICE
formal_buy: NO
```

### R&D capitalization quality issue discovered

2025 annual report disclosed:

```text
R&D expense: ~9.36 亿 RMB
Total R&D investment: ~12.68 亿 RMB
Capitalized R&D: ~3.32 亿 RMB
R&D capitalization rate: 26.18%
2024 capitalization rate: 5.63%
Capitalized R&D / current profit: ~24.72% (company disclosure)
```

The annual report explicitly states that the 2025 R&D expense decline was related to increased capitalization from newly capitalized semiconductor-equipment R&D projects.

This is **not** evidence of improper accounting by itself. It is an earnings-comparability issue:

> a sharp increase in R&D capitalization can make reported profit growth look stronger than a constant-accounting-policy economic comparison.

A research stress test using the prior-year `5.63%` capitalization rate as a normalization baseline would identify approximately `2.61 亿 RMB` of additional 2025 capitalized R&D versus that baseline. If one additionally assumes a 15% effective tax rate purely for stress testing, attributable profit would be roughly `2.22 亿 RMB` lower, or about `16.6%` below reported 2025 attributable profit.

This stress result is **not an accounting restatement and must never be presented as reported profit**. It exists only to measure earnings-quality sensitivity to capitalization policy.

### New model refinement triggered

Draft PR #25 now also contains an R&D capitalization diagnostic primitive:

```text
r_and_d_capitalization_rate
baseline_capitalization_rate
capitalization_rate_change
capitalized_r_and_d_to_net_profit
excess_capitalized_r_and_d_vs_baseline
after_tax_profit_adjustment
normalized_net_profit (only when caller explicitly provides baseline + tax rate)
earnings_quality_penalty
warning_flags
```

Safety rules:

- capitalization is not automatically treated as aggressive/improper;
- no baseline capitalization rate is invented;
- no net-profit adjustment is produced without an explicit baseline and effective tax rate;
- the output is an earnings-quality / sensitivity diagnostic, not a financial-statement rewrite.

## Next research batch

Continue with a fresh snapshot before each name:

```text
688019 安集科技
300666 江丰电子
603986 兆易创新
```

`688120 华海清科` and `300604 长川科技` are now completed for this batch sequence.
