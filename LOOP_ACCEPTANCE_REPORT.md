# Loop Acceptance Report

## A. Runability

- Pytest: `22 passed, 1 warning`.
- Fixture workflow: `.github/workflows/genge-cycle-bottom.yml`.
- Required fixture smoke: passed.
- Fixture smoke report: `reports/genge_cycle_bottom_ci_smoke/20260627_222008`.
- Real 5-year small-pool smoke: passed.
- Real 5-year report: `reports/genge_cycle_bottom_real/20260627_222109`.
- Real 10-year small-pool smoke: passed.
- Real 10-year report: `reports/genge_cycle_bottom_real/20260627_222319`.
- Generated files per run: `summary.md`, `summary.json`, `signal_details.csv`.
- Broker integration: none. The system does not connect to Citic Securities, does not read account data, and does not auto-trade.

## B. Data Quality And Anti-Lookahead

- Signal generation remains `as_of_date` based; future bars are only used by the backtest evaluator after a signal exists.
- Financial availability still prefers explicit disclosure/publish/announcement dates; otherwise conservative reporting lags apply.
- Valuation, financial, price percentile, benchmark, and industry-cycle gaps are written to `missing_fields`; missing values are not fabricated.
- Fixture smoke data failures: 0.
- Real 5-year data failures: 0.
- Real 10-year data failures: 0.
- Real 5-year PE/PB/financial missing counts: 28 / 28 / 28.
- Real 10-year PE/PB/financial missing counts: 19 / 19 / 19.
- Promise-word scan found no matches for `保证上涨`, `确定买入`, `必买`, `必卖`, `保证收益`, or `稳赚`.

## C. Strategy Expectancy And Risk

- Fixture smoke candidates: 2177.
- Fixture risk review count: 89.
- Fixture average net return: 20d 0.0248%, 60d -0.0918%, 120d -3.4064%, 250d -9.4437%.
- Fixture average low-based 250d drawdown: -36.1739%.
- Real 5-year candidates: 28.
- Real 5-year average net return: 20d 4.5472%, 60d 4.9633%, 120d 7.2985%, 250d 11.6953%.
- Real 5-year average low-based 250d drawdown: -28.5182%.
- Real 10-year candidates: 19.
- Real 10-year average net return: 20d 8.5013%, 60d 17.5848%, 120d 17.5233%, 250d 62.3113%.
- Real 10-year average low-based 250d drawdown: -40.1429%.
- The real runs are encouraging mechanically but statistically too small; all real signals lack valuation and financial fields, and drawdown remains above the paper gate.

## D. Acceptance Decision

- Final enum: `PASS_RESEARCH_ONLY`.
- Current stage: real public-data research smoke is runnable, but not paper-trading ready.
- Why not paper:
  - Real 5-year sample count is 28, below the 100-signal minimum.
  - Real 10-year sample count is 19, also below the minimum.
  - Real valuation, PE/PB, and financial fields are missing for every generated real signal.
  - 250-day low-based drawdown is too large in both real runs.
  - CI is implemented locally but not yet observed on GitHub after push.
  - No full cycle/broad pool validation has been completed.
- Next recommendations:
  - Improve real valuation and financial data adapters before relying on PE/PB or debt/cash-flow tags.
  - Add industry-cycle data files for the configured pools.
  - Run `genge_cycle_pool.txt` and then `genge_broad_pool.txt` after data quality improves.
  - Add limit-up/down, suspension, and executable-price diagnostics before any simulated observation stage.
