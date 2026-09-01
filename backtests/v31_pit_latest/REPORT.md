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
| V31_rare_earth     |         4.2537e+06  |       3.2537   | 0.182411  |      -0.5131   | 0.829892 |            -0.191831  |       65 |          0.52455  |
| BUYHOLD_rare_earth |         3.22954e+06 |       2.22954  | 0.145312  |      -0.697831 | 0.534174 |            -0.297893  |      nan |        nan        |
| V31_aerospace      |         1.8149e+06  |       0.814899 | 0.0714144 |      -0.231149 | 0.559835 |            -0.0757868 |       22 |          0.63393  |
| BUYHOLD_aerospace  |         2.3432e+06  |       1.3432   | 0.103567  |      -0.536193 | 0.457298 |            -0.346262  |      nan |        nan        |
| V31_combined       |         3.35979e+06 |       2.35979  | 0.150565  |      -0.346144 | 0.891809 |            -0.0767614 |       91 |          0.567386 |
| BUYHOLD_combined   |         3.54318e+06 |       2.54318  | 0.157663  |      -0.540771 | 0.596973 |            -0.241784  |      nan |        nan        |
| CSI300             |         1.11639e+06 |       0.116389 | 0.0128236 |      -0.456026 | 0.165344 |            -0.216328  |      nan |        nan        |

## Anti-cheating checks

- Rolling valuation anchors are shifted one trading day, so today's observation cannot set today's anchor.
- No future prices or future valuation observations are used.
- Rules and symbols are hard-coded in this script before execution.
- Missing valuation data yields HOLD_REVIEW rather than fabricated BUY/SELL.