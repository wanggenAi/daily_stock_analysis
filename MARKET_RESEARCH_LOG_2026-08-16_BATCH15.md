# Market Research Log — 2026-08-16 — Batch 15

## Scope

Financial-archetype expansion, third sub-batch: **capital markets / securities**.

Adversarial pair:

- `600030 中信证券` — balance-sheet-heavy full-service securities broker;
- `300059 东方财富` — securities brokerage + financial-data / fund-distribution / internet-platform hybrid.

Structural question:

> Can all companies labelled “证券” share one P/B or PE model?

**Answer: NO. The industry label contains materially different business models. A traditional capital-heavy broker can be anchored to common book value and normalized mid-cycle ROE; an internet broker/platform hybrid requires explicit segment economics or an explicitly documented lower-confidence whole-company alternative.**

---

## Freshness / evidence status

```text
analysis_as_of: 2026-08-16
latest_completed_a_share_trading_day: 2026-08-14
fundamental_data_as_of: 2026-03-31 (2026Q1), with 2025 annual baseline
fundamental_freshness: ACCEPTABLE
price_freshness: UNVERIFIED_FOR_2026-08-14
formal_buy: NO
```

This batch validates model architecture. Fresh 2026-08-14 prices were not independently verified, so no current-price Formal BUY conclusion is made.

---

# 1. 600030 中信证券 — traditional capital-heavy broker

## 2025 annual evidence

```text
total_assets: ~2.082 万亿
parent_common_equity_reference: ~3199.3 亿
revenue: 748.54 亿, +28.79%
attributable_net_profit: 300.76 亿, +38.58%
recurring_attributable_profit: 303.03 亿, +40.51%
weighted_ROE: 10.59% vs 8.09% prior year
```

2026Q1:

```text
revenue: 231.55 亿, +40.91% YoY (restated comparison basis)
attributable_net_profit: 102.16 亿, +54.60%
recurring_attributable_profit: 102.03 亿, +56.97%
```

Public Q1 business detail also showed very strong brokerage and investment-banking fee growth during a period of sharply higher A-share turnover.

## Model lesson

A securities broker's quarterly earnings are highly pro-cyclical with:

- equity/fund turnover;
- margin financing balances and spreads;
- IPO/refinancing/bond underwriting activity;
- proprietary/investment returns;
- wealth-management / fund distribution activity.

Therefore:

```text
Q1 profit × 4 -> NOT an acceptable normalized annual profit
current-quarter ROE -> NOT automatically sustainable ROE
```

For a traditional balance-sheet-heavy broker, the more auditable primary anchor is:

```text
common book value
+ normalized MID-CYCLE ROE
+ explicit cost of equity
+ explicit long-term growth
-> fair common P/B
```

using:

```text
fair_PB = (mid_cycle_ROE - g) / (cost_of_equity - g)
```

Reverse market expectation:

```text
implied_mid_cycle_ROE
    = current_common_PB * (cost_of_equity - g) + g
```

This is conceptually similar to the bank residual-income bridge, but **the normalization evidence is different**: broker ROE must be normalized against capital-market activity rather than bank NIM/credit-cost/deposit economics.

Research archetype:

```text
TRADITIONAL_BROKER / MID_CYCLE_ROE_PB
```

---

# 2. 300059 东方财富 — broker/platform hybrid

## 2025 annual evidence

```text
revenue: 160.68 亿, +38.46%
attributable_net_profit: 120.85 亿, +25.75%
recurring_attributable_profit: 116.54 亿, +25.94%
weighted_ROE: 14.03%
parent_equity: 918.75 亿, +13.81%
```

Revenue/business mix:

```text
securities_business_revenue: 125.35 亿, 78.02% of total, +47.59%
information_technology_service_revenue: 35.28 亿, 21.95% of total, +13.60%
financial_ecommerce_service_revenue: 31.82 亿, 19.80% of total, +11.99%
financial_ecommerce_gross_margin: ~93.01%
financial_data_service_revenue: 2.40 亿, +25.18%
```

2026Q1:

```text
revenue: 50.31 亿, +44.34%
attributable_net_profit: 37.38 亿, +37.67%
recurring_attributable_profit: 36.95 亿, +36.95%
quarterly_ROE: 3.99%
total_assets: ~4398.97 亿
```

## Structural conflict

东方财富 contains at least two economically different engines:

```text
A. securities / credit / transaction-linked business
   -> balance-sheet and market-turnover sensitive

B. information / financial ecommerce / data / platform services
   -> asset-light, very high gross margin, platform economics
```

A single consolidated P/B treats the asset-light platform franchise as if it requires the same book capital as a traditional securities business.

A single consolidated PE can also overstate durability if current securities earnings are near a capital-market activity peak.

Therefore the preferred research model is an explicit SOTP when segment economics are sufficiently disclosed:

```text
broker_value
    = normalized_broker_profit × explicit_broker_multiple

platform_value
    = normalized_platform_profit × explicit_platform_multiple

fair_equity_value
    = broker_value
      + platform_value
      + verified_explicit_equity_adjustment
```

### Critical data rule

**Revenue share is not segment profit.**

The model must not convert:

```text
78% securities revenue / 22% information-service revenue
```

into a fake segment-profit split. The two activities have very different margins and capital intensity.

If point-in-time segment profit cannot be established:

```text
SOTP confidence -> LOW / unavailable
```

rather than inventing profit allocation.

Research archetype:

```text
BROKER_PLATFORM_HYBRID / SOTP_REQUIRED_WHEN_SEGMENT_ECONOMICS_AVAILABLE
```

---

# 3. Capital-markets evidence layer

Carry explicitly where available:

```text
market_turnover_change
brokerage_fee_growth
investment_banking_fee_growth
net_interest_income_growth
proprietary_or_investment_income_share
wealth_or_fund_distribution_growth
platform_service_growth
weighted_ROE
```

For traditional brokers, these inputs help determine where current earnings sit relative to a mid-cycle baseline.

For hybrids, they also help identify whether current consolidated profit growth is driven by the cyclical brokerage engine or the more durable platform engine.

Do not compress this evidence into a magic score before out-of-time validation.

---

# 4. Model routing consequence

The industry alias `证券` is **not** a sufficient valuation-archetype key.

Correct routing contract:

```text
industry == 证券
-> inspect business model / revenue-profit structure
-> TRADITIONAL_BROKER
   or BROKER_PLATFORM_HYBRID
   or another explicit capital-markets subtype
```

The router must not use an arbitrary hard-coded revenue threshold without historical validation.

### Traditional broker

```text
common_BVPS
+ normalized_mid_cycle_ROE
+ explicit CoE / g
-> fair_PB / fair price
-> reverse implied mid-cycle ROE
```

### Broker/platform hybrid

```text
explicit segment normalized profit
+ segment-specific explicit multiples
-> SOTP
```

If segment profit is missing, fail closed / lower confidence.

---

# 5. Code consequence

Draft PR #25 now adds:

```text
src/strategies/genge_opportunity_discovery/capital_markets_valuation.py
tests/test_genge_capital_markets_valuation.py
```

Implemented paths:

```text
value_traditional_broker
build_traditional_broker_three_scenario_valuation
value_hybrid_broker_platform_sotp
collect_capital_markets_quality_evidence
```

Tests explicitly verify:

- fair P/B uses explicit normalized mid-cycle ROE;
- reverse implied mid-cycle ROE is auditable;
- `cost_of_equity <= g` fails closed;
- no quarterly-profit / quarterly-ROE annualization shortcut exists in the API;
- hybrid SOTP values broker and platform separately;
- missing segment profit fails with `SEGMENT_PROFIT_UNAVAILABLE`;
- revenue shares are not accepted as a segment-profit proxy;
- negative segment profit requires a different model;
- no arbitrary capital-markets quality score is manufactured;
- Bear/Base/Bull scenarios remain explicit.

Current PR #25 head after these tests:

```text
59d368d3a3ff1cd4c366a6fd5c0ba36fecc8f62f
```

At this checkpoint GitHub reports the PR as draft and `mergeable=false`; the main branch also advanced during the research-document commits and Actions had not yet registered runs for this newest head. **Do not infer a production-code failure from mergeability alone.** Re-check branch divergence / CI and synchronize only if required.

---

# 6. Financial archetype completion status

After BATCH13–15:

```text
BANK:
  structural adapter: IMPLEMENTED
  representative adversarial samples: 招商 / 宁波 / 民生
  CI validation: PENDING latest head

INSURANCE:
  structural adapter: IMPLEMENTED
  representative samples: 平安 / 国寿
  CI validation: PENDING latest head

CAPITAL_MARKETS:
  traditional broker adapter: IMPLEMENTED
  broker/platform hybrid adapter: IMPLEMENTED (fails closed without segment profit)
  representative samples: 中信证券 / 东方财富
  CI validation: PENDING latest head
```

These modules remain isolated research primitives. None changes Formal BUY, position sizing, stop, exit or market-regime logic.

---

# 7. Next queue

1. Inspect/synchronize PR #25 with main only if branch divergence actually blocks CI/mergeability; do not merge the draft.
2. Run/inspect latest PR #25 CI; repair only reproducible failures.
3. Begin **stable consumer compounder** archetype with contrasting names such as:
   - `600519 贵州茅台`
   - `000333 美的集团`
   - `603288 海天味业`
4. The consumer batch must test durable ROIC/FCF/reinvestment runway and valuation duration; quality alone is not a BUY and low price percentile alone is not value.
5. Then run a **pre-profit biotech adversarial sample** where the correct output may be `PE_MODEL_NOT_APPLICABLE` and an rNPV/cash-runway/dilution adapter.
6. Continue remaining material archetypes from `MODEL_COVERAGE_MATRIX_2026-08-16.md` before broad historical backtesting becomes the primary loop.
