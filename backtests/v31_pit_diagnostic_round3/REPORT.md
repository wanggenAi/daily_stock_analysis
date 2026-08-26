# V3.1 PIT round-3 diagnosis — implementation audit + attribution

> Production V3.1 rules are unchanged. This run diagnoses the backtest and the valuation/execution layer; it does not optimize thresholds.

## 1. Exact reproduction of the persisted V3.1 strategy

| group               |   stored_final_multiple |   reproduced_final_multiple |   relative_error |
|:--------------------|------------------------:|----------------------------:|-----------------:|
| strategic_resources |                 5.53291 |                     5.53291 |      5.4579e-15  |
| grid_equipment      |                 1.64392 |                     1.64392 |      8.10423e-16 |
| semiconductor       |                 1.72661 |                     1.72661 |      3.98665e-15 |
| combined            |                 2.96294 |                     2.96294 |      6.59477e-15 |

## 2. Important benchmark audit

The previous function named `run_buy_hold` used a fixed equal-weight return vector every day. That is a **daily equal-weight rebalanced portfolio**, not literal buy-and-hold. Round 3 therefore reports both the legacy benchmark and a true initial-equal-dollar / zero-rebalance buy-and-hold benchmark.

## 3. Cross-normalization audit

| group               |   trade_rows |   direction_mismatch_rows |   mismatch_turnover |   mismatch_share_of_turnover |
|:--------------------|-------------:|--------------------------:|--------------------:|-----------------------------:|
| strategic_resources |           72 |                        12 |           0.0192731 |                   0.00584141 |
| grid_equipment      |           16 |                         0 |           0         |                   0          |
| semiconductor       |           96 |                        23 |           0.145024  |                   0.029589   |
| combined            |          165 |                         0 |           0         |                   0          |

A direction mismatch is a recorded trade whose weight change contradicts its V3.1 action label (for example BUY with a negative delta, or HOLD with a non-zero delta). These can be created by the old all-target normalization step rather than by a stock-level V3.1 signal.

## 4. All diagnostic variants

| group               | variant                              |   final_multiple |      cagr |   max_drawdown |   sharpe |   trades |   avg_cash_weight |
|:--------------------|:-------------------------------------|-----------------:|----------:|---------------:|---------:|---------:|------------------:|
| strategic_resources | legacy_engine_geomean_756            |          5.53291 | 0.218943  |      -0.232557 | 1.06006  |       72 |          0.417055 |
| strategic_resources | corrected_engine_geomean_756         |          5.50439 | 0.218214  |      -0.232557 | 1.05807  |       56 |          0.416712 |
| strategic_resources | corrected_same_buy_no_valuation_sell |          7.5619  | 0.263821  |      -0.371152 | 0.93716  |        9 |          0.233081 |
| strategic_resources | corrected_pb_only_756                |          5.80772 | 0.225801  |      -0.238195 | 1.1477   |       59 |          0.471199 |
| strategic_resources | corrected_pe_only_756                |          4.32873 | 0.184806  |      -0.344522 | 0.887494 |       73 |          0.411839 |
| strategic_resources | corrected_geomean_504                |          4.58957 | 0.192857  |      -0.246079 | 0.962032 |       61 |          0.419002 |
| strategic_resources | corrected_geomean_1260               |          6.11639 | 0.233169  |      -0.262774 | 1.06914  |       60 |          0.382648 |
| strategic_resources | true_buyhold                         |          6.36325 | 0.238745  |      -0.447831 | 0.796674 |      nan |          0        |
| strategic_resources | legacy_daily_equal_weight_benchmark  |          7.28551 | 0.258295  |      -0.430487 | 0.842078 |      nan |          0        |
| grid_equipment      | legacy_engine_geomean_756            |          1.64392 | 0.0592151 |      -0.240295 | 0.470975 |       16 |          0.658053 |
| grid_equipment      | corrected_engine_geomean_756         |          1.64392 | 0.0592151 |      -0.240295 | 0.470975 |       16 |          0.658053 |
| grid_equipment      | corrected_same_buy_no_valuation_sell |          1.56595 | 0.0532754 |      -0.292179 | 0.391711 |       10 |          0.597512 |
| grid_equipment      | corrected_pb_only_756                |          1.69908 | 0.0632688 |      -0.182254 | 0.615765 |       27 |          0.717074 |
| grid_equipment      | corrected_pe_only_756                |          1.82233 | 0.0719211 |      -0.311738 | 0.476745 |       21 |          0.572915 |
| grid_equipment      | corrected_geomean_504                |          1.82069 | 0.0718094 |      -0.241346 | 0.531269 |       17 |          0.643679 |
| grid_equipment      | corrected_geomean_1260               |          1.45935 | 0.0447165 |      -0.229445 | 0.443523 |       15 |          0.741416 |
| grid_equipment      | true_buyhold                         |          2.19585 | 0.0952717 |      -0.476041 | 0.447465 |      nan |          0        |
| grid_equipment      | legacy_daily_equal_weight_benchmark  |          2.54753 | 0.114259  |      -0.468496 | 0.498193 |      nan |          0        |
| semiconductor       | legacy_engine_geomean_756            |          1.72661 | 0.0652485 |      -0.584819 | 0.399752 |       96 |          0.522865 |
| semiconductor       | corrected_engine_geomean_756         |          1.71118 | 0.0641424 |      -0.581451 | 0.39446  |       58 |          0.523309 |
| semiconductor       | corrected_same_buy_no_valuation_sell |          2.73694 | 0.123584  |      -0.710538 | 0.512296 |        5 |          0.245234 |
| semiconductor       | corrected_pb_only_756                |          3.67462 | 0.162554  |      -0.578563 | 0.691375 |       60 |          0.366702 |
| semiconductor       | corrected_pe_only_756                |          1.24449 | 0.025637  |      -0.59184  | 0.22884  |       51 |          0.573464 |
| semiconductor       | corrected_geomean_504                |          2.42243 | 0.107823  |      -0.567934 | 0.551332 |       54 |          0.481286 |
| semiconductor       | corrected_geomean_1260               |          2.18017 | 0.0943952 |      -0.636951 | 0.47632  |       62 |          0.385275 |
| semiconductor       | true_buyhold                         |          4.00964 | 0.174293  |      -0.705134 | 0.597369 |      nan |          0        |
| semiconductor       | legacy_daily_equal_weight_benchmark  |          4.92786 | 0.202645  |      -0.707357 | 0.661426 |      nan |          0        |
| combined            | legacy_engine_geomean_756            |          2.96294 | 0.133949  |      -0.252984 | 0.946534 |      165 |          0.513719 |
| combined            | corrected_engine_geomean_756         |          2.96294 | 0.133949  |      -0.252984 | 0.946534 |      165 |          0.513719 |
| combined            | corrected_same_buy_no_valuation_sell |          4.29595 | 0.183764  |      -0.353093 | 0.829181 |       45 |          0.290269 |
| combined            | corrected_pb_only_756                |          3.96157 | 0.172714  |      -0.223073 | 1.14081  |      167 |          0.502547 |
| combined            | corrected_pe_only_756                |          2.64797 | 0.119295  |      -0.328084 | 0.783954 |      170 |          0.48412  |
| combined            | corrected_geomean_504                |          3.1863  | 0.143527  |      -0.269998 | 0.962777 |      165 |          0.488271 |
| combined            | corrected_geomean_1260               |          3.3911  | 0.151801  |      -0.248913 | 0.976476 |      169 |          0.473925 |
| combined            | true_buyhold                         |          4.40695 | 0.1872    |      -0.446275 | 0.732904 |      nan |          0        |
| combined            | legacy_daily_equal_weight_benchmark  |          6.0662  | 0.231912  |      -0.37847  | 0.902448 |      nan |          0        |

## 5. Approximate return-drag attribution using the corrected execution engine

| group               |   engine_artifact_cagr_pp |   baseline_cagr_corrected_engine |   no_sell_cagr |   true_buyhold_cagr |   legacy_benchmark_cagr |   benchmark_definition_gap_cagr_pp |   sell_drag_cagr_pp |   entry_underexposure_gap_cagr_pp |   baseline_max_drawdown |   no_sell_max_drawdown |   true_buyhold_max_drawdown |   baseline_avg_cash |   no_sell_avg_cash |
|:--------------------|--------------------------:|---------------------------------:|---------------:|--------------------:|------------------------:|-----------------------------------:|--------------------:|----------------------------------:|------------------------:|-----------------------:|----------------------------:|--------------------:|-------------------:|
| strategic_resources |              -0.000728827 |                        0.218214  |      0.263821  |           0.238745  |                0.258295 |                         -0.0195503 |          0.0456068  |                       -0.0250763  |               -0.232557 |              -0.371152 |                   -0.447831 |            0.416712 |           0.233081 |
| grid_equipment      |               0           |                        0.0592151 |      0.0532754 |           0.0952717 |                0.114259 |                         -0.018987  |         -0.00593979 |                        0.0419963  |               -0.240295 |              -0.292179 |                   -0.476041 |            0.658053 |           0.597512 |
| semiconductor       |              -0.00110613  |                        0.0641424 |      0.123584  |           0.174293  |                0.202645 |                         -0.0283517 |          0.0594415  |                        0.050709   |               -0.581451 |              -0.710538 |                   -0.705134 |            0.523309 |           0.245234 |
| combined            |               0           |                        0.133949  |      0.183764  |           0.1872    |                0.231912 |                         -0.0447127 |          0.0498155  |                        0.00343532 |               -0.252984 |              -0.353093 |                   -0.446275 |            0.513719 |           0.290269 |

`sell_drag_cagr_pp = no-sell CAGR - corrected-baseline CAGR`. `entry_underexposure_gap_cagr_pp = true-buyhold CAGR - no-sell CAGR`. The latter remains an approximate path-dependent diagnostic.

## 6. What happened after genuine corrected-engine SELL / BUY events

| group               |   sell_events |   sell_median_12m_return |   sell_share_12m_return_gt20 |   sell_median_12m_max_gain |   sell_median_24m_max_gain |   buy_events |   buy_median_12m_return |   buy_median_12m_max_drawdown |   buy_share_12m_drawdown_le_minus30 |
|:--------------------|--------------:|-------------------------:|-----------------------------:|---------------------------:|---------------------------:|-------------:|------------------------:|------------------------------:|------------------------------------:|
| strategic_resources |            34 |                 0.159851 |                     0.176471 |                  0.451859  |                   1.00654  |           22 |                0.253731 |                    -0.12367   |                           0.0454545 |
| grid_equipment      |             4 |                -0.276842 |                     0        |                  0.0695322 |                   0.225032 |           12 |                0.119481 |                    -0.0225854 |                           0.0833333 |
| semiconductor       |            30 |                 0.154895 |                     0.4      |                  0.4771    |                   0.849262 |           28 |               -0.133161 |                    -0.266448  |                           0.357143  |
| combined            |            80 |                 0.103419 |                     0.25     |                  0.431639  |                   0.669613 |           85 |                0.148053 |                    -0.153957  |                           0.223529  |

Incomplete 12/24-month forward windows are excluded from corresponding forward statistics.

## 7. PE vs PB disagreement

| group               |   observations |   median_divergence_factor |   p90_divergence_factor |   share_over_2x |   share_over_3x |
|:--------------------|---------------:|---------------------------:|------------------------:|----------------:|----------------:|
| strategic_resources |            368 |                    1.30926 |                 2.10722 |        0.144022 |      0.00271739 |
| grid_equipment      |            276 |                    1.14251 |                 2.86109 |        0.166667 |      0.0942029  |
| semiconductor       |            250 |                    1.8396  |                 8.09017 |        0.436    |      0.256      |
| combined            |            894 |                    1.3432  |                 3.01836 |        0.232662 |      0.10179    |

A 2x divergence means the PE-relative and PB-relative components differ by a factor of two at the same month-end. Large disagreement warns that the geometric mean is combining economically inconsistent signals.

## 8. Proxy specification sensitivity

| group               |   cagr_min |   cagr_max |   cagr_range_pp |   variant_count |
|:--------------------|-----------:|-----------:|----------------:|----------------:|
| strategic_resources |  0.184806  |  0.233169  |       0.0483631 |               5 |
| grid_equipment      |  0.0447165 |  0.0719211 |       0.0272046 |               5 |
| semiconductor       |  0.025637  |  0.162554  |       0.136917  |               5 |
| combined            |  0.119295  |  0.172714  |       0.0534195 |               5 |

The CAGR range spans pre-declared PE-only, PB-only and 504/756/1260-day geometric-mean variants. A wide range is evidence of fragility, not a reason to select the best row.

## Mechanical diagnostic labels

- **strategic_resources**: valuation SELL has a noticeable return cost; entry underexposure is comparatively small; valuation proxy sensitivity is moderate/low.
- **grid_equipment**: valuation SELL is not the dominant return drag; entry underexposure remains meaningful; valuation proxy sensitivity is moderate/low.
- **semiconductor**: valuation SELL is materially costly; delayed/partial entry remains a major underexposure drag; valuation proxy is highly specification-sensitive.
- **combined**: valuation SELL has a noticeable return cost; entry underexposure is comparatively small; valuation proxy has meaningful specification sensitivity.

## Limits

- This is still an execution-layer test conditional on a fixed research universe; it is not a full PIT reconstruction of qualitative V3.1 hard gates.
- The current neutral-value proxy is historical relative PE/PB, not normalized-earnings DCF/NAV.
- No production BUY/SELL threshold is changed by this diagnosis.