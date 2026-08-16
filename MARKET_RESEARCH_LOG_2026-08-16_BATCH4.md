# Market Research Log — 2026-08-16 — Batch 4

> Read with `CURRENT_MARKET_RESEARCH.md`, `MODEL_EVOLUTION_LOG.md`, and prior batch logs.
>
> This batch completes `688019 安集科技` using the repository's 2026-08-14 production market snapshot plus the latest available public fundamental/company information. Formal BUY remains separate from research ranking.

## Analysis snapshot

```text
analysis_as_of: 2026-08-16
latest_a_share_trading_day: 2026-08-14
market_regime: YELLOW
market_position_multiplier: 0.5
price_source: repository production artifact
price_freshness: FRESH
fundamental_freshness: ACCEPTABLE (2025 annual + 2026Q1; H1 not yet disclosed)
```

## 688019 安集科技

### Price / technical snapshot — 2026-08-14

```text
close: 248.20
open: 246.79
high: 251.71
low: 243.03
MA20: 245.08
MA60: 254.02
MA120: 225.54
MA250: 192.19
price_percentile_1y: 0.88
price_percentile_5y: 0.976
return_1d_pct: +2.3505%
return_5d_pct: -1.3827%
return_10d_pct: +4.5581%
relative_strength_20d: -2.5193%
relative_strength_60d: +11.1559%
```

Legacy quant status remained a high-price hard reject / trend-unconfirmed style result. Under the upgraded architecture this is entry-readiness / expectation evidence, not sufficient grounds to remove a fundamentally attractive company from the Research Pool.

### Share count / market cap

After the June 2026 10-for-3 capitalization distribution, current A-share count used in this batch:

```text
227,492,715 shares
```

At `248.20`, simple equity market cap:

```text
~564.64 亿 RMB
```

### Latest fundamental basis

2025 full year:

```text
Revenue: ~25.04 亿 RMB, +36.47% YoY
Attributable net profit: ~7.836 亿 RMB, +46.85% YoY
Recurring attributable profit: ~6.966 亿 RMB, +32.36% YoY
Operating cash flow: ~4.398 亿 RMB
ROE: ~25.18%
R&D / revenue: ~17.76%
```

2026Q1:

```text
Revenue: ~7.239 亿 RMB, +32.76% YoY
Attributable net profit: ~2.077 亿 RMB, +23.01% YoY
Recurring attributable profit: ~1.967 亿 RMB, +21.65% YoY
Operating cash flow: ~1.406 亿 RMB, +143.82% YoY
R&D: ~1.188 亿 RMB, +28.66% YoY
R&D / revenue: ~16.40%
```

Quality diagnostics:

```text
2025 recurring / headline profit: ~88.9%
2026Q1 recurring / headline profit: ~94.7%
2025 OCF / headline profit: ~56.1%
2026Q1 OCF / headline profit: ~67.7%
```

Interpretation: earnings are materially cleaner than the fair-value/investment-gain cases seen in 中微公司 / 拓荆科技. Cash conversion is not perfect but is positive and improved in Q1.

### Business / industry driver

The company continues to build a `3+1` semiconductor-material platform:

```text
CMP slurries
functional wet electronic chemicals
electroplating solutions/additives
core raw materials / abrasives
```

2025 segment observations used in this batch:

```text
IC-related gross margin: ~56.79%
CMP slurry revenue: ~20.40 亿 RMB, +32.06%; gross margin ~58.28%
functional wet chemicals revenue: ~4.53 亿 RMB, +63.73%; gross margin ~50.00%, +6.79ppt
```

The company disclosed continued progress in advanced-node CMP, tungsten-related slurry, advanced packaging / 2.5D / 3D / TSV / hybrid-bonding applications, advanced wet chemicals, damascene plating and internally developed ceria abrasive materials.

Key thesis:

> Compared with capital-equipment names, consumable semiconductor materials can offer better repeat-purchase visibility and lower shipment lumpiness if qualification and share gains persist.

### Working-capital watch

2025 inventory increased materially (about +69.9% YoY), while receivables also increased. The company attributed inventory growth mainly to sales growth and safety-stock needs. This is not a hard negative, but future H1 analysis must check inventory turns, receivables and operating cash conversion.

### Consensus earnings reference

Third-party forecast aggregation used as a reference, not company guidance:

```text
2026E attributable profit: ~10.45 亿 RMB
2027E attributable profit: ~13.89 亿 RMB
2028E attributable profit: ~18.17 亿 RMB
```

At the 2026-08-14 market cap, approximate forward PE:

```text
2026E: ~54.0x
2027E: ~40.7x
2028E: ~31.1x
```

This is materially less expectation-heavy than the prior 华海清科 / 长川科技 cases, although still not cheap on current-year earnings.

### 2027-oriented scenario valuation

To avoid net-cash double counting, the first-pass scenario below is a **plain equity-profit PE** valuation: no separate net-cash amount is added.

```text
Bear: 11.5 亿 profit @ 32x -> 368 亿 equity value -> ~161.8 RMB/share
Base: 13.9 亿 profit @ 40x -> 556 亿 equity value -> ~244.4 RMB/share
Bull: 16.0 亿 profit @ 48x -> 768 亿 equity value -> ~337.6 RMB/share
```

At `248.20`, current price is approximately the working Base fair-value level, not the Bull level.

Approximate safety-margin levels versus Base:

```text
10% below Base: ~220.0
15% below Base: ~207.7
20% below Base: ~195.5
25% below Base: ~183.3
```

These are research valuation zones, not Formal BUY triggers.

### Current status

```text
industry_logic: A
business_quality: A
headline_vs_recurring_quality: A-
current_earnings_growth: A-
valuation: C / roughly fair under Base
expectation_risk: MEDIUM
entry_readiness: NOT CONFIRMED
market_regime: YELLOW
status: QUALITY_GROWTH / FAIR_VALUE / WATCH_FOR_ENTRY
formal_buy: NO
```

Working interpretation:

- `>240-250`: around Base fair value; insufficient safety margin.
- `215-225`: begins to provide a meaningful discount to Base if fundamentals remain intact.
- `195-210`: materially better safety margin.
- `180-195`: attractive research zone if H1 / industry thesis remains intact.

All zones must be recomputed after new financial reports, material events or capital changes.

### H-share financing uncertainty

The board has advanced an H-share listing plan. The disclosed base H-share issuance scale can reach up to 10% of total shares after the base issuance, with an additional over-allotment option up to 15% of the base issue.

This creates a potentially material future share-count change, but **must not be modeled as pure denominator dilution** because primary issuance also brings financing proceeds into the company.

At the time of this batch, issue price / verified net proceeds were not available. Therefore:

```text
h_share_post_financing_fair_price: UNVERIFIED
```

No exact post-H-share per-share fair value is produced.

### Model refinement #1 — financial asset income double-count protection

The company's balance sheet contains meaningful cash / financial assets. A model that:

```text
recurring equity net profit × PE
+ net cash
```

can double count interest / recurring financial income already present in equity net profit.

PR #25 now includes an explicit financial-income bridge. Plain equity-PE valuation can use recurring/equity net profit with no separate net-cash addition; an asset-adjusted valuation must first remove explicitly verified after-tax financial income and add back explicitly verified after-tax financing cost before adding net cash/assets.

### Model refinement #2 — primary financing is not zero-proceeds dilution

The existing share-dilution primitive originally treated financing shares as denominator-only dilution. The H-share case exposed that this is economically incomplete.

PR #25 now includes a primary-financing bridge:

```text
post_financing_equity_value = pre_financing_equity_value + verified_net_proceeds
post_financing_shares = current_shares + financing_shares
post_financing_fair_price = post_financing_equity_value / post_financing_shares
```

If financing shares are assumed but issue price / net proceeds are unavailable, the model fails closed with no precise post-financing fair price.

## Relative view after this batch

Among the recent semiconductor-equipment/material names already analyzed:

```text
安集科技: closest to Base fair value; best current valuation balance of the recent three
华海清科: high-quality platform, but prior analysis found current price near Bull case
长川科技: exceptional growth, but current price also near Bull case and earnings comparability needs R&D-capitalization diagnostics
```

This is a valuation/research comparison, not a Formal BUY ranking.

## Next research queue

Refresh the price/fundamental snapshot and continue:

```text
300666 江丰电子
603986 兆易创新
```
