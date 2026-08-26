# V3.1 Round-7 untouched OOS - cross-industry replication

> Research-only falsification. Production V3.1 remains unchanged.

## Frozen contract

- The Round-6 economic formula and V3.1 execution thresholds are unchanged.
- The eight-stock cross-industry universe was frozen before this output.
- Strict PIT availability uses NOTICE_DATE and ignores mutable UPDATE_DATE.
- Buy-and-hold retains the original-capital observation so initial friction cannot cancel.

## Fresh OOS universe

|   code | name   |
|-------:|:-------|
| 601100 | 恒立液压   |
| 002747 | 埃斯顿    |
| 002050 | 三花智控   |
| 600845 | 宝信软件   |
| 002027 | 分众传媒   |
| 600489 | 中金黄金   |
| 600089 | 特变电工   |
| 600887 | 伊利股份   |

## Headline result

| variant             |   final_capital_rmb |   total_return |      cagr |   max_drawdown |   sharpe |   worst_calendar_year |   best_calendar_year |   trades |   total_turnover |   avg_cash_weight |
|:--------------------|--------------------:|---------------:|----------:|---------------:|---------:|----------------------:|---------------------:|---------:|-----------------:|------------------:|
| expectation_gap_10y |         2.72616e+06 |        1.72616 | 0.12303   |     -0.131615  | 1.13628  |           -0.0972698  |            0.365904  |      147 |          3.38694 |          0.583728 |
| round5_5y_15x       |         1.20462e+06 |        0.20462 | 0.0217719 |     -0.0938838 | 0.499663 |           -0.0399077  |            0.0827105 |       55 |          1.01818 |          0.846991 |
| universal_geomean   |         2.2115e+06  |        1.2115  | 0.0961721 |     -0.255114  | 0.736783 |           -0.00717585 |            0.365834  |      131 |          3.0657  |          0.502644 |
| true_buyhold        |         3.19905e+06 |        2.19905 | 0.144007  |     -0.449878  | 0.647175 |           -0.220879   |            1.22358   |      nan |        nan       |        nan        |

## Expectation diagnostics

|   code | name   |   ready_days |   median_realistic_growth |   median_implied_growth |   median_expectation_gap |   positive_gap_fraction |   min_price_to_neutral |   days_buy_staged_or_better |   latest_price |   latest_neutral_round6 |   latest_ratio_round6 |   latest_realistic_growth |   latest_implied_growth |   latest_expectation_gap | latest_implied_status      |   latest_cash_conversion |   latest_deduct_factor |
|-------:|:-------|-------------:|--------------------------:|------------------------:|-------------------------:|------------------------:|-----------------------:|----------------------------:|---------------:|------------------------:|----------------------:|--------------------------:|------------------------:|-------------------------:|:---------------------------|-------------------------:|-----------------------:|
| 601100 | 恒立液压   |         2097 |                 0.26623   |                0.259247 |              -0.0647014  |                0.344778 |               0.473071 |                         575 |         105.11 |               26.2344   |              4.00657  |                 0.0230285 |               0.383719  |              -0.36069    | SOLVED                     |                 0.823039 |               0.856129 |
| 002747 | 埃斯顿    |         1525 |                 0         |                0.714912 |              -0.681325   |                0        |               2.22088  |                           0 |          30.82 |                0.327582 |             94.0832   |                 0         |             nan         |             nan          | IMPLIED_ABOVE_SEARCH_RANGE |                 3.35916  |               0.476191 |
| 002050 | 三花智控   |         2097 |                 0.153387  |                0.281777 |              -0.127315   |                0.319504 |               0.3183   |                         497 |          35.71 |               25.4162   |              1.40501  |                 0.168709  |               0.257435  |              -0.0887264  | SOLVED                     |                 1.40173  |               1        |
| 600845 | 宝信软件   |         2096 |                 0.0385287 |                0.226778 |              -0.0986233  |                0.183683 |               0.613134 |                         181 |          17.15 |                5.43884  |              3.15325  |                 0         |               0.292057  |              -0.292057   | SOLVED                     |                 1.73066  |               0.936095 |
| 002027 | 分众传媒   |         2097 |                 0         |                0.111699 |              -0.0961186  |                0.12351  |               0.499658 |                         160 |           4.88 |                2.44545  |              1.99555  |                 0         |               0.171808  |              -0.171808   | SOLVED                     |                 2.42264  |               0.746525 |
| 600489 | 中金黄金   |         2086 |                 0.105819  |                0.188956 |              -0.0378991  |                0.325503 |               0.497334 |                         408 |          27.26 |               27.6452   |              0.986067 |                 0.201339  |               0.197697  |               0.00364194 | SOLVED                     |                 1.30134  |               1        |
| 600089 | 特变电工   |         2097 |                 0.0230361 |                0        |               0.00165454 |                0.543157 |               0.071421 |                        1218 |          19    |               11.147    |              1.7045   |                 0         |               0.131629  |              -0.131629   | SOLVED                     |                 2.05036  |               0.834195 |
| 600887 | 伊利股份   |         2097 |                 0.101884  |                0.138036 |              -0.0240449  |                0.318073 |               0.656597 |                         109 |          25.84 |               21.4483   |              1.20476  |                 0.0287807 |               0.0745214 |              -0.0457407  | SOLVED                     |                 1.41742  |               0.973699 |

## Anti-overfit contract

- No Round-7 result was available when the formula, parameters and universe were committed.
- No Round-1..6 valuation-OOS security appears in this universe.
- No result-driven economic parameter tuning is performed in this run.
- Any later formula change requires another untouched OOS universe.