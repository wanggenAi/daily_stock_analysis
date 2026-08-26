# V3.1 normalized-earnings neutral-value draft

Status: **research only; frozen before Round-5 OOS results**.

This draft targets structural compounders/growth technology, where Rounds 3-4 falsified the idea that a historical PE/PB relative-multiple proxy is sufficient. Production V3.1 remains unchanged until an untouched OOS test is completed.

## Strict point-in-time data contract

For every historical financial observation:

- report values come from public historical financial statements;
- `NOTICE_DATE` is the availability boundary;
- `UPDATE_DATE` is ignored because later database revisions can rewrite it;
- when profit and cash-flow inputs are combined, `available_date = max(profit NOTICE_DATE, cash-flow NOTICE_DATE)`;
- the observation can affect a trading decision only on/after its availability date;
- Q1/H1/Q3 TTM values are reconstructed as current cumulative + previous FY - previous-year same-period cumulative.

## Earnings authenticity before valuation

For each available report, construct approximate TTM basic EPS, TTM parent net profit, TTM deduct-parent net profit and TTM operating cash flow.

Define:

- `deduct_quality = TTM deduct-parent net profit / TTM parent net profit`
- `cash_conversion = TTM operating cash flow / TTM parent net profit`
- `quality_factor = min(1.0, deduct_quality, cash_conversion)`
- `quality_adjusted_eps = TTM basic EPS * quality_factor`

A report has no positive valuation earning power if TTM basic EPS <= 0, parent net profit <= 0, deduct quality <= 0, or cash conversion <= 0. This does not fabricate a value; it yields `HOLD_REVIEW` until positive normalized earning power is available.

The per-report normalized earning power is the median of the latest four positive `quality_adjusted_eps` observations, requiring at least two observations.

This rule deliberately gives **no bonus** for cash conversion or deduct profit above reported EPS: both ratios are capped at 1.0. It only haircuts low-quality earnings.

## Conservative growth assumption

Estimate historical growth from normalized earning power approximately three years earlier using only already available report history.

- `historical_growth = CAGR(normalized_owner_eps / normalized_owner_eps_3y_ago)`
- negative historical growth is floored at 0 for valuation;
- assumed five-year starting growth is **50% of historical growth**;
- assumed starting growth is capped at **15%**;
- if a valid three-year comparison is unavailable, assumed starting growth is 0.

This is a pre-declared conservatism rule, not fitted to Round-5 securities.

## Neutral-value model

Treat normalized quality-adjusted EPS as an owner-earnings proxy for a transparent five-year earnings-power valuation.

Frozen base assumptions:

- discount rate: **10%**
- five-year starting growth: as defined above
- growth fades linearly over five years toward `min(starting_growth, 3%)`; the model never raises a 0%-to-3% starting assumption just to manufacture growth
- terminal multiple at year 5: **15x** normalized owner earnings

For years 1..5, project owner earnings with the fading growth path and discount each year's earning power at 10%. Add a year-5 terminal value of `15 * year5_owner_earnings`, also discounted at 10%.

The resulting value is the research `neutral_value` per share.

This is not claimed to be a perfect DCF. Its purpose is to test whether a transparent PIT earning-power model is materially more robust than historical relative PE/PB for structural growth companies.

## V3.1 execution remains frozen

Round 5 does **not** change:

- BUY_STAGED at price/neutral <= 0.85 -> up to 50% name cap
- BUY_A_LEVEL <= 0.75 -> up to 75%
- BUY_FULL_MARGIN <= 0.65 -> up to 100%
- HOLD_NO_ADD >= 1.00
- REDUCE_25 >= 1.20 -> max 75%
- REDUCE_50 >= 1.40 -> max 50%
- CORE_ONLY >= 1.70 -> max 25%
- one-way trading cost 0.10%
- month-end rebalance
- SELL ignores personal entry price/cost basis
- corrected cash-constrained engine: sells first; only incremental BUY requests are scaled if cash is insufficient.

## Round-5 untouched OOS universe

Frozen before results:

- 002371 北方华创
- 002475 立讯精密
- 002384 东山精密
- 600584 长电科技
- 603228 景旺电子
- 600703 三安光电

All are Shanghai/Shenzhen main-board A shares and none were used in Rounds 1-4.

## Comparators

On the exact same fresh universe Round 5 will report:

1. `NORMALIZED_EARNINGS`: this frozen PIT earning-power neutral value;
2. `UNIVERSAL_GEOMEAN`: the old 756-day relative PE/PB proxy, using the corrected execution engine;
3. literal initial-equal-dollar, zero-rebalance buy-and-hold;
4. CSI 300.

No post-result threshold or formula tuning is allowed. Any formula change after Round 5 requires another untouched universe.

## Scope limitation

This remains a valuation/execution-layer test conditional on a fixed research universe. It is not a retrospective reconstruction of qualitative moat, predictability, demand, financial-safety or earnings-authenticity hard gates.
