# Market Research Log — 2026-08-16 — Batch 16

## Scope

Archetype expansion: **stable consumer / durable compounder**.

Adversarial sample set:

- `600519 贵州茅台` — exceptional brand/economic moat, but current growth has decelerated and consolidated cash flow is distorted by a finance subsidiary;
- `000333 美的集团` — global multi-business compounder with strong cash generation, but current headline vs recurring earnings divergence and A/H structure;
- `603288 海天味业` — cleaner branded-consumer recovery/compounder sample with strong cash conversion, but also A/H listed.

Structural question:

> Should durable consumer franchises be valued by a fixed “quality PE” or by low historical price percentile?

**Answer: NO. Quality can justify a longer growth duration and/or lower business risk only when the assumptions are explicit. The primary research bridge should make owner earnings, growth duration, terminal growth and required return auditable, then reverse-solve the growth embedded in the market price.**

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

This batch is architecture validation. It intentionally does not invent a 2026-08-14 close or a current BUY call.

---

# 1. 600519 贵州茅台 — quality does not guarantee current growth

## 2025 audited results

```text
revenue: 1688.38 亿, -1.21%
attributable_net_profit: 823.20 亿, -4.53%
recurring_attributable_profit: 822.93 亿, -4.58%
weighted_ROE: 32.53% vs 36.02%
parent_equity: 2446.38 亿
reported_consolidated_OCF: 615.22 亿, -33.46%
capex_cash_paid: 31.28 亿
reported_raw_CFO_minus_capex: ~583.94 亿
```

Product economics remain exceptional:

```text
liquor_gross_margin: 91.23%
Moutai_liquor_revenue: 1465.00 亿, +0.39%
Moutai_liquor_gross_margin: 93.53%
series_liquor_revenue: 222.75 亿, -9.76%
series_liquor_gross_margin: 76.11%
```

2026Q1:

```text
revenue: 539.09 亿, +6.54%
attributable_net_profit: 272.43 亿, +1.47%
recurring_attributable_profit: 272.40 亿, +1.45%
quarter_ROE: 10.57% vs 10.92%
```

## Critical cash-flow scope defect

The 2025 annual report explicitly attributes the sharp consolidated OCF movement to the controlled finance company, including changes in:

- member deposits / interbank deposits;
- loans and advances;
- central-bank/interbank balances;
- interbank placements.

Therefore this apparently simple calculation:

```text
615.22 亿 consolidated OCF - 31.28 亿 capex
= 583.94 亿 “FCF”
```

is **not automatically a clean owner-earnings measure for the liquor franchise**.

### Hard model rule

```text
if consolidated_cash_flow_scope contains material financial-subsidiary deposit/loan/interbank flows:
    raw CFO - capex remains a diagnostic
    normalized_owner_earnings = UNAVAILABLE
    unless a separately verified adjusted measure is supplied
```

This prevents a high-quality company from receiving a falsely precise DCF simply because the statement contains an OCF line.

## Model lesson

Moutai is the direct counterexample to:

```text
strong brand + historically high ROE => assume double-digit growth forever
```

2025 profit contracted and 2026Q1 recurring growth was low single digit. The moat may remain strong while **growth duration changes materially**.

Research status:

```text
EXCEPTIONAL_QUALITY / GROWTH_DURATION_RESET / CASH_FLOW_SCOPE_ADJUSTMENT_REQUIRED
```

---

# 2. 000333 美的集团 — strong owner earnings but earnings-quality normalization still matters

## 2025 annual results

```text
revenue: 4564.52 亿, +12.11%
attributable_net_profit: 439.45 亿, +14.03%
recurring_attributable_profit: 412.67 亿, +15.46%
weighted_ROE: 19.70% vs 21.29%
parent_equity: 2232.21 亿
OCF: 533.46 亿, -11.84%
capex_cash_paid: 111.42 亿
raw_CFO_minus_capex: ~422.04 亿
raw_owner_earnings_conversion_vs_recurring_profit: ~102.3%
R&D_expense: 177.88 亿, +9.58%
```

This is a useful clean-cash-generation benchmark: the conservative raw `CFO - total capex` measure was close to recurring accounting profit.

However 2026Q1 shows why the existing earnings-quality layer must stay upstream of the DCF:

```text
revenue: 1310.99 亿, +2.55%
attributable_net_profit: 126.75 亿, +2.03%
recurring_attributable_profit: 109.62 亿, -14.02%
OCF: 145.29 亿, +1.45%
quarter_ROE: 5.56%
```

The headline / recurring divergence is material. A compounder model must therefore use a **normalized earnings/cash-flow baseline**, not headline net profit by default.

The business is also increasingly diversified across smart home, industrial technology, building technology, robotics/automation and other ToB activities. Growth durability should be backed by segment evidence rather than one consolidated historical CAGR.

Research status:

```text
HIGH_QUALITY_COMPOUNDER / CASH_GENERATION_STRONG / RECURRING_EARNINGS_NORMALIZATION_REQUIRED
```

---

# 3. 603288 海天味业 — cleaner stable-compounder control sample

## 2025 annual results

```text
revenue: 288.73 亿, +7.32%
attributable_net_profit: 70.38 亿, +10.95%
recurring_attributable_profit: 68.45 亿, +12.81%
weighted_ROE: 19.59% vs 21.77%
recurring_weighted_ROE: 19.06%
parent_equity: 413.30 亿
OCF: 77.46 亿, +13.24%
capex_cash_paid: 12.84 亿
raw_CFO_minus_capex: ~64.62 亿
raw_owner_earnings_conversion_vs_recurring_profit: ~94.4%
R&D_expense: 9.15 亿, +8.05%
```

Core food-manufacturing gross margin:

```text
food_manufacturing_gross_margin: 41.78%, +3.15 pp
soy_sauce_gross_margin: 48.73%, +4.03 pp
oyster_sauce_gross_margin: 36.98%, +3.29 pp
seasoning_sauce_gross_margin: 45.05%, +7.61 pp
```

2026Q1 after comparable-data restatement:

```text
revenue: 90.29 亿, +8.57%
attributable_net_profit: 24.44 亿, +10.97%
recurring_attributable_profit: 23.47 亿, +9.34%
OCF: -4.67 亿 (seasonal quarterly working-capital pattern; do not annualize)
```

This is the cleanest current sample of a branded consumer business where recurring profit growth, annual cash conversion and margin recovery broadly point in the same direction.

The negative Q1 OCF is also a useful reminder that **single-quarter consumer cash flow can be seasonal** and should not automatically invalidate a strong annual cash-conversion record.

Research status:

```text
STABLE_COMPOUNDER / CLEAN_ANNUAL_CASH_CONVERSION / QUARTERLY_CASH_SEASONALITY_AWARE
```

---

# 4. Stable-compounder valuation core

## 4.1 Owner earnings baseline

Default conservative diagnostic when the reporting scope is economically clean:

```text
raw_owner_earnings = operating_cash_flow - total_capex_cash_paid
```

This deliberately does **not** pretend to know maintenance capex vs growth capex.

If cash-flow scope is distorted:

```text
raw_owner_earnings remains visible
but normalized_owner_earnings = unavailable
until an explicit adjusted measure is verified
```

Useful evidence:

```text
owner_earnings_conversion
    = normalized_owner_earnings / normalized_recurring_profit
```

But the conversion ratio is diagnostic, not a universal pass/fail threshold.

## 4.2 Explicit growth-duration DCF

For current normalized owner earnings `FCF0`, an explicit finite high-growth period `N`, near-term growth `g1`, required return `r`, and terminal growth `gT`:

```text
FCF_t = FCF_(t-1) * (1 + g1), t = 1..N

PV_explicit = Σ FCF_t / (1+r)^t

terminal_FCF = FCF_N * (1 + gT)
terminal_value_N = terminal_FCF / (r - gT)
PV_terminal = terminal_value_N / (1+r)^N

fair_equity_value
    = PV_explicit
      + PV_terminal
      + explicit_non_operating_equity_adjustment
```

Hard applicability:

```text
r > gT
N must be explicit positive integer
FCF0 must be positive / verified
```

No universal 20x/25x/30x “consumer quality multiple” is hard-coded.

## 4.3 Reverse implied growth

Given current market cap and explicit `N/r/gT`, solve:

```text
DCF(g_implied) = current_market_cap - explicit_non_operating_adjustment
```

The search bounds are also caller supplied. The model must not silently assume that every stable consumer's plausible growth range is, for example, 0%–20%.

This converts valuation into the project's preferred expectation-gap form:

```text
current market cap
-> implied near-term growth over explicit duration
-> compare with evidence-based Bear/Base/Bull growth
-> expectation gap
```

## 4.4 ROIC / reinvestment consistency

Use the identity as a diagnostic:

```text
sustainable_growth ≈ core_ROIC × reinvestment_rate
```

A 10% long-duration growth scenario should require a credible reinvestment mechanism. A high ROIC company that distributes almost all incremental capital cannot automatically be assigned high organic growth forever; conversely, a business with large reinvestment but poor ROIC does not create compounder-quality value merely by spending more.

---

# 5. Why this is better than “quality PE”

The three live samples expose three different failure modes:

```text
贵州茅台:
  quality remains exceptional
  but profit growth slowed / contracted
  and consolidated OCF scope is distorted

美的集团:
  durable cash generation is strong
  but headline vs recurring earnings diverged in 2026Q1
  and business mix is multi-engine

海天味业:
  annual recurring growth + cash conversion + margins are aligned
  but quarterly OCF is seasonal
```

A fixed quality PE cannot encode these differences cleanly.

The explicit DCF/reverse-growth framework can.

---

# 6. Code consequence

Draft PR #25 now adds:

```text
src/strategies/genge_opportunity_discovery/consumer_compounder_valuation.py
tests/test_genge_consumer_compounder_valuation.py
```

Core functions:

```text
derive_owner_earnings
value_compounder_dcf
reverse_implied_near_term_growth
evaluate_growth_consistency
collect_compounder_quality_evidence
build_compounder_three_scenario_valuation
```

Safety properties:

- distorted cash-flow scope fails closed;
- explicit adjusted owner earnings can restore applicability;
- growth duration / required return / terminal growth are all explicit;
- required return must exceed terminal growth;
- reverse-implied growth requires caller-supplied brackets;
- `g ≈ ROIC × reinvestment` is a diagnostic rather than a forecast;
- no arbitrary quality score;
- no fixed “consumer PE” table;
- no Formal BUY / sizing / execution integration.

Current PR #25 head at this checkpoint:

```text
f7f37cebf155b78d5cbd29906034113f86c123de
```

GitHub currently reports:

```text
open: true
draft: true
mergeable: true
CI: in_progress
GenGe Cycle Bottom: in_progress
GenGe Opportunity Discovery: pending
GenGe Risk-Capped Opportunity Discovery: pending
```

---

# 7. Next queue

1. Continue while CI runs; do not wait idly.
2. Run **pre-profit / pipeline-driven biotech** adversarial research where the correct generic output should be `PE_MODEL_NOT_APPLICABLE`.
3. Implement the minimum rNPV / cash-runway / dilution-aware adapter only from auditable evidence exposed by the sample.
4. Re-check PR #25 CI and repair only reproducible failures.
5. Continue the remaining material archetypes in `MODEL_COVERAGE_MATRIX_2026-08-16.md`.
6. Broad historical regression/backtesting remains blocked until structural archetype gates are satisfied.
