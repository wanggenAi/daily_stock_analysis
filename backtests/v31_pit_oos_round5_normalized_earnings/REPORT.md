# V3.1 Round-5 untouched OOS — normalized earnings neutral value

> Research-only falsification. Production V3.1 is unchanged.

## Frozen model

- Financials become usable only from NOTICE_DATE; UPDATE_DATE is ignored.
- Quality-adjusted TTM EPS is haircutted by the weaker of deduct-profit quality and operating-cash conversion, never boosted above reported EPS.
- Normalized earning power is the rolling median of the latest four positive quality-adjusted TTM EPS observations.
- Starting growth = 50% of historical ~3y normalized-owner-EPS CAGR, floored at 0 and capped at 15%.
- Five-year earnings-power value uses 10% discount rate, growth fade toward min(start growth,3%), and 15x terminal owner earnings.
- Existing V3.1 BUY/SELL bands, month-end cadence, 0.10% friction and cost-basis-independent SELL remain unchanged.

## Fresh OOS universe

|   code | name   |
|-------:|:-------|
| 002371 | 北方华创   |
| 002475 | 立讯精密   |
| 002384 | 东山精密   |
| 600584 | 长电科技   |
| 603228 | 景旺电子   |
| 600703 | 三安光电   |

## Headline six-stock result

| variant             |   final_capital_rmb |      cagr |   max_drawdown |   sharpe |   trades |   avg_cash_weight |
|:--------------------|--------------------:|----------:|---------------:|---------:|---------:|------------------:|
| normalized_earnings |         1.53196e+06 | 0.0506038 |      -0.133302 | 0.809583 |       56 |          0.861569 |
| universal_geomean   |         3.45996e+06 | 0.154483  |      -0.407596 | 0.771636 |       96 |          0.4375   |
| true_buyhold        |         7.85001e+06 | 0.269302  |      -0.463875 | 0.851253 |      nan |        nan        |

## Individual diagnostics

| group         | variant             |   final_capital_rmb |       cagr |   max_drawdown |     sharpe |   trades |   avg_cash_weight |
|:--------------|:--------------------|--------------------:|-----------:|---------------:|-----------:|---------:|------------------:|
| single_002371 | normalized_earnings |         1e+06       |  0         |       0        | nan        |        0 |          1        |
| single_002371 | universal_geomean   |         3.0639e+06  |  0.138355  |      -0.38392  |   0.611983 |        9 |          0.529364 |
| single_002371 | true_buyhold        |         2.30211e+07 |  0.437612  |      -0.534618 |   0.973239 |      nan |        nan        |
| single_002475 | normalized_earnings |         1e+06       |  0         |       0        | nan        |        0 |          1        |
| single_002475 | universal_geomean   |         3.97276e+06 |  0.173098  |      -0.381286 |   0.673745 |       13 |          0.37552  |
| single_002475 | true_buyhold        |         5.30306e+06 |  0.212972  |      -0.592709 |   0.661542 |      nan |        nan        |
| single_002384 | normalized_earnings |         2.64719e+06 |  0.119257  |      -0.340019 |   0.815662 |       19 |          0.84513  |
| single_002384 | universal_geomean   |         4.67256e+06 |  0.195333  |      -0.635547 |   0.720566 |       19 |          0.422026 |
| single_002384 | true_buyhold        |         1.0944e+07  |  0.319064  |      -0.670247 |   0.804134 |      nan |        nan        |
| single_600584 | normalized_earnings |         1.57113e+06 |  0.053678  |      -0.288666 |   0.460658 |       14 |          0.805996 |
| single_600584 | universal_geomean   |         5.17576e+06 |  0.209566  |      -0.498738 |   0.752886 |       19 |          0.387321 |
| single_600584 | true_buyhold        |         3.48607e+06 |  0.155488  |      -0.683783 |   0.548704 |      nan |        nan        |
| single_603228 | normalized_earnings |         1.75145e+06 |  0.0670112 |      -0.224006 |   0.50577  |       16 |          0.701468 |
| single_603228 | universal_geomean   |         2.37627e+06 |  0.105359  |      -0.487546 |   0.49677  |       16 |          0.410665 |
| single_603228 | true_buyhold        |         3.81833e+06 |  0.167727  |      -0.580476 |   0.575874 |      nan |        nan        |
| single_600703 | normalized_earnings |         1.41498e+06 |  0.0409898 |      -0.291447 |   0.385879 |       14 |          0.832121 |
| single_600703 | universal_geomean   |         1.40781e+06 |  0.0403787 |      -0.610092 |   0.285842 |       24 |          0.434868 |
| single_600703 | true_buyhold        |    527437           | -0.0713625 |      -0.78712  |   0.093629 |      nan |        nan        |

## Anti-overfit contract

- Formula and six-stock universe were committed before this output existed.
- No Round-1..4 security appears in the Round-5 OOS universe.
- No result-driven parameter tuning is performed in this run.
- Any formula change after this report requires another untouched OOS universe.