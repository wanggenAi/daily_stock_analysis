# Market Research Log — 2026-08-16 — Batch 13

## Scope

Financial-archetype expansion, first sub-batch: **commercial banks**.

Representative adversarial set:

- `600036 招商银行` — high-quality national joint-stock bank / strong deposit and wealth franchise;
- `002142 宁波银行` — higher-growth regional bank / strong asset quality / more capital-consumptive growth;
- `600016 民生银行` — very low P/B but materially weaker sustainable ROE and thinner risk buffer.

This batch is designed to answer a structural model question, not to force a stock recommendation:

> Can the generic industrial `normalized profit × PE + OCF earnings-quality` framework value banks correctly?

**Answer: NO. A bank-specific common-equity P/B ↔ sustainable-ROE adapter is required.**

---

## Freshness / evidence status

```text
analysis_as_of: 2026-08-16
latest_completed_a_share_trading_day: 2026-08-14
fundamental_data_as_of: 2026-03-31 (2026Q1 filings)
fundamental_freshness: ACCEPTABLE
price_freshness: UNVERIFIED_FOR_2026-08-14
formal_buy: NO
```

Fresh 2026-08-14 closes were not independently verified inside this research sub-batch. Therefore this document intentionally does **not** publish a current target-price / Formal BUY conclusion.

Primary / filing evidence used:

- 招商银行股份有限公司 2026 年第一季度报告, published 2026-04-28/29;
- 宁波银行股份有限公司 2026 年第一季度报告, published 2026-04-24/25; Ningbo Bank investor-relations periodic-report index confirms the filing;
- 中国民生银行股份有限公司 2026 年第一季度报告, published 2026-04-29/30; China Minsheng Bank investor-relations financial-report index confirms the filing.

Secondary filing mirrors were used only to make the tabular text machine-readable where company IR pages exposed the document index but not the parsed body.

---

# 1. Structural failure of the generic industrial model

## 1.1 Bank operating cash flow is not industrial free cash flow

For an industrial company, operating cash conversion can be a useful cross-check on reported earnings. For a bank, customer deposits, loans, interbank balances and financial-asset movements are themselves operating balance-sheet items. A large positive or negative `经营活动产生的现金流量净额` is therefore **not** comparable to an industrial company's FCF conversion ratio.

### Model rule

```text
if archetype == BANK:
    do_not_use industrial OCF / normalized-profit cash-conversion score as a primary earnings-quality gate
```

Bank quality instead requires asset-quality, funding, margin and capital evidence.

## 1.2 The “B” in P/B must be common equity

Banks may have preferred shares / perpetual capital / other equity instruments. Generic data providers can compute P/B against total parent equity or a per-share net-asset field that does not subtract other equity instruments. That systematically understates the P/B paid by common shareholders.

### Model data contract

Use one of:

```text
reported_common_bvps
or
common_equity_attributable_to_common_shareholders / common_share_count
```

Do **not** silently substitute:

```text
total_parent_equity
shareholders_equity_including_other_equity_instruments
```

This failure is material in the live sample because all three banks disclose common-share book value separately.

---

# 2. Live sample facts

## 600036 招商银行

2026Q1:

```text
revenue: 869.40 亿, +3.81% YoY
attributable_net_profit: 378.52 亿, +1.52%
recurring_attributable_net_profit: 377.95 亿, +1.77%
annualized_common_ROAE: 13.48%
common_BVPS: 44.90 元
NIM: 1.83%
NIM_YoY_change: -8 bp
NPL_ratio: 0.94%
provision_coverage: 387.76%
loan_provision_ratio: 3.63%
advanced_method_group_CET1: 14.13%
weighted_method_group_CET1: 11.88%
```

Interpretation:

- strong sustainable ROE relative to peers remains the core economic advantage;
- asset-quality and provisioning buffers are substantial;
- NIM is still compressing, so trailing/high historical ROE must not automatically become the forward sustainable ROE;
- this is a **quality-bank benchmark**, not an automatic BUY benchmark.

Research archetype status:

```text
HIGH_QUALITY_BANK / SUSTAINABLE_ROE_DURABILITY_TEST
```

## 002142 宁波银行

2026Q1:

```text
revenue: 203.84 亿, +10.21% YoY
attributable_net_profit: 81.81 亿, +10.30%
recurring_attributable_net_profit: 81.88 亿, +10.16%
annualized_ROE: 14.38%
common_equity: 2324.93 亿
common_BVPS: 35.21 元
NIM: ~1.73%
NPL_ratio: 0.76%
provision_coverage: 369.39%
CET1: ~9.25%
```

Interpretation:

- stronger current growth and ROE than the weak-bank sample;
- very low NPL and high coverage support earnings quality;
- rapid balance-sheet expansion consumes capital, so sustainable growth must be constrained by CET1 / retained-capital capacity rather than extrapolating loan growth mechanically;
- this is the **quality-growth bank** sample.

Research archetype status:

```text
QUALITY_GROWTH_BANK / CAPITAL_CONSTRAINT_REQUIRED
```

## 600016 民生银行

2026Q1:

```text
revenue: 378.22 亿, +2.74% YoY
net_interest_income: 255.71 亿, +2.84%
attributable_net_profit: 115.14 亿, -9.64%
recurring_attributable_net_profit: 115.19 亿, -10.89%
annualized_ROE: 8.08%
common_equity: 5754.96 亿
common_BVPS: 13.14 元
NIM: 1.43%
NPL_ratio: 1.46%
provision_coverage: 141.94%
CET1: 9.35%
```

Interpretation:

- visibly lower sustainable profitability than 招行 / 宁波;
- weaker asset-quality / provisioning profile;
- a very low observed P/B can be economically justified when sustainable ROE is near or below the equity holder's required return;
- this is the critical **false-cheap adversarial sample**.

Research archetype status:

```text
LOW_PB_NOT_EQUAL_VALUE / ROE_RECOVERY_REQUIRED
```

---

# 3. Bank valuation core

Use a residual-income / Gordon P/B-to-ROE bridge.

For explicit decimal assumptions:

```text
fair_common_PB = (sustainable_ROE - long_term_growth)
                 / (cost_of_equity - long_term_growth)
```

Equivalent form:

```text
fair_common_PB = 1 + (sustainable_ROE - cost_of_equity)
                     / (cost_of_equity - long_term_growth)
```

Reverse implied expectation:

```text
implied_sustainable_ROE
    = current_common_PB * (cost_of_equity - long_term_growth)
      + long_term_growth
```

The reverse equation is particularly useful for the user's existing expectation-gap framework:

```text
market price
-> common P/B
-> implied sustainable ROE
-> compare with evidence-based sustainable ROE range
-> expectation gap
```

## Hard applicability rules

The model must fail closed when:

- common BVPS/common equity is unavailable;
- `cost_of_equity <= long_term_growth`;
- residual-income fair P/B is non-positive;
- current price is stale when a Formal BUY decision is requested.

The engine must never invent:

- cost of equity;
- long-term growth;
- target P/B;
- target CET1;
- target provision coverage;
- sustainable ROE.

---

# 4. Bank quality evidence layer

Do not compress all bank-specific evidence into an unexplained magic score.

Carry these fields explicitly:

```text
sustainable_ROE
ROE_trend
NIM
NIM_change
NPL_ratio
attention_loan_ratio_when_available
provision_coverage_ratio
credit_cost
CET1_ratio
capital_buffer_vs_applicable_requirement
deposit_growth_and_mix
loan_growth_and_mix
fee_income_growth
cost_income_ratio
```

### Why each matters

- `ROE`: economic value creation relative to common book;
- `NIM`: core spread profitability and funding franchise;
- `NPL / attention / credit cost`: forward loss pressure;
- `provision coverage`: buffer against future credit losses;
- `CET1`: ability to support growth and absorb stress without diluting common holders;
- `deposit mix`: funding-cost durability;
- `fee income`: lowers dependence on spread income;
- `cost-income`: operating efficiency.

No single low P/B, high provision ratio or high ROE should be allowed to override all other evidence.

---

# 5. Live-sample conclusions

## Ranking by economic quality, not current BUY attractiveness

```text
1. 招商银行 — strongest combination of ROE durability / provisioning / capital buffer
2. 宁波银行 — strongest current growth; high ROE and asset quality, but capital consumption must be watched
3. 民生银行 — low P/B can be a value trap unless sustainable ROE and asset-quality economics repair
```

This ranking is **not** a current valuation ranking because fresh 2026-08-14 A-share closes and explicit scenario CoE/g assumptions were intentionally not fabricated.

## Main model lesson

The old universal logic:

```text
low P/B + low price percentile + acceptable headline profit
=> potential value
```

is unsafe for banks.

The corrected logic is:

```text
common P/B
+ sustainable ROE relative to explicit cost of equity
+ capital constraint
+ asset-quality / provisioning evidence
+ NIM / funding durability
=> valuation odds
```

A 0.3x P/B bank can be expensive if sustainable ROE is structurally poor; a >1x P/B bank can be cheap if durable ROE materially exceeds the required return and the market-implied ROE is too low.

---

# 6. Code consequence

Draft PR #25 branch `feat/fundamental-reverse-valuation` now adds:

```text
src/strategies/genge_opportunity_discovery/bank_valuation.py
tests/test_genge_bank_valuation.py
```

Core functions:

```text
build_common_book_value
fair_pb_from_roe
implied_roe_from_pb
value_bank_common_equity
collect_bank_quality_evidence
build_bank_three_scenario_valuation
```

Safety properties:

- common equity only;
- explicit CoE/g/ROE assumptions;
- no arbitrary target PB;
- no arbitrary bank-quality score;
- low P/B is not a value signal by itself;
- no Formal BUY / execution / sizing integration.

Current PR head after this batch:

```text
b76273c89dd96c49d969d113900068686f49af3f
```

CI status at handoff:

```text
new head workflows triggered
CI: queued
GenGe Cycle Bottom: in_progress
GenGe Opportunity Discovery: pending
GenGe Risk-Capped Opportunity Discovery: pending
```

Do not mark the bank adapter fully validated until the new PR head is green.

---

# 7. Next queue

1. Wait only passively for PR #25 CI while continuing research; do not stop the queue.
2. Complete **insurance** archetype using `601318 中国平安` + `601628 中国人寿`.
3. Complete **broker/capital-markets** archetype using `600030 中信证券` + `300059 东方财富`.
4. Return to PR #25 CI result and fix only reproducible failures.
5. Then stable-consumer compounder batch and PE-inapplicable biotech adversarial batch.

Broad historical backtesting remains blocked until the coverage matrix's structural model-completion gates are satisfied.
