# GenGe Signal Quality Acceptance Report

## A Runability

- pytest：52 passed，1 warning。
- fixture smoke：通过，报告路径 `reports/genge_cycle_bottom_ci_smoke/20260628_233336`，耗时 96 秒，`total_signals=1451`，数据失败 0。
- real core：通过，报告路径 `reports/genge_exit_policy_core/20260628_224308`，耗时 235.51 秒，`total_signals=1532`，数据失败 0。
- real cycle：通过，报告路径 `reports/genge_exit_policy_cycle/20260628_225819`，耗时 903.44 秒，`total_signals=4571`，数据失败 0。
- real broad：通过，报告路径 `reports/genge_exit_policy_broad/20260628_232921`，耗时 1855.03 秒，`total_signals=9645`，数据失败 0。
- 不接入券商账户，不读取账户/持仓/密码/验证码，不自动下单，不打开中信证券交易页面。

## B Baseline Comparison

本轮基线更新为 commit `724b8f9d` 的 Loop 3 真实运行结果，目标是验证退出策略是否在不继续压缩样本的前提下改善 250 日死拿风险。

| pool | total | sample_change_pct | overfit_warning | raw_net_60 | win60 | outperform60 | raw_dd250 |
| --- | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| core | 1532 | 0.0000 | false | 0.2042 | 47.5378 | 44.6487 | -31.5753 |
| cycle | 4571 | 0.0000 | false | 3.8339 | 50.5414 | 49.1934 | -31.0902 |
| broad | 9645 | 0.0000 | false | 2.2924 | 46.8619 | 46.5272 | -30.1289 |

结论：core/cycle/broad 的样本数均未相对 `724b8f9d` 下降，broad 保持 9645 条信号，高于 8000 条最低线，没有过拟合警告。

## C 60d Repair And Exit Policy

| pool | raw_net_60 | exit_net_60 | exit_return_impact | raw_dd250 | exit_dd250 | dd_reduction | gate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| core | 0.2042 | 0.5716 | 0.3674 | -31.5753 | -4.7488 | 84.9604 | PASS_EXIT_POLICY_RESEARCH |
| cycle | 3.8339 | 1.0512 | -2.7827 | -31.0902 | -4.5716 | 85.2957 | PASS_EXIT_POLICY_RESEARCH |
| broad | 2.2924 | 0.1857 | -2.1067 | -30.1289 | -4.7574 | 84.2098 | PASS_EXIT_POLICY_RESEARCH |

- `strategy_primary_horizon = 60d`。
- `strategy_secondary_horizon = 20d/120d`。
- `strategy_risk_horizon = 250d`。
- 250 日 raw hold 只代表“如果死拿”的风险压力测试；策略不默认持有到 250 日。
- `hybrid_60d_repair_exit` 显著降低 250 日死拿风险，但 cycle/broad 的 60 日收益伤害偏大，因此退出策略仍处于研究通过阶段。

## D Data Quality

| pool | provider_error_count | pe_missing_count | pb_missing_count | financial_missing_count | valuation_coverage_rate | financial_coverage_rate | risk_review_count |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| core | 0 | 386 | 0 | 0 | 100.0 | 100.0 | 5 |
| cycle | 0 | 798 | 0 | 0 | 100.0 | 100.0 | 5 |
| broad | 0 | 688 | 0 | 0 | 100.0 | 100.0 | 5 |

PE 缺失会保留在报告字段里，不会被当作安全数据；财务缺失数量为 0，但净利润和经营现金流等字段仍需继续复核数据源字段质量。

## E Output Files

三组真实报告均生成：

- `summary.md` / `summary.json`。
- `signal_details.csv`。
- `baseline_comparison.json`。
- `parameter_experiment.json` / `parameter_experiment.md`。
- `exit_policy_experiment.json` / `exit_policy_experiment.md`。
- `strict_observation_candidates.csv`。
- `research_observation_candidates.csv`。
- `paper_observation_candidates.csv` 兼容旧文件名。

候选文件写明：仅用于模拟观察和复盘，不构成买入建议，不应自动交易。

## F Observation Candidates

| pool | strict_candidates | research_candidates |
| --- | ---: | ---: |
| core | 0 | 694 |
| cycle | 0 | 1872 |
| broad | 0 | 4676 |

严格候选仍为 0，说明当前高置信条件很保守；研究候选数量较多，只能作为人工复核池，不能叫买入清单。

## G Acceptance Decision

最终枚举：`PASS_EXIT_POLICY_RESEARCH`。

理由：真实公开数据全量运行通过，data failures 和 provider errors 均为 0；样本数没有相对 `724b8f9d` 继续收缩；退出策略把 broad 的 250 日 raw hold 低点回撤从 -30.1289 降到 -4.7574，回撤降低 84.2098%。但 broad 的 60 日退出净收益从 2.2924 降到 0.1857，60 日胜率 46.8619 低于 52%，60 日跑赢基准 46.5272 低于 50%，因此不能给出 `PASS_60D_REPAIR_STRATEGY_VALIDATED`，更不能给出 `PASS_PAPER_TRADING_READY`。
