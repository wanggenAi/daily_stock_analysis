# Loop Acceptance Report

## A. Runability

- Pytest: `18 passed, 1 warning`.
- Required 5-year CLI smoke: passed.
- Required smoke report: `reports/genge_cycle_bottom_smoke/20260627_191306`.
- Normal local report: `reports/genge_cycle_bottom/20260627_191416`.
- 10-year compatibility smoke: `reports/genge_cycle_bottom_10y_smoke/20260627_191504`.
- Generated files per run: `summary.md`, `summary.json`, `signal_details.csv`.
- Broker integration: none. The system does not connect to Citic Securities, does not read account data, and does not auto-trade.

## B. Data Quality And Anti-Lookahead

- Financial availability now prefers `disclosure_date`, `publish_date`, `ann_date`, or `announcement_date`.
- If only `report_date` exists, conservative lags are applied: annual 120 days, semiannual 90 days, quarterly 60 days, unknown period 90 days.
- Valuation scoring uses historical PE/PB/PS percentiles truncated at `as_of_date`; future valuation rows are covered by tests.
- Price position fields include 3-year, 5-year, and 10-year percentiles plus 5-year/10-year distance from lows and highs.
- Insufficient history is marked in `missing_fields`; it is not silently treated as complete data.
- Industry cycle data is optional; missing data degrades to neutral score 50 and records missing fields.
- Smoke data failures: 0.
- PE missing count in normal report: 386.
- PB missing count in normal report: 0.
- Financial missing count in normal report: 34.
- Entry missing count in normal report: 0.

## C. Strategy Expectancy And Risk

- Main candidate count: 2289.
- Risk review count: 89.
- Signal distribution: `LEFT_SMALL_BUY` 1564, `CONFIRM_BUY` 725.
- Average net return: 20d 0.1245%, 60d 0.2396%, 120d -2.7353%, 250d -9.8323%.
- Average low-based max drawdown at 250d: -36.4387%.
- Worst low-based max drawdown: -73.6199%.
- This first fixture-backed run is useful for validating mechanics and risk reporting, but its 120d/250d net returns and drawdowns are not good enough to call the strategy paper-trading ready.

## D. Acceptance Decision

- The implementation is runnable and produces the required first-version research artifacts.
- The current evidence is not sufficient for live trading or automatic decisions.
- Reports avoid promise wording such as `保证上涨`, `确定买入`, `必买`, and `必卖`.
- Final enum: `PASS_RESEARCH_ONLY`.
