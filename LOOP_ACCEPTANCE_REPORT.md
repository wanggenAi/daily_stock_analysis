# GenGe Signal Quality Acceptance Report

## A Runability

- pytest：44 passed，1 warning。
- fixture smoke：通过，报告路径 `reports/genge_cycle_bottom_ci_smoke/20260628_190621`，`total_signals=1451`，数据失败 0。
- real core：通过，报告路径 `reports/genge_signal_quality_core/20260628_191009`，耗时 211.95 秒，数据失败 0。
- real cycle：通过，报告路径 `reports/genge_signal_quality_cycle/20260628_192527`，耗时 903.14 秒，数据失败 0。
- real broad：通过，报告路径 `reports/genge_signal_quality_broad/20260628_195432`，耗时 1735.27 秒，数据失败 0。
- 不接入券商账户，不读取账户/持仓/密码/验证码，不自动下单，不打开中信证券交易页面。

## B Baseline Comparison

| pool | total | sample_change_pct | avg_net_60_delta | win60_delta | outperform60_delta | dd250_delta | overfit_warning |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| core | 1532 | -46.6574 | 1.3199 | 3.4928 | 3.7627 | 0.0072 | false |
| cycle | 4571 | -47.0397 | 1.9110 | 3.7011 | 4.3720 | 0.4241 | false |
| broad | 9645 | -51.9576 | 1.8959 | 3.9829 | 6.2084 | 1.1159 | true |

结论：core/cycle/broad 的 60 日胜率和 60 日跑赢基准改善均达到最低信号质量目标；但 broad 样本数下降 51.9576%，仍触发过拟合警告，且 broad 250 日低点回撤只改善 1.1159 个百分点，未达到至少改善 3 个百分点或优于 -28% 的最低线，因此不能给出更高通过枚举。

## C Strategy Quality

- broad：20/60/120/250 日平均净收益为 -0.1675 / 2.2924 / 4.5286 / 7.2183；20/60/120/250 日胜率为 44.3753 / 46.8619 / 48.4269 / 51.6082；60/120 日跑赢基准为 46.5272 / 37.4851；250 日低点平均回撤 -30.1289；60 日止损修正净收益 1.2899。
- cycle：20/60/120/250 日平均净收益为 0.8108 / 3.8339 / 7.2571 / 10.7637；20/60/120/250 日胜率为 50.7335 / 50.5414 / 51.0392 / 57.6482；60/120 日跑赢基准为 49.1934 / 49.9448；250 日低点平均回撤 -31.0902；60 日止损修正净收益 3.6144。
- core：20/60/120/250 日平均净收益为 0.1877 / 0.2042 / 1.9201 / 3.9159；20/60/120/250 日胜率为 50.9138 / 47.5378 / 46.4752 / 53.1586；60/120 日跑赢基准为 44.6487 / 43.6684；250 日低点平均回撤 -31.5753；60 日止损修正净收益 1.6966。
- value trap filtered：失败原因中估值陷阱计数为 core 462、cycle 1336、broad 3954；财务缺失不会默认安全。
- falling knife filtered：失败原因中买太早计数为 core 851、cycle 2443、broad 5626；稳定天数和趋势确认继续约束低位但未止跌的样本。
- trend confirmation distribution：已输出到各报告 `summary.json -> trend_confirmation_summary`；broad 中 STRONG 4270、MEDIUM 2728、WEAK 2647。

## D Failure Reason Changes

- 买太早：新增稳定天数、二次低点、飞刀过滤和 MA reclaim 评分，低位但趋势弱的样本最多观察；本轮 broad 买太早计数为 5626。
- 趋势未确认：`CONFIRM_BUY` 至少需要 MEDIUM，`LEFT_SMALL_BUY` 至少需要 WEAK；本轮 broad 趋势未确认计数为 384。
- 止损不够严格：动态止损综合 MA60、ATR、近期平台低点、5 年低点和 12% 风险上限；本轮 broad 止损不够严格计数为 6470。
- 估值陷阱：保留 value trap score/flag，财务缺失或恶化不默认安全；本轮 broad 估值陷阱计数为 3954。
- 行业周期不足：`industry_cycle_quality` 仍用于降级，manual/missing 不能单独支撑高置信确认；本轮 broad 行业周期判断不足计数为 6591。
- 长周期位置风险：长期位置风险和历史样本充分性已经进入评分、风险标签、CSV 和报告；本轮 broad 长周期位置风险计数为 109。

## E Execution Feasibility

- 新增信号日 `execution_risk_score` 和 `execution_risk_quality=good/degraded/risky`，仅使用 as-of 当日及之前数据，不读取未来成交信息。
- 涨停/跌停、异常日内波动、低流动性、当日成交量尖峰会写入执行风险标签并触发降级。
- broad 执行风险分布：低风险 9639、降级风险 3、高风险 3；core 低风险 1531、高风险 1；cycle 低风险 4569、高风险 2。

## F Observation Candidates

- 三组报告均生成 `paper_observation_candidates.csv`。
- 文件包含 code、stock_name、industry、as_of_date、signal_type、total_score、trend_confirmation_level、value_trap_score、stop_loss_distance_pct、execution_risk_score、max_position_pct_research_only、reason、invalidation_condition。
- 本轮严格条件下三组模拟观察候选数均为 0；文件内保留声明：该清单仅用于模拟观察和复盘，不构成买入建议。

## G Acceptance Decision

最终枚举：`PASS_REAL_DATA_RESEARCH`。

理由：三组真实公开数据运行均通过，数据失败为 0，估值和财务覆盖率均为 100%，且 60 日收益、胜率、跑赢基准均明显改善。但 broad 样本下降 51.9576%，仍触发过拟合警告；250 日低点回撤也未达到至少改善 3 个百分点或优于 -28% 的最低线，因此不能输出 `PASS_SIGNAL_QUALITY_IMPROVED`，更不能输出 `PASS_PAPER_TRADING_READY`。
