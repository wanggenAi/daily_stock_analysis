# V3.1 Round-6 expectation-gap OOS postmortem

Status: **economic failure recorded; research only; production V3.1 unchanged**.

Round 6 completed successfully in GitHub Actions run `32927453557`. The frozen formula, universe and execution bands ran without an infrastructure failure. The negative result therefore counts as untouched OOS evidence and must not be repaired by tuning this universe.

## Decision

Round 6 is **not eligible for production promotion**.

It modestly improved capital use and return over the already-falsified Round-5 formula, but it did not solve the two declared growth-company problems:

1. strong companies can still remain permanently unowned;
2. valuation SELL signals still frequently precede large subsequent gains.

## Headline result

2018-01-02 to 2026-08-24, RMB 1,000,000 initial capital, month-end execution and the frozen 0.10% one-way friction:

| Variant | Final capital | CAGR | Max drawdown | Sharpe | Worst year | Best year | Trades | Average cash |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Expectation Gap 10Y | RMB 1.203m | 2.16% | -20.03% | 0.317 | -12.92% | 21.59% | 90 | 80.21% |
| Round-5 5Y/15x | RMB 1.191m | 2.04% | -9.47% | 0.437 | -6.17% | 15.11% | 51 | 90.62% |
| Universal PE/PB | RMB 2.007m | 8.40% | -43.01% | 0.490 | -23.48% | 28.67% | 78 | 39.35% |
| True buy-and-hold | RMB 2.214m | 9.64% | -49.60% | 0.458 | -33.41% | 68.49% | n/a | n/a |
| CSI 300 | RMB 1.116m | 1.28% | -45.60% | 0.165 | -26.34% | 36.07% | n/a | n/a |

Relative to Round 5, Round 6 added only RMB 12,354 of ending capital and 0.12 percentage points of CAGR. Average cash fell by 10.41 percentage points, but remained 80.21%. The price paid for that small deployment improvement was 10.56 percentage points of additional drawdown and a lower Sharpe ratio.

Relative to Universal PE/PB, Round 6 lagged by RMB 803,911 and 6.23 percentage points of CAGR. It reduced maximum drawdown by 22.98 percentage points, but much of that protection came from holding 40.86 percentage points more cash.

Relative to true buy-and-hold, Round 6 lagged by RMB 1.011m and 7.47 percentage points of CAGR while reducing maximum drawdown by 29.57 percentage points.

## Stock-level outcome

| Code | Company | Round-6 final capital | Assessment |
|---|---|---:|---|
| 002179 | 中航光电 | RMB 1.525m | Partial success versus Round 5, but still lagged Universal and buy-and-hold. |
| 002138 | 顺络电子 | RMB 1.250m | Partial success versus Round 5, but capital use stayed low and returns lagged both comparators. |
| 002241 | 歌尔股份 | RMB 1.007m | Failure: near-zero return, -64.05% drawdown and materially worse than every comparator. |
| 002815 | 崇达技术 | RMB 1.225m | Best relative case: beat Universal and buy-and-hold with lower drawdown, but lagged Round 5. |
| 603019 | 中科曙光 | RMB 1.000m | Clear failure: zero trades and 100% cash. |
| 600570 | 恒生电子 | RMB 1.000m | Clear failure: zero trades and 100% cash. |

Round 6 reduced the number of permanently unowned names from the Round-5 pattern, but two of six fresh companies still had no entry at all. This fails the declared objective of materially resolving permanent `HOLD_REVIEW`/no-buy behavior.

## Why the realistic-growth input failed

The reverse valuation solver itself behaved numerically: all latest observations were solved inside the declared 0%-100% search range, and no value was fabricated above the range. The problem is economic interpretation, not root finding.

`realistic_growth` is a clipped point estimate from a single approximately three-year backward window. It is highly pro-cyclical:

- 歌尔股份 was floored at 0% on 71.8% of test days;
- 崇达技术 was floored at 0% on 66.6% of test days;
- 恒生电子 was floored at 0% on 55.8% of test days.

When trailing normalized EPS contracts, the model immediately treats 0% as the supportable starting path even when price may be discounting a recovery. This collapses neutral value and turns a cyclical earnings trough into a structural growth judgment.

The latest implied starting-growth estimates ranged from about 21.0% to 43.7%. These are mathematically consistent prices under the frozen formula, but they should not be presented as literal ten-year profit CAGRs: they are year-one growth rates that fade linearly toward 3%. For 顺络电子 the 28.9% implied rate versus 23.5% realistic rate is economically interpretable as a demanding but close expectation. For 中科曙光, 歌尔股份, 崇达技术 and 恒生电子, the much larger gaps are partly driven by depressed or zero backward-looking supportable growth, so the gap mixes market optimism with cycle-state measurement error.

## SELL diagnosis

The combined strategy produced 69 genuine negative-weight valuation SELL events. These are correlated monthly observations, not 69 independent investments.

| Horizon | Complete events | Median forward return | Positive fraction | Median maximum upside |
|---|---:|---:|---:|---:|
| 6 months | 67 | 4.74% | 58.2% | 23.88% |
| 12 months | 62 | 20.97% | 82.3% | 43.35% |
| 24 months | 45 | 38.43% | 82.2% | 87.98% |

To reduce repeated-month dependence, the diagnostic also marks the first SELL after each intervening BUY as a sell-regime entry. There were six such entries; five of six had positive 6-, 12- and 24-month endpoint returns. Their median 24-month return was 92.14%, and median maximum upside was 132.82%.

The most severe case was 歌尔股份's 2019-03-29 `REDUCE_25`: the stock gained 187.27% over the following 24 months and reached 418.11% maximum upside within that window. The SELL layer still sells too early when backward-looking growth and current neutral value fail to track a new earnings/expectation regime.

This does not prove that all valuation SELL should be removed. Round 3 already showed that removing valuation SELL raises drawdown. It shows that the Round-6 neutral value remains an unreliable growth-company SELL anchor.

## Data and execution audit

The deterministic post-run audit found:

- zero financial `available_date < report_date` errors;
- zero cases where `available_date` differed from the later profit/cash-flow `NOTICE_DATE`;
- zero future financial merges into a daily decision row;
- zero duplicate daily dates;
- zero BUY trades with negative weight change;
- zero valuation SELL trades with positive weight change.

Therefore the main failure is not attributable to an observed PIT leak or the previously fixed cash-constrained execution bug.

One comparator reporting caveat remains: the saved true-buy-and-hold NAV applies the 0.10% initial cost uniformly to the series, while the shared metric function normalizes by the first post-cost NAV. The cost therefore cancels from its reported return, overstating ending capital by about RMB 2,214. Correcting this immaterial 0.10% difference does not change any conclusion. Round 7 must represent initial capital explicitly so the cost cannot cancel.

No completed-trade win rate, holding period, or best/worst trade episodes are reported because the repository does not yet contain a validated lot/episode pairing contract. Signal-forward outcomes are reported directly instead of fabricating episode statistics.

## Anti-overfit decision

No Round-6 parameter, universe member, threshold, discount rate, growth cap, terminal rule or execution band is changed after observing this result. Production `selection_framework_v31.py` remains unchanged.

Round 7 is a fresh cross-industry replication of the same economic formula, with richer diagnostics and corrected buy-and-hold cost accounting. It is designed to establish whether the Round-6 failure is stable outside this electronics/software-heavy sample before a later round changes the growth estimator.
