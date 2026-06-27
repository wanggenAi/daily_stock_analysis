# Loop Acceptance Report

## A. Runability

- Pytest: `28 passed, 1 warning`.
- Fixture workflow: `.github/workflows/genge-cycle-bottom.yml`.
- Fixture workflow trigger: `pull_request` and `push` to `main`.
- Required fixture smoke: passed.
- Fixture smoke report: `reports/genge_cycle_bottom_ci_smoke/20260628_004518`.
- Real 5-year core-pool run: passed mechanically.
- Real 5-year core report: `reports/genge_cycle_bottom_real_core/20260627_232412`.
- Real 5-year cycle-pool run: passed mechanically.
- Real 5-year cycle report: `reports/genge_cycle_bottom_real_cycle/20260627_235033`.
- Real 5-year broad-pool run: passed mechanically.
- Real 5-year broad report: `reports/genge_cycle_bottom_real_broad/20260628_004115`.
- Generated files per run: `summary.md`, `summary.json`, `signal_details.csv`.
- Broker integration: none. The system does not connect to Citic Securities, does not read account data, and does not auto-trade.

## B. Data Quality And Anti-Lookahead

- Signal generation remains `as_of_date` based; future bars are only used by the backtest evaluator after a signal exists.
- Financial availability still prefers explicit disclosure/publish/announcement dates; otherwise conservative reporting lags apply.
- Valuation, financial, price percentile, benchmark, and industry-cycle gaps are written to `missing_fields`; missing values are not fabricated.
- Public valuation/financial auto-fetch uses AKShare and caches only successful results under `data/cache/genge_fundamentals`.
- CI and tests remain fixture-only and do not require real network行情.
- Fixture smoke data failures: 0.
- Fixture PE/PB/financial missing counts: 0 / 0 / 34.
- Real core data failures / provider errors: 0 / 1.
- Real core PE/PB/financial missing counts: 230 / 0 / 0.
- Real core valuation/financial/industry-cycle coverage: 100.0% / 100.0% / 100.0%.
- Real cycle data failures / provider errors: 0 / 0.
- Real cycle PE/PB/financial missing counts: 1000 / 0 / 0.
- Real cycle valuation/financial/industry-cycle coverage: 100.0% / 100.0% / 100.0%.
- Real broad data failures / provider errors: 0 / 0.
- Real broad PE/PB/financial missing counts: 1392 / 0 / 0.
- Real broad valuation/financial/industry-cycle coverage: 100.0% / 100.0% / 88.681%.
- Forbidden promise-word scan found no matches in generated strategy reports.

## C. Strategy Expectancy And Risk

- Fixture smoke candidates: 2177.
- Fixture risk review count: 5.
- Fixture average net return: 20d 0.0248%, 60d -0.0918%, 120d -3.4064%, 250d -9.4437%.
- Fixture average low-based 250d drawdown: -36.1739%.
- Real core candidates: 2646.
- Real core runtime: 434.61 seconds.
- Real core average net return: 20d -0.4346%, 60d -1.9653%, 120d -1.1080%, 250d -3.6391%.
- Real core 60d win/outperform: 42.6307% / 37.4802%.
- Real core average low-based 250d drawdown: -33.5991%.
- Real cycle candidates: 8247.
- Real cycle runtime: 1549.23 seconds.
- Real cycle average net return: 20d 0.6482%, 60d 2.1301%, 120d 5.4277%, 250d 8.4235%.
- Real cycle 60d win/outperform: 47.2995% / 45.9274%.
- Real cycle average low-based 250d drawdown: -31.8513%.
- Real broad candidates: 20682.
- Real broad runtime: 3020.33 seconds.
- Real broad average net return: 20d -0.4365%, 60d -0.2626%, 120d 1.1598%, 250d 3.1939%.
- Real broad 60d win/outperform: 41.94% / 40.1116%.
- Real broad average low-based 250d drawdown: -30.4961%.
- Real broad execution diagnostics: limit-up entry 45, limit-down entry 2, missing entry 25, degraded entry 47, low liquidity 25, abnormal gap open 69.
- Real broad main failure reasons: 止损不够严格、买太早、估值陷阱、趋势未确认、行业周期判断不足。

## D. Acceptance Decision

- Final enum: `FAIL_STRATEGY_EXPECTANCY`.
- Current stage: real public-data research validation is runnable, but the strategy result is not good enough for simulated observation.
- Why not `PASS_PAPER_TRADING_READY`:
  - Real broad 60 日平均净收益为 -0.2626%，未转正。
  - Real broad 60 日胜率为 41.94%，低于 52%。
  - Real broad 60 日跑赢基准比例为 40.1116%，低于 50%。
  - Real broad 250 日低点口径平均回撤为 -30.4961%，回撤偏大。
  - Fixture smoke 和 CI 本地逻辑通过，但 GitHub Actions 尚需 push 后观察真实运行结果。
  - 行业周期文件仍是人工样例，不能当作权威行业周期判断。
- Why not simply `PASS_REAL_DATA_RESEARCH`:
  - 数据覆盖和样本量已达到真实研究验证要求，但 broad 池收益期望失败，应优先暴露为 `FAIL_STRATEGY_EXPECTANCY`。
  - Cycle 池表现相对好一些，但胜率、跑赢基准和回撤仍低于模拟盘要求，不能用较小池子掩盖 broad 池失败。
- Next recommendations:
  - 不进入模拟盘，不输出任何交易指令。
  - 优先减少“买太早”和“止损不够严格”：提高趋势确认、降低左侧信号等级、增加回撤/破位过滤。
  - 将 `data/examples/genge_industry_cycle_manual.csv` 替换为可审计的行业周期数据维护流程。
  - 给 broad `step-days=1` 增加进度日志和性能优化；本轮 105 只股票耗时 3020.33 秒。
  - push 后观察 GitHub Actions，并把 CI 真实结果补入下一轮验收。
