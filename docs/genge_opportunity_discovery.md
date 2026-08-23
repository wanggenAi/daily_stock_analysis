# GenGe Opportunity Discovery

`src.strategies.genge_opportunity_discovery` 是日常盘前研究流程，不是自动交易系统。它只读取公开行情、估值、财务和用户维护证据；不接券商、不读取账户/持仓/密码/验证码、不自动买入/卖出/撤单。

## 目标

这个流程回答三个问题：

- 明天盘前优先人工复核哪些股票。
- 每只股票为什么不能直接进入严格候选，还缺哪些行业/公司证据。
- 进入 A/B 观察的股票，后续 5/10/20/40/60 个交易日表现如何被前向记录。

所有股票都只能是 `研究候选`、`人工复核候选` 或 `观察对象`。报告不承诺收益，不生成实盘委托。

## 冻结 V3.1 资格层

宽池量化排序只负责召回研究对象，不再直接授权 A 类或长期 Formal BUY。冻结 V3.1 是 A1/A2/A3 和长期 Formal BUY 的唯一资格层，按以下顺序执行：

1. 可预测性、长期需求、护城河、财务安全、盈利真实性五项硬门槛全部通过。
2. 完成长期需求、护城河方向、盈利质量、ROIC/增量 ROIC、资本配置、成长空间、正常化盈利确定性、市场预期差、估值安全边际和市场位置的 100 分评分。
3. 补齐正常化盈利方法、悲观/中性/乐观/极端压力价值、市场隐含增长、风险调整三年 CAGR、潜在基本面损失和反证条件。
4. 安全边际、风险调整收益、悲观损失、组合暴露和市场位置六项买入条件同时通过。

任何缺失的判断型证据都保持 `UNKNOWN`，不能从旧 Tier A、`TRY_POSITION`、低 PE、高量化分、技术形态或价格大跌推断为通过。失败或未知硬门槛会将对象降为研究/观察，不会被总分或估值补救。`v31_review_queue.csv`、`v31_review_queue.md` 和 `v31_review_queue_summary.json` 用于承接宽池召回后的人工深审；机器只预填价格、已验证正常化盈利等语义明确的字段。

这一资格层只约束研究结论和报告枚举，不读取真实持仓，不连接券商，也不自动下单。

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

统一入口从上交所、深交所公开清单的证券类型和板块元数据构建股票池，不按代码前缀猜板块。长期指标和支撑、阻力、ATR、突破位等计划几何只使用截至 `as_of_date` 的前复权日线，避免把除权前高价误当成当前真实阻力；最终价位再按计划起始日的精确 raw/qfq 因子映射为未复权价格，并只在 raw 口径按 A 股 0.01 元最小价位取整。`price_mapping_audit.csv` 记录两套价格、映射比例、除权事件判断、数据源和日期，不允许用未复权历史静默替代复权指标。

输出位于 `reports/all_a_full_scan/<下一交易日 YYYYMMDD>/`。用户层级只有 `STRICT_REVIEW_READY`、`CONDITION_WATCH`、`RESEARCH_WATCH` 和 `NOT_QUALIFIED`；后三者风险预算仓位固定为 0。严格候选仍只是公开数据下的人工复核对象，不是交易指令。

全 A 入口还会计算一层可审计的现实风险信号：沪深主要指数、全市场涨跌宽度与涨跌停失衡用于判断大盘状态；行业上涨参与度、中位涨跌、均线位置与放量下跌比例用于判断行业状态；个股涨跌、跳空、成交量/成交额相对 20 日水平、收盘位置和均线位置用于判断量价状态；巨潮和上交所近 730 日官方公告用于识别处罚、立案、退市、违约、冻结、事故、停产、预亏、大额减持等重大事件。事件公告可从同一标题识别多个事件类型，并区分 `ACTIVE`、`RESOLVED`、`EXPIRED` 及全部/部分解除；只有仍在有效期内且原文核验成功的活动风险进入负面门槛。标题必须表达事件实际发生或处理进展，年度例行的资金占用专项说明、专项审计或核查意见不会仅凭关键词被误判为高风险。公告接口响应缺字段、计数矛盾、查询截断或原文核验不完整时按 `PARTIAL/FAILED` 失败关闭，不能误当成没有风险。成交量本身不能区分所谓“买入量”和“卖出量”，第三方标注的“主力净流入”不作为事实或独立买入依据。

大盘 `RED`、行业 `CRISIS`、事件风险 `HIGH` 或个股量价为 `DISTRIBUTION/CAPITULATION_RISK` 时，股票不得进入正式条件买入清单。行业缺失或有效样本少于 5 只、重大事件公告扫描为 `UNKNOWN/PARTIAL/FAILED` 时也不放行，不能把“没抓到数据”解释成“没有风险”。主要指数当日数据全部缺失时大盘强制为 `RED`；外围市场使用当前实际日期的已收盘数据并检查时效，避免 A 股长假期间遗漏外盘变化。大盘 `YELLOW` 时严格候选的原风险预算乘以 0.5，行业 `WEAK` 时再乘以 0.75，事件风险 `MEDIUM` 时再乘以 0.75，量价为 `WEAK_DEMAND` 时再乘以 0.8；大盘 `GREEN` 使用原预算。所有非严格候选仓位始终为 0。

全 A 入口同时生成 `daily_signals.csv/json/md`、`buy_signals.csv` 和 `sell_signals.csv`。每日动作语义固定为：

- `BUY_IF_TRIGGERED`：满足全部严格门槛并具有下一交易日可执行的条件。回踩方案给出价格区间；突破方案只有在上一完整交易日已经收盘突破且整日成交量达标后，才给出下一交易日开盘区间。任何方案都必须低于最高买价且未出现取消条件，才可人工考虑；一字板日线无法证明排队委托成交，因此不会被记成参考买入。
- `HOLD_REVIEW`：系统已经观察到参考入场触发，但无法知道用户是否成交；若实际持仓则继续复核，必须人工确认持仓状态。参考入场、冻结止损和后续 OHLC/均线统一使用同一前复权口径。
- `SELL_EXIT`：只有先前已经观察到参考入场或进入持仓复核状态才可能生成。系统逐日执行与历史画像一致的 balanced-v7 逻辑：有效保护止损（中强趋势允许双收盘确认，但 2.5% 硬穿立即触发）、原计划收盘逻辑失效、第 45 个参考持有交易日起的确认趋势破坏、盈利后的分档回撤、第 55 日起仍未修复和固定第 60 日退出。报告在收盘后生成，`exit_earliest_trade_date`/`exit_execution_timing` 明确指向下一交易日开盘；输出始终标记“若已持仓”并要求人工确认，不把触发参考价冒充可成交价。
- `CANCEL_BUY_REVIEW`：待入场计划已被可观察行情明确证伪、出现公司行动/价格基准问题，或触发后资格丢失但未达到退出阈值；前两种情况取消新买入，后一种要求人工复核实际持仓，不等于卖出。单纯运行断档不能证明期间没有成交，不再用它静默取消计划。
- `WATCH_ONLY`：只满足观察层条件，或严格突破候选仍在等待收盘放量确认；仓位固定为 0，不是买入信号。

每日任务使用完整收盘数据生成研究信号，不监控券商成交，也不会盘中自动下单。历史画像对所有收盘后退出信号统一使用下一交易日开盘参考价，并扣除既定费用和滑点；入场当日发生退出条件时也遵守普通 A 股 T+1，不能伪造当日卖出。下一日若是一字跌停，OHLC 无法证明人工卖单成交，退出保持待执行并继续计入锁板期间的风险，直到首个可执行开盘；若历史截止时仍未解锁，则该未完成样本阻断画像，不能贡献 `PASSED`。真实成交仍可能因排队、流动性和价格限制偏离开盘参考。

突破信号采用两阶段生命周期，避免使用尚未完成的整日成交量：第一天只观察收盘价和完整成交量，确认日不追买；确认后的报告把下一交易日标为 `BUY_IF_TRIGGERED`，只有开盘价仍在原突破价与最高追价之间才成立。确认窗口内（包括确认日）只要最低价先触及冻结止损，或收盘价触及冻结逻辑失效位，计划立即取消。开盘低于原突破价、高于最高追价或盘前出现取消条件也会取消。若两次成功运行之间缺少交易日，系统无法证明期间是否已触发买入：冻结阈值已经被击穿时给出“若已成交需退出”的 `SELL_EXIT`，否则转为零仓位的 `HOLD_REVIEW` 并要求人工确认，不臆造“未成交”。若开盘入场与保护位在同一根日线内交错，系统会保存条件参考入场、价格基准和退出状态，但仍要求用户确认是否真实成交；若同日 balanced-v7/逻辑失效条件确实成立，则只生成“若已成交，下一交易日最早退出”的 T+1 条件信号，不臆造账户持仓或当日卖出。

系统每天固定输出 `daily_candidate_top5.csv/md`。正式 `BUY_IF_TRIGGERED` 始终排在最前；其余候选先排除大盘红灯、重大事件、执行风险等安全阻断，再按“失败门槛族更少、失败门槛总数更少、可操作性分更高”排序，因此 Top5 表示最接近正式条件且风险更可控的五只，而不是单纯综合分最高的五只。深度候选不足时再用量化排名补足。Top5 保留当天真实动作（买入、持仓复核、退出、取消或仅观察），并同时输出完整 `strict_gate_failed`；只有动作正好是 `BUY_IF_TRIGGERED` 的行才标记 `formal_buy_eligible=True`。`actionable_execution_list.csv/json/md` 与当日 `BUY_IF_TRIGGERED` 的代码集合严格相等，并与 `SELL_EXIT/CANCEL_BUY_REVIEW` 互斥。正式可买清单允许为 0，系统不会为了凑满五只而放宽门槛。

系统允许某天没有任何正式买入或卖出信号，禁止为了“每天有票”放宽门槛。入场计划从生成起固定，最多等待 10 个已观察交易日；不会因为每天重算支撑位而漂移。计划创建时保存该日 raw/qfq 价格基准，等待期间每天用当前历史重新核对同一日期；除权重写或映射缺失会先取消旧计划，不能用旧 raw 入场区产生新买入。首次观察到触发后冻结原计划、参考成交价、止损、逻辑失效位、入场日 raw/qfq 基准和退出状态；后续直接使用长历史中保留的精确 `adjustment_ratio` 重新计算“入场当天”的比率，而不是比较通常仍等于 1 的最新日比率，因此拆股、送股等前复权重写不会被误当成暴跌止损。故障回退缓存也必须恰好覆盖本次 `as_of_date`，旧缓存不能支撑当日可买信号。

当日相同行情重复运行不会重复累加持有天数；同一交易日的数据源若更正 OHLC、均线或复权基准，系统不会把更正后的日线当作新的一天，也不会沿用旧买卖动作，而是取消待买计划或把可能持仓转人工复核。行情连续性按交易所交易日历验证，不用自然日或简单工作日猜测。任何复权映射、退出状态或行情连续性错误都会保留上一成功处理日期并标记未解决断档，下一日不能静默跳过可能发生的买入、止损或持有计数。状态文件缺失或损坏时先备份并在本次运行关闭全部新买入。活跃计划和可能持仓会进入 `active_signal_review_queue.csv`，不受正常 Top80/Top30 研究名额截断。

为避免退出画像永远只覆盖当天 Top80，系统还会从 Top80 和活跃信号之外选取最多 40 只 `PRIORITY_RESEARCH/SECONDARY_RESEARCH` 股票，写入 `exit_profile_exploration_queue.csv` 并刷新长历史画像。队列先保留此前仍然有效的通过画像，再按 ISO 周、行业和代码哈希进行行业分散轮换；选择过程不读取本次新计算的回测结果。探索股票一旦真实通过画像，会被提升到深度证据队列；这只是扩大验证覆盖面，不改变任何样本、收益、回撤、近期稳定性或现实风险门槛。

退出画像使用两级验证。系统先验证候选自身与当天入场模式完全相同的历史触发，要求至少 12 个互不重叠且可重放的完成样本；每个样本观察最多 60 个持有交易日，并至少保留第 61 根行情作为下一交易日开盘执行证据；若遇连续一字跌停则继续跟踪到首个可执行开盘，样本间隔按真实退出执行日控制，最近两年至少 3 个完成样本且近期平均净收益不为负。公司行动映射变化、已知行情断档和不足 61 根后续行情的正常右删失不参与收益、胜率或回撤计算，但保留在可重放覆盖率分母中；个股和参考组都必须达到至少 80% 覆盖率，且断档样本不得超过全部结果尝试的 5%。自身证据不足时，使用固定参考分区：每个板块最多抽取 12 只并优先覆盖不同行业，选择只依赖板块、行业和版本化代码哈希，不依赖当天排名或回测结果。固定分区可以与 Top80 或目标候选重合，但验证某只目标时会先剔除该目标的全部样本（leave-one-out），不会用自身证明自身。

参考验证严格区分 `pullback` 与 `breakout`，并按主板/成长板风险族分组。每个时期必须至少包含 3 只股票；下一时期只有在上一时期所有成员的真实退出执行日都结束后才可开始，不能用简单工作日偏移冒充独立。至少需要 12 个时期、8 只股票，最近两年至少 3 个时期和 5 只股票；单只股票最多出现在 50% 的有效时期。时期平均收益、单侧置信下界、盈利时期比例、平均/尾部回撤、成员胜率、成员收益/回撤尾部和近期稳定性必须全部通过。候选自身已有明显负收益、失败画像或近期恶化时，会否决再好的参考结果；参考画像通过的风险预算乘 0.5。参考分区来自当前上市股票，仍存在幸存者偏差，因此半仓限制不能视为收益保证。

`run_summary.json.exit_profile_strategy_health` 明确区分三种状态：已有候选自身/回退画像通过、只有参考组通过但当前候选未通过、或 `NO_VALIDATED_EXIT_EDGE`。最后一种表示历史入场/退出证据本身没有证明正向优势，不是 GitHub 运行失败；此时严格候选和正式买入必须为 0。Top5 的 `exit_profile_blocker_detail` 会同时列出个股样本数、最近样本、平均收益/胜率，以及参考组时期数、置信下界、成员胜率和近期稳定性，避免只显示含糊的“画像未通过”。

回放只使用当时可见数据：技术几何在未被公司行动机械断点污染的 qfq 上计算，使用精确日期复权因子映射到 raw 一分钱价位，再用同日 raw OHLC 判断计划是否真实触发。可由历史 OHLCV 在当时重建的上市时长、换手、过热、趋势、价格分位、下跌刀口和量价风险门槛会逐日重放；当前公告、财务、行业证据和大盘状态仍由当日生产门槛独立核验，不会用今天的信息伪造历史证据。突破必须收盘和整日成交量确认，下一交易日开盘未超过最高追价才计入，确认前的冻结止损/失效也与线上规则一致；止损、逻辑失效、趋势破坏、盈利回撤、长期未修复和第 60 日退出均进入同一状态机，之后按下一交易日开盘计算。MA20/MA60 先在每个历史时点的完整既有行情上计算；最大回撤包含退出信号日低点、后续锁板低点和最终可执行开盘跳空，但不包含已经按开盘退出后的日内低点。待入场或持有窗口跨越 raw/qfq 因子变化、已知行情断档或在数据截止时尚未成熟时，结果标为不可重放并进入覆盖率审计，不得贡献收益或回撤；覆盖率或断档比例不达标仍不能 `PASSED`。一字跌停触发退出后截至数据截止仍无法成交、执行日期无法映射或出现未知不完整原因时属于硬否决，不能通过“排除样本”消除最差尾部风险。数据哈希覆盖 qfq/raw OHLC、精确因子、成交量、金额、入场参数和规则版本。长历史优先用公开 raw 行情和 qfq factor 构造无两位小数损失的 qfq，主源失败后尝试 raw/qfq 双序列第二数据源，再使用 7 日内且通过代码、请求截止日、实际数据截止日、行数和 SHA256 校验的缓存；候选或参考覆盖率低于 75% 时，本次运行仍输出 Top5/审计报告，但 `BUY_IF_TRIGGERED` 必须为 0。旧报告聚合画像只能作为种子，旧规则版本不能通过全 A 正式门槛。

国家统计局的工业增加值、工业企业利润、社会消费品零售和工业生产者价格报告属于跨行业统计，标题通常不写具体行业。自动行业证据采集会先识别这类官方报告，再在正文/表格中匹配 canonical 行业或证监会分类别名；数值、发布日期、原始 URL、正文哈希和方向仍必须通过验证。C35、C38、F52 等宽分类只映射到“专用设备”“电气机械”“零售”等同粒度行业，不会伪装成医疗器械、家电等更细结论。

板块差异化风控配置位于 `config/board_risk_rules.yaml`。每次运行还会生成股票池来源、排除原因、板块分布、双价格映射、候选升降级、证据变化、退出画像覆盖、`exit_profile_exploration_queue.csv`、`exit_profile_validation_reference.csv`、`market_regime.json`、`industry_regimes.csv`、`real_world_signal_audit.csv`、`strict_gate_audit.csv` 和报告哈希清单。`run_summary.json.exit_profile_refresh` 会记录逐组参考池的时期数、股票数、收益置信下界、回撤和近期稳定性；`strict_gate_feasibility` 按每一道严格门槛给出失败数量，可以区分真实市场条件未通过和数据链路不可达。生产验收枚举为：

- `FAIL_ALL_A_PRODUCTION`
- `PASS_ALL_A_PRODUCTION_RESEARCH_READY`
- `PASS_STRICT_REVIEW_CANDIDATE_GENERATED`

未显式传入日期时，入口使用 `exchange-calendars` 的中国交易日历选择最近已经完整收盘的交易日，并把下一交易日作为报告目标日。盘中手动运行会回退到上一完整交易日，周五收盘后或周末运行会把目标日指向下周一；也可以同时显式传入 `--as-of-date` 和 `--next-trade-date` 复现历史报告。

### 旧深市主板专用入口

下面的旧深市主板专用入口优先使用深交所公开清单中的板块/证券类型字段构建股票池，不用代码前缀猜测主板范围；BaoStock 的证监会行业分类只用于补充细行业，不改变证券范围，也不作为行业硬证据。它先对完整有效股票池做低成本量化粗筛，再只对 Top80/Top30 做重点证据和机会评估。输出目录默认为 `reports/shenzhen_full_scan/<目标交易日 YYYYMMDD>/`，股票池快照默认为 `stock_pools/shenzhen_mainboard_a_full_<行情日 YYYYMMDD>.csv`。

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

`evidence_inventory.csv` 使用以下核心字段：`evidence_date`、`collected_at`、`industry`、`code`、`stock_name`、`indicator`、`value`、`unit`、`comparison_period`、`direction`、`source`、`source_domain`、`source_type`、`confidence`、`freshness_days`、`raw_excerpt`、`normalized_summary`、`parser`、`parse_status`、`evidence_status`、`warning_flags`。重大事件证据还会记录 `event_kind`、`event_type`、`event_severity`、`event_status`、`resolution_scope` 和 `risk_valid_until`。新闻摘要、缺少数值支撑或只有链接的内容只会进入 `LEAD_ONLY` 或 `NEEDS_MANUAL_REVIEW`，不会作为高置信度硬证据。

公司自动证据对沪深 A 股统一优先查询巨潮资讯官方组织 ID，并直接解析其官方年报 PDF；仅在官方组织 ID 不可用时才尝试交易所回退。行业自动证据同时使用 canonical 行业和 `config/industry_alias_map.yaml` 中的别名，`UNRESOLVED` 不发起无意义采集；“专用设备/机械设备”等跨行业宽泛词不得映射为工程机械，歧义分类宁可保持未解析。物流行业还会读取国家邮政局公开列表，但只接受标题明确属于行业运行、行业发展或业务量统计，且正文包含发布日期和同行数值的原始页面；会议、宣传或只有关键词的页面不会升级为已验证证据。

## 分层标准

A 类要求同时满足：量化研究队列、低位/合理位置、非 falling knife、趋势至少 `MEDIUM`、行业证据和公司证据至少部分验证、硬逻辑至少 `MEDIUM`、估值未失败、财务通过、执行风险不过高、估值陷阱不过高、退出画像 `PASSED`、画像入场模式与当天计划一致、画像来源/仓位系数合法，并通过大盘、行业、量价和事件四道现实风险门槛。

B 类是观察名单：已经有一定硬逻辑、趋势或证据基础，但还没有满足 A 的全部条件。

C 类是证据不完整研究对象：量化形态有吸引力，但行业或公司证据缺失、过期、冲突或只有线索。

缺失数据必须显式降级。新闻摘要、链接或无数值支撑的证据会被标为 `LEAD_ONLY` 或需要人工复核；未来日期证据不会参与 as-of 判断。

## 每日自动运行

GitHub Actions 工作流位于 `.github/workflows/genge-opportunity-discovery.yml`。它支持：

- 工作日北京时间 18:30 自动运行，对应 UTC 10:30。
- `workflow_dispatch` 默认只运行同一套全 A 生产扫描；只有显式勾选 `run_legacy_report` 才额外运行旧深市报告。
- push / PR 时只跑 fixture smoke 和测试；定时 / 手动时才跑真实日常报告。
- 恢复并保存退出画像、证据缓存、全 A 股票池快照和前向观察状态。
- 在 Actions Summary 直接展示 `daily_signals.md`，并上传完整全 A 报告 artifact。

网络数据源失败时，流程仍会生成 `data_quality_audit.csv`、provider/fallback 分布和缺口报告。单只股票行情失败会被审计并在总体覆盖率不低于 95% 时降级继续；覆盖率低于 95% 或其他系统性关键数据失败才使生产验收失败，避免一个坏点拖垮整批扫描。

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
