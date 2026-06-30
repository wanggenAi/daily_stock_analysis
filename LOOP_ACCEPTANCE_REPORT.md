# GenGe Industry Evidence Layer Acceptance Report

## A Runability

- pytest：行业证据专项测试与报告 CLI 测试已通过，详见 `LOOP_PROGRESS.md` Loop 9 后续记录。
- 最新宽池报告：`reports/genge_industry_evidence_broad/20260630_162940`。
- 全量运行统计文件：`reports/genge_industry_evidence_broad/20260630_162940/full_run_stats.md`。
- 运行耗时记录：`elapsed_until_stopped=47m21s`。报告文件已落盘，但长跑进程最后由人工停止，因此不记为自然退出耗时。
- 不接入券商账户，不读取账户/持仓/密码/验证码，不自动下单，不打开中信证券交易页面。

## B Data Quality

| metric | value |
| --- | ---: |
| total_signals | 9915 |
| data_failures | 0 |
| provider_error_count | 0 |
| pe_missing_count | 690 |
| pb_missing_count | 0 |
| financial_missing_count | 0 |
| main_candidate_count | 5473 |
| risk_review_count | 5 |
| cycle_turning_point_candidate_count | 0 |

PE 缺失保留为显式统计项，不被当作安全数据；财务字段仍需要结合公开财报人工复核。

## C Evidence Inputs

- 样板研究记录：`research/industry_cycle/pork.json/md`、`research/industry_cycle/panel.json/md`。
- 生成的行业证据：`data/user_supplied/industry_cycle_evidence.csv`，16 行。
- 生成的公司证据：`data/user_supplied/company_cycle_evidence.csv`，20 行。
- 拒绝清单：`data/user_supplied/rejected_evidence.csv`，0 行。
- 质量报告：`data/user_supplied/evidence_quality_report.md`，`high_confidence_rows=20`。

猪肉、面板、牧原股份、TCL科技只作为证据链路样板，用于验证公开来源、结构化证据、质量门槛和报告链路；系统不得把它们硬编码为候选，也不得强行让它们入选。

## D Evidence Rules

- 支持 `official_report`、`company_announcement`、`exchange_disclosure`、`research_report_summary`、`news_summary` 等来源类型。
- 缺少 `source`、`date` 或必需字段的证据进入 `rejected_evidence.csv`，不会混入正式 CSV。
- 新闻摘要和研究摘要不能单独形成 `HIGH` 置信度。
- 模板或缺失证据不能形成 `STRONG` 硬逻辑。
- `STRONG` 必须同时具备行业证据和公司证据，且来源质量、来源多样性、时效性和正负方向均通过。

## E Output Files

最新宽池报告目录已生成：

- `summary.md` / `summary.json`。
- `signal_details.csv`。
- `industry_evidence_cards.md` / `industry_evidence_cards.json`。
- `cycle_turning_point_candidates.csv`。
- `strict_observation_candidates.csv`。
- `research_observation_candidates.csv`。
- `balanced_research_observation_candidates.csv`。
- `watch_only_candidates.csv`。
- `paper_observation_candidates.csv`。
- `full_run_stats.md`。
- `pork_panel_deep_dive.md`，文件名兼容旧专项复核，内容为动态样板证据链复核。

候选文件只表示公开数据研究观察，不是交易指令。

## F Hard Logic Integration

逐条信号明细已加入：

- `industry_evidence_items`
- `company_evidence_items`
- `hard_logic_reason`

这三类字段用于解释证据链路，避免只靠价格、均线、低位分位或总分生成硬逻辑。样板对象不参与特殊加分；价格、趋势、估值、财务或风险条件不足时，会按通用规则排除或降级。

## G Broad Run Note

最新宽池报告 `summary.json` 仍记录 evidence file 为 example/template 路径，说明这次落盘报告没有完成一次确认使用 `data/user_supplied` 的干净全量运行。当前 commit 已准备好真实样板证据 CSV、质量门槛和动态样板复核逻辑；下一次用相同宽池命令干净运行，应重点确认 `summary.json -> diagnostics -> industry_evidence_file/company_evidence_file` 指向 `data/user_supplied`。

## H Acceptance Decision

最终枚举：`PASS_INDUSTRY_EVIDENCE_FRAMEWORK`。

理由：行业周期证据层的 schema、证据字段、质量门槛、拒绝清单、特征合成、硬逻辑降级、证据卡片、周期拐点候选文件和动态样板复核均已可运行；最新宽池报告也保留了完整运行统计。但尚未完成一次自然退出且确认使用 `data/user_supplied` 的干净全量宽池运行，因此不能升级为 `PASS_HARD_LOGIC_RESEARCH_READY`、`PASS_CYCLE_TURNING_POINT_SCREENER`、`PASS_PAPER_TRADING_CANDIDATE` 或 `PASS_PAPER_TRADING_READY`。

## I Safety Boundary

本系统只使用公开行情、公开财务和本地结构化研究证据；不接入中信证券或其它券商账户，不读取资产、持仓、密码、验证码，不自动买入、卖出或撤单。所有结论必须由人工结合公告、财报、K线、流动性和风险标签复核。
