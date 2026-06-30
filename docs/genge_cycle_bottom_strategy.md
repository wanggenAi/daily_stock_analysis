# 根哥周期底部硬逻辑策略

`src/strategies/genge_cycle_bottom` 是一个独立的 A 股历史研究模块，用来验证“低位 + 估值 + 财务安全 + 止跌确认 + 市场环境 + 行业周期”的候选股筛选逻辑。

当前定位是研究验证版：只读取公开行情、估值和财务数据；不接入中信证券或任何券商账户；不读取资产、持仓、密码、验证码；不自动买入、卖出、撤单；报告里的区间、仓位和止损只用于复盘研究，不是实盘操作指令。

## 策略周期定位

当前版本把 `60d` 定义为主观察周期，目标是验证“低位修复能否在约 60 个交易日内完成初步验证”。`20d` 用于观察过早信号和短期无修复风险，`120d` 用于观察修复是否延伸，`250d` 只作为“如果死拿”的风险压力测试。

因此报告中的 `250d raw hold` 不代表策略默认持有 250 日。更重要的字段是 `exit_adjusted_*`：它表示信号出现后，按退出策略在 60 日修复、趋势破位、止盈回撤或时间退出条件下模拟退出后的结果。

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
  --industry-evidence-file tests/fixtures/genge_cycle_bottom/industry_evidence.csv \
  --company-evidence-file tests/fixtures/genge_cycle_bottom/company_evidence.csv \
  --industry-evidence-schema config/industry_evidence_schema.yaml \
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
  --industry-evidence-file data/user_supplied/industry_cycle_evidence.csv \
  --company-evidence-file data/user_supplied/company_cycle_evidence.csv \
  --industry-evidence-schema config/industry_evidence_schema.yaml \
  --output-industry-evidence-cards \
  --output-cycle-turning-point-candidates \
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
- `--industry-evidence-file`：行业周期证据 CSV，建议由 `scripts/update_industry_evidence_from_research.py` 从本地研究记录生成。若使用 example/template 文件，报告会标为 `manual_template`。
- `--company-evidence-file`：公司层周期证据 CSV，用于判断公司是否跟随行业改善。
- `--industry-evidence-schema`：行业证据 schema，当前路径为 `config/industry_evidence_schema.yaml`。
- `--enable-hard-logic-filter` / `--min-hard-logic-level`：可选硬逻辑门槛，默认不破坏历史 fixture；开启后低于门槛的确认类信号会降级。
- `--output-industry-evidence-cards`：输出 `industry_evidence_cards.md/json`。
- `--output-cycle-turning-point-candidates`：输出 `cycle_turning_point_candidates.csv`。
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
- `baseline_comparison.json`：与 `config/genge_signal_quality_baseline.json` 中的 core/cycle/broad 基线做自动对比。
- `parameter_experiment.json` / `parameter_experiment.md`：小型参数切片实验，包含 train、validation、recent_2y 三段。
- `exit_policy_experiment.json` / `exit_policy_experiment.md`：退出策略参数实验，比较 `balanced_v1`、`balanced_v2_looser_trail`、`balanced_v3_strong_extend`、`balanced_v4_tighter_loss_looser_profit`、`balanced_v5_late_guardrail`、`balanced_v6_close_confirmed_stop`、`balanced_v7_double_close_stop`，只重算退出条件，不改变入场样本。
- `strict_observation_candidates.csv`：严格模拟观察候选，仅用于研究记录，不构成买入建议，不应自动交易。
- `research_observation_candidates.csv`：研究观察候选，门槛比 strict 更宽，但仍不构成买入建议，不应自动交易。
- `balanced_research_observation_candidates.csv`：按 `balanced_hybrid_60d_exit` 过滤后的研究观察候选，仅用于人工复核和模拟观察。
- `watch_only_candidates.csv`：趋势、行业周期、估值陷阱或执行风险仍需继续跟踪的 watch-only 样本。
- `industry_evidence_cards.md/json`：按行业汇总证据分、周期阶段、缺失项、过期项、候选股票和风险提示。
- `cycle_turning_point_candidates.csv`：周期拐点研究观察候选，要求低位、估值/财务不过差、趋势至少 MEDIUM、行业阶段为 BOTTOMING/RECOVERING、硬逻辑至少 MEDIUM。
- `pork_panel_deep_dive.md`：样板证据链路专项复核，文件名为兼容上一轮专项复核保留；内容从本次输入证据动态发现样板对象，不把猪肉、面板、牧原股份、TCL科技或其它股票硬编码成候选。
- `paper_observation_candidates.csv`：兼容旧文件名，内容等同严格模拟观察候选。

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
- `trend_confirmation_summary`：`NONE/WEAK/MEDIUM/STRONG` 趋势确认等级分布。
- `industry_cycle_quality_summary`：行业周期证据质量分布，取值包括 `missing`、`manual_template`、`user_supplied`、`provider_derived`、`verified`。
- `industry_evidence_quality_summary` / `industry_evidence_confidence_summary`：行业证据质量和置信度分布。模板或样例证据不会被当作权威结论。
- `industry_evidence_source_type_summary` / `company_evidence_source_type_summary` / `evidence_source_type_distribution`：行业和公司证据来源类型分布，用来区分 `official_report`、`company_announcement`、`exchange_disclosure`、`research_report_summary`、`news_summary`、`manual_template`、`user_supplied`、`provider_derived`、`verified` 和 `missing`。
- `hard_logic_level_summary`：`NONE/WEAK/MEDIUM/STRONG` 硬逻辑等级分布。`STRONG` 必须来自行业和公司证据一致改善，不能只靠价格、均线或评分。
- `industry_evidence_missing_count` / `company_evidence_missing_count`：行业和公司证据缺失数量。
- `cycle_turning_point_candidate_count`：周期拐点研究观察候选数量。
- `cycle_turning_point_candidate_count_by_industry`：周期拐点研究观察候选的行业分布。
- `execution_entry_quality_summary`：入口执行质量分布，取值为 `good/degraded/risky/unavailable`。
- `stop_policy_summary`：动态止损修正收益、止损触发率、是否可能改善回撤或截断反弹。
- `strategy_horizon_profile`：策略周期定位，固定写明主周期 `60d`、辅助周期 `20d/120d`、风险周期 `250d`。
- `primary_horizon_metrics`：60 日主周期收益、胜率、跑赢基准、raw 回撤和 exit-adjusted 回撤。
- `long_horizon_risk_metrics`：250 日 raw hold 风险压力测试和退出策略后的风险变化。
- `exit_policy_summary`：raw_hold、fixed_60d_time_exit、trend_break_exit、profit_trailing_exit、旧 `hybrid_60d_repair_exit`、新 `balanced_hybrid_60d_exit` 的退出后收益、回撤、持有天数和退出原因分布。
- `balanced_exit_policy_summary`：`balanced_hybrid_60d_exit` 的单独摘要，包含 60 日收益保留率、250 日回撤压降率和综合效率分。
- `exit_policy_by_trend_confirmation`：按 `WEAK/MEDIUM/STRONG` 趋势等级分层比较 raw hold、旧 hybrid 和 balanced hybrid。
- `exit_reason_diagnostics`：统计 STOP_LOSS、TREND_BREAK_CONFIRMED、TAKE_PROFIT_TRAIL、NO_REPAIR_40D、TIME_EXIT_60D、TREND_EXTENSION_90D 的触发占比和收益贡献，用来判断哪类退出最伤收益。
- `raw_stop_exit_comparison`：raw hold、原动态止损修正、退出策略三种口径的横向对比。
- `exit_policy_experiment`：不同退出参数在 train、validation、recent_2y 和全样本的稳定性对比。
- `return_retention_rate_60d` / `drawdown_reduction_rate_250d` / `exit_efficiency_score`：新 balanced 退出策略的收益保留、回撤压降和综合平衡指标。
- `strict_observation_candidate_count` / `research_observation_candidate_count` / `balanced_research_observation_candidate_count` / `watch_only_candidate_count`：严格候选、研究候选、balanced 研究候选和 watch-only 数量。它们都只是模拟观察和复盘入口。
- `baseline_comparison`：与上一个真实研究基线的 total、60 日收益、60 日胜率、60 日跑赢基准比例、250 日低点回撤对比；样本数下降超过 50% 会标记 `overfit_warning`。
- `quality_filter_summary`：飞刀风险、估值陷阱、财务缺失不确定和高执行风险统计。
- `history_sufficiency_quality_summary`：历史样本充分性分布，辅助识别 3 年低位样本是否缺少 5 年/10 年长周期验证。
- `long_term_position_risk_score_summary`：长期位置风险分布，辅助识别低位修复中仍可能继续探底的样本。
- `parameter_experiment`：小型参数实验摘要，用来判断过滤是否只在某一段历史中有效。
- `paper_trading_gate`：当前是否达到模拟盘观察门槛。

报告中的 `avg_return_*` 为向后兼容字段，当前等同于 `avg_net_return_*`，不得改成原始收益口径。

## Acceptance Gate

行业证据层启用时，报告中的最终行业证据验收枚举只使用：

- `FAIL_EVIDENCE_LAYER`。
- `PASS_INDUSTRY_EVIDENCE_FRAMEWORK`。
- `PASS_HARD_LOGIC_RESEARCH_READY`。
- `PASS_CYCLE_TURNING_POINT_SCREENER`。
- `PASS_PAPER_TRADING_CANDIDATE`。
- `PASS_PAPER_TRADING_READY`。

当行业证据来自 example/template/fixture 或缺少真实多源证据时，只能保守返回 `PASS_INDUSTRY_EVIDENCE_FRAMEWORK`；这表示框架、字段和报告输出可运行，不表示行业逻辑已被验证。

样板研究记录可以放在 `research/industry_cycle/`，并由 `scripts/update_industry_evidence_from_research.py` 生成 `data/user_supplied/*evidence.csv`。缺少 `source`、`date` 或必需字段的证据会进入 `rejected_evidence.csv`，不会被降级后混入正式证据。猪肉、面板、牧原股份、TCL科技只作为证据链路样板；最终候选可以来自任意行业，取决于“低周期 + 边际改善 + 个股拐点 + 风险可控”的通用证据标准。

`PASS_REAL_DATA_RESEARCH` 是真实公开数据研究链路通过，不代表可以买入或进入模拟盘。它必须至少满足：fixture smoke 已通过、真实公开数据运行通过、样本数不少于 100、无已知未来函数风险、无自动交易能力、data errors/provider errors 不严重，且估值和财务覆盖率都超过 30%（除非明确标记为纯价格研究）。收益期望、胜率、跑赢基准和回撤问题会保留在 `reasons` 中，用于阻止进入 `PASS_PAPER_TRADING_READY`。

`PASS_EXIT_POLICY_RESEARCH` 表示退出策略字段和退出策略实验已经可用，且没有出现“收益显著受损同时回撤也未改善”的失败组合。它仍只是研究通过。

`FAIL_EXIT_BALANCE` 表示 balanced 退出策略没有做到收益/回撤平衡：例如收益继续被明显砍掉、回撤没有明显降低，或样本稳定性不满足要求。

`PASS_BALANCED_EXIT_POLICY` 表示 broad 样本不少于 9000，样本数相对当前基线变化不低于 -10%，`balanced_hybrid_60d_exit` 的 60 日退出净收益、收益保留率、250 日回撤压降率、60 日胜率和 60 日跑赢基准达到最低研究门槛。它仍不是交易建议。

`PASS_60D_REPAIR_STRATEGY_VALIDATED` 表示在 balanced 退出策略基础上，broad 的 60 日退出净收益、收益保留率、胜率、跑赢基准、recent_2y 稳定性和研究候选数量达到更高门槛。它代表“60 日修复策略研究验证通过”，不代表可以自动交易。

`PASS_PAPER_TRADING_CANDIDATE` 表示在 `PASS_60D_REPAIR_STRATEGY_VALIDATED` 之上存在研究观察候选，可进入人工模拟观察清单。该枚举仍不是 `PASS_PAPER_TRADING_READY`，也不是交易建议。

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

不满足时会返回 `PASS_RESEARCH_ONLY`、`PASS_REAL_DATA_RESEARCH`、`PASS_EXIT_POLICY_RESEARCH`、`FAIL_REAL_DATA_FETCH`、`FAIL_DATA_QUALITY`、`FAIL_LOOKAHEAD_RISK`、`FAIL_STRATEGY_EXPECTANCY` 或 `FAIL_EXIT_POLICY` 等枚举。

## 当前已做的保守过滤

- `CONFIRM_BUY` 提高趋势确认门槛。
- `LEFT_SMALL_BUY` 至少需要 `trend_confirmation_level=WEAK`，`CONFIRM_BUY` 至少需要 `MEDIUM`，`ADD` 预留为 `STRONG`。
- 新增 `stabilization_days`、`downtrend_exhaustion_score`、`reclaim_ma_score`、`no_falling_knife_filter` 和 `second_low_confirmation`，低位但未止跌的样本最多观察。
- 财务缺失、行业周期缺失或行业周期证据质量为 `manual_template` 时，`CONFIRM_BUY` 会降级。
- 行业证据层缺失时，`industry_evidence_score=50` 且 `hard_logic_level=NONE/WEAK`；模板证据最多到 `MEDIUM`，过期或冲突证据会打 warning。
- 负向行业或公司证据会阻止确认类信号升级，只保留研究观察或拒绝。
- 新增 `value_trap_score`、`value_trap_flag` 和 `valuation_repair_signal`；低估值但财务缺失或恶化不默认安全。
- 新增 `dynamic_stop_loss`、`stop_loss_distance_pct`、`invalidation_level` 和 `post_entry_adverse_excursion_pct`；回测同时保留原始收益、净收益和止损修正收益。
- 新增退出策略回测：`fixed_60d_time_exit`、`trend_break_exit`、`profit_trailing_exit`、旧 `hybrid_60d_repair_exit` 和新 `balanced_hybrid_60d_exit`。同一天多条件触发时按 STOP_LOSS、趋势破位/均线丢失、止盈回撤、时间退出的顺序执行。
- `balanced_hybrid_60d_exit` 不覆盖旧 hybrid：默认观察 60 个交易日，STRONG 且 60 日仍在 MA20/MA60 上方时可延长到 90/120 日；20 日未修复不直接退出，40-55 日仍无修复才退出；MA20 破位要求连续确认，trailing stop 只用入场后的滚动最高收盘价。当前默认参数为 `balanced_v7_double_close_stop`，在不取消硬止损的前提下，对 `MEDIUM/STRONG` 趋势样本要求连续 2 个交易日收盘低于止损位才确认止损；`WEAK` 趋势样本和盘中深跌超过 hard intraday buffer 的样本仍立即按 STOP_LOSS 处理。
- 退出策略只使用信号之后的价格数据，`ma20_post/ma60_post` 只在 post-entry 窗口内计算，不参与信号生成。
- 止损距离过宽时，`CONFIRM_BUY` 会降级为更保守信号。
- 新增 `history_sufficiency_score/history_sufficiency_quality`、`long_term_position_risk_score`、`distance_to_ma250_pct` 和 `ma250_slope_pct`；长期位置风险高、历史样本不足且止损偏宽、MA250 深度弱势等样本会降级。
- `stop_loss_distance_pct <= 7` 且长期位置风险未高时，长期位置风险扣分会适度降低，避免把可控失效位的左侧观察样本全部过滤掉；宽止损和高长期风险降级规则不放松。
- 弱市场环境下会降低信号级别或只观察。
- 严重亏损、高负债、经营现金流异常等会进入风险标签。
- 涨停买入、跌停、缺失下一交易日、低流动性和异常跳空会进入执行诊断或风险标签。
- 所有未来收益只在信号生成之后由回测层计算，特征层按 `as_of_date` 截断数据。

## 2026-06-28 信号质量优化验收

本轮基于 `config/genge_signal_quality_baseline.json` 中 commit `b2a298b0` 的真实研究基线复核。

- pytest：39 passed，1 warning。
- fixture smoke：`reports/genge_cycle_bottom_ci_smoke/20260628_154457`，`total_signals=1451`，`data_failures=0`。
- real core：`reports/genge_signal_quality_core/20260628_154858`，耗时 224.37 秒，`total_signals=1663`，`data_failures=0`。
- real cycle：`reports/genge_signal_quality_cycle/20260628_160347`，耗时 873.21 秒，`total_signals=5091`，`data_failures=0`。
- real broad：`reports/genge_signal_quality_broad/20260628_163352`，耗时 1785.23 秒，`total_signals=11185`，`data_failures=0`。

broad 相比基线：60 日平均净收益 +1.2670，60 日胜率 +3.3642，60 日跑赢基准比例 +6.0326，250 日低点回撤 +0.1670，样本数下降 44.2867%，未触发大于 50% 的过拟合警告。

最终研究枚举：`PASS_REAL_DATA_RESEARCH`。该结论表示真实公开数据研究链路通过，且 broad 的 60 日胜率和跑赢基准明显改善；但 250 日低点回撤只改善 0.1670 个百分点，未达到至少改善 3 个百分点或优于 -28% 的最低线，因此不能声明 `PASS_SIGNAL_QUALITY_IMPROVED`，也不能视为模拟盘就绪。

## 2026-06-28 长周期风险与样本恢复复核

Loop 2 新增长期位置风险和历史样本充分性门控后，core/cycle/broad 的 60 日收益、胜率和跑赢基准继续改善，但 broad 样本数下降 53.3323%，触发 `overfit_warning`；broad 250 日低点回撤为 -30.1682，仍未达到至少改善 3 个百分点或优于 -28% 的最低线。

Loop 3 只放松紧止损、非高长期风险样本的评分扣分，不放开宽止损和高长期风险降级。最新真实运行结果：

- pytest：44 passed，1 warning。
- fixture smoke：`reports/genge_cycle_bottom_ci_smoke/20260628_190621`，`total_signals=1451`，`data_failures=0`。
- real core：`reports/genge_signal_quality_core/20260628_191009`，耗时 211.95 秒，`total_signals=1532`，`data_failures=0`。
- real cycle：`reports/genge_signal_quality_cycle/20260628_192527`，耗时 903.14 秒，`total_signals=4571`，`data_failures=0`。
- real broad：`reports/genge_signal_quality_broad/20260628_195432`，耗时 1735.27 秒，`total_signals=9645`，`data_failures=0`。

broad 相比基线：60 日平均净收益 +1.8959，60 日胜率 +3.9829，60 日跑赢基准比例 +6.2084，250 日低点回撤 +1.1159，样本数下降 51.9576%，仍触发大于 50% 的过拟合警告。

最终研究枚举仍为 `PASS_REAL_DATA_RESEARCH`。当前版本可以用于公开数据研究和复盘报告生成，但不能声明 `PASS_SIGNAL_QUALITY_IMPROVED`，也不能视为模拟盘就绪。下一轮重点应继续处理长期深跌后继续探底、行业周期证据不足和 250 日低点回撤控制。

## 2026-06-28 退出策略与 60 日修复定位复核

本轮基于 commit `724b8f9d` 的 Loop 3 结果做退出策略研究，不继续压缩样本。`config/genge_signal_quality_baseline.json` 已更新为 `724b8f9d` 基线，core/cycle/broad 本轮样本变化均为 0%，`overfit_warning=false`。

- pytest：52 passed，1 warning。
- fixture smoke：`reports/genge_cycle_bottom_ci_smoke/20260628_233336`，耗时 96 秒，`total_signals=1451`，`data_failures=0`。
- real core：`reports/genge_exit_policy_core/20260628_224308`，耗时 235.51 秒，`total_signals=1532`，`data_failures=0`，`pe_missing_count=386`，`financial_missing_count=0`。
- real cycle：`reports/genge_exit_policy_cycle/20260628_225819`，耗时 903.44 秒，`total_signals=4571`，`data_failures=0`，`pe_missing_count=798`，`financial_missing_count=0`。
- real broad：`reports/genge_exit_policy_broad/20260628_232921`，耗时 1855.03 秒，`total_signals=9645`，`data_failures=0`，`pe_missing_count=688`，`financial_missing_count=0`。

broad 关键结论：60 日 raw 净收益 2.2924，60 日胜率 46.8619，60 日跑赢基准 46.5272；250 日 raw hold 低点回撤 -30.1289。`hybrid_60d_repair_exit` 后，60 日退出净收益为 0.1857，250 日退出回撤为 -4.7574，回撤降低 84.2098%，但 60 日收益影响为 -2.1067。

最终研究枚举为 `PASS_EXIT_POLICY_RESEARCH`。退出策略研究链路通过，且显著降低 250 日“死拿”风险；但 broad 的 60 日退出净收益被削弱，60 日胜率和跑赢基准仍低于更高门槛，因此不能声明 `PASS_60D_REPAIR_STRATEGY_VALIDATED`，也不能视为模拟盘就绪。

## 2026-06-29 Balanced 退出策略收益保留复核

本轮基于 commit `fa918e90` 之后的退出策略研究结果，新增 `balanced_v6_close_confirmed_stop` 参数组，并将其作为 `balanced_hybrid_60d_exit` 默认参数。修改点只在退出策略：盘中轻微跌破止损但收盘重新站回止损位时不立即退出；若盘中深跌超过 hard intraday buffer，仍按 STOP_LOSS 优先退出。入场信号、股票池、数据源和候选筛选不做放宽。

- pytest：60 passed，1 warning。
- fixture smoke：`reports/genge_cycle_bottom_ci_smoke/20260629_224223`，`total_signals=1451`，`data_failures=0`。
- real core：`reports/genge_exit_balance_core/20260629_225150`，耗时 289.01 秒，`total_signals=1533`，`data_failures=0`，`pe_missing_count=386`，`pb_missing_count=0`，`financial_missing_count=0`。
- real cycle：`reports/genge_exit_balance_cycle/20260629_231021`，耗时 1075.91 秒，`total_signals=4573`，`data_failures=0`，`pe_missing_count=798`，`pb_missing_count=0`，`financial_missing_count=0`。
- real broad：`reports/genge_exit_balance_broad/20260629_234715`，耗时 2183.43 秒，`total_signals=9628`，`data_failures=0`，`pe_missing_count=688`，`pb_missing_count=0`，`financial_missing_count=0`。

broad 关键结论：`balanced_hybrid_60d_exit` 的 60 日净收益从上一轮 1.0379 提升到 1.7329，收益保留率从 45.1045% 提升到 75.3075%；250 日退出回撤为 -9.7182，仍比 raw hold 的 -30.1780 明显更低，回撤压降率为 67.7971%。样本数保持 9628，未通过压缩样本达成指标。

与旧 hybrid 对比：旧 `hybrid_60d_repair_exit` 的 broad 60 日退出净收益为 0.1889，250 日退出回撤为 -4.7560；新的 balanced 版本保留了更多 60 日修复收益，但接受更宽的退出回撤，以换取收益/回撤平衡。

最终研究枚举仍为 `PASS_EXIT_POLICY_RESEARCH`。原因是 broad 已达到 `total_signals>=9000`、`balanced_exit_net_return_60d>=1.2%`、收益保留率 `>=50%`、250 日回撤压降 `>=60%` 和跑赢基准 `>=46%`，但 balanced 退出后的 60 日胜率为 33.7001%，低于 `PASS_BALANCED_EXIT_POLICY` 的胜率门槛，因此不能升级为 `PASS_BALANCED_EXIT_POLICY`、`PASS_PAPER_TRADING_CANDIDATE` 或 `PASS_PAPER_TRADING_READY`。

## 2026-06-30 Double Close Stop 退出策略复核

本轮继续基于 commit `fa918e90` 的退出策略收益/回撤平衡目标，新增 `balanced_v7_double_close_stop` 参数组，并将其作为 `balanced_hybrid_60d_exit` 默认参数。修改点只在退出策略：`MEDIUM/STRONG` 趋势样本需要连续 2 个交易日收盘低于止损位才确认 `STOP_LOSS`；`WEAK` 趋势样本不延迟止损，盘中深跌超过 hard intraday buffer 时也不延迟。入场信号、股票池、数据源和候选筛选不做放宽。

- pytest：62 passed，1 warning。
- fixture smoke：`reports/genge_cycle_bottom_ci_smoke/20260630_001300`，耗时 159.13 秒，`total_signals=1451`，`data_failures=0`。
- real core：`reports/genge_exit_balance_core/20260630_001811`，耗时 305.26 秒，`total_signals=1535`，`data_failures=0`，`pe_missing_count=386`，`pb_missing_count=0`，`financial_missing_count=0`。
- real cycle：`reports/genge_exit_balance_cycle/20260630_003658`，耗时 1120.30 秒，`total_signals=4576`，`data_failures=0`，`pe_missing_count=797`，`pb_missing_count=0`，`financial_missing_count=0`。
- real broad：`reports/genge_exit_balance_broad/20260630_011457`，耗时 2256.74 秒，`total_signals=9627`，`data_failures=0`，`pe_missing_count=687`，`pb_missing_count=0`，`financial_missing_count=0`。

broad 关键结论：`balanced_hybrid_60d_exit` 的 60 日净收益从 v6 的 1.7329 提升到 1.9083，收益保留率从 75.3075% 提升到 82.7752%；250 日退出回撤从 -9.7182 放宽到 -10.0461，仍比 raw hold 的 -30.1730 明显更低，回撤压降率为 66.7050%。样本数保持 9627，未通过压缩样本达成指标。

与旧 hybrid 对比：旧 `hybrid_60d_repair_exit` 的 broad 60 日退出净收益为 0.1900，250 日退出回撤为 -4.7556；新的 v7 balanced 版本保留了更多 60 日修复收益，但接受更宽的退出回撤，以换取收益/回撤平衡。

最终研究枚举仍为 `PASS_EXIT_POLICY_RESEARCH`。原因是 broad 达到 `total_signals>=9000`、`balanced_exit_net_return_60d>=1.2%`、收益保留率 `>=50%`、250 日回撤压降 `>=60%` 和跑赢基准 `>=46%`，但 balanced 退出后的 60 日胜率为 34.3115%，低于 `PASS_BALANCED_EXIT_POLICY` 的胜率门槛，因此不能升级为 `PASS_BALANCED_EXIT_POLICY`、`PASS_PAPER_TRADING_CANDIDATE` 或 `PASS_PAPER_TRADING_READY`。

## 已知限制

- 行业周期数据仍偏浅，第一版主要依赖人工维护样例和可得公开数据。仓库 `data/examples` 内文件只用于格式示范和研究验证。
- 估值、财务字段依赖数据源可得性，缺失会进入 `missing_fields`，不会补假数据。
- 真实数据源可能超时、限流或字段变化，运行失败要看 `data_errors`。
- 已记录部分涨跌停、停牌/缺失、低流动性和跳空风险，但尚未完整模拟真实成交队列、除权复权差异、真实资金曲线和组合级仓位。
- 没有真实组合 equity curve。
- 没有接入中信证券客户端 K 线/F10 复核模块。
- 没有任何自动交易或券商账户读取能力。
