# Market Research Log — 2026-08-16 — Batch 17

## Scope

Archetype expansion: **pre-profit / pipeline-driven biotech**.

Adversarial sample:

- `688180 君实生物` — already has meaningful commercial products and expanding indications, but normalized recurring earnings remain negative and material value still depends on clinical/regulatory pipeline outcomes.

Structural question:

> When a biotech company is close to headline break-even, should the generic PE model start treating it as a normal profitable company?

**Answer: NO. The correct gate is normalized sustainable earnings, not headline break-even. For a pipeline-dominant company with negative recurring economics, generic PE must return `PE_MODEL_NOT_APPLICABLE`; valuation should move to approved-product cash flows + probability-adjusted pipeline rNPV + liquidity/runway + financing/dilution risk.**

---

## Freshness / evidence status

```text
analysis_as_of: 2026-08-16
latest_completed_a_share_trading_day: 2026-08-14
fundamental_data_as_of: 2026-03-31 (2026Q1), with 2025 audited annual baseline
pipeline/news_cutoff: 2026-08-16
fundamental_freshness: ACCEPTABLE
pipeline_freshness: ACCEPTABLE
price_freshness: UNVERIFIED_FOR_2026-08-14
formal_buy: NO
```

This batch validates model architecture, not a current share-price target.

Primary evidence hierarchy:

- 2025 audited annual report / exchange filing;
- 2026Q1 report;
- Junshi Biosciences official pipeline/product/company announcements;
- exchange/company report mirrors only where needed for machine-readable statement details.

---

# 1. 688180 君实生物 — headline break-even is an earnings-quality trap

## 2025 audited baseline

```text
revenue: 24.984 亿, +28.23%
attributable_net_profit: -8.752 亿
recurring_attributable_net_profit: -9.897 亿
operating_cash_flow: -5.196 亿
R&D_expense: 13.421 亿, +5.24%
R&D_intensity: 53.72% of revenue
R&D_capitalization: 0
cash: ~26.146 亿
trading_financial_assets: ~6.008 亿
parent_equity: ~60.304 亿
```

Commercial-business evidence:

```text
pharmaceutical_manufacturing_revenue: ~24.622 亿
pharmaceutical_manufacturing_gross_margin: ~82.19%
anti_tumor_drug_revenue: ~21.395 亿, +38.78%
anti_tumor_drug_gross_margin: ~83.09%
technology_license_and_royalty_revenue: ~1.608 亿
```

The annual report explicitly states that the company was listed before achieving profitability and **still had not achieved profitability in 2025**; revenue was not yet sufficient to cover R&D and other expenditures.

## 2026Q1 — why headline profit is not enough

```text
revenue: ~7.263 亿, +45.09%
attributable_net_profit: ~-0.206 亿
recurring_attributable_net_profit: ~-1.436 亿
operating_cash_flow: ~+0.579 亿
R&D_expense: ~2.825 亿, -19.42%
investment_income: ~1.209 亿
```

The company also disclosed that excluding share-based payment, Q1 attributable profit would have been positive. However, the detailed income statement shows material investment income, while recurring profit remained clearly negative.

Therefore this is a direct live failure case for:

```text
headline loss almost zero
or adjusted headline profit positive
=> start using forward PE
```

### Hard model rule

```text
if normalized_sustainable_profit <= 0:
    PE_MODEL_NOT_APPLICABLE
```

A one-quarter headline result cannot override negative recurring economics.

---

# 2. Commercial base + pipeline structure

At the 2025 year-end / 2026 operating update boundary, toripalimab (拓益 / JS001) had a broad approved commercial base and continued to add indications / formulations / international registrations. The company's official 2026 updates also show additional regulatory and Phase III progress after year-end.

Examples of value-bearing pipeline / lifecycle-extension items include:

```text
Toripalimab / JS001:
  approved commercial base across multiple indications and geographies
  additional indications / international approvals
  subcutaneous formulation JS001sc with NDA applications accepted

JS004 / BTLA:
  late-stage / international clinical development

JS207 / PD-1 x VEGF:
  Phase II / II-III development, including US IND progress

JS005:
  China NDA accepted

other ADC / autoimmune / metabolic / infectious-disease assets:
  multiple earlier-stage opportunities
```

The correct valuation unit is therefore **not simply the consolidated company PE**. It is a set of economically scoped assets/indications whose future cash flows and probabilities differ.

---

# 3. Biotech rNPV core

## 3.1 Explicit probability-adjusted asset cash flows

For one non-overlapping asset/indication scope:

```text
PV_success_cash_flows
    = Σ success_contingent_FCF_t / (1 + required_return)^t

probability_adjusted_commercial_value
    = PV_success_cash_flows
      × explicit_probability_of_success
      × explicit_economic_ownership

PV_development_cash_flows
    = Σ explicit_expected_or_committed_development_FCF_t
      / (1 + required_return)^t

risk_adjusted_asset_value
    = probability_adjusted_commercial_value
      + PV_development_cash_flows × economic_ownership
```

### Critical safeguards

The engine does **not** contain a stage lookup table such as:

```text
Phase I = X%
Phase II = Y%
Phase III = Z%
NDA = W%
```

Those probabilities must be explicitly supplied from point-in-time evidence/research assumptions and are therefore versionable and auditable.

Development spending is not blindly multiplied by terminal approval probability. If a detailed phase-by-phase probability tree is available, expected development cash flows should be prepared upstream.

Economic ownership is also explicit because licensed products / regional partnerships may give the company only a royalty, profit share or territorial interest rather than 100% of global economics.

## 3.2 Approved product vs pipeline expansion — avoid double counting

An already commercial base indication can use:

```text
probability_of_success = 1.0
```

with explicit commercial cash flows.

A new indication/formulation can be valued separately only if its economic scope is incremental and non-overlapping.

The bridge rejects duplicate `asset_id` values, but name-level code cannot detect all biological/commercial overlap. The research layer must explicitly define indication/product scope so that:

```text
base commercial sales
+ expansion indication value
```

does not count the same patients/revenue twice.

---

# 4. Equity bridge

```text
fair_equity_value
    = Σ unique_asset_rNPV
      + verified_liquid_resources
      - verified_debt
      - PV_corporate_overhead_not_in_asset_cash_flows
      + explicit_equity_adjustment
```

Important distinction:

- **equity valuation** subtracts debt as a senior claim regardless of maturity;
- **cash runway** must not mechanically subtract every long-dated project loan from today's usable cash.

---

# 5. Cash runway — live sample exposed a second model defect

2025 balance-sheet evidence includes approximately:

```text
cash: 26.146 亿
trading_financial_assets: 6.008 亿
short_term_borrowings: 6.032 亿
current_portion_of_long_term_borrowings: ~6.594 亿
long_term_borrowings: 27.936 亿
```

Total interest-bearing borrowings using those categories are roughly `40.56 亿`, larger than cash + trading financial assets.

But the annual report also shows that significant project borrowings mature over multiple years, with some facilities extending toward 2030–2033. Therefore this naive calculation is economically wrong for liquidity runway:

```text
(cash + liquid investments - ALL long-term debt) / annual burn
```

because long-dated project debt is not necessarily an immediate cash call before the next regulatory/clinical catalyst.

## Correct horizon-matched runway

```text
net_runway_resources
    = available_liquid_resources
      - committed_cash_outflows_within_the_same_analysis_horizon

runway_years
    = net_runway_resources / normalized_annual_cash_burn
```

`committed_cash_outflows_within_horizon` can include, when verified:

- debt principal actually maturing before the catalyst window;
- committed capex not already embedded in normalized operating burn;
- other unavoidable cash commitments in the same window.

It must **not** automatically include all long-term borrowings outside the horizon.

### Burn normalization rule

2026Q1 OCF was positive. That does **not** mean runway is infinite.

The engine therefore requires an explicit positive `normalized_annual_cash_burn`. A zero/negative one-quarter burn returns:

```text
NORMALIZED_ANNUAL_BURN_NOT_POSITIVE_OR_UNAVAILABLE
```

rather than `infinite runway`.

2025 OCF burn (~5.20 亿) is useful evidence but should not automatically become the final forward burn because license receipts, commercialization growth, R&D timing and working-capital movements can change future burn.

---

# 6. Catalyst vs financing risk

For an explicit key catalyst horizon:

```text
required_runway_years
    = catalyst_horizon_years
      + explicit_liquidity_buffer_years

runway_gap
    = runway_years - required_runway_years
```

If negative:

```text
financing_before_catalyst_likely = true
```

This is where dilution belongs in the model.

The buffer has no hidden default. Historical backtesting must eventually test whether a proposed buffer improves out-of-time risk control rather than hard-coding one from intuition.

---

# 7. Why this model is structurally different from growth-stock PE

A high-duration profitable AI hardware company can still be analyzed with forward profit and an explicit valuation horizon if earnings are economically meaningful.

A pre-profit biotech cannot.

For biotech, value can exist despite negative current earnings because:

```text
approved product economics
+ probability-adjusted pipeline economics
+ net balance-sheet resources
```

may exceed current market value.

But that does **not** justify pretending negative recurring profit is positive future EPS today.

Correct routing:

```text
normalized sustainable earnings <= 0
+ material pipeline dependence
-> BIOTECH_RNPV
-> PE_MODEL_NOT_APPLICABLE
```

---

# 8. Code consequence

Draft PR #25 now adds:

```text
src/strategies/genge_opportunity_discovery/biotech_rnpv_valuation.py
tests/test_genge_biotech_rnpv_valuation.py
```

Core functions:

```text
evaluate_pe_applicability
value_probability_adjusted_asset
compute_cash_runway
assess_financing_before_catalyst
bridge_biotech_equity_value
collect_biotech_quality_evidence
```

Tests explicitly enforce:

- negative/zero normalized sustainable profit refuses PE;
- clinical success probability is mandatory and has no default;
- economic ownership and required return are mandatory;
- approved commercial asset may use explicit probability 1.0;
- development cash flows are not multiplied by terminal approval probability;
- cash runway uses horizon-matched committed outflows, not all long-term debt;
- no cash-positive quarter can create infinite runway;
- catalyst liquidity buffer is explicit and has no default;
- duplicate asset IDs are rejected;
- incomplete asset rNPV fails closed;
- equity bridge still subtracts verified debt;
- no arbitrary biotech quality score is manufactured.

Latest PR #25 head at this checkpoint:

```text
ce336ab245f5037aeb52ad7945697a60070c3cb2
```

GitHub state:

```text
open: true
draft: true
mergeable: true
CI: pending
GenGe Cycle Bottom: queued
GenGe Opportunity Discovery: pending
GenGe Risk-Capped Opportunity Discovery: pending
```

---

# 9. Archetype conclusion

```text
PRE_PROFIT_BIOTECH:
  generic PE: REJECTED when normalized sustainable profit <= 0
  structural adapter: IMPLEMENTED
  live adversarial sample: 688180 君实生物
  cash-runway maturity mismatch defect: IDENTIFIED + FIXED IN ADAPTER
  CI validation: PENDING latest head
```

The current sample is deliberately **not assigned a fabricated fair price**, because no stage probabilities, asset cash-flow forecasts, economic ownership assumptions, discount rates or fresh 2026-08-14 price were invented.

---

# 10. Next queue

1. Continue archetype expansion while PR #25 CI runs.
2. Prioritize a structurally different **regulated utility / yield-asset** batch next, then real-estate/NAV and transport/shipping/aviation where generic PE can also mislead.
3. Re-check PR #25 CI regularly; repair only reproducible implementation failures.
4. Update `MODEL_COVERAGE_MATRIX_2026-08-16.md` after the newly added adapters pass executable validation.
5. Continue material archetypes until each is VALIDATED or explicitly OUT_OF_SCOPE with a fail-closed routing rule.
6. Only after structural model freeze should broad point-in-time historical regression/backtesting become the main optimization loop.
