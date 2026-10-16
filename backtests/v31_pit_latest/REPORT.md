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
| V31_rare_earth     |         4.38918e+06 |       3.38918  | 0.186709  |      -0.515257 | 0.834726 |            -0.192747  |       65 |          0.523892 |
| BUYHOLD_rare_earth |         3.27956e+06 |       2.27956  | 0.147351  |      -0.700047 | 0.536991 |            -0.300195  |      nan |        nan        |
| V31_aerospace      |         1.8149e+06  |       0.814899 | 0.0714144 |      -0.231149 | 0.559835 |            -0.0757868 |       22 |          0.63393  |
| BUYHOLD_aerospace  |         2.3432e+06  |       1.3432   | 0.103567  |      -0.536193 | 0.457298 |            -0.346262  |      nan |        nan        |
| V31_combined       |         3.43603e+06 |       2.43603  | 0.153557  |      -0.347893 | 0.895943 |            -0.0768099 |       91 |          0.567103 |
| BUYHOLD_combined   |         3.59037e+06 |       2.59037  | 0.159437  |      -0.542569 | 0.598735 |            -0.24309   |      nan |        nan        |
| CSI300             |         1.11639e+06 |       0.116389 | 0.0128236 |      -0.456026 | 0.165344 |            -0.216328  |      nan |        nan        |

## Anti-cheating checks

- Rolling valuation anchors are shifted one trading day, so today's observation cannot set today's anchor.
- No future prices or future valuation observations are used.
- Rules and symbols are hard-coded in this script before execution.
- Missing valuation data yields HOLD_REVIEW rather than fabricated BUY/SELL.