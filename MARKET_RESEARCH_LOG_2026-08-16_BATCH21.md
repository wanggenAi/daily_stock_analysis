# Market Research Log — 2026-08-16 — Batch 21

## Scope

Archetype expansion: **agriculture / biological livestock cycle**.

Adversarial sample set:

- `002714 牧原股份` — large-scale low-cost hog producer with increasingly material slaughter/food-processing economics;
- `300498 温氏股份` — hog + poultry dual biological cycle;
- `000876 新希望` — feed + hog mixed business, useful for testing biological/non-biological segment separation.

Structural question:

> Can a livestock company be valued from current-period P/E or from one year's accounting profit?

**Answer: NO. Hog/poultry profit must first be rebuilt from sustainable output × normalized unit margin. Spot price, current annual profit and current P/E are cycle-state observations, not sustainable earnings. Feed, slaughter and other businesses must be normalized separately.**

---

## Freshness / evidence status

```text
analysis_as_of: 2026-08-16
latest_completed_a_share_trading_day: 2026-08-14
fundamental_data_as_of: 2026-03-31, with 2025 annual baseline
operating_data_as_of: 2026-06-30
fundamental_freshness: ACCEPTABLE
operating_freshness: FRESH_TO_ACCEPTABLE
price_freshness: UNVERIFIED_FOR_2026-08-14
formal_buy: NO
```

This batch validates cycle-normalization architecture. It intentionally does not create a current BUY call.

---

# 1. 002714 牧原股份 — 2025 profit is already stale versus 2026 spot economics

2025 operating / financial evidence:

```text
pig_sales: ~7798.1 万头
revenue: ~1441.45 亿, +4.49%
attributable_net_profit: ~154.87 亿
recurring_attributable_net_profit: ~159.88 亿
full_hog_production_cost: ~12 元/kg, down ~2 元/kg YoY
slaughter_volume: ~2866.3 万头
meat_products: ~323 万吨
slaughter_and_meat_revenue: ~452.28 亿, +86.32%
slaughter_business: first annual profit
```

By March 2026, disclosed fattening/full production cost had fallen further to approximately:

```text
~11.6 元/kg
```

But June 2026 spot operating data were already below that cost level:

```text
June_pig_sales: ~622.7 万头
June_average_sale_price: 9.69 元/kg
June_revenue: ~75.00 亿
H1_pig_sales: ~3861.5 万头
June_breeding_sow_inventory_reference: ~311.3 万头
```

The June unit-economics message is unambiguous:

```text
9.69 元/kg spot sale price
< ~11.6 元/kg recent disclosed production cost
```

Therefore the strong 2025 accounting profit is not a valid forward sustainable-profit denominator for mid-2026.

## Model lesson

This is the canonical biological-cycle P/E trap:

```text
high hog price year -> profit spikes -> trailing PE looks very low
low hog price year  -> profit collapses/turns negative -> trailing PE looks very high
```

The correct normalization variable is unit margin, not current P/E.

Research subtype:

```text
LOW_COST_HOG_PRODUCER / UNIT_COST_ADVANTAGE / BIOLOGICAL_CYCLE_NORMALIZATION
```

---

# 2. 300498 温氏股份 — multiple biological cycles must stay separate

2025:

```text
revenue: ~1038.62 亿, -1.69%
attributable_net_profit: ~52.66 亿, -43.25%
pig_sales: ~4047.69 万头
  fat_hogs_and_fresh_products: ~3544.67 万头
  piglets: ~503.02 万头
chicken_sales: ~13.03 亿只
hog_full_cost: ~6.1–6.2 元/斤 (~12.2–12.4 元/kg)
chicken_full_cost_reference: ~5.7 元/斤
hog_business_gross_margin/reference_margin: ~14.76%, -5.56 pp
```

2026Q1 company/IR disclosures indicated hog cost had continued to improve; after removing inventory-price provisions, cost was below 6 元/斤 and March was around:

```text
~5.8 元/斤 ≈ 11.6 元/kg
```

June 2026:

```text
meat_pig_sales: 257.09 万头
pig_revenue: 30.78 亿
average_hog_price: 9.62 元/kg
H1_pig_sales: ~1780.78 万头
June_chicken_sales: ~1.1071 亿只
June_chicken_price: 11.36 元/kg
H1_chicken_sales: ~6.331346 亿只
```

Again:

```text
June hog spot price ~9.62 元/kg
< recent hog cost reference ~11.6 元/kg
```

## Model lesson

温氏 cannot be normalized as one biological margin because hog and chicken cycles can be at different points simultaneously.

Correct structure:

```text
hog normalized profit
+ chicken normalized profit
+ other explicitly normalized business profit
-> company sustainable profit
```

No single “livestock price” or one consolidated gross margin should replace species-level economics.

Research subtype:

```text
MULTI_SPECIES_BIOLOGICAL_CYCLE / SPECIES_SEGMENT_NORMALIZATION_REQUIRED
```

---

# 3. 000876 新希望 — feed + livestock mix requires non-biological separation

2025:

```text
revenue: ~1068.56 亿
```

The annual-report narrative showed two different economic engines:

```text
feed business:
  core profitability improved / relatively non-hog-cycle economics

hog business:
  cost improved but Q4 hog-price decline and biological/fixed-asset provisions hurt annual result
```

June 2026 hog operating data:

```text
pig_sales: ~125.44 万头, +27.35% YoY
revenue: ~13.84 亿, -17.18% YoY
average_hog_price: 9.35 元/kg, -34.06% YoY
H1_pig_sales: ~710.64 万头
```

The combination is a direct warning against applying the hog cycle to consolidated earnings:

```text
feed economics != hog biological economics
```

Research subtype:

```text
FEED_HOG_HYBRID / NON_BIOLOGICAL_SEGMENT_SEPARATION_REQUIRED
```

---

# 4. Biological-cycle normalization core

For one species/product segment with consistent units:

```text
normalized_unit_margin
    = normalized_unit_price
      - normalized_full_unit_cost

normalized_operating_contribution
    = normalized_output_units
      × normalized_unit_margin

normalized_segment_profit
    = normalized_operating_contribution
      + explicit_segment_profit_adjustment
```

Negative unit margin is valid and is preserved.

The model deliberately does **not** floor:

```text
normalized_unit_margin >= 0
normalized_segment_profit >= 0
```

because industry-clearing losses are a real part of biological cycles.

---

# 5. Spot price vs normalized price

The adapter keeps these as separate concepts:

```text
spot_sale_price
normalized_unit_price
full_unit_cost
```

For example, June 2026 hog prices around 9–10 元/kg are powerful evidence that the sector is in a loss phase, but the model does not automatically declare 9.5 元/kg to be the long-run normalized price.

Likewise it does not hard-code:

```text
historical mean hog price
sow inventory target
feed cost
mortality target
cycle haircut
```

Those inputs must be explicitly constructed from point-in-time evidence and later validated out of time.

---

# 6. Aggregate mixed biological businesses

For a company with multiple species:

```text
normalized_biological_profit
    = Σ unique biological segment normalized profit
```

Then separately:

```text
normalized_sustainable_profit
    = normalized_biological_profit
      + normalized_non_biological_profit
      + explicit_corporate_adjustment
```

`normalized_non_biological_profit` is mandatory even when the correct value is explicitly zero.

This prevents:

- feed earnings inheriting a hog price assumption;
- slaughter/food-processing margins being mistaken for farm margin;
- the same species segment being counted twice.

Duplicate biological segment IDs fail closed.

---

# 7. Reverse implied unit economics

The existing reverse-valuation layer can first derive the total sustainable profit required by current market capitalization under an explicit valuation multiple/horizon.

The biological-cycle layer can then reverse-solve the unit margin demanded from one target species:

```text
implied_target_segment_profit
    = implied_total_normalized_profit
      - normalized_non_biological_profit
      - other_biological_segment_profit
      - explicit_corporate_adjustment

implied_target_unit_margin
    = implied_target_segment_profit
      / target_segment_output_units
```

This creates a much more interpretable expectation-gap question for hog producers:

> At the current market value, how much sustainable profit per kg/head must the market be assuming after separating feed/slaughter/other businesses?

That is superior to saying “current PE is 8x/20x/negative”.

---

# 8. Evidence layer

Carry explicitly:

```text
spot_sale_price
normalized_unit_price
full_unit_cost
unit_cost_change
output_growth
breeding_inventory
breeding_inventory_change
mortality_or_survival_change
feed_raw_material_cost_change
biological_asset_impairment
slaughter_or_processing_volume_growth
non_biological_profit_share
```

Important economic ordering:

```text
breeding inventory / survival / output
-> future supply
-> industry spot price
-> unit margin vs company-specific cost
-> sustainable biological profit
```

A company with a durable cost advantage can be attractive earlier in the cycle than a high-cost peer, but low cost alone does not make a loss-making spot environment immediately cheap.

---

# 9. Code consequence

Draft PR #25 adds:

```text
src/strategies/genge_opportunity_discovery/biological_cycle_normalization.py
tests/test_genge_biological_cycle_normalization.py
```

Core functions:

```text
normalize_biological_segment
aggregate_biological_cycle_profit
reverse_implied_unit_margin
collect_biological_cycle_evidence
```

Tests enforce:

- explicit `output × (price - full cost)` reconstruction;
- negative unit margin is preserved;
- no hidden spot price / historical mean / cycle haircut;
- hog/chicken/other biological segments stay separate;
- feed/slaughter/processing profit remains non-biological unless explicitly modeled otherwise;
- duplicate segment IDs fail closed;
- non-biological normalized profit is explicit even if zero;
- market-implied total profit can be translated back into unit margin;
- spot price and normalized price remain separate evidence;
- no arbitrary biological-cycle quality score.

Latest PR #25 head at this checkpoint:

```text
b5152b63b202c163a1ed0e551d253cc3bd2876b3
```

CI status at checkpoint:

```text
CI: pending
GenGe Cycle Bottom: queued
GenGe Opportunity Discovery: pending
GenGe Risk-Capped Opportunity Discovery: pending
```

---

# 10. Next queue

1. Continue into **auto / EV / battery** while PR #25 CI runs.
2. Explicitly separate OEM product-cycle economics from battery cell/GWh utilization economics; do not create one “新能源车” valuation model.
3. Suggested adversarial samples:
   - `002594 比亚迪` — vertically integrated EV OEM / battery / electronics, A/H scope;
   - `600104 上汽集团` — incumbent OEM transition / price-war / JV-to-NEV mix;
   - `300750 宁德时代` — battery/energy-storage manufacturer with utilization, raw-material and overseas/licensing economics, A/H scope if applicable.
4. Add code only where live samples expose a genuinely missing primitive; reuse existing cycle/segment/duration/EV modules when economically correct.
5. Re-check PR #25 CI; fix only reproducible failures.
6. Continue solar/wind/storage, energy/chemicals, software/platform, defense and remaining material archetypes before model freeze.
7. Broad point-in-time historical backtesting remains blocked until material archetypes are validated or explicitly fail-closed/out-of-scope.
