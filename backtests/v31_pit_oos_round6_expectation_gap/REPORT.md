# V3.1 Round-6 untouched OOS — expectation gap / ten-year earning power

> Research-only falsification. Production V3.1 remains unchanged.

## Frozen model

- Strict PIT financial availability uses NOTICE_DATE; mutable UPDATE_DATE is ignored.
- Normalized EPS uses deduct-profit quality but does not mechanically multiply by current TTM cash conversion.
- Realistic growth = min(~3y normalized-EPS CAGR, ~3y revenue CAGR + 5pp), clipped to 0..30%.
- Ten-year earning-power value discounts at 10%, fades growth toward 3%, and uses Gordon-derived terminal multiple 1/(10%-3%).
- Market-implied starting growth is solved with the same equation over 0..100%.
- Existing V3.1 BUY/SELL bands, month-end cadence, 0.10% friction and cost-basis-independent SELL are unchanged.

## Fresh OOS universe

|   code | name   |
|-------:|:-------|
| 002179 | 中航光电   |
| 002138 | 顺络电子   |
| 002241 | 歌尔股份   |
| 002815 | 崇达技术   |
| 603019 | 中科曙光   |
| 600570 | 恒生电子   |

## Headline six-stock result

| variant             |   final_capital_rmb |      cagr |   max_drawdown |   sharpe |   trades |   avg_cash_weight |
|:--------------------|--------------------:|----------:|---------------:|---------:|---------:|------------------:|
| expectation_gap_10y |         1.20317e+06 | 0.0216363 |     -0.200276  | 0.317208 |       90 |          0.802076 |
| round5_5y_15x       |         1.19081e+06 | 0.0204168 |     -0.0947097 | 0.436737 |       51 |          0.906151 |
| universal_geomean   |         2.00708e+06 | 0.0839678 |     -0.430051  | 0.489702 |       78 |          0.393501 |
| true_buyhold        |         2.21417e+06 | 0.0963568 |     -0.495995  | 0.457517 |      nan |        nan        |

## Expectation-gap diagnostics

|   code | name   |   ready_days |   median_realistic_growth |   median_implied_growth |   median_expectation_gap |   positive_gap_fraction |   min_price_to_neutral |   days_buy_staged_or_better |   latest_price |   latest_neutral_round6 |   latest_ratio_round6 |   latest_realistic_growth |   latest_implied_growth |   latest_expectation_gap | latest_implied_status   |   latest_cash_conversion |   latest_deduct_factor |
|-------:|:-------|-------------:|--------------------------:|------------------------:|-------------------------:|------------------------:|-----------------------:|----------------------------:|---------------:|------------------------:|----------------------:|--------------------------:|------------------------:|-------------------------:|:------------------------|-------------------------:|-----------------------:|
| 002179 | 中航光电   |         2097 |                 0.0665849 |                0.17531  |                -0.119322 |                0.140677 |               0.5195   |                         286 |          33.01 |                14.2548  |               2.31572 |                 0         |                0.210307 |               -0.210307  | SOLVED                  |                 0.32623  |               0.968014 |
| 002138 | 顺络电子   |         2097 |                 0.06789   |                0.288033 |                -0.200593 |                0.103004 |               0.604999 |                         119 |          47.66 |                38.8818  |               1.22577 |                 0.235022  |                0.289158 |               -0.0541358 | SOLVED                  |                 1.55577  |               0.966653 |
| 002241 | 歌尔股份   |         2097 |                 0         |                0.309334 |                -0.254083 |                0.164521 |               0.303277 |                         393 |          23.48 |                 6.35793 |               3.69303 |                 0.0262236 |                0.364728 |               -0.338505  | SOLVED                  |                 1.1865   |               0.39155  |
| 002815 | 崇达技术   |         2097 |                 0         |                0.127337 |                -0.127337 |                0.220792 |               0.511756 |                         289 |          13.36 |                 3.23856 |               4.12529 |                 0         |                0.365396 |               -0.365396  | SOLVED                  |                 1.22371  |               1        |
| 603019 | 中科曙光   |         2084 |                 0.090245  |                0.457257 |                -0.380996 |                0        |               1.27952  |                           0 |          82.18 |                24.0324  |               3.41955 |                 0.108726  |                0.436907 |               -0.328181  | SOLVED                  |                 0.469142 |               0.854395 |
| 600570 | 恒生电子   |         2097 |                 0         |                0.415294 |                -0.369847 |                0        |               1.23746  |                           0 |          21.14 |                 6.42608 |               3.28972 |                 0         |                0.303483 |               -0.303483  | SOLVED                  |                 0.720106 |               0.803727 |

## Individual strategy diagnostics

| group         | variant             |   final_capital_rmb |         cagr |   max_drawdown |      sharpe |   trades |   avg_cash_weight |
|:--------------|:--------------------|--------------------:|-------------:|---------------:|------------:|---------:|------------------:|
| single_002179 | expectation_gap_10y |         1.52484e+06 |  0.0500377   |      -0.279345 |   0.402994  |       12 |          0.663697 |
| single_002179 | round5_5y_15x       |         1e+06       |  0           |       0        | nan         |        0 |          1        |
| single_002179 | universal_geomean   |         1.98269e+06 |  0.082435    |      -0.366316 |   0.460828  |       11 |          0.377858 |
| single_002179 | true_buyhold        |         2.05798e+06 |  0.0871142   |      -0.458961 |   0.420591  |      nan |        nan        |
| single_002138 | expectation_gap_10y |         1.25046e+06 |  0.0262052   |      -0.269936 |   0.276047  |       18 |          0.817603 |
| single_002138 | round5_5y_15x       |         1e+06       |  0           |       0        | nan         |        0 |          1        |
| single_002138 | universal_geomean   |         3.12903e+06 |  0.141129    |      -0.378414 |   0.649704  |       10 |          0.408677 |
| single_002138 | true_buyhold        |         3.2181e+06  |  0.144842    |      -0.549145 |   0.541066  |      nan |        nan        |
| single_002241 | expectation_gap_10y |         1.00713e+06 |  0.000822785 |      -0.640454 |   0.116607  |       30 |          0.66722  |
| single_002241 | round5_5y_15x       |         1.67806e+06 |  0.061738    |      -0.357982 |   0.460829  |       33 |          0.735266 |
| single_002241 | universal_geomean   |         1.6239e+06  |  0.0577148   |      -0.682625 |   0.343105  |       25 |          0.483808 |
| single_002241 | true_buyhold        |         1.48326e+06 |  0.0466833   |      -0.757275 |   0.349183  |      nan |        nan        |
| single_002815 | expectation_gap_10y |         1.22547e+06 |  0.0238105   |      -0.385326 |   0.222947  |       22 |          0.685186 |
| single_002815 | round5_5y_15x       |         1.46808e+06 |  0.0454379   |      -0.293546 |   0.346952  |       17 |          0.708232 |
| single_002815 | universal_geomean   |         1.07562e+06 |  0.00847256  |      -0.665469 |   0.193031  |       10 |          0.304402 |
| single_002815 | true_buyhold        |         1.00527e+06 |  0.000608159 |      -0.708997 |   0.226995  |      nan |        nan        |
| single_603019 | expectation_gap_10y |         1e+06       |  0           |       0        | nan         |        0 |          1        |
| single_603019 | round5_5y_15x       |         1e+06       |  0           |       0        | nan         |        0 |          1        |
| single_603019 | universal_geomean   |         3.56546e+06 |  0.158504    |      -0.572696 |   0.594095  |        6 |          0.326289 |
| single_603019 | true_buyhold        |         4.09875e+06 |  0.177344    |      -0.60625  |   0.590734  |      nan |        nan        |
| single_600570 | expectation_gap_10y |         1e+06       |  0           |       0        | nan         |        0 |          1        |
| single_600570 | round5_5y_15x       |         1e+06       |  0           |       0        | nan         |        0 |          1        |
| single_600570 | universal_geomean   |    601639           | -0.0571076   |      -0.730906 |  -0.0463684 |        4 |          0.455738 |
| single_600570 | true_buyhold        |         1.42165e+06 |  0.0415573   |      -0.765225 |   0.31438   |      nan |        nan        |

## Anti-overfit contract

- Formula and six-stock universe were committed before this first successful output.
- No Round-1..5 security appears in the Round-6 OOS universe.
- All six securities were listed before the 2018 test start so the literal buy-and-hold comparison window is aligned.
- No result-driven parameter tuning is performed in this run.
- Any formula change after this report requires another untouched OOS universe.