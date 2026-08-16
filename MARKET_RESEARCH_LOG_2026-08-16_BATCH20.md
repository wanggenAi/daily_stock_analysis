# Market Research Log — 2026-08-16 — Batch 20

## Scope

Archetype expansion: **capital-intensive transport**, with three distinct economic subtypes:

- `601919 中远海控` — container-shipping freight/capacity cycle;
- `601021 春秋航空` — airline fare/load-factor/fuel/lease cycle;
- `600009 上海机场` — mature airport/infrastructure traffic + commercial-value asset.

Structural question:

> Can shipping, airlines and airports share a transport-sector P/E model?

**Answer: NO. Shipping and airlines need through-cycle operating economics and a lease/debt-consistent enterprise-value bridge. Mature airports are better routed to the already implemented yield-asset / explicit-FCFE model.**

---

## Freshness

```text
analysis_as_of: 2026-08-16
latest_completed_a_share_trading_day: 2026-08-14
fundamental_data_as_of: 2026-03-31, with 2025 annual baseline
operating_data_as_of: 2026-06-30 where monthly/H1 data exist
price_freshness: UNVERIFIED_FOR_2026-08-14
formal_buy: NO
```

---

# 1. 601919 中远海控 — volume growth can coexist with collapsing cycle profits

2025:

```text
revenue: ~2195.04 亿
EBIT: ~450.13 亿
net_profit: ~352.28 亿
attributable_net_profit: ~308.68 亿
container_volume: 2743.45 万 TEU, +5.76%
container_shipping_revenue: ~2107.31 亿
container_shipping_gross_margin: 19.44%
terminal_throughput: 1.53 亿 TEU, +6.22%
```

But the market environment moved the other way on price:

```text
SCFI_2025_average: ~-37% YoY
CCFI_2025_average: ~-23% YoY
global_container_capacity_growth: ~7%
demand_growth: ~3.5%-4%
```

2026Q1:

```text
revenue: 517.97 亿
container_volume: 691.56 万 TEU, +6.70%
EBIT: 87.63 亿, -47.14%
terminal_throughput: 3891.72 万 TEU, +8.86%
asset_liability_ratio: ~40.90%
cash_and_cash_equivalents: ~1497.02 亿
```

The sample proves the cycle identity:

```text
higher volume != higher normalized profit
```

when freight rates fall faster than unit-cost improvements.

Research subtype:

```text
CONTAINER_SHIPPING / FREIGHT_AND_CAPACITY_CYCLE / THROUGH_CYCLE_EV_REQUIRED
```

---

# 2. 601021 春秋航空 — load factor alone is not profitability

2025 operating evidence:

```text
average_load_factor: 91.53%, +0.04 pp
passenger_yield_per_RPK: 0.370 yuan, -3.78%
domestic_yield: -4.91%
international_yield: -1.86%
```

Thus an already very high load factor coexisted with weaker unit revenue.

2026Q1:

```text
revenue: 60.70 亿, +14.16%
attributable_net_profit: 9.83 亿, +45.15%
recurring_attributable_profit: 9.68 亿, +43.62%
operating_cash_flow: 16.40 亿, +261.59%
```

2026H1 operating data through June:

```text
cumulative_load_factor: ~92.59%, +2.08 pp
June_load_factor: 91.86%
cumulative_passengers: ~1737.31 万, +14.15%
```

Correct airline economic evidence must separate:

```text
RPK / traffic
ASK / capacity
load_factor = RPK / ASK
passenger_yield / RASK
unit_cost / CASK
fuel unit cost
FX
fleet / capex
lease liabilities / debt
```

A high load factor cannot substitute for yield or cost data.

Research subtype:

```text
AIRLINE / YIELD_LOAD_FACTOR_COST_CYCLE / LEASE_CONSISTENT_EV_REQUIRED
```

---

# 3. 600009 上海机场 — reuse yield-asset framework, do not force transport-cycle EV

2025 operating baseline included approximately:

```text
Pudong_passengers: 8499.45 万, +10.69%
Pudong_cargo: 409.19 万吨, +8.30%
```

2026Q1:

```text
revenue: 31.98 亿, +0.81%
attributable_net_profit: 5.78 亿, +11.33%
recurring_attributable_profit: 5.54 亿, +8.13%
operating_cash_flow: 6.60 亿, -6.27%
```

2026 June:

```text
Pudong_passengers: 686.35 万, -0.55%
Pudong_international_and_regional_passengers: 315.33 万, +1.58%
Pudong_cargo: 40.05 万吨, +17.88%
Hongqiao_passengers: 404.16 万, -0.80%
```

Airport economics combine:

```text
traffic / aeronautical charges
+ commercial rent / concession / duty-free economics
+ cargo / property / advertising / parking
- operating + maintenance + expansion capex
```

This is closer to a long-lived infrastructure/yield asset than an airline/shipping cycle business.

Routing:

```text
AIRPORT_LONG_LIVED_INFRASTRUCTURE
-> reuse yield_asset_valuation.py
```

No new airport-specific valuation multiple is created.

---

# 4. Capital-intensive transport EV bridge

For shipping/airline subtypes:

```text
fair_enterprise_value
    = through_cycle_normalized_EBITDA
      × explicit_fair_EV_EBITDA_multiple

fair_equity_value
    = fair_enterprise_value
      - net_debt_including_lease_liabilities
      + explicit_non_operating_equity_adjustment
```

Negative net debt is valid for net-cash companies and increases equity value.

For airlines, debt/lease scope must be consistent with EBITDA. The adapter therefore explicitly requires:

```text
net_debt_including_lease_liabilities
```

instead of silently omitting lease obligations.

Reverse implied expectation:

```text
current_enterprise_value
    = current_market_cap
      + lease_consistent_net_debt
      - explicit_non_operating_adjustment

implied_normalized_EBITDA
    = current_enterprise_value
      / explicit_fair_EV_EBITDA_multiple
```

Then compare the implied EBITDA with evidence-based through-cycle Bear/Base/Bull EBITDA.

---

# 5. No hidden cycle assumptions

The adapter contains no default:

```text
SCFI / CCFI mean
freight rate
passenger yield
load factor
fuel price
FX rate
fleet growth
capacity growth
cycle haircut
EV/EBITDA multiple
```

Those must be explicit point-in-time scenario inputs and later validated historically.

Raw evidence stays separate:

```text
volume_or_RPK_growth
capacity_or_ASK_growth
utilization_or_load_factor
unit_revenue_or_yield_change
unit_cost_change
fuel_unit_cost_change
benchmark_rate_or_fare_index_change
fleet_capacity_growth
lease_liabilities
capex
lease_consistent_net_debt
```

No transport magic score is introduced.

---

# 6. Code consequence

Draft PR #25 adds:

```text
src/strategies/genge_opportunity_discovery/transport_cycle_valuation.py
tests/test_genge_transport_cycle_valuation.py
```

Core functions:

```text
value_through_cycle_transport_ev
reverse_implied_transport_ebitda
collect_transport_cycle_evidence
build_transport_three_scenario_valuation
```

Tests enforce:

- through-cycle EBITDA rather than current/peak earnings;
- lease-consistent net debt is mandatory;
- net cash remains negative net debt;
- reverse implied EBITDA uses the same EV bridge;
- no freight/fare/fuel/cycle-haircut defaults;
- volume, price, capacity and cost remain separate evidence;
- Bear/Base/Bull scenarios are explicit.

Latest PR #25 head:

```text
dd99aef402a8cfb38e58b5e888b2b8bdfd73ce18
```

CI at checkpoint:

```text
CI: queued
GenGe Cycle Bottom: queued
GenGe Opportunity Discovery: pending
GenGe Risk-Capped Opportunity Discovery: pending
```

---

# 7. Next queue

1. Continue into **agriculture / biological cycle** while CI runs.
2. Use hog/poultry/feed samples to test unit-cost curve, breeding inventory and through-cycle margin economics.
3. Avoid current low PE after a high hog-price quarter.
4. Re-check PR #25 CI and repair only reproducible failures.
5. Then continue auto/EV/battery, solar/wind/storage, coal/oil, software/SaaS/platform, defense and remaining material archetypes before model freeze/backtest.
