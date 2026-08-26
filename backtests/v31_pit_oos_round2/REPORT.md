# V3.1 PIT out-of-sample round 2 (locked rules)

> This tests the valuation/execution layer on a fixed pre-declared 10-stock out-of-sample research universe. It is not a retrospective reconstruction of qualitative moat gates.

## Locked assumptions

- Period: 2018-01-01 to 2026-08-24
- One-way friction: 0.10%
- Valuation anchor: 756 prior trading days, shifted by one day; minimum 252
- Rebalance: month-end
- Exit decisions use dynamic price/latest-neutral-value only; entry cost is ignored.

## Results

| label                       |   final_capital_rmb |   total_return |      cagr |   max_drawdown |   sharpe |   worst_calendar_year |   trades |   avg_cash_weight |
|:----------------------------|--------------------:|---------------:|----------:|---------------:|---------:|----------------------:|---------:|------------------:|
| V31_strategic_resources     |         5.53291e+06 |       4.53291  | 0.218943  |      -0.232557 | 1.06006  |             0.0511778 |       72 |          0.417055 |
| BUYHOLD_strategic_resources |         7.2928e+06  |       6.2928   | 0.258533  |      -0.430487 | 0.842614 |            -0.0335895 |      nan |        nan        |
| V31_grid_equipment          |         1.64392e+06 |       0.643917 | 0.0592151 |      -0.240295 | 0.470975 |            -0.0543525 |       16 |          0.658053 |
| BUYHOLD_grid_equipment      |         2.55008e+06 |       1.55008  | 0.114426  |      -0.468496 | 0.498664 |            -0.193852  |      nan |        nan        |
| V31_semiconductor           |         1.72661e+06 |       0.726609 | 0.0652485 |      -0.584819 | 0.399752 |            -0.491548  |       96 |          0.522865 |
| BUYHOLD_semiconductor       |         4.9328e+06  |       3.9328   | 0.202854  |      -0.707357 | 0.661866 |            -0.4983    |      nan |        nan        |
| V31_combined                |         2.96294e+06 |       1.96294  | 0.133949  |      -0.252984 | 0.946534 |            -0.170375  |      165 |          0.513719 |
| BUYHOLD_combined            |         6.07227e+06 |       5.07227  | 0.232136  |      -0.37847  | 0.903088 |            -0.227702  |      nan |        nan        |
| CSI300                      |         1.11639e+06 |       0.116388 | 0.0128235 |      -0.456026 | 0.165344 |            -0.216328  |      nan |        nan        |

## Anti-cheating checks

- Rolling valuation anchors are shifted one trading day, so today's observation cannot set today's anchor.
- No future prices or future valuation observations are used.
- Rules and symbols are hard-coded in this script before execution.
- Missing valuation data yields HOLD_REVIEW rather than fabricated BUY/SELL.