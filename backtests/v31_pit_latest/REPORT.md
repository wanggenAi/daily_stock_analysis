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
| V31_aerospace      |         1.80396e+06 |       0.803963 | 0.0706653 |      -0.22856  | 0.561631 |            -0.0758061 |       22 |          0.634747 |
| BUYHOLD_aerospace  |         2.33607e+06 |       1.33607  | 0.103178  |      -0.536099 | 0.45728  |            -0.346232  |      nan |        nan        |
| V31_combined       |         3.42635e+06 |       2.42635  | 0.15318   |      -0.34776  | 0.896744 |            -0.0771191 |       91 |          0.56749  |
| BUYHOLD_combined   |         3.58077e+06 |       2.58077  | 0.159078  |      -0.542074 | 0.598881 |            -0.242164  |      nan |        nan        |
| CSI300             |         1.11639e+06 |       0.116388 | 0.0128235 |      -0.456026 | 0.165344 |            -0.216328  |      nan |        nan        |

## Anti-cheating checks

- Rolling valuation anchors are shifted one trading day, so today's observation cannot set today's anchor.
- No future prices or future valuation observations are used.
- Rules and symbols are hard-coded in this script before execution.
- Missing valuation data yields HOLD_REVIEW rather than fabricated BUY/SELL.