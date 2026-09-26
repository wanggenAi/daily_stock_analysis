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
| V31_aerospace      |         1.80576e+06 |       0.805756 | 0.0707884 |      -0.228703 | 0.561943 |            -0.0758143 |       22 |          0.634766 |
| BUYHOLD_aerospace  |         2.33782e+06 |       1.33782  | 0.103273  |      -0.536119 | 0.457225 |            -0.346266  |      nan |        nan        |
| V31_combined       |         3.42786e+06 |       2.42786  | 0.153239  |      -0.347563 | 0.89686  |            -0.0769537 |       91 |          0.567477 |
| BUYHOLD_combined   |         3.58367e+06 |       2.58367  | 0.159187  |      -0.542153 | 0.59885  |            -0.24245   |      nan |        nan        |
| CSI300             |         1.11639e+06 |       0.116388 | 0.0128235 |      -0.456026 | 0.165344 |            -0.216328  |      nan |        nan        |

## Anti-cheating checks

- Rolling valuation anchors are shifted one trading day, so today's observation cannot set today's anchor.
- No future prices or future valuation observations are used.
- Rules and symbols are hard-coded in this script before execution.
- Missing valuation data yields HOLD_REVIEW rather than fabricated BUY/SELL.