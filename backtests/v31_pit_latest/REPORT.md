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
| V31_rare_earth     |         4.22846e+06 |       3.22846  | 0.181597  |      -0.50824  | 0.827577 |            -0.18911   |       64 |          0.523806 |
| BUYHOLD_rare_earth |         3.23848e+06 |       2.23848  | 0.145679  |      -0.693745 | 0.535298 |            -0.297432  |      nan |        nan        |
| V31_aerospace      |         1.80576e+06 |       0.805756 | 0.0707884 |      -0.228703 | 0.561943 |            -0.0758143 |       22 |          0.634766 |
| BUYHOLD_aerospace  |         2.33782e+06 |       1.33782  | 0.103273  |      -0.536119 | 0.457225 |            -0.346266  |      nan |        nan        |
| V31_combined       |         3.33409e+06 |       2.33409  | 0.149543  |      -0.341986 | 0.889703 |            -0.0758594 |       91 |          0.567269 |
| BUYHOLD_combined   |         3.53752e+06 |       2.53752  | 0.157449  |      -0.536818 | 0.598084 |            -0.240981  |      nan |        nan        |
| CSI300             |         1.11639e+06 |       0.116388 | 0.0128235 |      -0.456026 | 0.165344 |            -0.216328  |      nan |        nan        |

## Anti-cheating checks

- Rolling valuation anchors are shifted one trading day, so today's observation cannot set today's anchor.
- No future prices or future valuation observations are used.
- Rules and symbols are hard-coded in this script before execution.
- Missing valuation data yields HOLD_REVIEW rather than fabricated BUY/SELL.