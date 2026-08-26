# V3.1 Round-5 normalized-earnings postmortem

Status: **research diagnosis; production V3.1 remains unchanged**.

Round 5 was an untouched OOS test. The frozen normalized-earnings formula and six-stock universe were committed before any Round-5 result existed. The successful run therefore counts as evidence, including negative evidence.

## Headline result

2018-01-02 to 2026-08-24, RMB 1,000,000 initial capital, month-end execution, 0.10% one-way friction:

| Variant | Final capital | CAGR | Max drawdown | Sharpe | Average cash |
|---|---:|---:|---:|---:|---:|
| Normalized earnings | RMB 1.532m | 5.06% | -13.33% | 0.810 | 86.16% |
| Old universal PE/PB proxy | RMB 3.460m | 15.45% | -40.76% | 0.772 | 43.75% |
| Literal buy-and-hold | RMB 7.850m | 26.93% | -46.39% | 0.851 | n/a |

The new formula reduced drawdown primarily by refusing to deploy capital. It did not solve the growth-company valuation problem.

Two of the six fresh securities illustrate the failure sharply:

- 002371 北方华创: normalized-earnings strategy made **zero trades** over the test window.
- 002475 立讯精密: normalized-earnings strategy made **zero trades** over the test window.

Therefore this formula must **not** be promoted into production V3.1/V3.2.

## Structural reason: the formula hard-caps the effective earnings multiple

The frozen Round-5 value model was:

- quality-adjusted normalized owner EPS;
- starting growth = 50% of historical ~3y growth, capped at 15%;
- five-year growth fade toward 3%;
- 10% discount rate;
- 15x terminal owner earnings.

For one unit of current normalized owner EPS, this model produces the following neutral-value multiples:

| Starting growth | Neutral value / normalized owner EPS |
|---:|---:|
| 0% | 13.10x |
| 5% | 15.61x |
| 10% | 17.44x |
| 15% (maximum allowed) | **19.41x** |

This is the key diagnosis. Even at the maximum growth assumption, the model can never assign more than about **19.41x** normalized owner earnings as neutral value.

Because the existing V3.1 execution bands were deliberately left unchanged, at the most optimistic allowed growth rate the corresponding normalized-owner-earnings multiples are approximately:

- BUY_STAGED (`price/neutral <= 0.85`): **<= 16.50x**
- BUY_A_LEVEL (`<= 0.75`): **<= 14.56x**
- BUY_FULL_MARGIN (`<= 0.65`): **<= 12.62x**
- HOLD_NO_ADD begins around **19.41x**
- REDUCE_25 begins around **23.29x**
- REDUCE_50 begins around **27.17x**
- CORE_ONLY begins around **33.00x**

Thus the Round-5 model is structurally predisposed to keep cash or de-risk structural growth companies even when their earnings compound rapidly. This is not a threshold bug; it is a neutral-value-model design issue.

## Concrete PIT evidence

### 北方华创 002371

At 2020-11-30, using only financial data public by 2020-10-27:

- price: RMB 126.34
- normalized owner EPS: about 0.1795
- assumed growth: about 12.07%
- frozen fundamental neutral value: about RMB 3.27
- price / neutral: about **38.60x**

By 2026-06-30, using the 2026-Q1 report available on 2026-04-30:

- price: RMB 883.76
- normalized owner EPS: about 4.663
- assumed growth: 15% cap
- fundamental neutral value: about RMB 90.50
- price / neutral: about **9.77x**

The earning power rose dramatically, but the formula's effective fair multiple remained capped near 19.4x owner EPS, so the strategy still could not enter.

### 立讯精密 002475

At 2026-06-30, using the 2026-Q1 report available on 2026-04-29:

- price: RMB 70.23
- normalized owner EPS: about 1.886
- assumed growth: about 10.17%
- fundamental neutral value: about RMB 33.01
- price / neutral: about **2.13x**

Again, the model remained too restrictive to produce an entry despite long-term earnings compounding.

## What Round 5 did validate

The strict PIT financial-data infrastructure **did** survive the test and should be retained:

- use `NOTICE_DATE` as the information-availability boundary;
- ignore mutable `UPDATE_DATE` for PIT reconstruction;
- reconstruct TTM profit, deduct-profit and operating cash flow without look-ahead;
- quality haircuts can remain a diagnostic/input, but they should not by themselves define a universal growth-company value multiple.

The failure is in the valuation transformation from earning power to neutral value, not in the PIT data plumbing.

## What must not be done

Do not repair this result by tuning the already-observed Round-5 sample, for example by changing 10% to 8%, 15% growth cap to 25%, terminal 15x to 30x, or changing the existing V3.1 BUY/SELL bands until the backtest looks attractive.

That would be post-result overfitting.

## Next research direction

The next growth-company valuation engine should be designed from economic structure rather than from the Round-5 return table.

Preferred direction: **reverse expectations / reinvestment-runway valuation**.

Instead of asking only, "what price does a fixed 15x-terminal DCF produce?", the engine should ask:

1. What growth/reinvestment expectations are embedded in today's price?
2. What growth is supportable by strict-PIT normalized earnings, cash conversion, incremental returns on capital, and the remaining 5-10 year runway?
3. Is the market-implied expectation materially below, close to, or above that supportable range?
4. Only after that expectation gap is established should the existing V3.1 margin-of-safety execution layer act.

This is consistent with the V3.1 philosophy: hard business logic first, normalized earning power second, valuation/expectation gap third, and market position last.

Any concrete next formula must be frozen before another untouched OOS universe is observed.
