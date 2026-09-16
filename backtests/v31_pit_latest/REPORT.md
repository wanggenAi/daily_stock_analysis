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
| V31_rare_earth     |         4.12813e+06 |       3.12813  | 0.178318  |      -0.506298 | 0.824579 |            -0.188351  |       65 |          0.524505 |
| BUYHOLD_rare_earth |         3.19975e+06 |       2.19975  | 0.144085  |      -0.691844 | 0.533159 |            -0.295246  |      nan |        nan        |
| V31_aerospace      |         1.8131e+06  |       0.813102 | 0.0712916 |      -0.23101  | 0.55952  |            -0.0757785 |       22 |          0.633912 |
| BUYHOLD_aerospace  |         2.34163e+06 |       1.34163  | 0.103482  |      -0.536173 | 0.457365 |            -0.346228  |      nan |        nan        |
| V31_combined       |         3.28318e+06 |       2.28318  | 0.147498  |      -0.340937 | 0.886101 |            -0.0757821 |       91 |          0.567257 |
| BUYHOLD_combined   |         3.50518e+06 |       2.50518  | 0.15622   |      -0.535614 | 0.596715 |            -0.240066  |      nan |        nan        |
| CSI300             |         1.11639e+06 |       0.116388 | 0.0128235 |      -0.456026 | 0.165344 |            -0.216328  |      nan |        nan        |

## Anti-cheating checks

- Rolling valuation anchors are shifted one trading day, so today's observation cannot set today's anchor.
- No future prices or future valuation observations are used.
- Rules and symbols are hard-coded in this script before execution.
- Missing valuation data yields HOLD_REVIEW rather than fabricated BUY/SELL.