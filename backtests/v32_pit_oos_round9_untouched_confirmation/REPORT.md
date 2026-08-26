# GenGe V3.2 Round 9 Untouched Confirmation

Frozen strict-PIT OOS production-candidate evaluation.

## Results

| label                      | start      | end        |   final_multiple |   final_capital_rmb |   total_return |      cagr |   max_drawdown |   sharpe |   worst_calendar_year |   best_calendar_year |   trades |   avg_cash_weight |   total_turnover |   low_invalid_decisions |   mechanical_low_invalid_actions | variant                    |
|:---------------------------|:-----------|:-----------|-----------------:|--------------------:|---------------:|----------:|---------------:|---------:|----------------------:|---------------------:|---------:|------------------:|-----------------:|------------------------:|---------------------------------:|:---------------------------|
| current_v31_baseline       | 2018-01-01 | 2026-08-24 |         17.4878  |         1.74878e+07 |      16.4878   | 0.392447  |      -0.915305 | 0.840418 |             -0.863006 |             6.71527  |      101 |          0.384429 |          3.7345  |                     175 |                              138 | current_v31_baseline       |
| v31_1_confidence_gate_only | 2018-01-01 | 2026-08-24 |         15.9931  |         1.59931e+07 |      14.9931   | 0.378127  |      -0.268884 | 1.24306  |             -0.136453 |             3.36646  |      108 |          0.399633 |          3.7405  |                     175 |                                0 | v31_1_confidence_gate_only |
| v32_candidate              | 2018-01-01 | 2026-08-24 |         16.321   |         1.6321e+07  |      15.321    | 0.381367  |      -0.275081 | 1.23937  |             -0.136453 |             3.36646  |       96 |          0.38107  |          3.59808 |                     175 |                                0 | v32_candidate              |
| universal_geomean          | 2018-01-01 | 2026-08-24 |          2.17389 |         2.17389e+06 |       1.17389  | 0.0939986 |      -0.76818  | 0.450939 |             -0.18439  |             0.889758 |      121 |          0.532868 |          4.00711 |                     nan |                              nan | universal_geomean          |
| true_buyhold               | 2018-01-01 | 2026-08-24 |          6.57664 |         6.57664e+06 |       5.57664  | 0.243481  |      -0.931116 | 0.671299 |             -0.866974 |             8.77156  |      nan |        nan        |        nan       |                     nan |                              nan | true_buyhold               |
| csi300                     | 2018-01-01 | 2026-08-24 |          1.11639 |         1.11639e+06 |       0.116388 | 0.0128194 |      -0.456026 | 0.165304 |             -0.263431 |             0.360695 |      nan |        nan        |        nan       |                     nan |                              nan | csi300                     |

## SELL opportunity cost

| variant                    |   months |   completed_sell_events |   completed_regime_entries | comparison_sample   |   comparison_count |   median_forward_return |   median_max_upside |
|:---------------------------|---------:|------------------------:|---------------------------:|:--------------------|-------------------:|------------------------:|--------------------:|
| current_v31_baseline       |       12 |                      28 |                          7 | regime_entries      |                  7 |             -0.0781544  |           0.0988701 |
| current_v31_baseline       |       24 |                      24 |                          7 | regime_entries      |                  7 |             -0.0705993  |           0.408663  |
| v31_1_confidence_gate_only |       12 |                      32 |                          8 | regime_entries      |                  8 |              0.133073   |           0.751869  |
| v31_1_confidence_gate_only |       24 |                      25 |                          8 | regime_entries      |                  8 |              0.0322622  |           0.940899  |
| v32_candidate              |       12 |                      27 |                          7 | regime_entries      |                  7 |             -0.03906    |           0.281919  |
| v32_candidate              |       24 |                      19 |                          7 | regime_entries      |                  7 |              0.00222916 |           0.328252  |

## Integrity

- strict PIT: True
- future financial merges: 0
- full V3.2 frozen thresholds: False
