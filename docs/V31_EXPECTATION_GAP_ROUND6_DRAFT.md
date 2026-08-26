# V3.1 Round-6 expectation-gap valuation draft

Status: **research only; frozen before Round-6 untouched OOS results**.

Round 5 falsified the five-year/15x direct normalized-earnings value formula for structural growth companies. This Round-6 design does not tune the observed Round-5 securities. It implements fields already required by the frozen V3.1 contract: `market_implied_profit_cagr`, `realistic_profit_cagr`, and `expectation_gap`.

Production V3.1 remains unchanged until untouched OOS evidence exists.

## 1. Strict point-in-time contract

Financial observations use the existing strict-PIT infrastructure:

- report-period values come from public historical statements;
- `NOTICE_DATE` is the information-availability boundary;
- mutable `UPDATE_DATE` is ignored;
- profit/cash-flow combinations become usable only from the later required notice date;
- Q1/H1/Q3 TTM values are reconstructed with only then-public report periods;
- no current or future revision is allowed to backfill an earlier decision.

## 2. Normalized earning power

Round 5 multiplied EPS directly by TTM cash conversion. That is too strong an assumption for expanding businesses because working-capital investment can depress current operating cash flow without making accounting earnings fictitious.

Round 6 therefore separates **earnings normalization** from **cash-conversion diagnostics**.

Per report:

- require positive TTM basic EPS and positive TTM parent net profit;
- `deduct_quality = TTM deduct-parent net profit / TTM parent net profit`;
- `deduct_factor = clip(deduct_quality, 0, 1)`;
- `clean_eps = TTM basic EPS * deduct_factor`;
- `normalized_eps = median(latest four positive clean_eps observations)`, requiring at least two observations.

Operating cash flow remains visible as an earnings-authenticity diagnostic and may block a future full hard-gate reconstruction, but it does **not** mechanically multiply EPS in this valuation-layer OOS test.

This prevents one quarter of working-capital build from being treated as a permanent reduction in per-share earning power.

## 3. Realistic growth — pre-declared supportable range

For each report, using only already available history, calculate approximately three-year CAGRs for:

- normalized clean EPS;
- TTM operating revenue.

Define the supportable starting profit growth rate as:

`realistic_growth = clip(min(eps_cagr, revenue_cagr + 5 percentage points), 0%, 30%)`

Requirements:

- both ~3y comparisons must exist and be positive-history comparisons;
- if either comparison is unavailable, valuation is `HOLD_REVIEW` rather than fabricated;
- negative CAGRs are floored at 0 only for valuation, not hidden in diagnostics.

Economic rationale, declared before OOS:

- long-run earnings cannot indefinitely outrun revenue without margin expansion;
- up to 5 percentage points of profit growth above revenue allows operating leverage/mix improvement without assuming unlimited margin expansion;
- 30% is a long-duration sanity ceiling for a ten-year valuation horizon, not a Round-5 fitted number.

## 4. Ten-year earning-power valuation

V3.1's hard-logic test explicitly asks whether demand/runway can remain intact over roughly 5-10 years. The growth-company valuation horizon is therefore ten years rather than the failed Round-5 five-year horizon.

Frozen assumptions:

- current normalized clean EPS is the starting earning power;
- discount rate `r = 10%`;
- year-1 growth starts at `realistic_growth`;
- growth fades linearly over years 1..10 toward 3%;
- terminal perpetual growth `g = 3%`;
- terminal owner-earnings multiple is not manually fitted: `1 / (r - g) = 14.2857x`;
- value equals discounted annual earning power for years 1..10 plus the discounted terminal value.

The resulting per-share value is the Round-6 research `neutral_value`.

## 5. Market-implied growth

Using the exact same valuation equation, current historical market price, then-public normalized EPS, 10% discount rate and 3% terminal growth, solve for the starting growth rate that makes model value equal market price.

- solve monotonically over starting growth from 0% to 100%;
- if price is below the 0%-growth value, implied growth is recorded as <=0% / cheap;
- if price exceeds the 100%-growth value, record `IMPLIED_ABOVE_SEARCH_RANGE`; do not invent a number.

This produces `market_implied_profit_cagr`.

## 6. Expectation gap

Define:

`expectation_gap = realistic_growth - market_implied_growth`

Interpretation:

- positive gap: business history supports more growth than price requires;
- near zero: price roughly requires the supportable path;
- negative gap: market requires more growth than the conservative supportable path.

Round 6 reports this gap for diagnosis. It does **not** introduce a newly fitted expectation-gap trading threshold.

## 7. Execution layer remains frozen

The existing V3.1 price/neutral execution bands remain unchanged:

- BUY_STAGED at `price / neutral <= 0.85` -> up to 50% name cap;
- BUY_A_LEVEL <= 0.75 -> up to 75%;
- BUY_FULL_MARGIN <= 0.65 -> up to 100%;
- HOLD_NO_ADD >= 1.00;
- REDUCE_25 >= 1.20 -> max 75%;
- REDUCE_50 >= 1.40 -> max 50%;
- CORE_ONLY >= 1.70 -> max 25%;
- month-end rebalance;
- 0.10% one-way friction;
- SELL never uses personal cost basis;
- corrected cash-constrained execution: sells first and scales only incremental BUY requests when cash is insufficient.

## 8. Untouched Round-6 OOS universe

Frozen before results; all are Shanghai/Shenzhen main-board A shares and none appeared in Rounds 1-5:

- 002179 中航光电
- 002138 顺络电子
- 002241 歌尔股份
- 002938 鹏鼎控股
- 603019 中科曙光
- 600570 恒生电子

The sample deliberately spans connectors/passives/consumer electronics/PCB/server infrastructure/software rather than selecting only one winning historical sub-theme.

## 9. Comparators

Round 6 will report on the same six securities:

1. `EXPECTATION_GAP_10Y`: this frozen strict-PIT normalized-EPS / realistic-growth value;
2. `ROUND5_5Y_15X`: the already-falsified Round-5 formula, carried forward unchanged as a diagnostic comparator;
3. `UNIVERSAL_GEOMEAN`: the old 756-day relative PE/PB proxy with corrected execution;
4. literal initial-equal-dollar, zero-rebalance buy-and-hold;
5. CSI 300.

## 10. Anti-overfit rule

No Round-6 formula, security, threshold, horizon, discount rate, growth cap, revenue allowance, terminal rule or execution band may be changed after the first successful Round-6 output is observed.

If Round 6 fails economically, the failure is recorded. Any subsequent formula change requires another untouched OOS universe.

## Scope limitation

This remains a fixed-universe valuation/execution-layer OOS test. It does not retrospectively reconstruct qualitative moat, long-term-demand, predictability, financial-safety or earnings-authenticity hard gates.
