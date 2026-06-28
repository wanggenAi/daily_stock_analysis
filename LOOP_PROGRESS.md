# GenGe Signal Quality Loop Progress

## Loop 1

- 本轮目标：针对上一版真实研究结果中的买太早、趋势未确认、止损不够严格、估值陷阱和执行风险，做信号质量优化，不新增回测外功能，不接入券商。
- 针对失败原因：买太早、趋势未确认、止损不够严格、估值陷阱、行业周期证据不足、执行入口风险。
- 修改文件：`src/strategies/genge_cycle_bottom/features.py`、`strategy.py`、`signals.py`、`backtest.py`、`metrics.py`、`report.py`、`cli.py`、`tests/test_genge_cycle_bottom_*.py`、`docs/genge_cycle_bottom_strategy.md`、`config/genge_signal_quality_baseline.json`。
- 修改策略规则：增加 `stabilization_days`、`downtrend_exhaustion_score`、`reclaim_ma_score`、`no_falling_knife_filter`、`second_low_confirmation`、`trend_confirmation_level`；`LEFT_SMALL_BUY` 至少需要 WEAK，`CONFIRM_BUY` 至少需要 MEDIUM，`ADD` 预留 STRONG；高估值陷阱、财务缺失不确定、手工模板行业周期、止损距离过宽、弱市场环境会降级。
- pytest：`/Users/seker./.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest tests/test_genge_cycle_bottom_*.py -q`，36 passed，1 warning。
- fixture：`reports/genge_cycle_bottom_ci_smoke/20260628_143138`，`total_signals=1453`，`data_failures=0`。
- real core：`reports/genge_signal_quality_core/20260628_143543`，耗时 199.05 秒，`total_signals=1876`，`data_failures=0`，`pe_missing_count=461`，`pb_missing_count=0`，`financial_missing_count=0`。
- real cycle：`reports/genge_signal_quality_cycle/20260628_144911`，耗时 802.18 秒，`total_signals=5807`，`data_failures=0`，`pe_missing_count=1003`，`pb_missing_count=0`，`financial_missing_count=0`。
- real broad：`reports/genge_signal_quality_broad/20260628_151610`，耗时 1610.63 秒，`total_signals=12718`，`data_failures=0`，`pe_missing_count=921`，`pb_missing_count=0`，`financial_missing_count=0`。
- baseline comparison：core 60 日平均净收益 +0.4463、胜率 +1.2826、跑赢基准 +1.4341、250 日低点回撤 -0.2203；cycle 60 日平均净收益 +0.9277、胜率 +2.2032、跑赢基准 +2.2047、250 日低点回撤 -0.2380；broad 60 日平均净收益 +1.0338、胜率 +2.9732、跑赢基准 +5.4145、250 日低点回撤 +0.0068。
- signal count change：core -34.6797%，cycle -32.7193%，broad -36.6507%，均未触发大于 50% 的样本骤降警告。
- win rate delta：core +1.2826，cycle +2.2032，broad +2.9732。
- outperform delta：core +1.4341，cycle +2.2047，broad +5.4145。
- drawdown delta：core -0.2203，cycle -0.2380，broad +0.0068。
- overfit warning：core/cycle/broad 均为 false。
- gate verdict：三组真实运行的 `paper_trading_gate` 均为 `PASS_REAL_DATA_RESEARCH`；本轮信号质量枚举为 `PASS_SIGNAL_QUALITY_IMPROVED`，尚未达到模拟盘观察更高门槛。
- 下一步：优化性能和行业周期证据质量；继续复核止损政策是否在 broad 之外的 core/cycle 中降低回撤，而不是只改善收益。
