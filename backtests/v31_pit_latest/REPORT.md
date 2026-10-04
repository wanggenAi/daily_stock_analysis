# V3.1 PIT sector backtest (locked rules)

> This tests the valuation/execution layer on a fixed five-stock research universe. It is not a retrospective reconstruction of qualitative moat gates.

## Locked assumptions

- Period: 2018-01-01 to 2026-08-24
- One-way friction: 0.10%
- Valuation anchor: 756 prior trading days, shifted by one day; minimum 252
- Rebalance: month-end
- Exit decisions use dynamic price/latest-neutral-value only; entry cost is ignored.

## Results

| label              |   final_capital_rmb |   total_return |      cagr |   max_drawdown |   sharpe |   worst_calendar_year |   trades |   avg_cash_weight |
|:-------------------|--------------------:|---------------:|----------:|---------------:|---------:|----------------------:|---------:|------------------:|
| V31_rare_earth     |         4.26143e+06 |       3.26143  | 0.182659  |      -0.508482 | 0.82967  |            -0.189269  |       65 |          0.523849 |
| BUYHOLD_rare_earth |         3.25148e+06 |       2.25148  | 0.14621   |      -0.694093 | 0.536099 |            -0.297542  |      nan |        nan        |
| V31_aerospace      |         1.80396e+06 |       0.803963 | 0.0706653 |      -0.22856  | 0.561631 |            -0.0758061 |       22 |          0.634747 |
| BUYHOLD_aerospace  |         2.33607e+06 |       1.33607  | 0.103178  |      -0.536099 | 0.45728  |            -0.346232  |      nan |        nan        |
| V31_combined       |         3.35046e+06 |       2.35046  | 0.150195  |      -0.342375 | 0.891404 |            -0.075948  |       90 |          0.567355 |
| BUYHOLD_combined   |         3.54595e+06 |       2.54595  | 0.157768  |      -0.537009 | 0.598664 |            -0.240731  |      nan |        nan        |
| CSI300             |         1.11639e+06 |       0.116388 | 0.0128235 |      -0.456026 | 0.165344 |            -0.216328  |      nan |        nan        |

## Anti-cheating checks

- Rolling valuation anchors are shifted one trading day, so today's observation cannot set today's anchor.
- No future prices or future valuation observations are used.
- Rules and symbols are hard-coded in this script before execution.
- Missing valuation data yields HOLD_REVIEW rather than fabricated BUY/SELL.