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

## 输出文件

每次运行会在 `reports/opportunity_discovery/<timestamp>/` 下生成：

- `quant_screen_all.csv`：全池量化粗筛结果。
- `priority_research_queue.csv`：明天优先人工复核队列。
- `secondary_research_queue.csv`：次级研究队列。
- `tier_a_candidates.csv`：严格研究候选，仍需人工复核。
- `tier_b_watchlist.csv`：观察名单，等待趋势或证据确认。
- `tier_c_evidence_incomplete.csv`：量化形态有吸引力但证据不完整。
- `evidence_gap_report.csv`：行业/公司证据缺口。
- `industry_research_tasks.json`：行业证据采集任务。
- `company_research_tasks.json`：公司证据采集任务。
- `opportunity_changes.csv`：相对上一次机会报告的分层/分数变化。
- `evidence_changes.csv`：相对上一次机会报告的证据状态变化。
- `data_quality_audit.csv`：行情、证据、as-of 防未来函数审计。
- `forward_observation_ledger.csv`：本次报告内的前向观察账本副本。
- `daily_opportunity_report.md/json`：日常汇总报告。

持久前向账本默认写入 `data/opportunity_snapshots/forward_observation_ledger.csv`。它只记录 A/B 观察对象，不重复追加同一天同一代码。

## 分层标准

A 类要求同时满足：量化研究队列、低位/合理位置、非 falling knife、趋势至少 `MEDIUM`、行业证据和公司证据至少部分验证、硬逻辑至少 `MEDIUM`、估值未失败、财务通过、执行风险不过高、估值陷阱不过高、退出画像 `PASSED`。

B 类是观察名单：已经有一定硬逻辑、趋势或证据基础，但还没有满足 A 的全部条件。

C 类是证据不完整研究对象：量化形态有吸引力，但行业或公司证据缺失、过期、冲突或只有线索。

缺失数据必须显式降级。新闻摘要、链接或无数值支撑的证据会被标为 `LEAD_ONLY` 或需要人工复核；未来日期证据不会参与 as-of 判断。

## Acceptance Enums

当前支持的日常流程枚举：

- `FAIL_CURRENT_SNAPSHOT`
- `PASS_CURRENT_SNAPSHOT_PIPELINE_READY`
- `PASS_QUANT_RESEARCH_QUEUE_GENERATED`
- `PASS_EVIDENCE_ENRICHMENT_READY`
- `PASS_OPPORTUNITY_DISCOVERY_RESEARCH_READY`
- `PASS_TIER_A_CANDIDATE_GENERATED`
- `PASS_FORWARD_OBSERVATION_READY`

`acceptance_milestones` 会保留本次运行已达到的所有里程碑；`acceptance_enum` 是本次最高状态。`PASS_FORWARD_OBSERVATION_READY` 只在本次运行存在 A/B 观察对象时升级，已有历史账本记录不会单独抬高本次验收。
