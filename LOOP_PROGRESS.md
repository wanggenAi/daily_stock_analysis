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

```bash
rg -n "保证上涨|确定买入|必买|必卖|保证收益|稳赚" \
  reports/genge_cycle_bottom_ci_smoke/20260627_222008 \
  reports/genge_cycle_bottom_real/20260627_222109 \
  docs/genge_cycle_bottom_strategy.md \
  src/strategies/genge_cycle_bottom
```

- Result: passed with no matches.
- Next action: improve public-data valuation and financial adapters before trying larger cycle/broad pools or considering any simulated observation stage.
