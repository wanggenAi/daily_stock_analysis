# GenGe Exit Balance Acceptance Report

## A Runability

- pytest：`/Users/seker./.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest tests/test_genge_cycle_bottom_*.py -q`，62 passed，1 warning，耗时 67.13 秒。
- fixture smoke：通过，报告路径 `reports/genge_cycle_bottom_ci_smoke/20260630_001300`，耗时 159.13 秒，`total_signals=1451`，`data_failures=0`。
- real core：通过，报告路径 `reports/genge_exit_balance_core/20260630_001811`，耗时 305.26 秒，`total_signals=1535`，`data_failures=0`。
- real cycle：通过，报告路径 `reports/genge_exit_balance_cycle/20260630_003658`，耗时 1120.30 秒，`total_signals=4576`，`data_failures=0`。
- real broad：通过，报告路径 `reports/genge_exit_balance_broad/20260630_011457`，耗时 2256.74 秒，`total_signals=9627`，`data_failures=0`。
- 不接入券商账户，不读取账户/持仓/密码/验证码，不自动下单，不打开中信证券交易页面。

## B Strategy Horizon

- `strategy_primary_horizon = 60d`。
- `strategy_secondary_horizon = 20d/120d`。
- `strategy_risk_horizon = 250d`。
- 250 日 raw hold 只作为风险压力测试，不是默认长期持有目标。
- `balanced_hybrid_60d_exit` 保留为收益/回撤平衡策略，旧 `hybrid_60d_repair_exit` 保留为风险压缩对照；当前默认参数为 `balanced_v7_double_close_stop`。

## C Exit Policy Comparison

| pool | raw_net_60 | old_hybrid_net_60 | balanced_net_60 | raw_dd250 | old_hybrid_dd250 | balanced_dd250 | retention_60d | dd_reduction_250d | efficiency |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| core | 0.2100 | 0.5683 | 1.8757 | -31.5738 | -4.7484 | -9.8741 | 893.1905 | 68.7269 | 76.5886 |
| cycle | 3.8480 | 1.0540 | 3.8867 | -31.0926 | -4.5690 | -10.1031 | 101.0057 | 67.5064 | 70.9423 |
| broad | 2.3054 | 0.1900 | 1.9083 | -30.1730 | -4.7556 | -10.0461 | 82.7752 | 66.7050 | 64.4014 |

结论：`balanced_v7_double_close_stop` 相比旧 hybrid 明显保留更多 60 日收益，broad 从 0.1900% 提升到 1.9083%；为保留收益，250 日退出回撤从旧 hybrid 的 -4.7556 放宽到 -10.0461，仍显著好于 raw hold 的 -30.1730。

## D Broad Key Metrics

| metric | value | target | result |
| --- | ---: | ---: | --- |
| total_signals | 9627 | >= 9000 | pass |
| sample_change_pct | -0.1866 | >= -10 | pass |
| raw_net_60 | 2.3054 | reference | - |
| old_hybrid_exit_net_60 | 0.1900 | reference | - |
| balanced_exit_net_60 | 1.9083 | >= 1.2 | pass |
| return_retention_rate_60d | 82.7752 | >= 50 | pass |
| raw_dd250 | -30.1730 | reference | - |
| old_hybrid_dd250 | -4.7556 | reference | - |
| balanced_dd250 | -10.0461 | significantly better than raw | pass |
| drawdown_reduction_rate_250d | 66.7050 | >= 60 | pass |
| balanced_win_rate_60d | 34.3115 | >= 46 | fail |
| balanced_outperform_60d | 51.3624 | >= 46 | pass |

## E Data Quality

| pool | provider_error_count | pe_missing_count | pb_missing_count | financial_missing_count | valuation_coverage_rate | financial_coverage_rate | risk_review_count |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| core | 0 | 386 | 0 | 0 | 100.0 | 100.0 | 5 |
| cycle | 0 | 797 | 0 | 0 | 100.0 | 100.0 | 5 |
| broad | 0 | 687 | 0 | 0 | 100.0 | 100.0 | 5 |

PE 缺失继续保留在报告字段中，不被当作安全数据；财务缺失数量为 0，但净利润、经营现金流等字段仍需人工复核公开数据质量。

## F Exit Reason Diagnostics

| reason | broad_count | broad_ratio | avg_exit_net_60 | avg_raw_net_60 |
| --- | ---: | ---: | ---: | ---: |
| STOP_LOSS | 4575 | 47.5226 | -7.3781 | -7.2604 |
| TIME_EXIT_60D | 1911 | 19.8504 | 14.0603 | 14.1564 |
| TREND_BREAK_CONFIRMED | 1594 | 16.5576 | -3.5769 | -4.5237 |
| TAKE_PROFIT_TRAIL | 1424 | 14.7917 | 21.6711 | 24.9032 |
| INSUFFICIENT_DATA | 85 | 0.8829 | 无可用数据 | 无可用数据 |
| NO_REPAIR_40D | 38 | 0.3947 | -1.6875 | -2.3531 |

STOP_LOSS 触发比例从 v6 的 50.0831% 降到 47.5226%，收益保留继续改善；但 STOP_LOSS 仍是最拖累收益的原因，下一轮应转向信号质量分层和真/假破位识别，不能直接取消风险控制。

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
| core | 0 | 695 | 859 | 1535 |
| cycle | 0 | 1877 | 2621 | 4576 |
| broad | 0 | 4672 | 5212 | 9627 |

严格候选仍为 0；balanced research 和 watch-only 只能作为人工复核池，不能称为实盘操作入口。

## I Acceptance Decision

最终枚举：`PASS_EXIT_POLICY_RESEARCH`。

理由：真实公开数据 core/cycle/broad 均可运行，data failures 和 provider errors 均为 0；broad 样本 9627，未出现样本骤降；balanced 退出策略把 broad 60 日退出净收益提高到 1.9083%，收益保留率提高到 82.7752%，并把 250 日 raw hold 回撤从 -30.1730 降到 -10.0461，回撤压降 66.7050%。但 broad balanced 60 日胜率 34.3115% 仍低于 46% 门槛，原始 60 日胜率/跑赢基准和 250 日回撤也仍阻止更高模拟盘枚举，所以不能输出 `PASS_BALANCED_EXIT_POLICY`，更不能输出 `PASS_PAPER_TRADING_CANDIDATE` 或 `PASS_PAPER_TRADING_READY`。
