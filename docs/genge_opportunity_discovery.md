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

深市主板A股全量机会扫描：

```bash
python3 -m src.strategies.genge_opportunity_discovery.shenzhen_full_scan \
  --max-workers 16 \
  --evidence-queue-size 80 \
  --deep-review-size 30 \
  --max-watchlist 12 \
  --fundamental-limit 30 \
  --industry-evidence-file data/user_supplied/industry_cycle_evidence.csv \
  --company-evidence-file data/user_supplied/company_cycle_evidence.csv \
  --industry-evidence-schema config/industry_evidence_schema.yaml \
  --industry-alias-map config/industry_alias_map.yaml \
  --exit-profile-file data/opportunity_snapshots/exit_profile.csv
```

沪深全 A 统一生产扫描（沪主板、科创板、深主板、创业板）：

```bash
python3 -m src.strategies.genge_opportunity_discovery.all_a_full_scan \
  --max-workers 20 \
  --evidence-queue-size 80 \
  --deep-review-size 30 \
  --max-watchlist 15 \
  --fundamental-limit 30 \
  --industry-evidence-file data/user_supplied/industry_cycle_evidence.csv \
  --company-evidence-file data/user_supplied/company_cycle_evidence.csv \
  --industry-evidence-schema config/industry_evidence_schema.yaml \
  --industry-alias-map config/industry_alias_map.yaml \
  --exit-profile-file data/opportunity_snapshots/exit_profile.csv
```

统一入口从上交所、深交所公开清单的证券类型和板块元数据构建股票池，不按代码前缀猜板块。长期指标只使用截至 `as_of_date` 的前复权日线；报告价位计划只使用同一交易日的未复权价格。`price_mapping_audit.csv` 记录两套价格、映射比例、除权事件判断、数据源和日期，不允许用未复权历史静默替代复权指标。

输出位于 `reports/all_a_full_scan/<下一交易日 YYYYMMDD>/`。用户层级只有 `STRICT_REVIEW_READY`、`CONDITION_WATCH`、`RESEARCH_WATCH` 和 `NOT_QUALIFIED`；后三者风险预算仓位固定为 0。严格候选仍只是公开数据下的人工复核对象，不是交易指令。

全 A 入口同时生成 `daily_signals.csv/json/md`、`buy_signals.csv` 和 `sell_signals.csv`。每日动作语义固定为：

- `BUY_IF_TRIGGERED`：首次满足全部严格门槛，并给出下一交易日的条件区间、止损、逻辑失效价和目标价；价格未触发时不成立。
- `HOLD_REVIEW`：上一日和本日都保持严格资格，继续按原条件人工复核。
- `SELL_EXIT`：上一日严格资格已经丢失，或最新价格触发上一日止损/逻辑失效位；它不读取实际持仓，只表示策略退出。
- `WATCH_ONLY`：只满足观察层条件，仓位固定为 0，不是买入信号。

系统允许某天没有任何买入或卖出信号，禁止为了“每天有票”放宽门槛。退出画像必须包含可追溯数据版本、当前规则版本、最近市场数据日期、至少 30 个总样本和至少 10 个最近两年样本；过期、版本不匹配或不可追溯时自动降级。

板块差异化风控配置位于 `config/board_risk_rules.yaml`。每次运行还会生成股票池来源、排除原因、板块分布、双价格映射、候选升降级、证据变化、退出画像覆盖和报告哈希清单。生产验收枚举为：

- `FAIL_ALL_A_PRODUCTION`
- `PASS_ALL_A_PRODUCTION_RESEARCH_READY`
- `PASS_STRICT_REVIEW_CANDIDATE_GENERATED`

未显式传入日期时，入口使用 `exchange-calendars` 的中国交易日历选择最近已经完整收盘的交易日，并把下一交易日作为报告目标日。盘中手动运行会回退到上一完整交易日，周五收盘后或周末运行会把目标日指向下周一；也可以同时显式传入 `--as-of-date` 和 `--tomorrow` 复现历史报告。

该入口优先使用深交所公开清单中的板块/证券类型字段构建股票池，不用代码前缀猜测主板范围；BaoStock 的证监会行业分类只用于补充细行业，不改变证券范围，也不作为行业硬证据。它先对完整有效股票池做低成本量化粗筛，再只对 Top80/Top30 做重点证据和机会评估。输出目录默认为 `reports/shenzhen_full_scan/<目标交易日 YYYYMMDD>/`，股票池快照默认为 `stock_pools/shenzhen_mainboard_a_full_<行情日 YYYYMMDD>.csv`。

深市全量扫描会生成 `shenzhen_universe.csv`、`universe_exclusion_audit.csv`、`shenzhen_quant_screen_all.csv`、`top80_evidence_queue.csv`、`top30_deep_review.csv`、`buy_ready.csv`、`near_ready.csv`、`deep_watch.csv`、`tomorrow_watchlist_top12.csv`、`buy_sell_price_plan.csv/json`、`evidence_review.md`、`rejection_summary.csv`、`run_summary.json` 和 `tomorrow_watchlist.md`。回踩和突破计划分开计算，正式买入资格只使用真实压力位下的收益风险比；非 `BUY_READY` 对象仓位始终为 0。

候选分层不再按“失败条件数量”决定。`NEAR_READY` 必须没有硬风险，5 年价格分位不高于 50%，趋势至少达到 `WEAK`，估值和财务不得失败，公司改善证据至少部分核验，真实收益风险比不低于 1.0，并且存在可核验证据 URL。行业证据、退出画像或 1.8 收益风险比尚未满足时，它仍然只是等待确认对象，仓位固定为 0；只有全部严格条件满足后才可进入 `BUY_READY`。

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

明日自选与条件化价格计划可在 full 报告生成后运行：

```bash
python3 -m src.strategies.genge_opportunity_discovery.tomorrow_watchlist \
  --opportunity-report-dir reports/opportunity_discovery/<timestamp> \
  --output-dir reports/tomorrow_watchlist/20260708 \
  --as-of-date 2026-07-07 \
  --tomorrow 2026-07-08
```

该步骤只生成公开数据研究观察文件，不接券商、不读取账户、不自动下单。输出目录包含 `tomorrow_watchlist.md`、`tomorrow_watchlist.csv`、`buy_sell_price_plan.csv/json`、`evidence_review.md`、`data_quality_audit.csv` 和 `run_summary.json`。价格计划使用未复权可交易价格，并用区间和条件表达回踩、突破、止损、逻辑失效与止盈，不输出确定性买卖结论。

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
- `workflow_dispatch` 支持手动运行同一套全 A 生产扫描。
- push / PR 时只跑 fixture smoke 和测试；定时 / 手动时才跑真实日常报告。
- 恢复并保存退出画像、证据缓存、全 A 股票池快照和前向观察状态。
- 在 Actions Summary 直接展示 `daily_signals.md`，并上传完整全 A 报告 artifact。

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
