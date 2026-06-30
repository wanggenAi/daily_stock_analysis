# GenGe Industry Evidence Layer Acceptance Report

## A Runability

- pytest：`/Users/seker./.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest tests/test_genge_cycle_bottom_*.py`，72 passed，1 warning，耗时 235.95 秒。
- fixture smoke：通过，报告路径 `reports/genge_cycle_bottom_ci_smoke/20260630_132735`，`total_signals=1451`，`data_failures=0`。
- real broad：通过，报告路径 `reports/genge_industry_evidence_broad/20260630_162940`，耗时 3446.30 秒，`total_signals=9915`，`data_failures=0`。
- 不接入券商账户，不读取账户/持仓/密码/验证码，不自动下单，不打开中信证券交易页面。

## B Evidence Layer

- 行业证据 schema：`config/industry_evidence_schema.yaml`。
- 行业证据模板：`data/examples/industry_cycle_evidence_template.csv`。
- 公司证据模板：`data/examples/company_cycle_evidence_template.csv`。
- 本次真实运行中 `data/user_supplied/industry_cycle_evidence.csv` 和 `data/user_supplied/company_cycle_evidence.csv` 不存在，脚本降级使用 example/template 文件。
- 行业证据覆盖率 0.7161%，行业证据缺失 9844；公司证据覆盖率 0.0%，公司证据缺失 9915。
- 证据来源分布：行业 `MANUAL_TEMPLATE=71`、`MISSING=9844`；公司 `MISSING=9915`。
- 证据质量分布：`MANUAL_TEMPLATE=71`、`MISSING=9844`；证据置信度分布：`MEDIUM=71`、`LOW=9844`。

## C Output Files

真实报告目录 `reports/genge_industry_evidence_broad/20260630_162940` 已生成：

- `summary.md` / `summary.json`。
- `signal_details.csv`。
- `industry_evidence_cards.md` / `industry_evidence_cards.json`，行业证据卡片 30 个。
- `cycle_turning_point_candidates.csv`。
- `strict_observation_candidates.csv`。
- `research_observation_candidates.csv`。
- `balanced_research_observation_candidates.csv`。
- `watch_only_candidates.csv`。
- `paper_observation_candidates.csv` 兼容旧文件名。

候选文件写明：仅用于模拟观察和复盘；研究观察候选需人工复核，不构成买入建议，不应自动交易。

## D Hard Logic Integration

| item | value |
| --- | ---: |
| hard_logic_level NONE | 9910 |
| hard_logic_level MEDIUM | 5 |
| hard_logic_level STRONG | 0 |
| industry_evidence_score covered signals | 71 |
| company evidence covered signals | 0 |

`STRONG` 硬逻辑不能只靠价格、均线、低位分位或总分产生；模板、过期、冲突或缺失证据都会阻止升级。本轮有 5 条 `MEDIUM` 来自模板证据，只能说明框架链路可运行，不说明行业逻辑已经被真实数据验证。

## E Cycle Screener

| metric | value |
| --- | ---: |
| cycle_turning_point_candidate_count | 0 |
| strict_observation_candidate_count | 0 |
| research_observation_candidate_count | 4831 |
| balanced_research_observation_candidate_count | 5473 |
| watch_only_candidate_count | 9915 |
| risk_review_count | 5 |

`cycle_turning_point_candidates.csv` 本次只有空结果占位行，不能解释为真实周期拐点候选。主候选池仍是人工复核池，不是交易清单。

## F Data Quality

| metric | value |
| --- | ---: |
| provider_error_count | 0 |
| pe_missing_count | 690 |
| pb_missing_count | 0 |
| financial_missing_count | 0 |
| valuation_coverage_rate | 100.0 |
| financial_coverage_rate | 100.0 |

PE 缺失保留为显式统计项，不被当作安全数据；财务覆盖率为 100.0%，但负债、净利润、经营现金流等字段仍应结合公开财报人工复核。

## G Strategy Impact

| metric | value |
| --- | ---: |
| raw avg_net_return_60d | 2.0603 |
| raw win_rate_60d | 46.5256 |
| raw benchmark_outperform_60d | 46.4442 |
| balanced_exit_net_return_60d | 1.8834 |
| balanced_exit_win_rate_60d | 34.7671 |
| balanced_exit_outperform_rate_60d | 51.3423 |
| return_retention_rate_60d | 91.4139 |
| drawdown_reduction_rate_250d | 66.1695 |

退出原因诊断：STOP_LOSS 4542 条、占 45.8094%；TIME_EXIT_60D 2099 条、占 21.1699%；TREND_BREAK_CONFIRMED 1754 条、占 17.6904%；TAKE_PROFIT_TRAIL 1393 条、占 14.0494%；INSUFFICIENT_DATA 81 条；NO_REPAIR_40D 46 条。

## H Acceptance Decision

最终枚举：`PASS_INDUSTRY_EVIDENCE_FRAMEWORK`。

理由：行业周期证据层的 schema、模板、加载、特征合成、硬逻辑降级、证据卡片、周期拐点候选文件和 summary 统计均可运行；真实 broad 全量运行完成且 `data_failures=0`。但用户真实行业/公司证据文件尚未提供，本次主要是模板和缺失证据，不能声称硬逻辑研究已经通过，也不能声称周期拐点筛选器已被真实证据验证。

因此，本轮不能输出 `PASS_HARD_LOGIC_RESEARCH_READY`、`PASS_CYCLE_TURNING_POINT_SCREENER`、`PASS_PAPER_TRADING_CANDIDATE` 或 `PASS_PAPER_TRADING_READY`。下一步应先填充 `data/user_supplied` 下的真实行业和公司证据，再重新跑同一命令复核。
