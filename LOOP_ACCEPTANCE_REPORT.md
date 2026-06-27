# Loop Acceptance Report

## A. Runability

- Pytest: `28 passed, 1 warning`.
- Fixture workflow: `.github/workflows/genge-cycle-bottom.yml`.
- Fixture workflow trigger: `pull_request` and `push` to `main`.
- GitHub Actions observed result: passed, run `https://github.com/wanggenAi/daily_stock_analysis/actions/runs/28302776026`.
- Fixture smoke: passed.
- Fixture smoke report: `reports/genge_cycle_bottom_ci_smoke/20260628_010009`.
- Real 5-year core-pool run: passed.
- Real 5-year core report: `reports/genge_cycle_bottom_real/20260628_010337`.
- Real 5-year cycle-pool run: passed.
- Real 5-year cycle report: `reports/genge_cycle_bottom_real_cycle/20260628_011853`.
- Real 5-year broad-pool run: passed with `--max-codes 100`.
- Real 5-year broad report: `reports/genge_cycle_bottom_real_broad/20260628_014649`.
- Generated files per run: `summary.md`, `summary.json`, `signal_details.csv`.
- Broker integration: none. The system does not connect to Citic Securities, does not read account data, and does not auto-trade.

## B. Data Quality And Anti-Lookahead

- Signal generation remains `as_of_date` based; future bars are only used by the backtest evaluator after a signal exists.
- Financial availability still prefers explicit disclosure/publish/announcement dates; otherwise conservative reporting lags apply.
- Valuation, financial, price percentile, benchmark, and industry-cycle gaps are written to `missing_fields`; missing values are not fabricated.
- Public valuation/financial auto-fetch uses AKShare and caches only successful results under `data/cache/genge_fundamentals`.
- CI and tests remain fixture-only and do not require real network行情.
- Fixture data failures / provider errors: 0 / 0.
- Fixture PE/PB/financial missing counts: 0 / 0 / 34.
- Fixture valuation/financial/industry-cycle coverage: 100.0% / 98.4382% / 67.7538%.
- Real core data failures / provider errors: 0 / 0.
- Real core PE/PB/financial missing counts: 719 / 0 / 0.
- Real core valuation/financial/industry-cycle coverage: 100.0% / 100.0% / 100.0%.
- Real cycle data failures / provider errors: 0 / 0.
- Real cycle PE/PB/financial missing counts: 1627 / 0 / 0.
- Real cycle valuation/financial/industry-cycle coverage: 100.0% / 100.0% / 100.0%.
- Real broad data failures / provider errors: 0 / 0.
- Real broad PE/PB/financial missing counts: 1417 / 0 / 0.
- Real broad valuation/financial/industry-cycle coverage: 100.0% / 100.0% / 88.0305%.
- Forbidden promise-word scan found no matches for `保证上涨`, `确定买入`, or `必卖` in the latest real strategy reports.

## C. Strategy Expectancy And Risk

- Fixture candidates: 2177.
- Fixture average net return: 20d 0.0248%, 60d -0.0918%, 120d -3.4064%, 250d -9.4437%.
- Fixture average low-based 250d drawdown: -36.1739%.
- Real core candidates: 2872.
- Real core runtime: 200.84 seconds.
- Real core average net return: 20d -0.3042%, 60d -1.1157%, 120d 0.5589%, 250d 3.9730%.
- Real core 60d win/outperform: 44.0450% / 40.8860%.
- Real core average low-based 250d drawdown: -31.5825%.
- Real core recent 2y: 60d average net return 4.7416%, 60d win rate 58.4012%, 60d outperform 44.5596%, verdict `回撤偏大`.
- Real cycle candidates: 8631.
- Real cycle runtime: 816.13 seconds.
- Real cycle average net return: 20d 0.6039%, 60d 1.9229%, 120d 4.9925%, 250d 8.6170%.
- Real cycle 60d win/outperform: 46.8403% / 44.8214%.
- Real cycle average low-based 250d drawdown: -31.5143%.
- Real cycle recent 2y: 60d average net return 8.5665%, 60d win rate 57.6595%, 60d outperform 47.3263%, verdict `回撤偏大`.
- Real broad candidates: 20076.
- Real broad runtime: 1669.94 seconds.
- Real broad average net return: 20d -0.2087%, 60d 0.3965%, 120d 2.0174%, 250d 3.9542%.
- Real broad 60d win/outperform: 42.8790% / 40.3188%.
- Real broad average low-based 250d drawdown: -31.2448%.
- Real broad recent 2y: 60d average net return 4.4333%, 60d win rate 50.1963%, 60d outperform 38.2591%, verdict `回撤偏大`.
- Main broad failure reasons: 止损不够严格、买太早、估值陷阱、趋势未确认、行业周期判断不足。

## D. Execution Feasibility Diagnostics

- Real core execution diagnostics: limit-up entry 8, limit-down entry 0, missing entry 4, degraded entry 8, low liquidity 4, abnormal gap open 10.
- Real cycle execution diagnostics: limit-up entry 21, limit-down entry 0, missing entry 9, degraded entry 21, low liquidity 9, abnormal gap open 26.
- Real broad execution diagnostics: limit-up entry 51, limit-down entry 2, missing entry 25, degraded entry 53, low liquidity 25, abnormal gap open 75.
- Execution diagnostics remain research risk labels only; they are not broker-order simulations and do not create trades.

## E. Acceptance Decision

- Final enum: `PASS_REAL_DATA_RESEARCH`.
- Current stage: real public-data research validation is runnable and data coverage is sufficient.
- Why `PASS_REAL_DATA_RESEARCH`:
  - Fixture smoke passed and GitHub Actions was observed green.
  - At least one real 5-year run passed; core, cycle, and broad all passed mechanically with `step-days=1`.
  - Real runs had `total_signals >= 100`.
  - Valuation and financial coverage both exceeded 30% in all real runs.
  - Data failures and provider errors were not severe.
  - No lookahead risk and no auto-trading capability are declared in diagnostics.
- Why not `PASS_PAPER_TRADING_READY`:
  - Real broad 60 日胜率为 42.8790%，低于 52%。
  - Real broad 60 日跑赢基准比例为 40.3188%，低于 50%。
  - Real broad 250 日低点口径平均回撤为 -31.2448%，回撤偏大。
  - Execution diagnostics still show limit-up, missing-bar, low-liquidity, and degraded-entry risks.
  - 行业周期文件仍是人工样例，不能当作权威行业周期判断。
- Next stage:
  - 不进入模拟盘，不输出任何交易指令。
  - 下一轮应专注改善信号质量、左侧买太早、止损/破位过滤、行业周期数据来源和 broad 性能。
