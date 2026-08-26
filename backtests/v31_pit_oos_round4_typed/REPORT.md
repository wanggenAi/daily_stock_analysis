# V3.1 typed valuation — round-4 untouched OOS

> Research-only falsification test. Production V3.1 remains unchanged.

## Pre-declared economic router

- RESOURCE_ASSET: PB-relative historical proxy (future production target: NAV + normalized cycle earnings).
- STABLE_CASHFLOW: frozen PE/PB relative geometric mean.
- GROWTH_TECH_CONSENSUS: PE and PB must agree in direction before valuation changes position size.
- BUY/SELL thresholds, 756-day past-only anchor, month-end rebalance and 0.10% one-way friction are unchanged.
- Corrected execution never creates a sale in one holding merely to fund another holding's BUY request.

## Fresh locked universe

|   code | name   | valuation_type        |
|-------:|:-------|:----------------------|
| 600362 | 江西铜业   | RESOURCE_ASSET        |
| 000807 | 云铝股份   | RESOURCE_ASSET        |
| 600547 | 山东黄金   | RESOURCE_ASSET        |
| 600988 | 赤峰黄金   | RESOURCE_ASSET        |
| 600900 | 长江电力   | STABLE_CASHFLOW       |
| 600886 | 国投电力   | STABLE_CASHFLOW       |
| 600025 | 华能水电   | STABLE_CASHFLOW       |
| 000333 | 美的集团   | STABLE_CASHFLOW       |
| 600183 | 生益科技   | GROWTH_TECH_CONSENSUS |
| 002463 | 沪电股份   | GROWTH_TECH_CONSENSUS |
| 002916 | 深南电路   | GROWTH_TECH_CONSENSUS |
| 603160 | 汇顶科技   | GROWTH_TECH_CONSENSUS |

## Results

| group           | variant           |   final_capital_rmb |      cagr |   max_drawdown |   sharpe |   trades |   avg_cash_weight |
|:----------------|:------------------|--------------------:|----------:|---------------:|---------:|---------:|------------------:|
| resource_asset  | typed_router      |         4.19377e+06 | 0.180471  |      -0.230779 | 1.06463  |       42 |          0.582569 |
| resource_asset  | universal_geomean |         4.2762e+06  | 0.183133  |      -0.316202 | 0.87709  |       46 |          0.480591 |
| resource_asset  | true_buyhold      |         3.9499e+06  | 0.172314  |      -0.465155 | 0.630745 |      nan |        nan        |
| stable_cashflow | typed_router      |         2.20887e+06 | 0.096053  |      -0.118547 | 1.01839  |       27 |          0.626374 |
| stable_cashflow | universal_geomean |         2.20887e+06 | 0.096053  |      -0.118547 | 1.01839  |       27 |          0.626374 |
| stable_cashflow | true_buyhold      |         2.38799e+06 | 0.105988  |      -0.260874 | 0.65708  |      nan |        nan        |
| growth_tech     | typed_router      |         2.10761e+06 | 0.0901166 |      -0.475738 | 0.487594 |       51 |          0.545681 |
| growth_tech     | universal_geomean |         2.13169e+06 | 0.0915504 |      -0.475303 | 0.502202 |       73 |          0.523694 |
| growth_tech     | true_buyhold      |         1.75763e+07 | 0.3937    |      -0.705169 | 0.92693  |      nan |        nan        |
| combined        | typed_router      |         2.88892e+06 | 0.130633  |      -0.231234 | 1.05605  |      129 |          0.575907 |
| combined        | universal_geomean |         2.84509e+06 | 0.128635  |      -0.278171 | 0.963823 |      163 |          0.537933 |
| combined        | true_buyhold      |         7.96206e+06 | 0.27158   |      -0.387173 | 0.949229 |      nan |        nan        |
| benchmark       | csi300            |         1.11639e+06 | 0.0128235 |      -0.456026 | 0.165344 |      nan |        nan        |

## Typed vs universal vs literal buy-and-hold

| group           |   typed_cagr |   universal_cagr |   true_buyhold_cagr |   typed_minus_universal_cagr_pp |   typed_minus_buyhold_cagr_pp |   typed_max_drawdown |   universal_max_drawdown |   true_buyhold_max_drawdown |   typed_sharpe |   universal_sharpe |   true_buyhold_sharpe |   typed_avg_cash |   universal_avg_cash |
|:----------------|-------------:|-----------------:|--------------------:|--------------------------------:|------------------------------:|---------------------:|-------------------------:|----------------------------:|---------------:|-------------------:|----------------------:|-----------------:|---------------------:|
| resource_asset  |    0.180471  |        0.183133  |            0.172314 |                     -0.00266219 |                    0.00815655 |            -0.230779 |                -0.316202 |                   -0.465155 |       1.06463  |           0.87709  |              0.630745 |         0.582569 |             0.480591 |
| stable_cashflow |    0.096053  |        0.096053  |            0.105988 |                      0          |                   -0.00993507 |            -0.118547 |                -0.118547 |                   -0.260874 |       1.01839  |           1.01839  |              0.65708  |         0.626374 |             0.626374 |
| growth_tech     |    0.0901166 |        0.0915504 |            0.3937   |                     -0.00143383 |                   -0.303583   |            -0.475738 |                -0.475303 |                   -0.705169 |       0.487594 |           0.502202 |              0.92693  |         0.545681 |             0.523694 |
| combined        |    0.130633  |        0.128635  |            0.27158  |                      0.00199832 |                   -0.140946   |            -0.231234 |                -0.278171 |                   -0.387173 |       1.05605  |           0.963823 |              0.949229 |         0.575907 |             0.537933 |

## Anti-overfit checks

- Router rules were committed in docs/V31_TYPED_VALUATION_DRAFT.md before this OOS run.
- No security from rounds 1 or 2 appears in this 12-stock universe.
- No threshold is tuned from round-4 output.
- Rolling anchors are shifted one trading day and use only past observations.
- True buy-and-hold is initial equal-dollar and zero-rebalance, not the old daily equal-weight benchmark.
- Missing/invalid growth-tech valuation components produce HOLD_REVIEW rather than a fabricated target.

## Interpretation rule

A typed-router win is not sufficient to promote it to production. A loss is evidence against the draft. Any post-result rule change requires a new untouched universe.