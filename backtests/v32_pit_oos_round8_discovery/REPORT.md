# GenGe V3.2 Round 8 Discovery

Frozen strict-PIT OOS production-candidate evaluation.

## Results

| label                      | start      | end        |   final_multiple |   final_capital_rmb |   total_return |      cagr |   max_drawdown |   sharpe |   worst_calendar_year |   best_calendar_year |   trades |   avg_cash_weight |   total_turnover |   low_invalid_decisions |   mechanical_low_invalid_actions | variant                    |
|:---------------------------|:-----------|:-----------|-----------------:|--------------------:|---------------:|----------:|---------------:|---------:|----------------------:|---------------------:|---------:|------------------:|-----------------:|------------------------:|---------------------------------:|:---------------------------|
| current_v31_baseline       | 2018-01-01 | 2026-08-24 |          2.3564  |         2.3564e+06  |       1.3564   | 0.10425   |      -0.239004 | 0.742182 |            -0.0887818 |             0.511608 |      102 |          0.435347 |          2.20165 |                     148 |                              115 | current_v31_baseline       |
| v31_1_confidence_gate_only | 2018-01-01 | 2026-08-24 |          2.21762 |         2.21762e+06 |       1.21762  | 0.0965222 |      -0.182464 | 0.780876 |            -0.066062  |             0.430251 |       93 |          0.479284 |          2.0759  |                     148 |                                0 | v31_1_confidence_gate_only |
| v32_candidate              | 2018-01-01 | 2026-08-24 |          2.18297 |         2.18297e+06 |       1.18297  | 0.0945266 |      -0.182149 | 0.755492 |            -0.066062  |             0.441348 |       94 |          0.468994 |          2.04503 |                     148 |                                0 | v32_candidate              |
| universal_geomean          | 2018-01-01 | 2026-08-24 |          1.90639 |         1.90639e+06 |       0.906395 | 0.077505  |      -0.292771 | 0.571573 |            -0.0721785 |             0.296714 |      112 |          0.422253 |          2.76454 |                     nan |                              nan | universal_geomean          |
| true_buyhold               | 2018-01-01 | 2026-08-24 |          2.07477 |         2.07477e+06 |       1.07477  | 0.0881078 |      -0.509226 | 0.476671 |            -0.26717   |             0.818854 |      nan |        nan        |        nan       |                     nan |                              nan | true_buyhold               |
| csi300                     | 2018-01-01 | 2026-08-24 |          1.11639 |         1.11639e+06 |       0.116388 | 0.0128194 |      -0.456026 | 0.165304 |            -0.263431  |             0.360695 |      nan |        nan        |        nan       |                     nan |                              nan | csi300                     |

## SELL opportunity cost

| variant                    |   months |   completed_sell_events |   completed_regime_entries | comparison_sample   |   comparison_count |   median_forward_return |   median_max_upside |
|:---------------------------|---------:|------------------------:|---------------------------:|:--------------------|-------------------:|------------------------:|--------------------:|
| current_v31_baseline       |       12 |                      25 |                          5 | regime_entries      |                  5 |               0.0897915 |            0.228764 |
| current_v31_baseline       |       24 |                      21 |                          5 | regime_entries      |                  5 |               0.376372  |            0.513447 |
| v31_1_confidence_gate_only |       12 |                      18 |                          5 | regime_entries      |                  5 |               0.077104  |            0.142446 |
| v31_1_confidence_gate_only |       24 |                      14 |                          4 | all_sell_events     |                 14 |              -0.102128  |            0.253114 |
| v32_candidate              |       12 |                      21 |                          5 | regime_entries      |                  5 |               0.137139  |            0.225569 |
| v32_candidate              |       24 |                      17 |                          4 | all_sell_events     |                 17 |              -0.118746  |            0.242806 |

## Integrity

- strict PIT: True
- future financial merges: 0
- full V3.2 frozen thresholds: True
