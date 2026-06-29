# GenGe Signal Quality Acceptance Report

## A Runability

- pytest：`/Users/seker./.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest tests/test_genge_cycle_bottom_*.py -q`，59 passed，1 warning。
- fixture smoke：通过，报告路径 `reports/genge_cycle_bottom_ci_smoke/20260629_195104`，`total_signals=1451`，`data_failures=0`。
- real core：通过，报告路径 `reports/genge_exit_balance_core/20260629_185341`，耗时 338.19 秒，`total_signals=1533`，`data_failures=0`。
- real cycle：通过，报告路径 `reports/genge_exit_balance_cycle/20260629_191109`，耗时 1027.08 秒，`total_signals=4573`，`data_failures=0`。
- real broad：通过，报告路径 `reports/genge_exit_balance_broad/20260629_194612`，耗时 2082.33 秒，`total_signals=9628`，`data_failures=0`。
- 不接入券商账户，不读取账户/持仓/密码/验证码，不自动下单，不打开中信证券交易页面。

## B Strategy Horizon

- `strategy_primary_horizon = 60d`。
- `strategy_secondary_horizon = 20d/120d`。
- `strategy_risk_horizon = 250d`。
- 250 日 raw hold 只作为风险压力测试，不是默认长期持有目标。
- 新增 `balanced_hybrid_60d_exit`，旧 `hybrid_60d_repair_exit` 保留为风险压缩对照。

## C Exit Policy Comparison

| pool | raw_net_60 | old_hybrid_net_60 | balanced_net_60 | raw_dd250 | old_hybrid_dd250 | balanced_dd250 | retention_60d | dd_reduction_250d | efficiency |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| core | 0.2042 | 0.5716 | 1.3564 | -31.5759 | -4.7488 | -8.0412 | 664.2507 | 74.5337 | 76.6562 |
| cycle | 3.8339 | 1.0512 | 2.8661 | -31.0975 | -4.5716 | -7.9873 | 74.7568 | 74.3153 | 62.7327 |
| broad | 2.3011 | 0.1889 | 1.0379 | -30.1780 | -4.7560 | -7.8005 | 45.1045 | 74.1517 | 53.0676 |

结论：`balanced_hybrid_60d_exit` 相比旧 hybrid 明显保留更多 60 日收益，broad 从 0.1889% 提升到 1.0379%；但 broad 仍未达到 1.2% 净收益和 50% 收益保留率两条最低线。

## D Broad Key Metrics

| metric | value | target | result |
| --- | ---: | ---: | --- |
| total_signals | 9628 | >= 9000 | pass |
| sample_change_pct | -0.1763 | >= -10 | pass |
| raw_net_60 | 2.3011 | reference | - |
| old_hybrid_exit_net_60 | 0.1889 | reference | - |
| balanced_exit_net_60 | 1.0379 | >= 1.2 | fail |
| return_retention_rate_60d | 45.1045 | >= 50 | fail |
| raw_dd250 | -30.1780 | reference | - |
| old_hybrid_dd250 | -4.7560 | reference | - |
| balanced_dd250 | -7.8005 | significantly better than raw | pass |
| drawdown_reduction_rate_250d | 74.1517 | >= 60 | pass |
| balanced_win_rate_60d | 24.8664 | >= 46 | fail |
| balanced_outperform_60d | 48.8421 | >= 46 | pass |

## E Data Quality

| pool | provider_error_count | pe_missing_count | pb_missing_count | financial_missing_count | valuation_coverage_rate | financial_coverage_rate | risk_review_count |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| core | 0 | 386 | 0 | 0 | 100.0 | 100.0 | 5 |
| cycle | 0 | 798 | 0 | 0 | 100.0 | 100.0 | 5 |
| broad | 0 | 688 | 0 | 0 | 100.0 | 100.0 | 5 |

PE 缺失继续保留在报告字段中，不被当作安全数据；财务缺失数量为 0，但净利润、经营现金流等字段仍需人工复核公开数据质量。

## F Exit Reason Diagnostics

| reason | broad_count | broad_ratio | avg_exit_net_60 | avg_raw_net_60 |
| --- | ---: | ---: | ---: | ---: |
| STOP_LOSS | 6427 | 66.7532 | -5.1123 | -3.5686 |
| TIME_EXIT_60D | 1271 | 13.2011 | 15.4912 | 15.5480 |
| TAKE_PROFIT_TRAIL | 1145 | 11.8924 | 21.9441 | 24.8070 |
| TREND_BREAK_CONFIRMED | 696 | 7.2289 | -2.9406 | -4.6887 |
| INSUFFICIENT_DATA | 85 | 0.8828 | 无可用数据 | 无可用数据 |
| NO_REPAIR_40D | 4 | 0.0415 | -1.6898 | -1.8459 |

STOP_LOSS 触发比例过高，是 broad 收益保留率不足的主要原因。下一轮应继续优化止损分层和假跌破确认，但不能直接取消风险控制。

## G Output Files

三组真实报告均生成：

- `summary.md` / `summary.json`。
- `signal_details.csv`。
- `baseline_comparison.json`。
- `parameter_experiment.json` / `parameter_experiment.md`。
- `exit_policy_experiment.json` / `exit_policy_experiment.md`。
- `strict_observation_candidates.csv`。
- `research_observation_candidates.csv`。
- `balanced_research_observation_candidates.csv`。
- `watch_only_candidates.csv`。
- `paper_observation_candidates.csv` 兼容旧文件名。

候选文件写明：仅用于模拟观察和复盘，不构成买入建议，不应自动交易。

## H Observation Candidates

| pool | strict_candidates | research_candidates | balanced_research_candidates | watch_only_candidates |
| --- | ---: | ---: | ---: | ---: |
| core | 0 | 694 | 1031 | 1533 |
| cycle | 0 | 1872 | 3109 | 4573 |
| broad | 0 | 4667 | 6453 | 9628 |

严格候选仍为 0；balanced research 和 watch-only 只能作为人工复核池，不能称为实盘操作入口。

## I Acceptance Decision

最终枚举：`PASS_EXIT_POLICY_RESEARCH`。

理由：真实公开数据 core/cycle/broad 均可运行，data failures 和 provider errors 均为 0；broad 样本 9628，未出现样本骤降；balanced 退出策略把 broad 250 日 raw hold 回撤从 -30.1780 降到 -7.8005，回撤压降 74.1517%。但 broad 60 日 balanced 净收益 1.0379% 低于 1.2%，收益保留率 45.1045% 低于 50%，balanced 60 日胜率 24.8664% 低于 46%，所以不能输出 `PASS_BALANCED_EXIT_POLICY`，更不能输出 `PASS_PAPER_TRADING_CANDIDATE` 或 `PASS_PAPER_TRADING_READY`。
