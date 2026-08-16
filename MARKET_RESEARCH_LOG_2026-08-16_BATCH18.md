# Market Research Log — 2026-08-16 — Batch 18

## Scope

Archetype expansion: **regulated utility / long-lived yield asset**.

Contrasting sample set:

- `600900 长江电力` — mature long-lived hydropower cash-flow / yield asset with hydrology variance;
- `601985 中国核电` — stable operating nuclear fleet plus heavy nuclear/new-energy growth capex;
- `600011 华能国际` — utility + fuel/tariff/utilization cycle hybrid dominated by thermal generation while expanding renewables.

Structural question:

> Can “utility” be valued by one fixed PE or one dividend-yield threshold?

**Answer: NO. Stable mature assets may support an explicit FCFE/Gordon framework, but growth-heavy or finite-life assets require explicit forecast cash flows, and fuel/tariff-sensitive thermal assets require through-cycle normalization before a yield valuation is meaningful.**

---

## Freshness / evidence status

```text
analysis_as_of: 2026-08-16
latest_completed_a_share_trading_day: 2026-08-14
fundamental_data_as_of: 2026-03-31, with 2025 audited annual baseline
operating_data_as_of: 2026-06-30 where H1 generation disclosures exist
fundamental_freshness: ACCEPTABLE
operating_freshness: FRESH_TO_ACCEPTABLE
price_freshness: UNVERIFIED_FOR_2026-08-14
formal_buy: NO
```

This is archetype validation, not a current share-price recommendation.

---

# 1. 600900 长江电力 — mature long-lived yield asset, but hydrology still matters

## 2025 audited evidence

```text
revenue: ~862.42 亿, +2.07%
profit_total: ~417.40 亿, +7.40%
attributable_net_profit: ~345.03 亿, +6.17%
recurring_attributable_profit: ~341.01 亿
operating_cash_flow: ~605.63 亿, +1.53%
capex_cash_paid: ~184.88 亿
financing_cash_flow: ~-443.44 亿
2025_total_generation: ~3097.35 亿 kWh, +3.97%
```

Domestic hydropower segment:

```text
revenue: ~756.62 亿
gross_margin: 65.79%
revenue_growth: +1.59%
cost_growth: -7.30%
gross_margin_change: +3.28 pp
```

2026Q1:

```text
revenue: ~181.12 亿, +6.44%
attributable_net_profit: ~67.61 亿, +30.50%
recurring_attributable_profit: ~62.37 亿, +19.20%
operating_cash_flow: ~117.11 亿, -1.15%
```

The company explicitly said Q1 profit growth was helped both by electricity-sales income and unrealized gains on financial assets; therefore the recurring result is the cleaner operating reference.

2026H1 operating data:

```text
six_cascade_hydropower_generation: ~1327.44 亿 kWh, +4.81%
Three_Gorges_generation: +31.62%
Wudongde_generation: -16.76%
Baihetan_generation: -5.05%
```

Hydrology diverged materially across basins: Wudongde reservoir inflow was below prior year while Three Gorges inflow was much stronger.

## Model lesson

This is the closest of the three samples to a long-duration yield asset, but even here the model must not annualize one wet quarter or one station's inflow.

Correct evidence path:

```text
multi-year normalized generation
+ realized tariff / dispatch rules
+ maintenance capex
+ debt / interest economics
+ normalized FCFE
-> stable yield DCF when maturity assumption is justified
```

Research subtype:

```text
MATURE_LONG_LIVED_YIELD_ASSET / HYDROLOGY_NORMALIZATION_REQUIRED
```

---

# 2. 601985 中国核电 — stable installed base + heavy growth capex

## 2025 audited evidence

```text
revenue: ~820.75 亿, +6.22%
attributable_net_profit: ~93.04 亿, +6.00%
recurring_attributable_profit: ~91.48 亿, +6.75%
operating_cash_flow: ~374.08 亿, -8.13%
investment_cash_flow: ~-946.79 亿
financing_cash_flow: ~+530.40 亿
weighted_ROE: 8.21% vs 9.44%
total_assets: ~7492.62 亿, +13.57%
parent_equity: ~1187.18 亿, +7.71%
```

The annual report attributes revenue growth primarily to more operating nuclear units and increased renewable installed capacity. The cash-flow profile is the critical clue: stable positive operating cash flow coexists with enormous investment outflow and external financing.

2026Q1:

```text
revenue: ~189.25 亿, -6.65%
attributable_net_profit: ~20.64 亿, -34.19%
recurring_attributable_profit: ~20.37 亿, -34.99%
operating_cash_flow: ~81.31 亿, +41.71%
```

At 2026Q1 end:

```text
operating_nuclear_units: 27
operating_nuclear_capacity: 2621.20 万 kW
under_construction_or_approved_nuclear_units: 18
under_construction_or_approved_capacity: 2067.50 万 kW
operating_controlled_new_energy_capacity: ~3400.47 万 kW
new_energy_capacity_under_construction: ~787.34 万 kW
```

This is not a simple mature dividend asset. A large share of future value depends on capital invested today whose cash generation arrives later.

## Model lesson

Wrong shortcuts:

```text
current dividend yield alone
current PE alone
CFO - all capex as if all capex were maintenance
```

Correct path:

```text
operating fleet normalized FCFE
+ explicit construction/project cash flows
+ financing requirements
+ project commissioning timing
+ terminal/residual value only if explicit
-> multi-year FCFE / SOTP DCF
```

Research subtype:

```text
UTILITY_GROWTH_CAPEX / EXPLICIT_PROJECT_CASH_FLOW_REQUIRED
```

---

# 3. 600011 华能国际 — utility + fuel/tariff cycle hybrid

## 2025 evidence

```text
revenue: ~2292.88 亿, -6.62%
attributable_net_profit: ~144.10 亿, +42.17%
recurring_attributable_profit: ~134.82 亿, +28.13%
operating_cash_flow: ~672.13 亿, +33.02%
weighted_ROE: 19.04% vs 13.14%
```

The 2025 profit improvement was much stronger than revenue growth, which already warns that current earnings are sensitive to fuel costs, tariff, utilization, generation mix and other cycle inputs.

2026Q1:

```text
revenue: ~567.83 亿, -5.89%
attributable_net_profit: ~44.84 亿, -9.83%
recurring_attributable_profit: ~42.21 亿, -12.04%
operating_cash_flow: ~124.37 亿, -28.51%
```

2026H1 domestic operations:

```text
on_grid_generation: ~1995.78 亿 kWh, -2.97%
average_settlement_tariff: 463.02 元/MWh, -4.58%
coal_generation: ~1529.45 亿 kWh, -3.42%
gas_generation: ~117.95 亿 kWh, -11.01%
wind_generation: ~208.72 亿 kWh, -0.75%
solar_generation: ~131.26 亿 kWh, +7.22%
```

Coal generation still represents the dominant production block. Therefore fuel-price and tariff normalization remain material even as renewable capacity grows.

## Model lesson

A high current ROE / low current PE after a favorable coal-cost year may be a classic cycle trap.

Correct routing:

```text
fuel/tariff/utilization evidence
-> through-cycle operating margin / FCFE
-> only then stable-yield or explicit FCFE valuation
```

Research subtype:

```text
CYCLE_SENSITIVE_UTILITY / THROUGH_CYCLE_FCFE_REQUIRED
```

---

# 4. Utility / yield-asset valuation architecture

## 4.1 Explicit FCFE stream — default safe path

For explicit annual equity cash flows:

```text
PV_explicit_FCFE
    = Σ FCFE_t / (1 + required_return)^t
```

Optional terminal value:

```text
PV_terminal
    = explicit_terminal_equity_value_at_last_forecast_year
      / (1 + required_return)^N
```

Then:

```text
fair_equity_value
    = PV_explicit_FCFE
      + PV_terminal_if_explicit
      + explicit_equity_adjustment
```

### Critical rule

**There is no default terminal value.**

For a finite concession / finite remaining asset-life case:

```text
explicit_terminal_equity_value = 0
```

is valid.

For a growth utility, the terminal value must be explicitly constructed after the major project/capex transition; the engine does not silently invoke Gordon forever.

## 4.2 Stable long-duration FCFE path

Only when the research layer explicitly identifies a mature long-duration asset:

```text
fair_equity_value
    = normalized_FCFE * (1 + g)
      / (cost_of_equity - g)
```

with hard condition:

```text
cost_of_equity > g
```

Reverse market expectation:

```text
implied_cost_of_equity
    = normalized_FCFE * (1 + g) / current_market_cap + g
```

This turns dividend/yield intuition into an auditable expectation variable rather than an arbitrary “4% yield is cheap” rule.

## 4.3 Dividend coverage

```text
dividend_coverage = normalized_FCFE / common_dividends
payout_of_FCFE = common_dividends / normalized_FCFE
```

The adapter reports these values but has **no hard-coded safe payout threshold**. Historical out-of-time tests must determine whether such thresholds add value by subtype.

---

# 5. Maintenance capex vs growth capex

The live samples prove this separation is mandatory.

Long-lived infrastructure can report enormous capex while producing healthy operating cash flow. That capex may include:

```text
maintenance / life-extension capex
replacement capex
growth / new-project capex
strategic equity investment
```

Therefore the adapter intentionally does **not** expose a raw:

```text
CFO - capex -> normalized FCFE
```

shortcut.

The research/provider layer must construct normalized FCFE with auditable treatment of maintenance, growth projects and financing.

---

# 6. Code consequence

Draft PR #25 adds:

```text
src/strategies/genge_opportunity_discovery/yield_asset_valuation.py
tests/test_genge_yield_asset_valuation.py
```

Core functions:

```text
value_explicit_fcfe_stream
value_stable_yield_asset
reverse_implied_cost_of_equity
evaluate_dividend_coverage
collect_yield_asset_evidence
```

Tests enforce:

- explicit FCFE stream has no automatic terminal value;
- a caller-supplied terminal value is discounted from the final explicit year;
- finite-life zero residual value is valid;
- stable Gordon path requires explicit FCFE / CoE / growth and CoE > growth;
- market-implied cost of equity is reversible;
- dividend coverage has no hard-coded safe threshold;
- no raw OCF-minus-capex shortcut is present;
- maintenance and growth capex remain separate evidence fields;
- no utility-quality magic score.

Latest PR #25 head:

```text
8e4148a13434f61fa7e49685441317f9983ae4a9
```

CI at checkpoint:

```text
CI: pending
GenGe Cycle Bottom: queued
GenGe Opportunity Discovery: pending
GenGe Risk-Capped Opportunity Discovery: pending
```

---

# 7. Routing conclusion

The broad industry label must route into subtypes:

```text
UTILITY
-> MATURE_LONG_LIVED_YIELD_ASSET
   or UTILITY_GROWTH_CAPEX
   or CYCLE_SENSITIVE_UTILITY
   or FINITE_LIFE_CONCESSION / other explicit subtype
```

Industry classification alone must never select a universal utility PE.

---

# 8. Next queue

1. Continue while PR #25 CI runs.
2. Research **real estate / property** next because PE can become deeply misleading when earnings are recognized from old presales while current sales, collections and inventory/NAV deteriorate.
3. Build NAV / net-debt / inventory-haircut primitives only after live adversarial samples expose the minimum data contract.
4. Then transport/shipping/aviation and agriculture/biological cycle.
5. Update the coverage matrix after executable validation passes.
6. Broad historical backtesting remains blocked until structural archetype coverage is complete enough to freeze routing/model contracts.
