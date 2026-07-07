# GenGe Opportunity Discovery

`src.strategies.genge_opportunity_discovery` 是日常盘前研究流程，不是自动交易系统。它只读取公开行情、估值、财务和用户维护证据；不接券商、不读取账户/持仓/密码/验证码、不自动买入/卖出/撤单。

## 目标

这个流程回答三个问题：

- 明天盘前优先人工复核哪些股票。
- 每只股票为什么不能直接进入严格候选，还缺哪些行业/公司证据。
- 进入 A/B 观察的股票，后续 5/10/20/40/60 个交易日表现如何被前向记录。

所有股票都只能是 `研究候选`、`人工复核候选` 或 `观察对象`。报告不承诺收益，不生成实盘委托。

## 运行命令

真实宽池日常运行：

```bash
python3 -m src.strategies.genge_opportunity_discovery.cli \
  --stock-pool-file stock_pools/genge_broad_pool.txt \
  --years 5 \
  --benchmark 000905 \
  --output-dir reports/opportunity_discovery \
  --max-codes 100 \
  --run-mode full \
  --industry-evidence-file data/user_supplied/industry_cycle_evidence.csv \
  --company-evidence-file data/user_supplied/company_cycle_evidence.csv \
  --industry-evidence-schema config/industry_evidence_schema.yaml \
  --industry-alias-map config/industry_alias_map.yaml \
  --as-of-date 2026-07-06 \
  --fixture-smoke-passed \
  --ci-passed
```

如果已经有历史退出画像 CSV，可以追加：

```bash
  --exit-profile-file reports/path/to/exit_profile.csv
```

`exit_profile_file` 至少包含 `code` 和 `balanced_exit_historical_profile` 或 `exit_profile_status`。取值为 `PASSED`、`DEGRADED`、`NOT_AVAILABLE`、`FAILED`。`NOT_AVAILABLE` 和 `DEGRADED` 不会进入 A 类严格候选。

`--run-mode` 支持 `quant-only`、`quant-evidence` 和 `full`，供本地或 GitHub Actions 调度区分运行意图。当前实现仍会生成完整审计文件，但报告会记录 run mode，方便后续按阶段扩展缓存和深度证据抓取。

## 输出文件

每次运行会在 `reports/opportunity_discovery/<timestamp>/` 下生成：

- `quant_screen_all.csv`：全池量化粗筛结果。
- `priority_research_queue.csv`：明天优先人工复核队列。
- `secondary_research_queue.csv`：次级研究队列。
- `tier_a_candidates.csv`：严格研究候选，仍需人工复核。
- `tier_b_watchlist.csv`：观察名单，等待趋势或证据确认。
- `tier_c_evidence_incomplete.csv`：量化形态有吸引力但证据不完整。
- `evidence_gap_report.csv`：行业/公司证据缺口。
- `evidence_inventory.csv`：标准化证据清单，包含发布日期、来源、来源类型、方向、原文摘要、解析状态、证据状态和 warning flags。
- `industry_research_tasks.json`：行业证据采集任务。
- `company_research_tasks.json`：公司证据采集任务。
- `opportunity_changes.csv`：相对上一次机会报告的分层/分数变化。
- `evidence_changes.csv`：相对上一次机会报告的证据状态变化。
- `data_quality_audit.csv`：行情、证据、as-of 防未来函数审计。
- `forward_observation_ledger.csv`：本次报告内的前向观察账本副本。
- `daily_opportunity_report.md/json`：日常汇总报告。

持久前向账本默认写入 `data/opportunity_snapshots/forward_observation_ledger.csv`。它只记录 A/B 观察对象，不重复追加同一天同一代码。

`evidence_inventory.csv` 使用以下核心字段：`evidence_date`、`collected_at`、`industry`、`code`、`stock_name`、`indicator`、`value`、`unit`、`comparison_period`、`direction`、`source`、`source_domain`、`source_type`、`confidence`、`freshness_days`、`raw_excerpt`、`normalized_summary`、`parser`、`parse_status`、`evidence_status`、`warning_flags`。新闻摘要、缺少数值支撑或只有链接的内容只会进入 `LEAD_ONLY` 或 `NEEDS_MANUAL_REVIEW`，不会作为高置信度硬证据。

## 分层标准

A 类要求同时满足：量化研究队列、低位/合理位置、非 falling knife、趋势至少 `MEDIUM`、行业证据和公司证据至少部分验证、硬逻辑至少 `MEDIUM`、估值未失败、财务通过、执行风险不过高、估值陷阱不过高、退出画像 `PASSED`。

B 类是观察名单：已经有一定硬逻辑、趋势或证据基础，但还没有满足 A 的全部条件。

C 类是证据不完整研究对象：量化形态有吸引力，但行业或公司证据缺失、过期、冲突或只有线索。

缺失数据必须显式降级。新闻摘要、链接或无数值支撑的证据会被标为 `LEAD_ONLY` 或需要人工复核；未来日期证据不会参与 as-of 判断。

## 每日自动运行

GitHub Actions 工作流位于 `.github/workflows/genge-opportunity-discovery.yml`。它支持：

- 工作日北京时间 18:30 自动运行，对应 UTC 10:30。
- `workflow_dispatch` 手动运行，可选择 `quant-only`、`quant-evidence` 或 `full`。
- 手动指定股票池和 `max_codes`。
- push / PR 时只跑 fixture smoke 和测试；定时 / 手动时才跑真实日常报告。
- 上传 fixture 和每日 opportunity report artifact。

网络数据源失败时，流程仍会生成 `data_quality_audit.csv`、provider/fallback 分布和缺口报告，不会因为单一数据源失败直接整批报废。

## 扩大股票池

第一阶段可用 `stock_pools/genge_broad_pool.txt --max-codes 100` 验证。扩大到更大 A 股池时，建议：

- 先用必要行情和基础量化指标做粗筛。
- 将 `--priority-queue-size` 控制在 30-50，只对优先队列做深度证据处理。
- 使用 `data/cache/genge_fundamentals` 缓存公开估值和财务成功结果。
- 证据未过期时优先复用 `data/user_supplied` 或后续自动采集缓存。
- 观察 `quant_screen_summary.json` 中的 provider/fallback 分布和阶段耗时，再决定是否扩大 `max_codes`。

## Acceptance Enums

当前支持的日常流程枚举：

- `FAIL_CURRENT_SNAPSHOT`
- `PASS_CURRENT_SNAPSHOT_PIPELINE_READY`
- `PASS_QUANT_RESEARCH_QUEUE_GENERATED`
- `PASS_EVIDENCE_TASKS_GENERATED`
- `PASS_AUTO_EVIDENCE_COLLECTION_READY`
- `PASS_OPPORTUNITY_DISCOVERY_RESEARCH_READY`
- `PASS_TIER_A_CANDIDATE_GENERATED`
- `PASS_FORWARD_OBSERVATION_READY`

`acceptance_milestones` 会保留本次运行已达到的所有里程碑；`acceptance_enum` 是本次最高状态。仅生成任务不能称为证据增强完成，自动证据采集链路必须真实运行并成功取得可验证原文证据，或完成任务并输出可审计失败，才会进入 `PASS_AUTO_EVIDENCE_COLLECTION_READY`。`PASS_FORWARD_OBSERVATION_READY` 只在本次 full 运行存在 A/B 观察对象时升级，已有历史账本记录不会单独抬高本次验收。
