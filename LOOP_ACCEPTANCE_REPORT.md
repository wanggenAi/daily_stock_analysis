# GenGe Signal Quality Acceptance Report

## A Runability

- pytest：36 passed，1 warning。
- fixture smoke：通过，报告路径 `reports/genge_cycle_bottom_ci_smoke/20260628_143138`。
- real core：通过，报告路径 `reports/genge_signal_quality_core/20260628_143543`。
- real cycle：通过，报告路径 `reports/genge_signal_quality_cycle/20260628_144911`。
- real broad：通过，报告路径 `reports/genge_signal_quality_broad/20260628_151610`。
- 不接入券商账户，不读取账户/持仓/密码/验证码，不自动下单，不打开中信证券交易页面。

## B Baseline Comparison

| pool | total | sample_change_pct | avg_net_60_delta | win60_delta | outperform60_delta | dd250_delta | overfit_warning |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| core | 1876 | -34.6797 | 0.4463 | 1.2826 | 1.4341 | -0.2203 | false |
| cycle | 5807 | -32.7193 | 0.9277 | 2.2032 | 2.2047 | -0.2380 | false |
| broad | 12718 | -36.6507 | 1.0338 | 2.9732 | 5.4145 | 0.0068 | false |

结论：broad 核心指标全部优于基线，且样本数未下降超过 50%；core/cycle 的 60 日收益、胜率和跑赢基准改善，但 250 日低点回撤略差。

## C Strategy Quality

- broad：20/60/120/250 日平均净收益为 -0.1520 / 1.4303 / 2.7324 / 4.8769；60 日胜率 45.8522；60 日跑赢基准 45.7333；250 日低点平均回撤 -31.2380。
- cycle：20/60/120/250 日平均净收益为 0.7003 / 2.8506 / 5.8226 / 8.9784；60 日胜率 49.0435；60 日跑赢基准 47.0261；250 日低点平均回撤 -31.7523。
- core：20/60/120/250 日平均净收益为 0.1147 / -0.6694 / 0.5908 / 3.4889；60 日胜率 45.3276；60 日跑赢基准 42.3201；250 日低点平均回撤 -31.8028。
- stop adjusted：core 60/250 日止损修正净收益 1.1241 / 0.5887；cycle 3.1413 / 0.5252；broad 0.6759 / -1.3357。止损政策对 60 日风险收益有帮助，但 250 日可能截断反弹。
- value trap filtered：三组真实运行当前最终候选中 `value_trap_flagged_count=0`，缺失财务未默认安全。
- falling knife filtered：三组最终候选中 `falling_knife_filtered_count=0`，说明进入回测的信号已通过基础止跌门槛。
- trend confirmation distribution：已输出到各报告 `summary.json -> trend_confirmation_summary`。

## D Failure Reason Changes

- 买太早：新增稳定天数、二次低点、飞刀过滤和 MA reclaim 评分，低位但趋势弱的样本最多观察，不直接确认。
- 趋势未确认：`CONFIRM_BUY` 至少需要 MEDIUM，`LEFT_SMALL_BUY` 至少需要 WEAK。
- 止损不够严格：新增动态止损、止损距离、失效位、MAE 和 stop-adjusted return 字段，原始收益和净收益没有被覆盖。
- 估值陷阱：新增 value trap score/flag，财务缺失或恶化不默认安全。
- 行业周期不足：新增 `industry_cycle_quality`，manual/missing 不能单独支撑高置信确认。

## E Execution Feasibility

- 新增 `execution_risk_score` 和 `executable_entry_quality=good/degraded/risky/unavailable`。
- 高涨停入口、缺失下一交易日、低流动性、异常跳空会写入执行诊断和风险标签。
- broad 高执行风险样本计数 50，core 7，cycle 20。

## F Observation Candidates

- 三组报告均生成 `paper_observation_candidates.csv`。
- 文件包含 code、stock_name、industry、as_of_date、signal_type、total_score、trend_confirmation_level、value_trap_score、stop_loss_distance_pct、execution_risk_score、max_position_pct_research_only、reason、invalidation_condition。
- 文件内声明：该清单仅用于模拟观察和复盘，不构成买入建议。

## G Acceptance Decision

最终枚举：`PASS_SIGNAL_QUALITY_IMPROVED`。

理由：broad 真实 100 只样本相对基线在 60 日平均净收益、60 日胜率、60 日跑赢基准比例、250 日低点回撤全部改善，且样本缩减未超过 50%。但 core/cycle 回撤略差，60 日胜率和跑赢基准仍未达到更高模拟盘门槛，因此不能输出 `PASS_PAPER_TRADING_READY`。
