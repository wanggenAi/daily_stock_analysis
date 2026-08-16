# Market Research Log — 2026-08-16 — Batch 22

## Scope

Archetype expansion: **automotive OEM / EV / battery manufacturing**.

Adversarial sample set:

- `002594 比亚迪` — vertically integrated BEV/PHEV OEM + battery/electronics ecosystem, A/H listed;
- `600104 上汽集团` — incumbent OEM in transition, own-brand/JV/NEV/overseas mix and material equity-method/investment-income effects;
- `300750 宁德时代` — EV/ESS battery + materials/recycling capacity-cycle manufacturer, A/H listed.

Structural question:

> Can the broad “新能源车” sector share one high-growth P/E model?

**Answer: NO. OEMs require product/mix/unit-economics normalization and strict non-overlapping segment scopes. Battery/capacity manufacturers require utilization/volume/price/cost normalization before valuation. Volume growth, market-share gains or overseas expansion do not mechanically imply profit growth.**

---

## Freshness / evidence status

```text
analysis_as_of: 2026-08-16
latest_completed_a_share_trading_day: 2026-08-14
fundamental_data_as_of:
  BYD: 2026-03-31 + 2026H1 sales data
  SAIC: 2026-03-31 + 2025 annual baseline
  CATL: 2026-06-30 interim report
fundamental_freshness: FRESH_TO_ACCEPTABLE
operating_freshness: FRESH_TO_ACCEPTABLE
price_freshness: UNVERIFIED_FOR_2026-08-14
formal_buy: NO
```

This batch validates model architecture. It intentionally does not invent current A/H market capitalization or a Formal BUY.

---

# 1. 002594 比亚迪 — product mix and margin matter more than headline unit growth

## 2025 baseline

Official 2025 results / company summary:

```text
revenue: ~8040 亿
net_profit: ~326 亿
NEV_sales: ~460 万辆
R&D: ~634 亿, +17%
overseas_passenger_and_pickup_sales: ~105 万辆
```

The company remains one of the most vertically integrated global EV manufacturers, combining vehicles, batteries, electronics and overseas manufacturing/distribution.

## Critical 2026Q1 correction

The official 2026Q1 report shows a sharp decline, not growth:

```text
revenue: 1502.25 亿, -11.82% YoY
attributable_net_profit: 40.85 亿, -55.38%
recurring_attributable_net_profit: 41.48 亿, -49.24%
operating_cash_flow: 27.90 亿, -67.48%
```

Finance expense also moved adversely because the period contained FX losses versus FX gains in the comparable period.

This correction is important because an earlier superficial reading of reversed table columns could have incorrectly classified Q1 as growth. The official filing confirms the opposite.

2026H1 sales mix:

```text
total_NEV_sales: 1,808,511, -1.01% YoY
passenger_BEV_sales: 1,002,360, +11.44%
passenger_PHEV_sales: 574,133, -17.73%
overseas_passenger_and_pickup_sales: ~789,367, strongly higher YoY
```

## Model lesson

The live sample falsifies:

```text
BEV sales growth
+ overseas growth
=> group profit growth
```

because group economics depend on:

```text
BEV/PHEV/model mix
net realized revenue per vehicle
price cuts / dealer incentives
battery/material cost
factory utilization
warranty / after-sales
FX
R&D and capex
internal vertical-integration transfer economics
```

### Double-count guard

For a vertically integrated OEM, the model must not separately capitalize:

```text
vehicle margin that already embeds internally supplied battery/electronics economics
+
internal battery/electronics margin for the same economic scope
```

unless the scopes are explicitly non-overlapping (for example verified external battery sales separate from vehicle economics).

Research subtype:

```text
VERTICALLY_INTEGRATED_OEM / PRODUCT_MIX_UNIT_ECONOMICS / A_H_SCOPE
```

---

# 2. 600104 上汽集团 — incumbent transition requires JV/equity-income separation

## 2025 baseline

```text
revenue: ~6134.10 亿
attributable_net_profit: ~101.07 亿, +51.19%
operating_cash_flow: ~247.78 亿
auto_manufacturing_gross_margin: ~10.48%, +1.82 pp
total_vehicle_sales: ~450.6 万辆, +12.32%
NEV_sales: ~164.3 万辆, +33.08%
overseas_sales: ~107.1 万辆, -1.96%
own_brand_sales: ~292.8 万辆, +21.84%
own_brand_share_of_total: >65%
```

## 2026Q1

```text
revenue: ~1377.00 亿, -0.93%
attributable_net_profit: ~30.16 亿, -0.73%
recurring_attributable_net_profit: ~28.11 亿, +44.36%
operating_cash_flow: ~45.21 亿, +257.43%
vehicle_sales: ~105.9 万辆, +18.95%
NEV_sales: ~32.7 万辆, +2.29%
overseas_sales: ~23.2 万辆, +17.27%
```

The headline-vs-recurring divergence and changing investment/equity-income contribution show why OEM normalization must preserve earnings-quality separation.

## Model lesson

For an incumbent OEM, normalized profit can include distinct economic engines:

```text
own-brand vehicle product scopes
JV / equity-method income
parts / services / finance or other businesses
non-recurring investment gains
```

The product-cycle layer therefore requires `normalized_equity_method_income` as a separate explicit input rather than hiding JV income inside vehicle unit margin.

Research subtype:

```text
INCUMBENT_OEM_TRANSITION / PRODUCT_MIX + EQUITY_METHOD_INCOME
```

---

# 3. 300750 宁德时代 — high growth does not remove capacity-cycle economics

## 2026H1 official interim evidence

```text
revenue: 2769.17 亿, +54.80%
attributable_net_profit: 432.84 亿, +41.98%
```

Segment revenue:

```text
EV_battery_revenue: 1921.25 亿, 69.38% of total, +46.02%
ESS_battery_revenue: 532.61 亿, 19.23%, +87.54%
materials_recycling_minerals_revenue: 188.11 亿, 6.79%, +67.23%
```

Margins:

```text
overall_gross_margin: 23.93%, -1.09 pp
EV_battery_gross_margin: 20.63% vs 22.41%
ESS_battery_gross_margin: 23.96% vs 25.52%
materials_recycling_minerals_gross_margin: 27.04% vs 21.23%
```

Market position:

```text
China_passenger_NEV_battery_install_share_Jan-Jun: 46.7%, +5.6 pp
global_EV_battery_usage_share_Jan-May: 40.2%, +2.2 pp
overseas_share_Jan-May: 33.7%, +3.7 pp
```

Cash / balance-sheet / expansion evidence:

```text
operating_cash_flow: ~602.17 亿, +2.61%
liquid_bank_balances_deposits_cash: ~3720.53 亿
inventory: ~1308.19 亿 vs ~945.26 亿 at year-end
fixed_assets: ~1693.82 亿
construction_in_progress: ~330.25 亿
total_borrowings: ~1465.35 亿
borrowings_due_within_one_year: ~422.55 亿
R&D_H1: ~113.77 亿, +12.70%
```

The company is expanding capacity domestically and internationally, including major projects/JVs in China, Indonesia, Hungary and Spain.

## Model lesson

The strong top-line/profit growth is real, but several cycle/capacity diagnostics moved differently:

```text
EV/ESS gross margins declined
OCF growth (~2.6%) lagged revenue/profit growth materially
inventory rose strongly
fixed assets / construction / global capacity continue to expand
```

Therefore the model must not simply extrapolate H1 profit CAGR.

The preferred normalized structure is:

```text
EV battery scope
ESS battery scope
materials/recycling/minerals scope
other non-cycle / service / licensing economics
```

For each capacity-driven scope use either:

```text
physical unit mode:
  normalized volume
  × (normalized realized price - normalized variable unit cost)
  - normalized fixed operating cost
```

or, when GWh/tonne unit data are unavailable:

```text
explicit normalized revenue
× explicit normalized operating margin
```

The second mode is a fail-soft data interface, not permission to treat current margin as normalized margin.

Research subtype:

```text
BATTERY_CAPACITY_CYCLE_GROWTH / SEGMENT_MARGIN_AND_UTILIZATION_NORMALIZATION / A_H_SCOPE
```

---

# 4. OEM product-cycle normalization

New generic product-cycle primitive:

```text
normalized_unit_operating_margin
    = normalized_net_revenue_per_unit
      - normalized_full_operating_cost_per_unit

normalized_product_profit
    = normalized_units
      × normalized_unit_operating_margin
      + explicit_segment_adjustment
```

Company sustainable profit:

```text
normalized_sustainable_profit
    = Σ non-overlapping_product_scope_profit
      + normalized_non_product_profit
      + normalized_equity_method_income
      + explicit_corporate_adjustment
```

### Economic-scope guard

Each product segment carries an explicit `economic_scope_id`.

Duplicate scope IDs fail closed to catch obvious double capitalization.

This is especially important for vertically integrated OEMs and for companies with JV/affiliate economics.

### Reverse expectation

Given a market-implied total normalized profit from the common valuation layer:

```text
implied_target_product_unit_margin
    = (implied_total_profit
       - non_product_profit
       - equity_method_income
       - other_product_scope_profit
       - corporate_adjustment)
      / target_scope_units
```

This answers a more useful question than “current OEM PE is X”:

> What sustainable profit per vehicle does the current share price require after separating other businesses/JV income?

---

# 5. Reusable capacity-cycle manufacturing normalization

A second generic primitive is created for batteries, PV, chemicals and other capacity-driven sectors.

## Physical-unit mode

```text
normalized_segment_profit
    = normalized_sales_units
      × (normalized_realized_unit_price - normalized_variable_unit_cost)
      - normalized_fixed_operating_cost
      + explicit_segment_adjustment
```

If effective capacity is explicitly known:

```text
normalized_capacity_utilization
    = normalized_sales_units / effective_capacity_units
```

Utilization is diagnostic only. It does not automatically set volume or margin.

## Revenue/margin mode

When reliable physical-unit data are missing:

```text
normalized_segment_profit
    = explicit_normalized_revenue
      × explicit_normalized_operating_margin
      + explicit_segment_adjustment
```

Both values must be explicitly prepared; no current-margin fallback is hidden in the adapter.

## Reverse unit contribution margin

```text
implied_target_unit_contribution_margin
    = (implied_total_profit
       - normalized_non_cycle_profit
       - other_cycle_scope_profit
       - corporate_adjustment
       + target_fixed_operating_cost)
      / target_sales_units
```

This creates a common expectation-gap language for battery, solar, chemical and similar capacity cycles.

---

# 6. Evidence contract

## Product-cycle/OEM evidence

```text
total_unit_sales_growth
product_mix_shares
overseas_unit_share
net_revenue_per_unit_change
incentive/rebate_change
gross_margin and change
capacity_utilization
inventory_days
warranty_cost_ratio
R&D_intensity
capex
equity_method_income_share
FX_profit_or_loss
```

## Capacity-cycle evidence

```text
current_sales_units
current_effective_capacity
current_utilization
realized_unit_price_change
variable_unit_cost_change
gross_margin and change
inventory_value / growth
capex
construction_in_progress
planned_capacity_additions
market_share / change
operating_cash_flow_growth
```

No composite auto/battery quality score is created before out-of-time validation.

---

# 7. Code consequence

Draft PR #25 adds:

```text
src/strategies/genge_opportunity_discovery/product_cycle_normalization.py
tests/test_genge_product_cycle_normalization.py

src/strategies/genge_opportunity_discovery/capacity_cycle_normalization.py
tests/test_genge_capacity_cycle_normalization.py
```

Product-cycle tests enforce:

- explicit units/revenue-per-unit/full-cost-per-unit;
- negative unit margin preserved;
- no hidden BEV/PHEV mix, ASP, incentive defaults;
- duplicate economic scopes rejected;
- non-product and equity-method income separated;
- implied total profit can be reversed to product unit margin.

Capacity-cycle tests enforce:

- explicit volume/price/variable-cost/fixed-cost reconstruction;
- negative cycle profit preserved;
- utilization is diagnostic, not a volume generator;
- revenue/margin mode still requires explicit normalized inputs;
- no lithium/silicon price, utilization target or cycle haircut defaults;
- duplicate economic scopes rejected;
- reverse implied unit contribution margin;
- inventory/capex/market-share/cash-flow evidence remains separate.

Latest PR #25 head after these modules:

```text
687a025848c08560be935d5f3aef44d26b7fee6d
```

CI at checkpoint:

```text
CI: queued
GenGe Cycle Bottom: queued
GenGe Opportunity Discovery: pending
GenGe Risk-Capped Opportunity Discovery: pending
```

Earlier agriculture head already had Opportunity Discovery and Risk-Capped passing, with no reproducible test failure observed before this new head was created.

---

# 8. Routing conclusion

```text
AUTO_EV_BATTERY
-> PRODUCT_CYCLE_OEM
   or CAPACITY_CYCLE_MANUFACTURER
   or explicit hybrid/SOTP using non-overlapping scopes
```

Do not route by the marketing label “新能源车” alone.

A/H issuers must continue to use the existing multi-share-class market-cap bridge rather than A-price × total shares shortcuts.

---

# 9. Next queue

1. Apply the reusable capacity-cycle layer to **solar / wind / storage** rather than creating redundant sector code.
2. Suggested adversarial samples:
   - `601012 隆基绿能` — PV capacity/price-clearance stress;
   - `300274 阳光电源` — inverter/storage system quality-growth counterexample;
   - `002202 金风科技` or `601615 明阳智能` — wind equipment/project economics.
3. Add code only if live samples expose a primitive not already covered by capacity-cycle, product-cycle, yield-asset, industrial or DCF modules.
4. Re-check latest PR #25 CI and repair only reproducible failures.
5. Continue energy/chemicals, software/SaaS/platform, defense and remaining material archetypes.
6. Model freeze/backtest remains blocked until coverage/routing gates are updated and validated.
