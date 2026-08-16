# Market Research Log — 2026-08-16 — Batch 14

## Scope

Financial-archetype expansion, second sub-batch: **life insurance / diversified insurance groups**.

Representative samples:

- `601318 中国平安` — diversified financial group with life & health, P&C, banking and other businesses;
- `601628 中国人寿` — predominantly life-insurance franchise and cleaner embedded-value sample.

Structural question:

> Is reported net profit × PE an adequate primary valuation model for insurers?

**Answer: NO. For life insurance, the primary economic bridge should use embedded value (EV) plus an explicitly valued future-new-business franchise. Reported PE is secondary because investment-market volatility can dominate short-period accounting profit.**

---

## Freshness / evidence status

```text
analysis_as_of: 2026-08-16
latest_completed_a_share_trading_day: 2026-08-14
fundamental_data_as_of: 2026-03-31 (Q1 operating data), EV anchored at 2025-12-31
fundamental_freshness: ACCEPTABLE
price_freshness: UNVERIFIED_FOR_2026-08-14
formal_buy: NO
```

No fresh 2026-08-14 A-share close is asserted here, so this is architecture validation rather than a current BUY call.

Key evidence:

- China Ping An official 2025 results / 2026Q1 results and investor-relations definition of embedded value;
- China Life 2025 annual report / 2026Q1 report.

---

# 1. Why PE is structurally incomplete for insurers

Insurance accounting profit can move sharply with:

- equity-market mark-to-market / realized investment results;
- bond yields and asset-liability valuation effects;
- insurance finance income/expense;
- one-period investment mix.

These items matter economically, but a single year's net profit can be a poor denominator for the durable value of long-duration in-force policies.

For life insurers, both Ping An and China Life explicitly define **embedded value** as an actuarial estimate of the economic value of existing life business under stated assumptions, and explicitly state that it **does not include future new business after the valuation date**.

That immediately creates the correct conceptual split:

```text
existing in-force / adjusted net assets -> embedded value
future franchise                       -> future new-business value
```

Therefore:

```text
appraisal value ≈ embedded value + value assigned to future NBV franchise
```

rather than:

```text
one-period accounting net profit × generic PE
```

---

# 2. Live sample: 601318 中国平安

## 2025 / 2026Q1 evidence

2025 group / life-health indicators:

```text
attributable_operating_profit: 1344.15 亿, +10.3% YoY
parent_equity: 10004.19 亿, +7.7%
life_health_NBV: 368.97 亿, +29.3%
life_health_NBV_margin_standard_premium: 28.5%, +5.8 pp
life_health_embedded_value: 9286.30 亿, +11.2%
life_health_embedded_value_operating_return: 11.2%
P&C_original_premium: 3431.68 亿, +6.6%
P&C_combined_ratio: 96.8%, improved 1.5 pp
insurance_funds_portfolio: ~6.49 万亿
comprehensive_investment_yield: 6.3%
```

The 2025 annual-report embedded-value bridge also shows that Ping An is not a pure life insurer: the group-level EV/SOTP contains the life & health EV plus adjusted net assets of other businesses. Therefore **do not add group book value on top of a group embedded value**; doing so double counts non-life net assets.

2026Q1:

```text
group_attributable_operating_profit: 407.80 亿, +7.6%
parent_equity: 10183.10 亿, +1.8% from year-end
life_health_first_year_premium: 663.40 亿, +45.5%
life_health_NBV: 155.74 亿, +20.8%
P&C_premium: 909.51 亿, +6.8%
P&C_combined_ratio: 95.8%, improved 0.8 pp
```

Interpretation:

- Q1 NBV growth validates franchise momentum but **Q1 NBV must not be multiplied by four** to create a forward annual NBV;
- operating profit is a useful supplementary stability measure but not a replacement for EV/NBV economics;
- Ping An requires an explicitly scoped group EV / SOTP input so life EV, P&C, bank and other adjusted net assets are not double counted;
- P&C quality should remain visible through combined ratio; banking quality should use the separate bank adapter where segment detail permits.

Research status:

```text
DIVERSIFIED_INSURANCE_GROUP / EV_SCOPE_AND_SOTP_REQUIRED
```

---

# 3. Live sample: 601628 中国人寿

## 2025 annual evidence

```text
total_premium: 7298.87 亿
attributable_net_profit: 1540.78 亿, +44.1%
weighted_ROE: 27.81%
embedded_value: 14678.76 亿, +4.8%
one_year_NBV: 457.52 亿, +35.7%
adjusted_net_asset_value_inside_EV: 9366.73 亿
value_of_in_force_after_cost_of_required_capital: 5312.03 亿
core_solvency_ratio: 128.77%
comprehensive_solvency_ratio: 174.01%
total_investment_yield: 6.09%
```

The EV decomposition is especially important:

```text
adjusted net assets 9366.73 亿
+ value of in-force after required-capital cost 5312.03 亿
= embedded value 14678.76 亿
```

Thus adding ordinary book value again after using EV would be a double-counting error.

2026Q1:

```text
total_premium: 3584.78 亿, +1.1% (reported public release)
long-term_new_premium: 856.60 亿, +29.9%
first_year_regular_premium: +41.4% YoY
NBV_growth: +75.5% YoY
surrender_rate: 0.24%, -0.05 pp
attributable_net_profit: 195.05 亿, -32.3% YoY
investment_assets: 75531.04 亿
Q1_total_investment_income: 355.36 亿
Q1_total_investment_yield: 2.21%
```

Interpretation:

- this is a clean demonstration of why accounting net-profit growth and franchise-value growth can diverge: Q1 reported profit fell materially while NBV rose sharply;
- 2025 EV grew only modestly versus very strong accounting profit / NBV growth, reminding the model that EV movement also includes assumption changes, market-value effects, dividends and other actuarial/economic changes;
- therefore neither PE nor NBV growth alone should dominate the decision.

Research status:

```text
LIFE_INSURANCE / EV_NBV_PRIMARY / INVESTMENT_VOLATILITY_SECONDARY
```

---

# 4. Insurance valuation core

## Appraisal-value bridge

Use an explicitly prepared annual/forward NBV measure:

```text
future_new_business_value
    = normalized_annual_NBV × explicit_NBV_franchise_multiple

fair_equity_value
    = embedded_value
      + future_new_business_value
      + explicit_equity_adjustment_not_already_in_EV
```

Reverse implied market expectation:

```text
implied_NBV_franchise_multiple
    = (current_market_cap
       - embedded_value
       - explicit_equity_adjustment)
      / normalized_annual_NBV
```

Useful companion diagnostic:

```text
current_P_EV = current_market_cap / embedded_value
```

A negative implied NBV multiple is intentionally preserved: it means the market cap is below the supplied EV after adjustments. The engine must not silently floor it at zero because that would hide the market's discount to EV quality / assumptions.

## Hard rules

Do not invent:

- future NBV franchise multiple;
- annual NBV by `Q1 × 4`;
- EV growth rate;
- investment yield;
- solvency target;
- holding-company discount;
- SOTP adjustments.

Fail closed when EV or normalized annual NBV is missing.

---

# 5. Quality/evidence layer

Carry explicitly:

```text
NBV_growth
NBV_margin
13m_persistency
25m_persistency
surrender_rate
net_investment_yield
total_or_comprehensive_investment_yield
core_solvency_ratio
comprehensive_solvency_ratio
P&C_combined_ratio_when_applicable
```

Do not collapse these into one unexplained insurance-quality score.

Special scope guard for diversified groups:

```text
if embedded_value_scope == GROUP:
    do_not_add group_book_equity_again

if embedded_value_scope == LIFE_ONLY:
    other_businesses_require explicit SOTP / adjusted_net_asset bridge
```

---

# 6. Model lessons from the adversarial pair

## 中国平安

- EV/NBV useful but group scope is complex;
- diversified SOTP/double-count protection is mandatory;
- operating profit and P&C combined ratio add segment-quality evidence.

## 中国人寿

- cleaner pure-life EV/NBV sample;
- 2026Q1 shows `NBV +75.5%` while accounting profit fell sharply, directly falsifying a PE-only interpretation of franchise momentum;
- investment volatility remains economically relevant but should not erase the in-force/new-business split.

## Core conclusion

```text
low PE / high PE is not the primary insurance valuation question.

The primary questions are:
1. What is the verified EV and its scope?
2. What sustainable annual NBV can the franchise create?
3. What future-NBV multiple is embedded in the current market cap?
4. Are EV assumptions, persistency, solvency and investment economics credible?
5. For groups, have non-life assets already been included?
```

---

# 7. Code consequence

Draft PR #25 now adds:

```text
src/strategies/genge_opportunity_discovery/insurance_valuation.py
tests/test_genge_insurance_valuation.py
```

Functions:

```text
value_insurance_appraisal
reverse_implied_nbv_franchise_multiple
collect_insurance_quality_evidence
build_insurance_three_scenario_valuation
```

Safety properties:

- EV + explicit normalized annual NBV franchise value;
- no Q1 annualization API;
- negative market-implied NBV franchise multiple preserved;
- explicit anti-double-counting documentation for group EV;
- no arbitrary quality score;
- no Formal BUY / sizing / execution integration.

Current PR head after insurance tests:

```text
a6c7ec81576c0aba39b5c1865bd667d44fd76e5e
```

CI at this checkpoint:

```text
CI: in_progress
GenGe Cycle Bottom: in_progress
GenGe Opportunity Discovery: pending
GenGe Risk-Capped Opportunity Discovery: pending
```

---

# 8. Next queue

1. Continue research immediately into broker / capital-markets archetype (`600030 中信证券`, `300059 东方财富`).
2. Re-check PR #25 CI without pausing the research queue.
3. If green, update coverage matrix bank + insurance status; if failed, repair only reproducible defects.
4. Then stable consumer compounder + pre-profit biotech adversarial batch.
