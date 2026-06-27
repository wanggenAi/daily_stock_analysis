# 根哥周期底部硬逻辑策略

`src/strategies/genge_cycle_bottom` 是一个独立的 A 股历史研究模块，用来验证“低位 + 估值 + 财务安全 + 止跌确认 + 市场环境 + 行业周期”的候选股筛选逻辑。

当前定位是研究验证版：只读取公开行情、估值和财务数据；不接入中信证券或任何券商账户；不读取资产、持仓、密码、验证码；不自动买入、卖出、撤单；报告里的区间、仓位和止损只用于复盘研究，不是交易指令。

## 运行环境

建议使用 Python 3.10+。CI 的 fixture 验证使用 Python 3.11。

```bash
python3 -m pip install -r requirements.txt
```

如果只跑本策略的 fixture 测试，最小依赖是 `pytest pandas numpy matplotlib pyyaml requests`。

## Fixture Smoke

fixture smoke 不访问网络，用于验证代码、报告结构和反未来函数保护：

```bash
python3 -m src.strategies.genge_cycle_bottom.cli \
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

GitHub Actions 工作流在 `.github/workflows/genge-cycle-bottom.yml`，只跑 `tests/test_genge_cycle_bottom_*.py` 和上面的 fixture smoke，不依赖 AKShare 网络数据。

## 真实数据研究

真实数据入口：

```bash
python3 scripts/run_genge_real_research.py \
  --stock-pool-file stock_pools/genge_core_pool.txt \
  --years 5 \
  --benchmark 000300 \
  --output-dir reports/genge_cycle_bottom_real \
  --max-codes 20 \
  --step-days 1 \
  --auto-fetch-valuation \
  --auto-fetch-financial \
  --industry-cycle-file data/examples/genge_industry_cycle_manual.csv \
  --fixture-smoke-passed \
  --ci-passed
```

可选参数：

- `--stock-pool-file`：股票池文件，格式为 `code` 或 `code,name,industry`。
- `--years`：历史年数，建议先跑 5 年，再用 10 年复核。
- `--benchmark`：支持 `000300`、`000905`、`000985`。
- `--max-codes`：本地烟测限制股票数量，默认 20。
- `--step-days`：扫描步长，正式研究默认 1；越小越慢。`--fast-smoke` 会在没有显式设置 `--step-days` 时使用 20。
- `--fee-bps` / `--slippage-bps`：交易成本和滑点，summary 默认使用净收益口径。
- `--auto-fetch-valuation`：缺少估值 CSV 时，尝试通过公开 AKShare 接口拉取 PE/PB/总市值，并把成功结果缓存到 `data/cache/genge_fundamentals/valuation`。
- `--auto-fetch-financial`：缺少财务 CSV 时，尝试通过公开 AKShare 接口拉取财务指标，并把成功结果缓存到 `data/cache/genge_fundamentals/financial`。
- `--fundamental-cache-dir`：估值/财务缓存目录，默认 `data/cache/genge_fundamentals`。缓存目录被 `.gitignore` 忽略。
- `--industry-cycle-file`：行业周期人工样例或用户维护文件。仓库内的 `data/examples/genge_industry_cycle_manual.csv` 只是研究样例，不是权威行业判断。
- `--stock-industry-map`：当股票池没有行业列时，用 CSV 补充 `code,industry` 映射。
- `--fixture-smoke-passed`：真实研究前已经完成 fixture smoke 时传入，用于验收枚举上下文；不会改变信号生成逻辑。
- `--ci-passed`：GitHub Actions fixture CI 已经观察通过时传入，用于验收枚举上下文；不会改变信号生成逻辑。

内置股票池：

- `stock_pools/genge_core_pool.txt`：12 只核心周期/低位修复观察池。
- `stock_pools/genge_cycle_pool.txt`：50 只周期行业池。
- `stock_pools/genge_broad_pool.txt`：100+ 只中大市值扩展池。

真实数据通过 `DataFetcherManager` 拉取，优先使用仓库既有数据源链路。若 AKShare 或其他公开源失败，错误会写入 `summary.json -> diagnostics -> data_errors`，不会伪造成功数据。

估值和财务自动抓取只使用公开数据源。`summary.json -> diagnostics -> provider_errors` 会记录 PE/PB/财务 provider 的异常；`valuation_coverage_rate`、`financial_coverage_rate`、`pe_missing_count`、`pb_missing_count` 和 `financial_missing_count` 用来判断基本面字段是否足够可信。

## 输出文件

每次运行会生成一个时间戳目录，例如：

```text
reports/genge_cycle_bottom_real/20260627_203000/
```

目录内包含：

- `summary.md`：中文摘要、分组结果、失败原因、验收枚举。
- `summary.json`：机器可读统计结果。
- `signal_details.csv`：逐条历史信号明细。

当前模块是研究回测，不生成实盘委托，也不打开券商页面。

## Summary 解释

重点字段：

- `total_signals`：可验证历史信号数。少于 100 只适合看机制，不适合判断策略稳定性。
- `avg_net_return_20d/60d/120d/250d`：扣除 fee/slippage 后的平均净收益。
- `avg_raw_return_*`：未扣交易成本的原始收益，只做对照，不能替代净收益。
- `win_rate_*`：对应持有周期净收益大于 0 的比例。
- `benchmark_outperform`：20/60/120/250 日跑赢基准比例。
- `low_max_drawdown` / `drawdown_diagnostics`：默认使用低点口径回撤，比收盘口径更保守。
- `industry_summary`：分行业统计，看哪些行业拖累或贡献最大。
- `signal_type_summary`：比较 `LEFT_SMALL_BUY` 和 `CONFIRM_BUY` 谁更有效。
- `time_split_summary`：前半段、后半段、最近两年表现。
- `failure_reason_summary`：对亏损样本归因，包括买太早、趋势未确认、财务缺失或恶化、行业周期判断不足等。
- `valuation_coverage_rate` / `financial_coverage_rate`：估值和财务字段覆盖率。两者都低时，不能按完整基本面研究通过。
- `pe_missing_count` / `pb_missing_count` / `financial_missing_count`：PE、PB、财务字段缺失数量。
- `execution_diagnostics`：涨停买入风险、跌停/停牌/缺失 bar、低流动性、异常跳空等可成交诊断。该字段是研究风控提示，不代表真实委托结果。
- `paper_trading_gate`：当前是否达到模拟盘观察门槛。

报告中的 `avg_return_*` 为向后兼容字段，当前等同于 `avg_net_return_*`，不得改成原始收益口径。

## Acceptance Gate

`PASS_REAL_DATA_RESEARCH` 是真实公开数据研究链路通过，不代表可以买入或进入模拟盘。它必须至少满足：fixture smoke 已通过、真实公开数据运行通过、样本数不少于 100、无已知未来函数风险、无自动交易能力、data errors/provider errors 不严重，且估值和财务覆盖率都超过 30%（除非明确标记为纯价格研究）。收益期望、胜率、跑赢基准和回撤问题会保留在 `reasons` 中，用于阻止进入 `PASS_PAPER_TRADING_READY`。

`PASS_PAPER_TRADING_READY` 必须同时满足：

- CI 通过。
- fixture smoke 通过。
- 真实小池 5 年运行通过。
- 真实小池 10 年运行通过，或清楚记录为安全降级。
- `total_signals >= 200`。
- 估值覆盖率和财务覆盖率都超过 30%，或明确标记为纯价格研究。
- 可成交风险诊断占比不超过 20%。
- 60 日平均净收益大于 0。
- 120 日平均净收益大于 0；若 120 日不佳，只能明确降级为 20/60 日短中期研究。
- 60 日胜率不低于 52%。
- 60 日跑赢基准比例不低于 50%。
- 250 日低点回撤不过大。
- 最近两年没有明显失效。
- 无未来函数风险。
- 无自动交易能力。

不满足时会返回 `PASS_RESEARCH_ONLY`、`PASS_REAL_DATA_RESEARCH`、`FAIL_REAL_DATA_FETCH`、`FAIL_DATA_QUALITY`、`FAIL_LOOKAHEAD_RISK` 或 `FAIL_STRATEGY_EXPECTANCY` 等枚举。

## 当前已做的保守过滤

- `CONFIRM_BUY` 提高趋势确认门槛。
- 财务缺失或行业周期缺失时，`CONFIRM_BUY` 会降级为 `LEFT_SMALL_BUY`。
- 弱市场环境下会降低信号级别或只观察。
- 严重亏损、高负债、经营现金流异常等会进入风险标签。
- 涨停买入、跌停、缺失下一交易日、低流动性和异常跳空会进入执行诊断或风险标签。
- 所有未来收益只在信号生成之后由回测层计算，特征层按 `as_of_date` 截断数据。

## 已知限制

- 行业周期数据仍偏浅，第一版主要依赖人工维护样例和可得公开数据。仓库 `data/examples` 内文件只用于格式示范和研究验证。
- 估值、财务字段依赖数据源可得性，缺失会进入 `missing_fields`，不会补假数据。
- 真实数据源可能超时、限流或字段变化，运行失败要看 `data_errors`。
- 已记录部分涨跌停、停牌/缺失、低流动性和跳空风险，但尚未完整模拟真实成交队列、除权复权差异、真实资金曲线和组合级仓位。
- 没有真实组合 equity curve。
- 没有接入中信证券客户端 K 线/F10 复核模块。
- 没有任何自动交易或券商账户读取能力。
