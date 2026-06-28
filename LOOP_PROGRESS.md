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
