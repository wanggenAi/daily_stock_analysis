# GenGe Signal Quality Loop Progress

## Loop 1

- 本轮目标：针对上一版真实研究结果中的买太早、趋势未确认、止损不够严格、估值陷阱和执行风险，做信号质量优化，不新增回测外功能，不接入券商。
- 针对失败原因：买太早、趋势未确认、止损不够严格、估值陷阱、行业周期证据不足、信号日执行入口风险。
- 修改文件：`src/strategies/genge_cycle_bottom/features.py`、`strategy.py`、`metrics.py`、`report.py`、`tests/test_genge_cycle_bottom_*.py`、`LOOP_PROGRESS.md`、`LOOP_ACCEPTANCE_REPORT.md`、`docs/genge_cycle_bottom_strategy.md`。
- 修改策略规则：新增信号日执行风险评分，涨停/跌停、异常日内波动、低流动性和当日放量尖峰会降级；动态止损改为按 MA60、ATR、近期平台低点、5 年低点和 12% 风险上限综合取更紧失效位；稳定天数不足 5 日或止损距离过宽时，确认类信号降级为观察或小仓试探；模拟观察清单只保留趋势、估值、止损、执行风险和行业/大盘证据同时通过的候选。
- pytest：`/Users/seker./.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest tests/test_genge_cycle_bottom_*.py -q`，39 passed，1 warning。
- fixture：`reports/genge_cycle_bottom_ci_smoke/20260628_154457`，`total_signals=1451`，`data_failures=0`。
- real core：`reports/genge_signal_quality_core/20260628_154858`，耗时 224.37 秒，`total_signals=1663`，`data_failures=0`，`pe_missing_count=392`，`pb_missing_count=0`，`financial_missing_count=0`，`risk_review_count=5`。
- real cycle：`reports/genge_signal_quality_cycle/20260628_160347`，耗时 873.21 秒，`total_signals=5091`，`data_failures=0`，`pe_missing_count=849`，`pb_missing_count=0`，`financial_missing_count=0`，`risk_review_count=5`。
- real broad：`reports/genge_signal_quality_broad/20260628_163352`，耗时 1785.23 秒，`total_signals=11185`，`data_failures=0`，`pe_missing_count=752`，`pb_missing_count=0`，`financial_missing_count=0`，`risk_review_count=5`。
- baseline comparison：core 60 日平均净收益 +0.6853、胜率 +2.0251、跑赢基准 +2.7658、250 日低点回撤 -0.0661；cycle 60 日平均净收益 +1.0555、胜率 +2.7534、跑赢基准 +3.4244、250 日低点回撤 -0.1526；broad 60 日平均净收益 +1.2670、胜率 +3.3642、跑赢基准 +6.0326、250 日低点回撤 +0.1670。
- signal count change：core -42.0961%，cycle -41.0149%，broad -44.2867%，均未触发大于 50% 的样本骤降警告。
- win rate delta：core +2.0251，cycle +2.7534，broad +3.3642。
- outperform delta：core +2.7658，cycle +3.4244，broad +6.0326。
- drawdown delta：core -0.0661，cycle -0.1526，broad +0.1670。
- overfit warning：core/cycle/broad 均为 false。
- gate verdict：三组真实运行的 `paper_trading_gate` 均为 `PASS_REAL_DATA_RESEARCH`；broad 60 日胜率和跑赢基准改善达到要求，但 250 日低点回撤只改善 0.1670 个百分点，未达到至少改善 3 个百分点或优于 -28% 的最低线，因此本轮信号质量枚举仍保持 `PASS_REAL_DATA_RESEARCH`。
- 下一步：继续专门处理 250 日低点回撤和行业周期证据；当前版本可作为真实数据研究结果推送，但不能声明模拟盘就绪或信号质量完整通过。

## Loop 2

- 本轮目标：针对 Loop 1 的 250 日低点回撤不足，新增长期价格位置和历史样本充分性风控，不新增回测外功能，不接入券商。
- 修改策略规则：新增 `history_sufficiency_score/history_sufficiency_quality`、`long_term_position_risk_score`、`distance_to_ma250_pct`、`ma250_slope_pct`；长期位置风险高、历史样本不足且止损偏宽、MA250 深度弱势等样本进入风险标签或降级。
- pytest：`tests/test_genge_cycle_bottom_*.py`，42 passed，1 warning。
- fixture：`reports/genge_cycle_bottom_ci_smoke/20260628_170042`，`data_failures=0`。
- real core：`reports/genge_signal_quality_core/20260628_181235`，耗时 210.97 秒，`total_signals=1490`，`data_failures=0`，`pe_missing_count=384`，`pb_missing_count=0`，`financial_missing_count=0`，`risk_review_count=5`。
- real cycle：`reports/genge_signal_quality_cycle/20260628_182725`，耗时 882.18 秒，`total_signals=4407`，`data_failures=0`，`pe_missing_count=783`，`pb_missing_count=0`，`financial_missing_count=0`，`risk_review_count=5`。
- real broad：`reports/genge_signal_quality_broad/20260628_185643`，耗时 1746.06 秒，`total_signals=9369`，`data_failures=0`，`pe_missing_count=680`，`pb_missing_count=0`，`financial_missing_count=0`，`risk_review_count=5`。
- baseline comparison：core 60 日平均净收益 +1.4789、胜率 +4.0981、跑赢基准 +3.7460、250 日低点回撤 +0.1287；cycle 60 日平均净收益 +1.9428、胜率 +3.7444、跑赢基准 +4.1353、250 日低点回撤 +0.4892；broad 60 日平均净收益 +1.9071、胜率 +3.9650、跑赢基准 +5.7712、250 日低点回撤 +1.0766。
- signal count change：core -48.1198%，cycle -48.9399%，broad -53.3323%；broad 触发大于 50% 的样本骤降警告。
- 失败归因：broad 亏损样本中行业周期判断不足 6377、止损不够严格 6258、买太早 5468、估值陷阱 3858、持有周期不适合 1442、趋势未确认 371、长周期位置风险 109。
- 结论：真实数据链路仍为 `PASS_REAL_DATA_RESEARCH`，60 日质量继续改善，但 broad 样本骤降超过 50%，且 250 日低点回撤 -30.1682 未达到至少改善 3 个百分点或优于 -28% 的最低线，不能声明 `PASS_SIGNAL_QUALITY_IMPROVED`。

## Loop 3

- 本轮目标：在不放开硬风险门槛的前提下，恢复“紧止损且非高长期位置风险”的样本，降低 Loop 2 的 broad 样本骤降风险。
- 修改策略规则：`stop_loss_distance_pct <= 7` 且 `long_term_position_risk_score < 45` 时，长期位置风险扣分从 5% 降到 2.5%；`limited` 历史样本在紧止损下历史扣分从 1.5 降到 0.5；宽止损和高长期风险降级规则保持不变。
- pytest：`/Users/seker./.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest tests/test_genge_cycle_bottom_*.py -q`，44 passed，1 warning。
- fixture：`reports/genge_cycle_bottom_ci_smoke/20260628_190621`，`total_signals=1451`，`data_failures=0`。
- real core：`reports/genge_signal_quality_core/20260628_191009`，耗时 211.95 秒，`total_signals=1532`，`data_failures=0`，`pe_missing_count=386`，`pb_missing_count=0`，`financial_missing_count=0`，`risk_review_count=5`。
- real cycle：`reports/genge_signal_quality_cycle/20260628_192527`，耗时 903.14 秒，`total_signals=4571`，`data_failures=0`，`pe_missing_count=798`，`pb_missing_count=0`，`financial_missing_count=0`，`risk_review_count=5`。
- real broad：`reports/genge_signal_quality_broad/20260628_195432`，耗时 1735.27 秒，`total_signals=9645`，`data_failures=0`，`pe_missing_count=688`，`pb_missing_count=0`，`financial_missing_count=0`，`risk_review_count=5`。
- baseline comparison：core 60 日平均净收益 +1.3199、胜率 +3.4928、跑赢基准 +3.7627、250 日低点回撤 +0.0072；cycle 60 日平均净收益 +1.9110、胜率 +3.7011、跑赢基准 +4.3720、250 日低点回撤 +0.4241；broad 60 日平均净收益 +1.8959、胜率 +3.9829、跑赢基准 +6.2084、250 日低点回撤 +1.1159。
- signal count change：core -46.6574%，cycle -47.0397%，broad -51.9576%；broad 样本数从 Loop 2 的 9369 恢复到 9645，但仍触发大于 50% 的样本骤降警告。
- 失败归因：broad 亏损样本中行业周期判断不足 6591、止损不够严格 6470、买太早 5626、估值陷阱 3954、持有周期不适合 1511、趋势未确认 384、长周期位置风险 109、大盘环境差 52。
- 额外观察：Loop 3 相比 Loop 2 新增 276 个 broad 样本，新增样本 60 日平均净收益 1.9127、胜率 47.4638%、跑赢基准 61.2319%、250 日低点回撤 -29.0402，未明显拖累整体质量。
- 结论：真实数据链路仍为 `PASS_REAL_DATA_RESEARCH`，但 broad 样本骤降仍为 -51.9576%，250 日低点回撤 -30.1289 仍未达到至少改善 3 个百分点或优于 -28% 的最低线。当前不能声明 `PASS_SIGNAL_QUALITY_IMPROVED`，下一轮应继续处理长期深跌后继续探底、行业周期证据不足和回撤控制。

## Loop 4

- 本轮目标：基于 commit `724b8f9d`，把策略定位改为“60 日修复观察为主、20/120 日为辅助、250 日为风险压力测试”，新增持仓退出策略研究，不新增回测外功能，不接入券商客户端。
- 修改策略规则：新增 `fixed_60d_time_exit`、`trend_break_exit`、`profit_trailing_exit`、`hybrid_60d_repair_exit`；同日触发顺序为 STOP_LOSS、趋势破位/均线丢失、止盈回撤、时间退出；退出策略只使用信号之后的价格数据，`ma20_post/ma60_post` 只在 post-entry 窗口内计算。
- 新增报告字段：`strategy_primary_horizon=60d`、`strategy_secondary_horizon=20d/120d`、`strategy_risk_horizon=250d`、`primary_horizon_metrics`、`long_horizon_risk_metrics`、`exit_policy_summary`、`raw_stop_exit_comparison`、`exit_policy_experiment`。
- 新增输出文件：`exit_policy_experiment.json/md`、`strict_observation_candidates.csv`、`research_observation_candidates.csv`；候选文件均写明“仅用于模拟观察和复盘，不构成买入建议，不应自动交易。”
- 基线口径：`config/genge_signal_quality_baseline.json` 更新为 `724b8f9d` 的 Loop 3 结果，用于判断本轮是否相对当前版本继续压缩样本；core/cycle/broad 当前样本变化均为 0%，`overfit_warning=false`。
- pytest：`/Users/seker./.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest tests/test_genge_cycle_bottom_*.py -q`，52 passed，1 warning。
- fixture：`reports/genge_cycle_bottom_ci_smoke/20260628_233336`，耗时 96 秒，`total_signals=1451`，`data_failures=0`。
- real core：`reports/genge_exit_policy_core/20260628_224308`，耗时 235.51 秒，`total_signals=1532`，`data_failures=0`，`provider_error_count=0`，`pe_missing_count=386`，`pb_missing_count=0`，`financial_missing_count=0`，`risk_review_count=5`，严格候选 0，研究候选 694。
- real cycle：`reports/genge_exit_policy_cycle/20260628_225819`，耗时 903.44 秒，`total_signals=4571`，`data_failures=0`，`provider_error_count=0`，`pe_missing_count=798`，`pb_missing_count=0`，`financial_missing_count=0`，`risk_review_count=5`，严格候选 0，研究候选 1872。
- real broad：`reports/genge_exit_policy_broad/20260628_232921`，耗时 1855.03 秒，`total_signals=9645`，`data_failures=0`，`provider_error_count=0`，`pe_missing_count=688`，`pb_missing_count=0`，`financial_missing_count=0`，`risk_review_count=5`，严格候选 0，研究候选 4676。
- core 指标：60 日 raw 净收益 0.2042、胜率 47.5378、跑赢基准 44.6487；250 日 raw hold 低点回撤 -31.5753；hybrid 60 日退出净收益 0.5716，250 日退出回撤 -4.7488，回撤降低 84.9604%。
- cycle 指标：60 日 raw 净收益 3.8339、胜率 50.5414、跑赢基准 49.1934；250 日 raw hold 低点回撤 -31.0902；hybrid 60 日退出净收益 1.0512，250 日退出回撤 -4.5716，回撤降低 85.2957%，60 日收益影响 -2.7827。
- broad 指标：60 日 raw 净收益 2.2924、胜率 46.8619、跑赢基准 46.5272；250 日 raw hold 低点回撤 -30.1289；hybrid 60 日退出净收益 0.1857，250 日退出回撤 -4.7574，回撤降低 84.2098%，60 日收益影响 -2.1067。
- 结论：退出策略显著降低 250 日“死拿”风险，研究链路和输出文件通过，最终枚举为 `PASS_EXIT_POLICY_RESEARCH`。但 broad 的 60 日退出净收益被削弱，且 60 日胜率低于 52%、跑赢基准比例低于 50%，因此不能提升到 `PASS_60D_REPAIR_STRATEGY_VALIDATED`，也不能输出 `PASS_PAPER_TRADING_READY`。

## Loop 5

- 本轮目标：基于 commit `fa918e90` 之后的当前代码进入“退出策略收益/回撤平衡优化阶段”，新增 `balanced_hybrid_60d_exit`，在不改变入场样本、不接入券商、不自动交易的前提下，尽量保留 60 日修复收益并继续压低 250 日 raw hold 风险。
- 修改的退出参数：保留旧 `hybrid_60d_repair_exit`，新增 `balanced_v1`、`balanced_v2_looser_trail`、`balanced_v3_strong_extend`、`balanced_v4_tighter_loss_looser_profit`、`balanced_v5_late_guardrail`；当前默认推荐 `balanced_v5_late_guardrail`，参数为 stop loss 上限 12%/STRONG 14%、trailing 18% 启动且 12% 回撤触发、浮盈 26% 后 8% 回撤触发、趋势破坏最早 45 日确认、无修复 55 日退出、STRONG 最长 90 日。
- 修改文件：`src/strategies/genge_cycle_bottom/backtest.py`、`metrics.py`、`report.py`、`acceptance.py`、`tests/test_genge_cycle_bottom_backtest.py`、`tests/test_genge_cycle_bottom_report_cli.py`、`docs/genge_cycle_bottom_strategy.md`、`docs/CHANGELOG.md`、`LOOP_PROGRESS.md`、`LOOP_ACCEPTANCE_REPORT.md`。
- pytest 结果：`/Users/seker./.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest tests/test_genge_cycle_bottom_*.py -q`，59 passed，1 warning。
- fixture smoke 结果：`reports/genge_cycle_bottom_ci_smoke/20260629_195104`，`total_signals=1451`，`data_failures=0`。
- real core result：`reports/genge_exit_balance_core/20260629_185341`，耗时 338.19 秒，`total_signals=1533`，`data_failures=0`，`provider_error_count=0`，`pe_missing_count=386`，`pb_missing_count=0`，`financial_missing_count=0`，`risk_review_count=5`，`paper_trading_gate=PASS_EXIT_POLICY_RESEARCH`。
- real cycle result：`reports/genge_exit_balance_cycle/20260629_191109`，耗时 1027.08 秒，`total_signals=4573`，`data_failures=0`，`provider_error_count=0`，`pe_missing_count=798`，`pb_missing_count=0`，`financial_missing_count=0`，`risk_review_count=5`，`paper_trading_gate=PASS_EXIT_POLICY_RESEARCH`。
- real broad result：`reports/genge_exit_balance_broad/20260629_194612`，耗时 2082.33 秒，`total_signals=9628`，`data_failures=0`，`provider_error_count=0`，`pe_missing_count=688`，`pb_missing_count=0`，`financial_missing_count=0`，`risk_review_count=5`，`paper_trading_gate=PASS_EXIT_POLICY_RESEARCH`。
- raw_hold vs old_hybrid vs balanced_hybrid：core raw 60 日净收益 0.2042、旧 hybrid 0.5716、balanced 1.3564；cycle raw 3.8339、旧 hybrid 1.0512、balanced 2.8661；broad raw 2.3011、旧 hybrid 0.1889、balanced 1.0379。balanced 明显高于旧 hybrid，但 broad 尚未达到 1.2% 最低线。
- 250 日回撤对比：core raw -31.5759、旧 hybrid -4.7488、balanced -8.0412；cycle raw -31.0975、旧 hybrid -4.5716、balanced -7.9873；broad raw -30.1780、旧 hybrid -4.7560、balanced -7.8005。balanced 放松后回撤高于旧 hybrid，但仍显著优于 raw hold。
- return_retention_rate_60d：core 664.2507%，cycle 74.7568%，broad 45.1045%。broad 未达到 `PASS_BALANCED_EXIT_POLICY` 要求的 50%。
- drawdown_reduction_rate_250d：core 74.5337%，cycle 74.3153%，broad 74.1517%，三组均高于 60%。
- exit_efficiency_score：core 76.6562，cycle 62.7327，broad 53.0676。
- exit_reason_diagnostics：broad STOP_LOSS 6427 条，占 66.7532%，60 日退出平均净收益 -5.1123；TIME_EXIT_60D 1271 条，占 13.2011%，平均 15.4912；TAKE_PROFIT_TRAIL 1145 条，占 11.8924%，平均 21.9441；TREND_BREAK_CONFIRMED 696 条，占 7.2289%，平均 -2.9406；INSUFFICIENT_DATA 85 条，占 0.8828%；NO_REPAIR_40D 4 条，占 0.0415%。
- sample count change：相对当前基线 `724b8f9d`，core +0.0653%，cycle +0.0438%，broad -0.1763%，`overfit_warning=false`；相对附件中的 `fa918e90` 目标，broad 仍保持 9628 条，超过 9000 条最低线。
- observation candidate count：core strict 0、research 694、balanced research 1031、watch-only 1533；cycle strict 0、research 1872、balanced research 3109、watch-only 4573；broad strict 0、research 4667、balanced research 6453、watch-only 9628。候选文件继续写明仅用于模拟观察和复盘，不构成买入建议，不应自动交易。
- gate verdict：三组真实运行均为 `PASS_EXIT_POLICY_RESEARCH`。broad 未能达到 `PASS_BALANCED_EXIT_POLICY`，原因是 `balanced_exit_net_return_60d=1.0379% < 1.2%`、`return_retention_rate_60d=45.1045% < 50%`，且 balanced 60 日胜率 24.8664% 也低于 46% 门槛；不能输出 `PASS_PAPER_TRADING_CANDIDATE` 或 `PASS_PAPER_TRADING_READY`。
- 下一步：继续围绕 STOP_LOSS 触发比例过高做收益保留优化，但不能直接取消止损；优先研究“低波动假跌破/信号质量分层止损/入场后前 10-20 日异常波动识别”，并继续保持不接券商、不自动交易、不读取账户。

## Loop 6

- 本轮目标：基于 commit `fa918e90` 之后的退出策略收益/回撤平衡研究，继续优化 `balanced_hybrid_60d_exit`，尽量保留 60 日修复收益，同时继续压低 250 日 raw hold 回撤；不新增回测外功能，不接入券商，不自动交易，不读取账户。
- 修改的退出参数：新增 `balanced_v6_close_confirmed_stop`，并作为默认 balanced 参数。核心变化是 `stop_confirm_by_close=true`：盘中轻微触碰止损但收盘重新站回止损位时不立即退出；若盘中深跌超过 `stop_hard_intraday_pct=2.5` 的 hard buffer，仍按 `STOP_LOSS` 优先退出。入场信号、股票池、候选筛选和数据源不放宽。
- 修改文件：`src/strategies/genge_cycle_bottom/backtest.py`、`tests/test_genge_cycle_bottom_backtest.py`、`docs/genge_cycle_bottom_strategy.md`、`docs/CHANGELOG.md`、`LOOP_PROGRESS.md`、`LOOP_ACCEPTANCE_REPORT.md`。
- pytest 结果：`/Users/seker./.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest tests/test_genge_cycle_bottom_*.py -q`，60 passed，1 warning。
- fixture smoke 结果：`reports/genge_cycle_bottom_ci_smoke/20260629_224223`，`total_signals=1451`，`data_failures=0`。
- real core result：`reports/genge_exit_balance_core/20260629_225150`，耗时 289.01 秒，`total_signals=1533`，`data_failures=0`，`provider_error_count=0`，`pe_missing_count=386`，`pb_missing_count=0`，`financial_missing_count=0`，`risk_review_count=5`，`paper_trading_gate=PASS_EXIT_POLICY_RESEARCH`。
- real cycle result：`reports/genge_exit_balance_cycle/20260629_231021`，耗时 1075.91 秒，`total_signals=4573`，`data_failures=0`，`provider_error_count=0`，`pe_missing_count=798`，`pb_missing_count=0`，`financial_missing_count=0`，`risk_review_count=5`，`paper_trading_gate=PASS_EXIT_POLICY_RESEARCH`。
- real broad result：`reports/genge_exit_balance_broad/20260629_234715`，耗时 2183.43 秒，`total_signals=9628`，`data_failures=0`，`provider_error_count=0`，`pe_missing_count=688`，`pb_missing_count=0`，`financial_missing_count=0`，`risk_review_count=5`，`paper_trading_gate=PASS_EXIT_POLICY_RESEARCH`。
- raw_hold vs old_hybrid vs balanced_hybrid：core raw 60 日净收益 0.2042、旧 hybrid 0.5716、balanced 1.8459；cycle raw 3.8339、旧 hybrid 1.0512、balanced 3.7621；broad raw 2.3011、旧 hybrid 0.1889、balanced 1.7329。balanced v6 明显高于旧 hybrid，且 broad 已超过 1.2% 最低线。
- 250 日回撤对比：core raw -31.5759、旧 hybrid -4.7488、balanced -9.5773；cycle raw -31.0975、旧 hybrid -4.5716、balanced -9.8063；broad raw -30.1780、旧 hybrid -4.7560、balanced -9.7182。balanced v6 为保留收益接受了更宽回撤，但仍显著优于 raw hold。
- return_retention_rate_60d：core 903.9667%，cycle 98.1272%，broad 75.3075%。broad 达到 `PASS_BALANCED_EXIT_POLICY` 对收益保留率的最低要求。
- drawdown_reduction_rate_250d：core 69.6690%，cycle 68.4660%，broad 67.7971%，三组均高于 60%。
- exit_efficiency_score：core 76.8547，cycle 70.1923，broad 62.2954。
- exit_reason_diagnostics：broad STOP_LOSS 4822 条，占 50.0831%，60 日退出平均净收益 -7.4105；TIME_EXIT_60D 1870 条，占 19.4225%，平均 14.1536；TREND_BREAK_CONFIRMED 1414 条，占 14.6863%，平均 -3.3035；TAKE_PROFIT_TRAIL 1405 条，占 14.5929%，平均 21.7266；INSUFFICIENT_DATA 85 条，占 0.8828%；NO_REPAIR_40D 32 条，占 0.3324%。
- sample count change：相对当前基线 `724b8f9d`，core +0.0653%，cycle +0.0438%，broad -0.1763%，`overfit_warning=false`；broad 保持 9628 条，超过 9000 条最低线。
- observation candidate count：core strict 0、research 694、balanced research 851、watch-only 1533；cycle strict 0、research 1872、balanced research 2590、watch-only 4573；broad strict 0、research 4667、balanced research 5081、watch-only 9628。候选文件继续写明仅用于模拟观察和复盘，不构成买入建议，不应自动交易。
- gate verdict：三组真实运行均为 `PASS_EXIT_POLICY_RESEARCH`。broad 已达到 `total_signals>=9000`、样本稳定、balanced 60 日净收益 >=1.2%、收益保留率 >=50%、250 日回撤压降 >=60%、balanced 60 日跑赢基准 >=46%，但 balanced 60 日胜率 33.7001% 低于 46% 门槛，且原始 60 日胜率/跑赢基准和 250 日回撤仍未达到更高模拟盘要求；因此不能输出 `PASS_BALANCED_EXIT_POLICY`、`PASS_PAPER_TRADING_CANDIDATE` 或 `PASS_PAPER_TRADING_READY`。
- 下一步：继续研究 STOP_LOSS 后续是否存在可区分的“假跌破后修复”和“真破位继续下跌”，优先做信号质量分层与止损确认条件复核；不能简单取消止损，也不能把观察候选称为实盘操作入口。

## Loop 7

- 本轮目标：基于 commit `fa918e90` 要求继续做退出策略收益/回撤平衡优化，保持入场样本、股票池、数据源和候选筛选不放宽；不新增回测外功能，不接入券商，不自动交易，不读取账户。
- 修改的退出参数：新增 `balanced_v7_double_close_stop`，并作为默认 balanced 参数。核心变化是保留 `stop_confirm_by_close=true` 和 hard intraday stop，同时对 `MEDIUM/STRONG` 趋势样本要求连续 2 个交易日收盘低于止损位才确认 `STOP_LOSS`；`WEAK` 趋势样本和盘中深跌超过 `stop_hard_intraday_pct=2.5` 的样本仍立即按 `STOP_LOSS` 处理。
- 修改文件：`src/strategies/genge_cycle_bottom/backtest.py`、`tests/test_genge_cycle_bottom_backtest.py`、`docs/genge_cycle_bottom_strategy.md`、`docs/CHANGELOG.md`、`LOOP_PROGRESS.md`、`LOOP_ACCEPTANCE_REPORT.md`。
- pytest 结果：`/Users/seker./.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest tests/test_genge_cycle_bottom_*.py -q`，62 passed，1 warning，耗时 67.13 秒。
- fixture smoke 结果：`reports/genge_cycle_bottom_ci_smoke/20260630_001300`，耗时 159.13 秒，`total_signals=1451`，`data_failures=0`。
- real core result：`reports/genge_exit_balance_core/20260630_001811`，耗时 305.26 秒，`total_signals=1535`，`data_failures=0`，`provider_error_count=0`，`pe_missing_count=386`，`pb_missing_count=0`，`financial_missing_count=0`，`risk_review_count=5`，`paper_trading_gate=PASS_EXIT_POLICY_RESEARCH`。
- real cycle result：`reports/genge_exit_balance_cycle/20260630_003658`，耗时 1120.30 秒，`total_signals=4576`，`data_failures=0`，`provider_error_count=0`，`pe_missing_count=797`，`pb_missing_count=0`，`financial_missing_count=0`，`risk_review_count=5`，`paper_trading_gate=PASS_EXIT_POLICY_RESEARCH`。
- real broad result：`reports/genge_exit_balance_broad/20260630_011457`，耗时 2256.74 秒，`total_signals=9627`，`data_failures=0`，`provider_error_count=0`，`pe_missing_count=687`，`pb_missing_count=0`，`financial_missing_count=0`，`risk_review_count=5`，`paper_trading_gate=PASS_EXIT_POLICY_RESEARCH`。
- raw_hold vs old_hybrid vs balanced_hybrid：core raw 60 日净收益 0.2100、旧 hybrid 0.5683、balanced 1.8757；cycle raw 3.8480、旧 hybrid 1.0540、balanced 3.8867；broad raw 2.3054、旧 hybrid 0.1900、balanced 1.9083。v7 相比旧 hybrid 继续显著提高 60 日收益保留。
- 250 日回撤对比：core raw -31.5738、旧 hybrid -4.7484、balanced -9.8741；cycle raw -31.0926、旧 hybrid -4.5690、balanced -10.1031；broad raw -30.1730、旧 hybrid -4.7556、balanced -10.0461。v7 为保留收益接受更宽退出回撤，但仍明显优于 raw hold。
- return_retention_rate_60d：core 893.1905%，cycle 101.0057%，broad 82.7752%，三组均高于 50%。
- drawdown_reduction_rate_250d：core 68.7269%，cycle 67.5064%，broad 66.7050%，三组均高于 60%。
- exit_efficiency_score：core 76.5886，cycle 70.9423，broad 64.4014。
- exit_reason_diagnostics：broad STOP_LOSS 4575 条，占 47.5226%，60 日退出平均净收益 -7.3781；TIME_EXIT_60D 1911 条，占 19.8504%，平均 14.0603；TREND_BREAK_CONFIRMED 1594 条，占 16.5576%，平均 -3.5769；TAKE_PROFIT_TRAIL 1424 条，占 14.7917%，平均 21.6711；INSUFFICIENT_DATA 85 条，占 0.8829%；NO_REPAIR_40D 38 条，占 0.3947%。
- 与 v6 对比：broad balanced 60 日净收益从 1.7329 提升到 1.9083，收益保留率从 75.3075% 提升到 82.7752%，60 日跑赢基准从 50.8855% 提升到 51.3624%，综合效率从 62.3042 提升到 64.4107；250 日退出回撤从 -9.7182 放宽到 -10.0461，回撤压降率从 67.7971% 降到 66.7050%，仍高于 60% 门槛。
- sample count change：相对当前基线，core +0.1958%，cycle +0.1094%，broad -0.1866%，`overfit_warning=false`；broad 保持 9627 条，超过 9000 条最低线。
- observation candidate count：core strict 0、research 695、balanced research 859、watch-only 1535；cycle strict 0、research 1877、balanced research 2621、watch-only 4576；broad strict 0、research 4672、balanced research 5212、watch-only 9627。候选文件继续写明仅用于模拟观察和复盘，不构成买入建议，不应自动交易。
- gate verdict：三组真实运行均为 `PASS_EXIT_POLICY_RESEARCH`。broad 达到 `total_signals>=9000`、样本稳定、balanced 60 日净收益 >=1.2%、收益保留率 >=50%、250 日回撤压降 >=60%、balanced 60 日跑赢基准 >=46%；但 balanced 60 日胜率 34.3115% 低于 46% 门槛，且原始 60 日胜率/跑赢基准和 250 日回撤仍未达到更高模拟盘要求；因此不能输出 `PASS_BALANCED_EXIT_POLICY`、`PASS_PAPER_TRADING_CANDIDATE` 或 `PASS_PAPER_TRADING_READY`。
- 下一步：不应继续简单放松止损；优先做入场信号质量分层、STOP_LOSS 后续走势分组、行业周期证据质量和执行风险分层复核，寻找能提高胜率而不明显压缩样本的规则。

## Loop 8

- 本轮目标：基于 commit `85be6b6c`，新增“行业周期证据层”和周期拐点研究观察输出，保持不接入券商、不自动交易、不读取账户、不输出交易指令；本轮不新增回测外交易功能。
- 新增证据 schema 和模板：`config/industry_evidence_schema.yaml`、`data/examples/industry_cycle_evidence_template.csv`、`data/examples/company_cycle_evidence_template.csv`，覆盖猪肉、面板、稀土、光伏、锂电、化工、有色等行业证据示例。若 `data/user_supplied/*` 缺失，运行脚本会降级使用 example/template，并在报告中标记为 `MANUAL_TEMPLATE`。
- 新增证据处理模块：`src/strategies/genge_cycle_bottom/industry_evidence.py`，把行业证据、公司证据、证据日期、证据来源类型、过期/缺失/冲突标记合入特征和信号；`STRONG` 硬逻辑不能只靠价格、均线、低位分位或总分产生。
- 新增输出：`industry_evidence_cards.md/json` 和 `cycle_turning_point_candidates.csv`；候选文件写明“仅用于模拟观察和复盘；研究观察候选需人工复核，不构成买入建议，不应自动交易。”
- 新增验收枚举：`FAIL_EVIDENCE_LAYER`、`PASS_INDUSTRY_EVIDENCE_FRAMEWORK`、`PASS_HARD_LOGIC_RESEARCH_READY`、`PASS_CYCLE_TURNING_POINT_SCREENER`。当证据主要来自模板、fixture 或缺失时，最终最多只能到 `PASS_INDUSTRY_EVIDENCE_FRAMEWORK`。
- pytest：`/Users/seker./.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest tests/test_genge_cycle_bottom_*.py`，72 passed，1 warning，耗时 235.95 秒。
- fixture smoke：`reports/genge_cycle_bottom_ci_smoke/20260630_132735`，`total_signals=1451`，`data_failures=0`，`paper_trading_gate=PASS_INDUSTRY_EVIDENCE_FRAMEWORK`，已生成行业证据卡片和周期拐点候选文件。
- real broad：`reports/genge_industry_evidence_broad/20260630_162940`，耗时 3446.30 秒，`total_signals=9915`，`data_failures=0`，`provider_error_count=0`，`pe_missing_count=690`，`pb_missing_count=0`，`financial_missing_count=0`，`valuation_coverage_rate=100.0`，`financial_coverage_rate=100.0`。
- real broad 候选和复核数量：主候选 `balanced_research_observation_candidate_count=5473`，研究观察候选 4831，严格候选 0，风险复核数量 5，周期拐点研究观察候选 0。
- 证据覆盖：行业证据覆盖率 0.7161%，行业证据缺失 9844，行业证据来源分布为 `MANUAL_TEMPLATE=71`、`MISSING=9844`；公司证据覆盖率 0.0%，公司证据缺失 9915，来源分布为 `MISSING=9915`。
- 证据质量和硬逻辑分布：`hard_logic_level_summary` 为 `MEDIUM=5`、`NONE=9910`；`industry_evidence_quality_summary` 为 `MANUAL_TEMPLATE=71`、`MISSING=9844`；`industry_evidence_confidence_summary` 为 `MEDIUM=71`、`LOW=9844`。
- 60 日和退出指标：raw 60 日净收益 2.0603，raw 60 日胜率 46.5256，raw 60 日跑赢基准 46.4442；balanced 60 日净收益 1.8834，balanced 60 日胜率 34.7671，balanced 60 日跑赢基准 51.3423，收益保留率 91.4139%，250 日回撤压降率 66.1695%。
- 退出原因诊断：STOP_LOSS 4542 条、占 45.8094%；TIME_EXIT_60D 2099 条、占 21.1699%；TREND_BREAK_CONFIRMED 1754 条、占 17.6904%；TAKE_PROFIT_TRAIL 1393 条、占 14.0494%；INSUFFICIENT_DATA 81 条、NO_REPAIR_40D 46 条。
- gate verdict：`PASS_INDUSTRY_EVIDENCE_FRAMEWORK`。原因是证据层框架、schema、字段、报告和候选输出可运行，但用户真实证据文件尚未提供，当前主要使用模板和缺失证据；因此不能输出 `PASS_HARD_LOGIC_RESEARCH_READY`、`PASS_CYCLE_TURNING_POINT_SCREENER`、`PASS_PAPER_TRADING_CANDIDATE` 或 `PASS_PAPER_TRADING_READY`。
- 安全检查：本轮没有接入中信证券或任何券商接口，没有读取账户/持仓/密码/验证码，没有自动下单；报告措辞继续避免承诺收益和交易指令。下一步应先补充真实 `data/user_supplied` 行业/公司证据，再评估硬逻辑和周期拐点筛选效果。

## Loop 9

- 本轮目标：基于 commit `b3a3e` 之后继续强化行业证据层，补充真实公开样板证据和质量门槛；猪肉、面板、牧原股份、TCL科技只作为证据链路样板，不硬编码为候选，不强行入选；最终候选可以来自任意行业。
- 新增研究数据：`research/industry_cycle/pork.json/md`、`research/industry_cycle/panel.json/md`；生成 `data/user_supplied/industry_cycle_evidence.csv` 16 行、`data/user_supplied/company_cycle_evidence.csv` 20 行、`rejected_evidence.csv` 0 行。
- 证据质量规则：新增 `official_report`、`company_announcement`、`exchange_disclosure`、`research_report_summary`、`news_summary` 来源类型；缺少 `source`、`date` 或必需字段的证据进入拒绝清单，不再混入正式 CSV；新闻摘要不能单独形成 HIGH，模板来源不能形成 STRONG。
- 硬逻辑规则：`STRONG` 必须同时具备行业与公司证据、非模板/非缺失来源、至少两类来源、高权威来源、无过期或冲突；`hard_logic_reason`、`industry_evidence_items`、`company_evidence_items` 写入信号明细，便于逐条审计。
- 报告改造：`pork_panel_deep_dive.md` 保留旧文件名兼容，但内容改为动态样板证据链复核，从本次输入证据和运行结果动态发现样板对象，不再写固定股票名单；样板对象不参与特殊加分。
- pytest 结果：`/Users/seker./.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest tests/test_genge_cycle_bottom_industry_evidence.py -q`，11 passed，1 warning，耗时 161.46 秒；`/Users/seker./.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest tests/test_genge_cycle_bottom_report_cli.py -q`，16 passed，1 warning，耗时 68.70 秒。
- 静态检查：`py_compile` 通过；`git diff --check` 通过；报告禁用词检查未命中。
- 最新宽池报告路径：`reports/genge_industry_evidence_broad/20260630_162940`；`full_run_stats.md` 记录 `elapsed_until_stopped=47m21s`、`total_signals=9915`、`data_failures=0`、`provider_error_count=0`、`pe_missing_count=690`、`pb_missing_count=0`、`financial_missing_count=0`、主候选 5473、风险复核 5、周期拐点候选 0。
- 说明：该宽池报告文件已落盘，但运行摘要仍显示本次长跑使用 example/template 证据文件；当前 commit 已准备好 `data/user_supplied` 证据和动态样板报告逻辑，下一次干净全量运行应用同一命令即可验证真实样板证据 uptake。
- gate verdict：维持 `PASS_INDUSTRY_EVIDENCE_FRAMEWORK`。原因是证据层、质量门槛、拒绝清单和动态样板复核已可运行，但最新宽池报告尚未完成一次自然退出且确认使用 `data/user_supplied` 的干净全量运行；不能声明 `PASS_HARD_LOGIC_RESEARCH_READY`、`PASS_CYCLE_TURNING_POINT_SCREENER`、`PASS_PAPER_TRADING_CANDIDATE` 或 `PASS_PAPER_TRADING_READY`。
- 安全检查：没有接入中信证券或任何券商接口，没有读取账户/持仓/密码/验证码，没有自动下单；所有候选仍只是公开数据研究观察和人工复核入口。

## Loop 10

- 本轮目标：基于 commit `2d96e66a` 进入 Industry Evidence Layer 终局验收，不新增模块、不新增行业、不调整退出策略、不重构架构；只允许修复阻塞测试/CLI/报告生成的问题，并完成一次使用真实用户证据文件的宽池 full validation run。
- 本轮代码规则：未为行业证据验收放宽规则，未硬编码猪肉、面板、牧原股份、TCL科技为候选，未接入券商、未自动下单、未读取账户。
- pytest：`/Users/seker./.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest tests/test_genge_cycle_bottom_*.py`，75 passed，1 warning，耗时 240.27 秒。full pytest 已完整跑完。
- 真实宽池命令：指定 `--industry-evidence-file data/user_supplied/industry_cycle_evidence.csv`、`--company-evidence-file data/user_supplied/company_cycle_evidence.csv`、`--output-cycle-turning-point-candidates`、`--fixture-smoke-passed`、`--ci-passed`，使用 `stock_pools/genge_broad_pool.txt`、`--max-codes 100`、`--years 5`、`--benchmark 000905`。
- full validation run：`reports/genge_industry_evidence_broad/20260703_160805`，自然退出，耗时 3424.62 秒，`total_signals=9909`，`data_failures=0`，`provider_error_count=0`，`pe_missing_count=691`，`pb_missing_count=0`，`financial_missing_count=0`，估值覆盖率 100.0%，财务覆盖率 100.0%。
- 候选与复核数量：主候选 `balanced_research_observation_candidate_count=5485`，研究观察候选 4841，严格候选 0，模拟观察候选 0，风险复核数量 5，周期拐点研究观察候选 0。
- clean evidence path 核对：`summary.json -> diagnostics -> industry_evidence_file` 为 `data/user_supplied/industry_cycle_evidence.csv`；`company_evidence_file` 为 `data/user_supplied/company_cycle_evidence.csv`。本轮不是 example/template/fixture 证据运行，因此不触发 `FAIL_CLEAN_EVIDENCE_RUN`。
- 真实证据文件行数：`data/user_supplied/industry_cycle_evidence.csv` 为 16 行数据，`data/user_supplied/company_cycle_evidence.csv` 为 20 行数据，`rejected_evidence.csv` 为 0 行数据。
- 证据覆盖结果：行业证据覆盖率 0.0%，公司证据覆盖率 0.0%；行业证据缺失 9909，公司证据缺失 9909；`hard_logic_level_summary` 为 `NONE=9909`，`industry_evidence_quality_summary` 为 `MISSING=9909`。证据文件被实际指定和记录，但未形成有效信号覆盖。
- 周期拐点文件：`cycle_turning_point_candidates.csv` 已生成，文件包含免责声明占位行；`cycle_turning_point_candidate_count=0`。没有强行制造候选。
- 免责声明与禁用词：`cycle_turning_point_candidates.csv`、`paper_observation_candidates.csv` 均写明“仅用于模拟观察和复盘；研究观察候选需人工复核，不构成买入建议，不应自动交易。”报告目录禁用承诺和交易指令短语检查未命中。
- 样板对象复核：`000100/TCL科技` 作为普通股票自然出现在宽池信号中，但 `hard_logic_level=NONE`，未进入周期拐点或模拟观察候选；牧原股份未被强行加入本次 100 只宽池。猪肉、面板、TCL、牧原仍只是证据链样板，不参与特殊加分或强制入选。
- real broad 指标：60 日平均净收益 2.0838，60 日胜率 46.5738%，60 日跑赢基准 46.6653%，250 日低点平均回撤 -29.0947；balanced 60 日退出净收益 1.9090，收益保留率 91.6115%，250 日回撤压降率 66.1887%。
- 失败原因：行业周期判断不足 6860，止损不够严格 6731，买太早 5823，估值陷阱 4095，持有周期不适合 1605。执行风险分布为低风险 9903，高风险 4，降级 2。
- gate verdict：`PASS_INDUSTRY_EVIDENCE_FRAMEWORK`。本轮完成干净 user_supplied full run，但因证据覆盖率为 0%、hard logic 全部安全降级为 NONE、周期拐点候选为 0，不能升级为 `PASS_HARD_LOGIC_RESEARCH_READY` 或 `PASS_CYCLE_TURNING_POINT_SCREENER`。

## Loop 11

- 本轮目标：回到 GenGe Cycle Bottom Strategy 信号质量优化终局验收，基于 commit `b2a298b0b2ff35a7454fb0b731c9d5e0c6f07917` 的真实研究基线做可复核比较；停止新增功能，不新增回测，不接入中信客户端，不读取账户，不自动下单，不硬编码样板股票或行业。
- 本轮规则修正：`config/genge_signal_quality_baseline.json` 已恢复为 b2a baseline；`PASS_SIGNAL_QUALITY_IMPROVED` 只允许 broad 池在样本稳定、60 日收益/胜率/跑赢基准和 250 日低点回撤同时达标时升级。core/cycle 只能作为辅助研究结果，不能单独升级。
- 测试结果：`/Users/seker./.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest tests/test_genge_cycle_bottom_report_cli.py -q`，18 passed，1 warning，耗时 127.18 秒；full pytest `/Users/seker./.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest tests/test_genge_cycle_bottom_*.py`，75 passed，1 warning，耗时 285.93 秒。
- fixture smoke：`reports/genge_cycle_bottom_ci_smoke/20260703_212323`，自然退出，`total_signals=1451`，`data_failures=0`。
- real core：`reports/genge_signal_quality_core/20260703_213113`，自然退出，耗时 460.90 秒，`total_signals=1811`，`data_failures=0`，`provider_error_count=0`，`pe_missing_count=396`，`pb_missing_count=0`，`financial_missing_count=0`，主候选 968，风险复核 5，gate 为 `PASS_REAL_DATA_RESEARCH`。
- real cycle：`reports/genge_signal_quality_cycle/20260703_220538`，自然退出，耗时 2054.69 秒，`total_signals=5253`，`data_failures=0`，`provider_error_count=0`，`pe_missing_count=843`，`pb_missing_count=0`，`financial_missing_count=0`，主候选 2858，风险复核 5，gate 为 `PASS_REAL_DATA_RESEARCH`。
- real broad：`reports/genge_signal_quality_broad/20260703_230046`，自然退出，耗时 3299.67 秒，`total_signals=9909`，`data_failures=0`，`provider_error_count=0`，`pe_missing_count=691`，`pb_missing_count=0`，`financial_missing_count=0`，主候选 5485，风险复核 5，gate 为 `PASS_REAL_DATA_RESEARCH`。
- broad 相比 b2a baseline：60 日平均净收益改善 +1.6873，60 日胜率改善 +3.6948pct，60 日跑赢基准比例改善 +6.3465pct，250 日低点回撤改善 +2.1501pct；但样本数从 20076 降到 9909，下降 50.6426%，触发 overfit warning。
- broad 当前核心指标：20/60/120/250 日平均净收益为 -0.1427/2.0838/3.9176/6.9694；60 日胜率 46.5738%，60 日跑赢基准比例 46.6653%，250 日低点平均回撤 -29.0947%。
- failure reason change：b2a 指标基线没有保存 failure reason 明细，因此原因变化使用本地可复核最早 b2a 标记宽池运行 `reports/genge_signal_quality_broad/20260628_151610` 做对照。当前 broad 相比该运行，买太早 -1778/-1.00pct，止损不够严格 -1948/-0.31pct，估值陷阱 -1327/-1.31pct，趋势未确认 -101/+0.04pct，行业周期判断不足 -2150/-1.61pct；相比上一条 signal-quality 宽池运行 `20260703_145745` 基本持平。
- 候选输出：`paper_observation_candidates.csv` 真实候选数 0，仅有免责声明占位行；`research_observation_candidates.csv` broad 4841；`balanced_research_observation_candidates.csv` broad 5485；`strict_observation_candidates.csv` 为 0；`watch_only_candidates.csv` broad 9909。
- 免责声明与安全检查：候选文件继续写明仅用于模拟观察和复盘、需人工复核、不构成买入建议、不应自动交易；禁用确定性承诺和交易指令短语扫描未命中。猪肉、面板、牧原股份、TCL科技只出现在样例或 user supplied evidence 数据中，`src/` 和运行逻辑没有把它们硬编码为候选。
- gate verdict：最终枚举为 `PASS_REAL_DATA_RESEARCH`。不能升级到 `PASS_SIGNAL_QUALITY_IMPROVED` 的原因是 broad 样本下降超过 50%，250 日低点回撤改善未达到 3pct 或不差于 -28% 的升级线，且 paper observation 候选数仍为 0。本轮收口，不提出新的大功能方向。

## Loop 12

- 本轮目标：基于 commit `1beed4b72b7b36d68a24efb41251262bd7431ea6` 进入 Industry Evidence Layer 终局验收；停止新增功能，不新增行业，不调整退出策略，不重构架构，只修复阻塞测试、CLI、报告生成和 clean evidence path 审计的问题。
- 本轮代码修复：`scripts/run_genge_real_research.py` 不再把显式 evidence 文件静默回退到 `data/examples` 模板；`summary.json` 写入 `data_failures`、`data_failure_count`、`provider_error_count`；`cycle_turning_point_candidates.csv` 补齐验收字段，并在 0 候选时写入 blocker summary；相关测试同步覆盖。
- 真实证据文件：`data/user_supplied/industry_cycle_evidence.csv` 16 行，`data/user_supplied/company_cycle_evidence.csv` 20 行，`data/user_supplied/rejected_evidence.csv` 0 行数据；summary 中实际记录的 industry/company evidence 路径均为 `data/user_supplied`，不是 example/template/fixture。
- pytest：`/Users/seker./.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest tests/test_genge_cycle_bottom_*.py`，77 passed，1 warning，耗时 276.31 秒；full pytest 已完整跑完，fixture smoke 已包含并通过。
- final broad run：`reports/genge_industry_evidence_final/20260704_114820`，自然退出，wall time 2400.47 秒，runner 输出 `elapsed_seconds=500.28`，`total_signals=1720`，`data_failures=90`，`provider_error_count=0`，`pe_missing_count=0`，`pb_missing_count=0`，`financial_missing_count=0`。
- 候选与复核数量：主候选 `balanced_research_observation_candidate_count=915`，研究观察候选 1044，观察列表 1720，paper observation 候选 0，风险复核数量 5，周期拐点候选 0。
- 证据覆盖结果：行业证据覆盖率 0.0%，公司证据覆盖率 0.0%，行业证据缺失 1720，公司证据缺失 1720；输出来源分布均为 `MISSING=1720`；`hard_logic_level` 为 `NONE=1720`、`WEAK=0`、`MEDIUM=0`、`STRONG=0`。
- 周期拐点文件：`cycle_turning_point_candidates.csv` 已生成，包含免责声明和 0 候选 blocker summary；主要 blocker 为 `hard_logic_insufficient=1720`、`cycle_phase_mismatch=1720`、`price_percentile_not_low=657`、`trend_insufficient=458`、`balanced_exit_profile_not_passed=361`。
- 样板对象复核：猪肉、面板、牧原股份、TCL科技只作为 user supplied evidence 和研究说明里的样板对象；生产代码没有把这些股票或行业硬编码为候选，没有强制入选。
- 安全检查：没有接入中信证券或任何券商接口，没有读取账户/持仓/密码/验证码，没有自动买入、卖出或撤单。
- gate verdict：最终枚举为 `FAIL_CLEAN_EVIDENCE_RUN`。阻塞原因是 latest final-code 宽池运行 `data_failures=90`，证据覆盖率 0.0% 导致 hard logic 全部安全降级为 NONE，周期拐点真实候选为 0；本轮没有为了结果好看制造候选或放宽规则。

## Loop 13

- 本轮目标：基于 commit `f686c4cba31146d518551de841f14e416016f7ff` 增加“当前快照周期拐点筛选器”，与历史 walk-forward 回测严格分离；不调历史买卖策略，不新增券商接入，不读取账户，不自动下单。
- 本轮代码修改：新增 `src/strategies/genge_cycle_bottom/current_snapshot.py`、`config/industry_alias_map.yaml`、`tests/test_genge_cycle_bottom_current_snapshot.py`；CLI 和 runner 增加 `--current-snapshot`、`--as-of-date`、`--output-current-snapshot`、`--industry-alias-map` 参数；现有 walk-forward 路径保持原 backtester。
- 当前快照输出设计：`current_snapshot_summary.md/json`、`current_snapshot_all.csv`、`current_cycle_turning_point_candidates.csv`、`current_watch_only_candidates.csv`、`industry_alias_resolution.csv`、`evidence_match_audit.csv`、`data_failure_audit.csv`、`industry_evidence_cards.md/json`。
- 证据规则：行业别名只做归一化匹配，company evidence 的 stock code 优先于行业别名；`STRONG` 需要行业证据和公司证据同时有效、方向一致、来源类型足够、非过期且无冲突；未匹配证据时安全降级为 `NONE`。
- 样板对象复核：猪肉、面板、牧原股份、TCL科技没有被硬编码为候选，也没有强制入选；它们只作为 user supplied evidence 的样板链路，可被审计文件自然追踪。
- 本轮收口修复：current snapshot 遇到公开行情源连续失败时不再卡在多源 fallback；`EfinanceFetcher` 历史 K 线接口使用模块级 timeout；报告仍会生成 `data_failure_audit.csv` 和别名审计，并保守给出 `FAIL_CURRENT_SNAPSHOT`。
- pytest：`/Users/seker./.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest tests/test_genge_cycle_bottom_current_snapshot.py -q`，6 passed，1 warning，耗时 0.25 秒。
- full pytest：`/Users/seker./.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest tests/test_genge_cycle_bottom_*.py`，83 passed，1 warning，耗时 270.36 秒；full pytest 已完整跑完。
- 真实 current snapshot 宽池命令：指定 `--stock-pool-file stock_pools/genge_broad_pool.txt`、`--years 5`、`--benchmark 000905`、`--output-dir reports/genge_current_snapshot`、`--max-codes 100`、`--auto-fetch-valuation`、`--auto-fetch-financial`、`--industry-evidence-file data/user_supplied/industry_cycle_evidence.csv`、`--company-evidence-file data/user_supplied/company_cycle_evidence.csv`、`--industry-evidence-schema config/industry_evidence_schema.yaml`、`--industry-alias-map config/industry_alias_map.yaml`、`--current-snapshot`、`--output-current-snapshot`、`--fixture-smoke-passed`、`--ci-passed`。
- 真实运行结果：`reports/genge_current_snapshot/20260705_092526`，自然退出，runner `elapsed_seconds=23.71`，wall time `real 24.07`；summary 明确记录 `industry_evidence_file=data/user_supplied/industry_cycle_evidence.csv`、`company_evidence_file=data/user_supplied/company_cycle_evidence.csv`。
- current snapshot 宽池指标：`snapshot_total_stocks=100`，`snapshot_valid_stocks=0`，`fatal_data_failures=0`，`skipped_data_unavailable=100`，`data_failure_status_distribution=SKIPPED_DATA_UNAVAILABLE=100`；benchmark 跳过原因为 `skipped_current_snapshot_price_provider_unavailable`。
- 证据与别名审计：行业证据 16 行、公司证据 20 行；`industry_alias_resolution.csv` 100 行，其中 `EXACT=31`、`COMPANY_CODE=2`、`UNRESOLVED=67`；因无有效当前价格数据，行业/公司 evidence coverage 均为 0.0%。
- 候选与安全：`current_cycle_turning_point_candidates.csv` 已生成免责声明占位行，真实候选 0；猪肉、面板、牧原股份、TCL科技仍只是样板证据对象，未硬编码为候选，未强制入选；未接券商、未读取账户、未自动下单。
- current snapshot full validation verdict：`FAIL_CURRENT_SNAPSHOT`。阻塞原因是外部公开行情源不可用导致 `snapshot_valid_stocks=0`，hard logic/候选无法基于当前行情评估，候选数为 0；没有为了结果好看改规则或制造候选。
