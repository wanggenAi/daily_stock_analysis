# Market Research Log — 2026-08-16 — Batch 19

## Scope

Archetype expansion: **residential property developer / project NAV**.

Adversarial sample set:

- `600048 保利发展` — large state-backed developer with leading current contract sales but severe margin/impairment pressure in recognized earnings;
- `000002 万科A` — balance-sheet / inventory-quality / debt-stress adversarial sample where low P/B or historical PE is obviously unsafe;
- `002244 滨江集团` — relatively stronger private developer with active current sales/land acquisition, showing that even healthier operators still have a large lag between contract sales and recognized profit.

Structural question:

> Can a residential developer be valued primarily from current-period P/E, P/B or raw inventory book value?

**Answer: NO. Project-level attributable cash-flow NAV should be the primary economic bridge. P/E is a lagging settlement diagnostic; accounting inventory is evidence, not market NAV; contract sales are a leading operating indicator but are not immediately available cash.**

---

## Freshness / evidence status

```text
analysis_as_of: 2026-08-16
latest_completed_a_share_trading_day: 2026-08-14
fundamental_data_as_of: 2026-03-31 / 2025 audited annual baseline
operating_data_as_of: 2026-06-30 where H1 sales disclosures exist
fundamental_freshness: ACCEPTABLE
operating_freshness: FRESH_TO_ACCEPTABLE
price_freshness: UNVERIFIED_FOR_2026-08-14
formal_buy: NO
```

This batch validates valuation architecture. No current target price or BUY is asserted.

---

# 1. Why developer P/E is structurally lagging

For a presale-based residential developer, today's income statement normally reflects delivery/settlement of projects sold in earlier periods.

The value chain is closer to:

```text
land acquisition / project investment
-> construction
-> presale / contract sales
-> cash collection
-> remaining construction / taxes / delivery
-> revenue + profit recognition
```

Therefore:

```text
current recognized revenue/profit
!= current contract sales
!= current cash collections
!= remaining project NAV
```

A low current P/E can simply mean that an old high-margin project is being recognized while current sales/land economics deteriorate. A high or negative P/E can coexist with valuable projects if current recognition is temporarily weak. P/E is therefore secondary for the developer archetype.

---

# 2. 600048 保利发展 — sales leadership does not equal recognized-profit quality

## 2025 / 2026 evidence

2025 audited/reported baseline:

```text
revenue: ~3081.44 亿
attributable_net_profit: ~10.3 亿
recurring_attributable_profit: ~6.6 亿
```

The company separately announced 2025 real-estate project impairment provisions of approximately:

```text
total_real_estate_project_impairment: 69.5816 亿
inventory_impairment: 54.4220 亿
long_term_equity_investment_impairment: 10.1512 亿
other_receivable_impairment: 5.0084 亿
```

The impairment methodology itself is instructive: for completed projects the recoverable value is estimated selling price less selling expenses/taxes; for unfinished projects it also deducts remaining completion costs. That is much closer to project economics than raw accounting inventory.

2026H1 operating / earnings evidence:

```text
contracted_sales_area: 631.94 万㎡, -11.44%
contracted_sales_amount: 1351.06 亿, -6.93%
H1_revenue_quick_report: 1028.97 亿, -11.95%
H1_attributable_net_profit_quick_report: 19.28 亿, -38.96%
H1_recurring_attributable_profit_quick_report: 18.47 亿, -38.99%
```

The company explicitly attributed H1 profit pressure to lower project delivery/settlement scale and lower settlement gross margin.

## Model lesson

This is the direct proof that:

```text
current contract sales rank / amount
-> cannot be mapped mechanically to current earnings or NAV
```

The research model must retain at least three separate states:

```text
current sales / new project economics
cash collections / liquidity
recognized delivery / accounting margin
```

Research subtype:

```text
LARGE_DEVELOPER / PROJECT_MARGIN_AND_IMPAIRMENT_NORMALIZATION_REQUIRED
```

---

# 3. 000002 万科A — raw book value and inventory can be false comfort

## 2025 audited evidence

```text
revenue: 2334.33 亿, -31.98%
attributable_net_profit: -885.56 亿
recurring_attributable_net_profit: -859.17 亿
operating_cash_flow: -9.88 亿
parent_equity: 1169.05 亿, -42.32%
common_BVPS: 9.80 元 vs 17.09 元 prior year
asset_liability_ratio: 76.89%
net_debt_ratio: 123.48% vs 80.60%
```

Key balance-sheet / impairment evidence:

```text
cash: 672.41 亿
inventory: 3737.38 亿
  completed_development_products: 1144.48 亿
  projects_under_development: 1788.18 亿
  land_to_be_developed: 778.84 亿
contract_liabilities_including_tax: 1017.69 亿
asset_impairment_loss: ~219.29 亿
credit_impairment_loss: ~341.74 亿
```

The annual report explicitly says development-business settlement scale fell and inventory impairment increased in response to market/project conditions.

2026Q1:

```text
revenue: 289.28 亿, -23.86%
attributable_net_profit: -59.52 亿
recurring_attributable_net_profit: ~-53.34 亿
operating_cash_flow: ~-21.63 亿
```

2026H1 guidance:

```text
expected_attributable_loss: 120–150 亿
expected_recurring_loss: 110–140 亿
```

Reasons include lower development-project settlement scale, still-low gross margin, new asset impairments, and losses in some operating/non-core investments. The company also reported completing approximately 2.3万 homes of scheduled delivery and receiving bond-holder approval to extend 10 public bonds.

## Model lesson

This sample falsifies two common shortcuts:

```text
low P/B -> cheap
inventory book value -> NAV
```

Accounting inventory is historical/adjusted cost. The economic value to common shareholders depends on:

```text
realizable selling proceeds
- remaining construction cost
- taxes / selling cost
- project liabilities / financing
- time to collection
x economic ownership
```

The large 2025 impairment charges also demonstrate why a universal inventory haircut would be false precision: impairment differs by project, city, acquisition basis, product and remaining cost.

Research subtype:

```text
DEVELOPER_STRESS / PROJECT_NAV_AND_LIQUIDITY_PRIMARY / PB_NOT_VALUE_PROOF
```

---

# 4. 002244 滨江集团 — healthier operator still exhibits settlement lag

## 2025 audited evidence

```text
revenue: 828.88 亿, +19.86%
attributable_net_profit: 21.16 亿, -16.87%
recurring_attributable_profit: 20.79 亿, -14.46%
operating_cash_flow: -42.91 亿 vs +76.68 亿 prior year
weighted_ROE: 7.43% vs 9.63%
parent_equity: 294.74 亿, +7.07%
```

The contrast is important: revenue rose almost 20% while recurring profit fell about 14.5%. Recognized volume alone did not preserve economics.

2026Q1:

```text
revenue: 124.90 亿, -44.51%
attributable_net_profit: 8.11 亿, -16.92%
recurring_attributable_profit: 7.87 亿, -18.03%
operating_cash_flow: -16.52 亿
```

2026H1 current operating data:

```text
contracted_sales: 431.5 亿
new_land_count: 12
new_land_total_price: 150.49 亿
new_land_equity_spend: 88.27 亿
new_saleable_value: 281.26 亿
equity_interest_bearing_debt: 236 亿
average_financing_cost: 2.8%
```

This is a relatively stronger-control sample: active current sales and low disclosed financing cost can coexist with declining recognized quarterly revenue/profit because settlement timing and project margin differ.

Research subtype:

```text
ACTIVE_PRIVATE_DEVELOPER / CURRENT_SALES_STRONGER_THAN_SETTLEMENT_EARNINGS
```

---

# 5. Preferred project-level NAV model

For each explicitly non-overlapping project or project portfolio, construct remaining 100%-project **equity cash flows** after project operating economics:

```text
sales / collections
- remaining land/construction cost
- taxes
- selling costs
- project-level financing/liability cash flows as explicitly modeled
= project equity cash flow
```

Then:

```text
PV_100pct_project_equity_cash_flows
    = Σ project_equity_FCF_t / (1 + project_required_return)^t

attributable_project_NAV
    = PV_100pct_project_equity_cash_flows
      × economic_ownership
```

There is no automatic terminal value. Residential development is a finite project economics problem unless the research layer explicitly constructs further projects/assets.

Negative early project cash flow is valid because remaining construction/land investment can precede future collections.

---

# 6. Corporate equity bridge and double-count protection

```text
fair_equity_NAV
    = Σ unique_attributable_project_NAV
      + unrestricted_cash
      + verified_non_project_asset_value
      - corporate_interest_bearing_debt_NOT_ALREADY_IN_PROJECTS
      - corporate_liability_PV_NOT_ALREADY_IN_PROJECTS
      + explicit_equity_adjustment
```

The `NOT_ALREADY_IN_PROJECTS` scope is critical.

If project cash flows already include project debt service, remaining construction payables, taxes or other liabilities, those cannot be subtracted again at corporate level.

Likewise a property-management stake, investment property or other operating asset can be added only using a separately verified economic value and only if its cash flows/value are outside project NAV.

---

# 7. Inventory is evidence, not NAV

The production valuation interface deliberately has **no** input called:

```text
inventory_book_value_as_NAV
inventory_haircut_default
```

Accounting inventory remains useful evidence for:

- scale of unsold/completing projects;
- impairment trend;
- completed vs under-construction vs land composition;
- future settlement resources;
- stress testing.

But converting raw inventory to NAV requires project/city/economic assumptions. A universal 20%/30%/40% haircut is not introduced.

---

# 8. Reverse implied project recovery

If an externally constructed attributable project NAV exists, current market capitalization can be converted into an auditable implied recovery ratio:

```text
implied_project_recovery
    = (current_market_cap - non_project_net_asset_value)
      / reference_attributable_project_NAV
```

where:

```text
non_project_net_asset_value
    = cash + other_non_project_assets
      - corporate_debt/liabilities
      + explicit_adjustments
```

A negative result is preserved. It can signal that the market is discounting project NAV, non-project asset quality, liquidity, hidden liabilities or the input NAV itself; the engine must not floor the value and hide that message.

This is the property-developer version of the project's reverse-implied-expectation framework.

---

# 9. Horizon-matched liquidity

Developer solvency must distinguish current resources from long-dated obligations.

```text
liquidity_sources
    = unrestricted_cash
      + expected_cash_collections_within_same_horizon

committed_outflows
    = debt_principal_due_within_horizon
      + committed_land_and_construction_outflows_within_horizon
      + other_committed_cash_outflows_within_horizon

horizon_liquidity_surplus
    = liquidity_sources - committed_outflows
```

Hard rules:

- contract sales face value is **not** counted as cash;
- collections must be explicitly estimated/verified for the horizon;
- all long-term debt is **not** automatically subtracted from short-horizon liquidity;
- full verified debt remains a senior claim in equity NAV where it has not already been handled inside projects.

This distinction mirrors the biotech runway lesson but with developer-specific sales/land/construction commitments.

---

# 10. Evidence layer

Carry leading and lagging signals separately:

```text
contracted_sales_growth
contracted_sales_area_growth
cash_collection_ratio
recognized_revenue_growth
recognized_gross_margin
recognized_gross_margin_change
inventory_book_value
inventory_impairment_charge
contract_liabilities
new_land_equity_spend
new_land_sale_value
interest_bearing_debt
near_term_debt
average_financing_cost
```

No composite developer-quality score is created before out-of-time validation.

Especially important:

```text
contracted_sales = leading demand / future settlement evidence
cash collections = liquidity evidence
recognized revenue/profit = lagging delivery evidence
inventory impairment = project-quality/recovery evidence
land acquisition = future supply + cash-commitment evidence
```

They must not be collapsed into one period's PE.

---

# 11. Code consequence

Draft PR #25 adds:

```text
src/strategies/genge_opportunity_discovery/real_estate_nav_valuation.py
tests/test_genge_real_estate_nav_valuation.py
```

Core functions:

```text
value_project_equity_cash_flows
bridge_developer_equity_nav
reverse_implied_project_recovery
assess_developer_horizon_liquidity
collect_developer_evidence
```

Tests enforce:

- explicit project cash-flow timing;
- explicit project economic ownership and required return;
- negative development-period cash flow is allowed;
- no automatic project terminal value;
- no raw inventory-book-value NAV input;
- no default inventory haircut;
- duplicate project IDs are rejected;
- corporate bridge only accepts debts/liabilities declared outside project cash flows;
- reverse implied project recovery preserves negative values;
- liquidity uses expected collections, not contract-sales face value;
- liquidity uses horizon debt maturities, not total debt;
- inventory/impairment remain evidence only;
- no developer magic score.

Latest PR #25 head after real-estate tests:

```text
34beb7d02d3f52b9e0d77409a4868f79dd501493
```

CI at this checkpoint:

```text
CI: queued
GenGe Cycle Bottom: in_progress
GenGe Opportunity Discovery: pending
GenGe Risk-Capped Opportunity Discovery: pending
```

The PR remains open and draft. These primitives are still isolated from Formal BUY / sizing / exit / market-regime logic.

---

# 12. Next queue

1. Continue research while CI runs; do not wait idly.
2. Research **transport / shipping / aviation** next because freight, load factor, aircraft/ship asset cycles and concession economics create multiple non-PE archetypes inside one broad sector.
3. Then agriculture/biological cycle, auto/EV/battery, solar/wind/storage, coal/oil/petrochemical, software/SaaS, defense and other remaining material archetypes.
4. Re-check PR #25 CI after each meaningful code batch and repair only reproducible failures.
5. Update `MODEL_COVERAGE_MATRIX_2026-08-16.md` and `RESEARCH_QUEUE.md` with validated status before context handoff.
6. Broad point-in-time historical regression/backtesting remains blocked until material archetypes are VALIDATED or deliberately OUT_OF_SCOPE with fail-closed routing.
