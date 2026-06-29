# GenGe Signal Quality Acceptance Report

## A Runability

- pytest：`/Users/seker./.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest tests/test_genge_cycle_bottom_*.py -q`，60 passed，1 warning。
- fixture smoke：通过，报告路径 `reports/genge_cycle_bottom_ci_smoke/20260629_224223`，`total_signals=1451`，`data_failures=0`。
- real core：通过，报告路径 `reports/genge_exit_balance_core/20260629_225150`，耗时 289.01 秒，`total_signals=1533`，`data_failures=0`。
- real cycle：通过，报告路径 `reports/genge_exit_balance_cycle/20260629_231021`，耗时 1075.91 秒，`total_signals=4573`，`data_failures=0`。
- real broad：通过，报告路径 `reports/genge_exit_balance_broad/20260629_234715`，耗时 2183.43 秒，`total_signals=9628`，`data_failures=0`。
- 不接入券商账户，不读取账户/持仓/密码/验证码，不自动下单，不打开中信证券交易页面。

## B Strategy Horizon

- `strategy_primary_horizon = 60d`。
- `strategy_secondary_horizon = 20d/120d`。
- `strategy_risk_horizon = 250d`。
- 250 日 raw hold 只作为风险压力测试，不是默认长期持有目标。
- 新增 `balanced_hybrid_60d_exit`，旧 `hybrid_60d_repair_exit` 保留为风险压缩对照；当前默认参数为 `balanced_v6_close_confirmed_stop`。

## C Exit Policy Comparison

| pool | raw_net_60 | old_hybrid_net_60 | balanced_net_60 | raw_dd250 | old_hybrid_dd250 | balanced_dd250 | retention_60d | dd_reduction_250d | efficiency |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| core | 0.2042 | 0.5716 | 1.8459 | -31.5759 | -4.7488 | -9.5773 | 903.9667 | 69.6690 | 76.8547 |
| cycle | 3.8339 | 1.0512 | 3.7621 | -31.0975 | -4.5716 | -9.8063 | 98.1272 | 68.4660 | 70.1923 |
| broad | 2.3011 | 0.1889 | 1.7329 | -30.1780 | -4.7560 | -9.7182 | 75.3075 | 67.7971 | 62.2954 |

结论：`balanced_hybrid_60d_exit` 相比旧 hybrid 明显保留更多 60 日收益，broad 从 0.1889% 提升到 1.7329%；但为保留收益，250 日退出回撤从旧 hybrid 的 -4.7560 放宽到 -9.7182，仍显著好于 raw hold 的 -30.1780。

## D Broad Key Metrics

| metric | value | target | result |
| --- | ---: | ---: | --- |
| total_signals | 9628 | >= 9000 | pass |
| sample_change_pct | -0.1763 | >= -10 | pass |
| raw_net_60 | 2.3011 | reference | - |
| old_hybrid_exit_net_60 | 0.1889 | reference | - |
| balanced_exit_net_60 | 1.7329 | >= 1.2 | pass |
| return_retention_rate_60d | 75.3075 | >= 50 | pass |
| raw_dd250 | -30.1780 | reference | - |
| old_hybrid_dd250 | -4.7560 | reference | - |
| balanced_dd250 | -9.7182 | significantly better than raw | pass |
| drawdown_reduction_rate_250d | 67.7971 | >= 60 | pass |
| balanced_win_rate_60d | 33.7001 | >= 46 | fail |
| balanced_outperform_60d | 50.8855 | >= 46 | pass |

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
| STOP_LOSS | 4822 | 50.0831 | -7.4105 | -6.9926 |
| TIME_EXIT_60D | 1870 | 19.4225 | 14.1536 | 14.2432 |
| TREND_BREAK_CONFIRMED | 1414 | 14.6863 | -3.3035 | -4.1368 |
| TAKE_PROFIT_TRAIL | 1405 | 14.5929 | 21.7266 | 24.8874 |
| INSUFFICIENT_DATA | 85 | 0.8828 | 无可用数据 | 无可用数据 |
| NO_REPAIR_40D | 32 | 0.3324 | -1.5982 | -2.3337 |

STOP_LOSS 触发比例从上一轮 66.7532% 降到 50.0831%，收益保留明显改善；但 STOP_LOSS 仍是最拖累收益的原因，下一轮应继续优化止损分层和假跌破确认，不能直接取消风险控制。

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
| core | 0 | 694 | 851 | 1533 |
| cycle | 0 | 1872 | 2590 | 4573 |
| broad | 0 | 4667 | 5081 | 9628 |

严格候选仍为 0；balanced research 和 watch-only 只能作为人工复核池，不能称为实盘操作入口。

## I Acceptance Decision

最终枚举：`PASS_EXIT_POLICY_RESEARCH`。

理由：真实公开数据 core/cycle/broad 均可运行，data failures 和 provider errors 均为 0；broad 样本 9628，未出现样本骤降；balanced 退出策略把 broad 60 日退出净收益提高到 1.7329%，收益保留率提高到 75.3075%，并把 250 日 raw hold 回撤从 -30.1780 降到 -9.7182，回撤压降 67.7971%。但 broad balanced 60 日胜率 33.7001% 仍低于 46% 门槛，原始 60 日胜率/跑赢基准和 250 日回撤也仍阻止更高模拟盘枚举，所以不能输出 `PASS_BALANCED_EXIT_POLICY`，更不能输出 `PASS_PAPER_TRADING_CANDIDATE` 或 `PASS_PAPER_TRADING_READY`。
