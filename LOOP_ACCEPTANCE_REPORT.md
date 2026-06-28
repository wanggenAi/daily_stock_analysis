# GenGe Signal Quality Acceptance Report

## A Runability

- pytest：39 passed，1 warning。
- fixture smoke：通过，报告路径 `reports/genge_cycle_bottom_ci_smoke/20260628_154457`。
- real core：通过，报告路径 `reports/genge_signal_quality_core/20260628_154858`，耗时 224.37 秒，数据失败 0。
- real cycle：通过，报告路径 `reports/genge_signal_quality_cycle/20260628_160347`，耗时 873.21 秒，数据失败 0。
- real broad：通过，报告路径 `reports/genge_signal_quality_broad/20260628_163352`，耗时 1785.23 秒，数据失败 0。
- 不接入券商账户，不读取账户/持仓/密码/验证码，不自动下单，不打开中信证券交易页面。

## B Baseline Comparison

| pool | total | sample_change_pct | avg_net_60_delta | win60_delta | outperform60_delta | dd250_delta | overfit_warning |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| core | 1663 | -42.0961 | 0.6853 | 2.0251 | 2.7658 | -0.0661 | false |
| cycle | 5091 | -41.0149 | 1.0555 | 2.7534 | 3.4244 | -0.1526 | false |
| broad | 11185 | -44.2867 | 1.2670 | 3.3642 | 6.0326 | 0.1670 | false |

结论：broad 的 60 日胜率和 60 日跑赢基准改善达到信号质量目标，且样本数未下降超过 50%；但 broad 250 日低点回撤只改善 0.1670 个百分点，core/cycle 的 250 日低点回撤仍略差，因此不能给出更高通过枚举。

## C Strategy Quality

- broad：20/60/120/250 日平均净收益为 -0.1107 / 1.6635 / 2.9499 / 4.7179；20/60/120/250 日胜率为 44.4703 / 46.2432 / 45.9126 / 48.5689；60/120 日跑赢基准为 46.3514 / 38.0069；250 日低点平均回撤 -31.0778；60 日止损修正净收益 0.8306。
- cycle：20/60/120/250 日平均净收益为 0.6660 / 2.9784 / 5.8921 / 8.4727；20/60/120/250 日胜率为 49.8623 / 49.5937 / 49.6050 / 56.1242；60/120 日跑赢基准为 48.2458 / 48.9366；250 日低点平均回撤 -31.6669；60 日止损修正净收益 2.9032。
- core：20/60/120/250 日平均净收益为 0.0287 / -0.4304 / 0.8249 / 2.7207；20/60/120/250 日胜率为 50.3307 / 46.0701 / 45.5855 / 51.4774；60/120 日跑赢基准为 43.6518 / 43.1434；250 日低点平均回撤 -31.6486；60 日止损修正净收益 1.1130。
- value trap filtered：失败原因中估值陷阱计数为 core 533、cycle 1609、broad 4792；财务缺失不会默认安全。
- falling knife filtered：失败原因中买太早计数为 core 954、cycle 2792、broad 6647；稳定天数和趋势确认继续约束低位但未止跌的样本。
- trend confirmation distribution：已输出到各报告 `summary.json -> trend_confirmation_summary`；broad 中 MEDIUM 3297、STRONG 4912、WEAK 2976。

## D Failure Reason Changes

- 买太早：新增稳定天数、二次低点、飞刀过滤和 MA reclaim 评分，低位但趋势弱的样本最多观察；本轮 broad 买太早计数从 7601 降到 6647。
- 趋势未确认：`CONFIRM_BUY` 至少需要 MEDIUM，`LEFT_SMALL_BUY` 至少需要 WEAK；本轮 broad 趋势未确认计数从 475 降到 443。
- 止损不够严格：动态止损综合 MA60、ATR、近期平台低点、5 年低点和 12% 风险上限；本轮 broad 止损不够严格计数从 8679 降到 7776。
- 估值陷阱：保留 value trap score/flag，财务缺失或恶化不默认安全；本轮 broad 估值陷阱计数从 5422 降到 4792。
- 行业周期不足：`industry_cycle_quality` 仍用于降级，manual/missing 不能单独支撑高置信确认；本轮 broad 行业周期判断不足计数从 9010 降到 7902。

## E Execution Feasibility

- 新增信号日 `execution_risk_score` 和 `execution_risk_quality=good/degraded/risky`，仅使用 as-of 当日及之前数据，不读取未来成交信息。
- 涨停/跌停、异常日内波动、低流动性、当日成交量尖峰会写入执行风险标签并触发降级。
- broad 执行风险分布：低风险 11176、降级风险 6、高风险 3；core 低风险 1662、高风险 1；cycle 低风险 5089、高风险 2。

## F Observation Candidates

- 三组报告均生成 `paper_observation_candidates.csv`。
- 文件包含 code、stock_name、industry、as_of_date、signal_type、total_score、trend_confirmation_level、value_trap_score、stop_loss_distance_pct、execution_risk_score、max_position_pct_research_only、reason、invalidation_condition。
- 本轮严格条件下三组模拟观察候选数均为 0；文件内保留声明：该清单仅用于模拟观察和复盘，不构成买入建议。

## G Acceptance Decision

最终枚举：`PASS_REAL_DATA_RESEARCH`。

理由：三组真实公开数据运行均通过，数据失败为 0，样本数充足且没有大于 50% 的样本骤降；broad 的 60 日胜率和跑赢基准改善明显。但 250 日低点回撤未达到至少改善 3 个百分点或优于 -28% 的最低线，core/cycle 回撤也未改善，因此不能输出 `PASS_SIGNAL_QUALITY_IMPROVED`，更不能输出 `PASS_PAPER_TRADING_READY`。
