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
