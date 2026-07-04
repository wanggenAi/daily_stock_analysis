# GenGe Signal Quality Acceptance Report

## A Runability

- full pytest：`/Users/seker./.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest tests/test_genge_cycle_bottom_*.py`，75 passed，1 warning，耗时 285.93 秒。
- fixture smoke：`reports/genge_cycle_bottom_ci_smoke/20260703_212323`，自然退出，`total_signals=1451`，`data_failures=0`。
- real core：`reports/genge_signal_quality_core/20260703_213113`，自然退出，耗时 460.90 秒，`total_signals=1811`，`data_failures=0`。
- real cycle：`reports/genge_signal_quality_cycle/20260703_220538`，自然退出，耗时 2054.69 秒，`total_signals=5253`，`data_failures=0`。
- real broad：`reports/genge_signal_quality_broad/20260703_230046`，自然退出，耗时 3299.67 秒，`total_signals=9909`，`data_failures=0`。
- 本轮未重新观察 GitHub Actions；本地 full pytest 和 fixture smoke 已通过。
- 不接入券商，不读取账户/持仓/密码/验证码，不自动下单，不打开中信证券交易页面。

## B Baseline Comparison

本轮信号质量基线为 `config/genge_signal_quality_baseline.json` 中的 commit `b2a298b0b2ff35a7454fb0b731c9d5e0c6f07917`。

| pool | signals | sample delta | 60d net delta | 60d win delta | 60d outperform delta | 250d low drawdown delta | overfit |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| core | 1811 | -36.9429% | +3.1324 | +6.7328 | n/a | +0.1182 | false |
| cycle | 5253 | -39.1380% | +2.6904 | +5.2550 | n/a | +1.1470 | false |
| broad | 9909 | -50.6426% | +1.6873 | +3.6948 | +6.3465 | +2.1501 | true |

core/cycle 的 benchmark `000300` 本轮所有数据源失败，跑赢基准指标不可比；broad 的 benchmark `000905` 由 Akshare 获取成功。broad 虽然 60 日胜率和跑赢率提升达到 3pct 要求，但样本相对 b2a baseline 下降超过 50%，且 250 日低点回撤改善 2.1501pct，未达到 3pct 或不差于 -28% 的升级线。

## C Strategy Quality

| pool | 20d net | 60d net | 120d net | 250d net | 60d win | 60d outperform | 250d low drawdown |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| core | 1.0745 | 2.0167 | 3.8138 | 7.8714 | 50.7778% | n/a | -31.4643% |
| cycle | 0.8964 | 4.6133 | 7.1859 | 12.6794 | 52.0953% | n/a | -30.3673% |
| broad | -0.1427 | 2.0838 | 3.9176 | 6.9694 | 46.5738% | 46.6653% | -29.0947% |

| pool | stop-adjusted 60d net | balanced 60d net | balanced 60d win | balanced 60d outperform | balanced 250d drawdown |
| --- | ---: | ---: | ---: | ---: | ---: |
| core | 2.0485 | 2.1186 | 37.6111% | n/a | -9.7182% |
| cycle | 3.0325 | 3.5191 | 38.5236% | n/a | -9.8077% |
| broad | 1.1986 | 1.9090 | 34.9024% | 51.5250% | -9.8373% |

broad 趋势确认分布为 `STRONG=4450`、`MEDIUM=2789`、`WEAK=2670`。当前 `hard_logic_level` 全部为 `NONE`，说明本轮 signal-quality 跑法没有启用行业证据输入，不把证据模板或样板行业强行转成硬逻辑候选。

## D Failure Reason Changes

`config/genge_signal_quality_baseline.json` 中的 b2a 指标基线不包含 failure reason 明细，因此 failure reason change 不能直接声明为相对 20076 条原始 baseline 的变化。这里使用本地可复核的最早 b2a 标记宽池运行 `reports/genge_signal_quality_broad/20260628_151610` 做原因分布对照，并同时观察上一条 signal-quality 宽池运行 `reports/genge_signal_quality_broad/20260703_145745`。

| failure reason | earliest local b2a run | previous signal-quality run | current broad | current vs earliest | current vs previous |
| --- | ---: | ---: | ---: | ---: | ---: |
| 买太早 | 7601 / 59.77% | 5756 / 58.88% | 5823 / 58.76% | -1778 / -1.00pct | +67 / -0.12pct |
| 止损不够严格 | 8679 / 68.24% | 6637 / 67.90% | 6731 / 67.93% | -1948 / -0.31pct | +94 / +0.03pct |
| 估值陷阱 | 5422 / 42.63% | 4039 / 41.32% | 4095 / 41.33% | -1327 / -1.31pct | +56 / +0.01pct |
| 趋势未确认 | 475 / 3.73% | 374 / 3.83% | 374 / 3.77% | -101 / +0.04pct | 0 / -0.05pct |
| 行业周期判断不足 | 9010 / 70.84% | 6755 / 69.10% | 6860 / 69.23% | -2150 / -1.61pct | +105 / +0.13pct |

broad 当前失败原因计数：行业周期判断不足 6860，止损不够严格 6731，买太早 5823，估值陷阱 4095，持有周期不适合 1605，趋势未确认 374，长周期位置风险 89，大盘环境差 54。

质量过滤摘要：`high_execution_risk_count=4`，`long_term_position_degraded_count=114`，`falling_knife_filtered_count=0`，`value_trap_flagged_count=0`，`missing_financial_uncertain_count=0`。

## E Execution Feasibility

broad 执行诊断：`limit_up_entry_count=3`，`limit_down_entry_count=1`，`missing_entry_count=0`，`degraded_entry_count=2`，`low_liquidity_count=0`，`abnormal_gap_open_count=6`，`risky_entry_count=4`。

broad 执行风险分布：低风险 9903，降级 2，高风险 4。估值覆盖率 100.0%，财务覆盖率 100.0%，PE 缺失 691，PB 缺失 0，财务缺失 0，风险复核数量 5。

## F Observation Candidates

- `paper_observation_candidates.csv` 已生成，真实候选数 0，仅有免责声明占位行。
- `research_observation_candidates.csv` 摘要计数：core 709，cycle 1803，broad 4841。
- `balanced_research_observation_candidates.csv` 摘要计数：core 968，cycle 2858，broad 5485。
- `strict_observation_candidates.csv` 摘要计数：0。
- `watch_only_candidates.csv` 摘要计数：core 1811，cycle 5253，broad 9909。
- 禁用确定性承诺和交易指令短语扫描未命中。

候选文件免责声明为“仅用于模拟观察和复盘；研究观察候选需人工复核，不构成买入建议，不应自动交易。”

猪肉、面板、牧原股份、TCL科技只作为样板行业和样板股票出现在 example/template 或 user supplied evidence 文件中；`src/` 和运行逻辑没有把它们硬编码为候选，也没有强制入选。

## G Acceptance Decision

最终枚举：`PASS_REAL_DATA_RESEARCH`。

没有升级到 `PASS_SIGNAL_QUALITY_IMPROVED` 的阻塞原因：

- broad 样本相对 b2a baseline 下降 50.6426%，超过 50% 的样本稳定性红线。
- broad 250 日低点回撤为 -29.0947%，只比 baseline 改善 2.1501pct，未达到改善 3pct 或不差于 -28% 的升级线。
- broad 60 日胜率 46.5738%，仍低于更高模拟观察门槛；paper observation 候选数为 0。

当前版本可以作为真实公开数据研究和复盘报告继续使用；不能声明模拟盘候选、模拟盘就绪或交易可执行。
