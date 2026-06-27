# Loop Progress

## Loop 1

- Objective: close P0 gaps for anti-lookahead fundamentals, historical valuation percentiles, executable next-open entry, raw/net returns, per-window stop loss, drawdown basis, industry cycle inputs, reports, and tests.
- Changes: updated feature engineering, signal contract, strategy scoring, walk-forward backtest, metrics, report writer, CLI options, fixtures, and P0 tests.
- Test command: `/Users/seker./.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest tests/test_genge_cycle_bottom_*.py`
- Result: 15 passed, 3 failed.
- Failures:
  - `_window_for_years` used a string date in direct unit tests.
  - price percentile test expected no missing fields even though 10-year data was intentionally insufficient.
  - forward-return test still expected the old same-close style 20-day return instead of next-open entry semantics.
- Next action: normalize dates inside `_window_for_years` and align tests with next-open and insufficient-history behavior.

## Loop 2

- Objective: fix Loop 1 failures without changing the strategy scope.
- Changes:
  - Normalized window dates before subtracting year offsets.
  - Updated price percentile fixture to verify 3-year/5-year availability and 10-year missing tags.
  - Updated forward-return expectations to the next trading day open entry basis.
- Test command: `/Users/seker./.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest tests/test_genge_cycle_bottom_*.py`
- Result: 18 passed, 1 warning.
- Warning: dependency deprecation warning from `fastapi.testclient`, not strategy code.

## Loop 3

- Objective: run the required CLI smoke with fixture data and default `--step-days 1`.
- Smoke command:

```bash
python -m src.strategies.genge_cycle_bottom.cli \
  --codes 000001,000002 \
  --years 5 \
  --benchmark 000300 \
  --price-data-dir tests/fixtures/genge_cycle_bottom/prices \
  --valuation-data-dir tests/fixtures/genge_cycle_bottom/valuation \
  --financial-data-dir tests/fixtures/genge_cycle_bottom/financial \
  --industry-cycle-file tests/fixtures/genge_cycle_bottom/industry_cycle.csv \
  --stock-industry-map tests/fixtures/genge_cycle_bottom/stock_industry_map.csv \
  --output-dir reports/genge_cycle_bottom_smoke
```

- Result: passed.
- Runtime: 61.75 seconds.
- Report directory: `reports/genge_cycle_bottom_smoke/20260627_191306`
- Total signals: 2289.
- Data failures: 0.

## Loop 4

- Objective: generate the normal local report tree and collect acceptance metrics.
- Report command: same fixture inputs as Loop 3, with `--output-dir reports/genge_cycle_bottom`.
- Result: passed.
- Runtime: 62.19 seconds.
- Report directory: `reports/genge_cycle_bottom/20260627_191416`
- Data failures: 0.
- PE missing count: 386.
- PB missing count: 0.
- Financial missing count: 34.
- Main candidate count: 2289.
- Risk review count: 89.
- Forbidden promise words check: passed for `summary.md` and `signal_details.csv`.

## Loop 5

- Objective: verify 10-year mode degrades safely when fixture history is not long enough.
- Command: same fixture inputs as Loop 3, with `--years 10 --step-days 20 --output-dir reports/genge_cycle_bottom_10y_smoke`.
- Result: passed.
- Runtime: 3.76 seconds.
- Report directory: `reports/genge_cycle_bottom_10y_smoke/20260627_191504`
- Total signals: 117.
- Data failures: 0.

## Loop 6

- Objective: upgrade `genge_cycle_bottom` from fixture-backed research skeleton toward real A-share public-data research validation.
- Changes:
  - Added GitHub Actions fixture workflow at `.github/workflows/genge-cycle-bottom.yml`.
  - Added real-data runner `scripts/run_genge_real_research.py`.
  - Added stock pools under `stock_pools/`: core, cycle, and broad.
  - Extended signal/detail schema with industry, industry cycle phase, and market environment state.
  - Extended summary schema with industry, signal type, market environment, industry cycle phase, time splits, drawdown diagnostics, expectancy diagnostics, failure reason diagnostics, data gap counts, and paper trading gate.
  - Made strategy classification more conservative: higher `CONFIRM_BUY` trend threshold, weak-market cap, and financial/industry-cycle missing downgrade.
  - Updated strategy docs and README entry.
  - Added tests for CI smoke workflow contract, summary schema, group aggregation, recent 2-year split, failure reasons, net-return defaults, raw/net separation, data errors, and paper gate.
- Test command:

```bash
/Users/seker./.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
  -m pytest tests/test_genge_cycle_bottom_*.py
```

- Result: 22 passed, 1 warning.
- Warning: dependency deprecation warning from `fastapi.testclient`, not strategy code.

## Loop 7

- Objective: run the required fixture CLI smoke after the real-data research upgrades.
- Smoke command:

```bash
/Users/seker./.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
  -m src.strategies.genge_cycle_bottom.cli \
  --codes 000001,000002 \
  --years 5 \
  --benchmark 000300 \
  --price-data-dir tests/fixtures/genge_cycle_bottom/prices \
  --valuation-data-dir tests/fixtures/genge_cycle_bottom/valuation \
  --financial-data-dir tests/fixtures/genge_cycle_bottom/financial \
  --industry-cycle-file tests/fixtures/genge_cycle_bottom/industry_cycle.csv \
  --stock-industry-map tests/fixtures/genge_cycle_bottom/stock_industry_map.csv \
  --output-dir reports/genge_cycle_bottom_ci_smoke
```

- Result: passed.
- Runtime: about 56 seconds.
- Report directory: `reports/genge_cycle_bottom_ci_smoke/20260627_222008`.
- Total signals: 2177.
- Data failures: 0.
- PE missing count: 0.
- PB missing count: 0.
- Financial missing count: 34.
- Main candidate count: 2177.
- Risk review count: 89.
- Acceptance enum in report: `PASS_RESEARCH_ONLY`.

## Loop 8

- Objective: attempt the required real small-pool 5-year run with public data.
- Command:

```bash
/Users/seker./.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
  scripts/run_genge_real_research.py \
  --stock-pool-file stock_pools/genge_core_pool.txt \
  --years 5 \
  --benchmark 000300 \
  --output-dir reports/genge_cycle_bottom_real \
  --max-codes 20
```

- Result: passed.
- Runtime: 54.51 seconds.
- Report directory: `reports/genge_cycle_bottom_real/20260627_222109`.
- Loaded codes: 12.
- Total signals: 28.
- Data failures: 0.
- PE missing count: 28.
- PB missing count: 28.
- Financial missing count: 28.
- Main candidate count: 28.
- Risk review count: 0.
- Acceptance enum in report: `PASS_RESEARCH_ONLY`.
- Failure/limitation: sample count is below 100, valuation/financial/industry-cycle data are missing for all real signals, and 250-day low-based drawdown is still too large.

## Loop 9

- Objective: attempt a 10-year real small-pool robustness run.
- Command: same as Loop 8, with `--years 10`.
- Result: passed.
- Runtime: 59.89 seconds.
- Report directory: `reports/genge_cycle_bottom_real/20260627_222319`.
- Loaded codes: 12.
- Total signals: 19.
- Data failures: 0.
- PE missing count: 19.
- PB missing count: 19.
- Financial missing count: 19.
- Main candidate count: 19.
- Risk review count: 0.
- Acceptance enum in report: `PASS_RESEARCH_ONLY`.
- Failure/limitation: 10-year mode is runnable, but signal count is smaller, data gaps remain complete for valuation/financial fields, and drawdown remains too large for paper-trading readiness.

## Loop 10

- Objective: verify promise-word guardrails after generated reports.
- Command:

Command: scanned generated reports, docs, and strategy source for forbidden promise wording.

- Result: passed with no matches.
- Next action: improve public-data valuation and financial adapters before trying larger cycle/broad pools or considering any simulated observation stage.

## Loop 11

- Objective: close the P1 engineering gaps for real public-data research without fitting the strategy to fixture results.
- Modified files:
  - `.github/workflows/genge-cycle-bottom.yml`
  - `.gitignore`
  - `scripts/run_genge_real_research.py`
  - `src/strategies/genge_cycle_bottom/acceptance.py`
  - `src/strategies/genge_cycle_bottom/backtest.py`
  - `src/strategies/genge_cycle_bottom/cli.py`
  - `src/strategies/genge_cycle_bottom/features.py`
  - `src/strategies/genge_cycle_bottom/fundamentals.py`
  - `src/strategies/genge_cycle_bottom/metrics.py`
  - `src/strategies/genge_cycle_bottom/report.py`
  - `tests/test_genge_cycle_bottom_backtest.py`
  - `tests/test_genge_cycle_bottom_features.py`
  - `tests/test_genge_cycle_bottom_report_cli.py`
  - `data/examples/*.csv`
- Changes:
  - Added public AKShare valuation/financial auto-fetch with successful-result cache at `data/cache/genge_fundamentals`.
  - Kept fixture/CI runs offline and fixture-only.
  - Made real runner default to `--step-days 1`; `--fast-smoke` now safely uses 20 unless an explicit step is given.
  - Added coverage metrics for valuation, financial, PE/PB, and industry-cycle fields.
  - Added provider error diagnostics without fabricating missing PE/PB/financial data.
  - Added execution diagnostics for missing next bar, limit-up/limit-down entry risk, abnormal gaps, and low liquidity.
  - Added explicit `--fixture-smoke-passed` acceptance context flag; it does not change signal generation.
  - Updated CI smoke schema checks for coverage and execution diagnostics.
- Targeted test command:

```bash
/Users/seker./.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
  -m pytest \
  tests/test_genge_cycle_bottom_report_cli.py::test_cli_fixture_smoke_context_flag_for_real_runs \
  tests/test_genge_cycle_bottom_report_cli.py::test_real_runner_step_days_defaults_and_fast_smoke
```

- Result: 2 passed, 1 warning.
- Failure/limitation: none from targeted tests. Warning is a dependency deprecation warning from `fastapi.testclient`.
- Next action: run full strategy tests, fixture smoke, and real core/cycle/broad research.

## Loop 12

- Objective: run fixture smoke and real public-data research pools with the upgraded diagnostics.
- Full test command:

```bash
/Users/seker./.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
  -m pytest tests/test_genge_cycle_bottom_*.py
```

- Result after final docs: 28 passed, 1 warning.
- Fixture smoke command:

```bash
/Users/seker./.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
  -m src.strategies.genge_cycle_bottom.cli \
  --codes 000001,000002 \
  --years 5 \
  --benchmark 000300 \
  --price-data-dir tests/fixtures/genge_cycle_bottom/prices \
  --valuation-data-dir tests/fixtures/genge_cycle_bottom/valuation \
  --financial-data-dir tests/fixtures/genge_cycle_bottom/financial \
  --industry-cycle-file tests/fixtures/genge_cycle_bottom/industry_cycle.csv \
  --stock-industry-map tests/fixtures/genge_cycle_bottom/stock_industry_map.csv \
  --output-dir reports/genge_cycle_bottom_ci_smoke
```

- Fixture result: passed.
- Fixture report directory: `reports/genge_cycle_bottom_ci_smoke/20260628_004518`.
- Fixture total signals: 2177.
- Fixture data failures / provider errors: 0 / 0.
- Fixture PE/PB/financial missing: 0 / 0 / 34.
- Fixture acceptance enum: `PASS_RESEARCH_ONLY`.
- Real core command:

```bash
/Users/seker./.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
  scripts/run_genge_real_research.py \
  --stock-pool-file stock_pools/genge_core_pool.txt \
  --years 5 \
  --benchmark 000300 \
  --output-dir reports/genge_cycle_bottom_real_core \
  --max-codes 12 \
  --step-days 1 \
  --auto-fetch-valuation \
  --auto-fetch-financial \
  --fundamental-cache-dir data/cache/genge_fundamentals \
  --industry-cycle-file data/examples/genge_industry_cycle_manual.csv
```

- Real core result: passed mechanically, failed strategy expectancy.
- Runtime: 434.61 seconds.
- Report directory: `reports/genge_cycle_bottom_real_core/20260627_232412`.
- Data failures / provider errors: 0 / 1.
- PE/PB/financial missing: 230 / 0 / 0.
- Main candidate count: 2646.
- Risk review count: 5.
- Acceptance enum: `FAIL_STRATEGY_EXPECTANCY`.
- Key failure: 60 日平均净收益 -1.9653%，60 日胜率 42.6307%，60 日跑赢基准 37.4802%，250 日低点回撤 -33.5991%。
- Real cycle command:

```bash
/Users/seker./.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
  scripts/run_genge_real_research.py \
  --stock-pool-file stock_pools/genge_cycle_pool.txt \
  --years 5 \
  --benchmark 000300 \
  --output-dir reports/genge_cycle_bottom_real_cycle \
  --max-codes 50 \
  --step-days 1 \
  --auto-fetch-valuation \
  --auto-fetch-financial \
  --fundamental-cache-dir data/cache/genge_fundamentals \
  --industry-cycle-file data/examples/genge_industry_cycle_manual.csv
```

- Real cycle result: passed mechanically, still not paper ready.
- Runtime: 1549.23 seconds.
- Report directory: `reports/genge_cycle_bottom_real_cycle/20260627_235033`.
- Data failures / provider errors: 0 / 0.
- PE/PB/financial missing: 1000 / 0 / 0.
- Main candidate count: 8247.
- Risk review count: 5.
- Acceptance enum in single-run report: `PASS_RESEARCH_ONLY`.
- Key limitation: average returns were positive, but 60 日胜率 47.2995%、跑赢基准 45.9274%、250 日低点回撤 -31.8513%，未达模拟盘门槛。
- Real broad command:

```bash
/Users/seker./.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
  scripts/run_genge_real_research.py \
  --stock-pool-file stock_pools/genge_broad_pool.txt \
  --years 5 \
  --benchmark 000300 \
  --output-dir reports/genge_cycle_bottom_real_broad \
  --max-codes 105 \
  --step-days 1 \
  --auto-fetch-valuation \
  --auto-fetch-financial \
  --fundamental-cache-dir data/cache/genge_fundamentals \
  --industry-cycle-file data/examples/genge_industry_cycle_manual.csv
```

- Real broad result: passed mechanically, failed strategy expectancy.
- Runtime: 3020.33 seconds.
- Report directory: `reports/genge_cycle_bottom_real_broad/20260628_004115`.
- Data failures / provider errors: 0 / 0.
- PE/PB/financial missing: 1392 / 0 / 0.
- Main candidate count: 20682.
- Risk review count: 5.
- Acceptance enum: `FAIL_STRATEGY_EXPECTANCY`.
- Key failure: 20 日平均净收益 -0.4365%，60 日平均净收益 -0.2626%，60 日胜率 41.94%，60 日跑赢基准 40.1116%，250 日低点回撤 -30.4961%。
- Failure reason summary: 止损不够严格、买太早、估值陷阱、趋势未确认、行业周期判断不足居前。
- Next action: do not enter paper trading. Future work should focus on signal quality, left-side risk control, industry-cycle data quality, and performance optimization for broad `step-days=1` runs.

## Loop 13

- Objective: correct the acceptance enum boundary so real-data research can pass independently from paper-trading expectancy, then rerun fixture, core, cycle, and broad validations without changing strategy features.
- Code changes:
  - `PASS_REAL_DATA_RESEARCH` now requires fixture smoke, a real public-data run, `total_signals >= 100`, no lookahead, no auto-trade, non-severe data/provider errors, and valuation plus financial coverage both above 30% unless explicitly price-only.
  - Poor 60d expectancy, weak win rate, weak benchmark outperformance, and large drawdown remain in `paper_trading_gate.reasons` and continue to block `PASS_PAPER_TRADING_READY`.
  - Added `--ci-passed` acceptance context to the strategy CLI and real runner.
  - Kept fixture/CI workflow fixture-only and kept all real runs public-data only.
- Full test command:

```bash
/Users/seker./.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
  -m pytest tests/test_genge_cycle_bottom_*.py
```

- Test result: 28 passed, 1 warning.
- Fixture smoke command:

```bash
/Users/seker./.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
  -m src.strategies.genge_cycle_bottom.cli \
  --codes 000001,000002 \
  --years 5 \
  --benchmark 000300 \
  --price-data-dir tests/fixtures/genge_cycle_bottom/prices \
  --valuation-data-dir tests/fixtures/genge_cycle_bottom/valuation \
  --financial-data-dir tests/fixtures/genge_cycle_bottom/financial \
  --industry-cycle-file tests/fixtures/genge_cycle_bottom/industry_cycle.csv \
  --stock-industry-map tests/fixtures/genge_cycle_bottom/stock_industry_map.csv \
  --output-dir reports/genge_cycle_bottom_ci_smoke
```

- Fixture result: passed.
- Fixture report directory: `reports/genge_cycle_bottom_ci_smoke/20260628_010009`.
- Fixture total signals: 2177.
- Fixture data failures / provider errors: 0 / 0.
- Fixture PE/PB/financial missing: 0 / 0 / 34.
- Fixture valuation/financial/industry-cycle coverage: 100.0% / 98.4382% / 67.7538%.
- Fixture acceptance enum: `PASS_RESEARCH_ONLY`.
- Real core command:

```bash
/Users/seker./.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
  scripts/run_genge_real_research.py \
  --stock-pool-file stock_pools/genge_core_pool.txt \
  --years 5 \
  --benchmark 000300 \
  --output-dir reports/genge_cycle_bottom_real \
  --max-codes 12 \
  --step-days 1 \
  --auto-fetch-valuation \
  --auto-fetch-financial \
  --fundamental-cache-dir data/cache/genge_fundamentals \
  --industry-cycle-file data/examples/genge_industry_cycle_manual.csv \
  --fixture-smoke-passed \
  --ci-passed
```

- Real core result: passed real-data research gate.
- Runtime: 200.84 seconds.
- Report directory: `reports/genge_cycle_bottom_real/20260628_010337`.
- Data failures / provider errors: 0 / 0.
- PE/PB/financial missing: 719 / 0 / 0.
- Main candidate count: 2872.
- Risk review count: 5.
- Acceptance enum: `PASS_REAL_DATA_RESEARCH`.
- Key paper-trading blockers: 60 日平均净收益 -1.1157%，60 日胜率 44.0450%，60 日跑赢基准 40.8860%，250 日低点回撤 -31.5825%。
- Real cycle command:

```bash
/Users/seker./.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
  scripts/run_genge_real_research.py \
  --stock-pool-file stock_pools/genge_cycle_pool.txt \
  --years 5 \
  --benchmark 000300 \
  --output-dir reports/genge_cycle_bottom_real_cycle \
  --max-codes 50 \
  --step-days 1 \
  --auto-fetch-valuation \
  --auto-fetch-financial \
  --fundamental-cache-dir data/cache/genge_fundamentals \
  --industry-cycle-file data/examples/genge_industry_cycle_manual.csv \
  --fixture-smoke-passed \
  --ci-passed
```

- Real cycle result: passed real-data research gate.
- Runtime: 816.13 seconds.
- Report directory: `reports/genge_cycle_bottom_real_cycle/20260628_011853`.
- Data failures / provider errors: 0 / 0.
- PE/PB/financial missing: 1627 / 0 / 0.
- Main candidate count: 8631.
- Risk review count: 5.
- Acceptance enum: `PASS_REAL_DATA_RESEARCH`.
- Key paper-trading blockers: 60 日胜率 46.8403%，60 日跑赢基准 44.8214%，250 日低点回撤 -31.5143%。
- Real broad command:

```bash
/Users/seker./.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
  scripts/run_genge_real_research.py \
  --stock-pool-file stock_pools/genge_broad_pool.txt \
  --years 5 \
  --benchmark 000300 \
  --output-dir reports/genge_cycle_bottom_real_broad \
  --max-codes 100 \
  --step-days 1 \
  --auto-fetch-valuation \
  --auto-fetch-financial \
  --fundamental-cache-dir data/cache/genge_fundamentals \
  --industry-cycle-file data/examples/genge_industry_cycle_manual.csv \
  --fixture-smoke-passed \
  --ci-passed
```

- Real broad result: passed real-data research gate.
- Runtime: 1669.94 seconds.
- Report directory: `reports/genge_cycle_bottom_real_broad/20260628_014649`.
- Data failures / provider errors: 0 / 0.
- PE/PB/financial missing: 1417 / 0 / 0.
- Main candidate count: 20076.
- Risk review count: 5.
- Acceptance enum: `PASS_REAL_DATA_RESEARCH`.
- Key paper-trading blockers: 60 日胜率 42.8790%，60 日跑赢基准 40.3188%，250 日低点回撤 -31.2448%。
- Broad run used `--max-codes 100` because broad `step-days=1` remains slow; this run took 1669.94 seconds.
- Forbidden promise-word scan: latest real core/cycle/broad summary reports contain 0 matches for `保证上涨`, `确定买入`, or `必卖`.
- GitHub Actions observation before this loop: run `28302776026` passed.
- Final acceptance enum: `PASS_REAL_DATA_RESEARCH`.
- Next action: do not enter paper trading. Future work should improve signal quality, left-side entry timing, stop/exit filters, industry-cycle data source quality, and broad run performance.
