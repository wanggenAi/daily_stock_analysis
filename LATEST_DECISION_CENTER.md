# 三支柱投资决策中心

> 最终页面回答四件事：我的持仓怎么办；社会/市场/资金往哪里去；哪些股票值得行动；今天账户里的钱具体怎么处理。

## 1. 我的持仓：深算后到底怎么办

- 持仓：**4**；已有显式深算：**4**；深算完整：**0**；仍有 gap：**4**。

| 股票 | 现价 | 价值中枢 | 盈亏% | 正式动作 | 现在怎么办 | 估值信心 | 持续研究 | 深算状态 |
|---|---:|---:|---:|---|---|---|---|---|
| 国电南瑞 600406 | 22.49 | 17.46 | -2.75 | REDUCE_25 | **维持减仓25%目标；本轮无新增减仓/退出信号；目标减50股，当前可执行0股（手数约束；禁止向上取整）** | HIGH | ACTIVE/seen=282 | DEEP_REVIEW_PARTIAL |
| 润贝航科 001316 | 25.29 | 49.37 | -1.77 | HOLD_REVIEW | **持有观察** | LOW | ACTIVE/seen=284 | DEEP_REVIEW_PARTIAL |
| 中国平安 601318 | 51.78 | 83.07 | -7.48 | HOLD | **继续持有** | MEDIUM | ACTIVE/seen=209 | DEEP_REVIEW_PARTIAL |
| 洛阳钼业 603993 | 15.99 | 28.13 | -14.14 | HOLD | **继续持有；历史分批加仓授权已消费，本轮新增可执行0股** | HIGH | ACTIVE/seen=251 | DEEP_REVIEW_PARTIAL |

### 估值折价观察（非买单）

100股仅用于展示追加仓位的现金/成本情景；任何正式新增动作都要重新核验市场、授权、已消费额度和即时券商数据。

- **洛阳钼业 603993**：2026-10-15收盘参考价¥15.99，低于模型估值下沿¥18.03约11.31%；现有1100股；假设额外100股约¥1599，平均成本约¥18.4049（未计费用）。**实际可执行0股；不产生新Formal BUY。** 阻断原因：MARKET_NEW_BUY_DISABLED, NO_CURRENT_FORMAL_HOLDING_ADD, DEEP_GATES_NOT_ALL_PASS, BROKER_CASH_UNVERIFIED_LIVE, EXECUTION_QUOTE_NOT_LIVE。

### 每只持仓的决策链

- **国电南瑞 600406**：现价 22.49 / 价值中枢 17.46（价/值 1.29；价值区间 12.84–26.09；区位 **UPPER_VALUE**）；估值信心 **HIGH**；Formal **REDUCE_25**；Deep **PASS 0 / FAIL 0 / UNKNOWN 5**；Lifecycle **ACTIVE / seen=282**；原因码：`V31_IMMEDIATE_VALUATION_SELL;REDUCE_25;SELL_RATIONALE_STABLE_VALUE_PRICE_OVEREXTENSION`。
- **润贝航科 001316**：现价 25.29 / 价值中枢 49.37（价/值 0.51；价值区间 21.64–70.29；区位 **FAIR_VALUE**）；估值信心 **LOW**；Formal **HOLD_REVIEW**；Deep **PASS 2 / FAIL 0 / UNKNOWN 3**；Lifecycle **ACTIVE / seen=284**；原因码：`VALUATION_CONFIDENCE_LOW;REALISTIC_GROWTH_UNSTABLE`。
- **中国平安 601318**：现价 51.78 / 价值中枢 83.07（价/值 0.62；价值区间 未形成完整区间；区位 **UNKNOWN**）；估值信心 **MEDIUM**；Formal **HOLD**；Deep **PASS 0 / FAIL 0 / UNKNOWN 5**；Lifecycle **ACTIVE / seen=209**；原因码：`INSURER_EVIDENCE_VALID;NO_ACTION_THRESHOLD;price_to_neutral=0.623<1.00`。
- **洛阳钼业 603993**：现价 15.99 / 价值中枢 28.13（价/值 0.57；价值区间 18.03–43.07；区位 **BELOW_VALUE**）；估值信心 **HIGH**；Formal **HOLD**；Deep **PASS 4 / FAIL 0 / UNKNOWN 1**；Lifecycle **ACTIVE / seen=251**；原因码：`FUNDAMENTALS_INTACT;NO_ACTION_THRESHOLD`。

## 2. 世界/社会/市场：钱可能在哪里

### 今日A股大盘脉搏

- 2026-10-15：市场 **RED**；数据质量 **OK**；市场分数 **19.15**；仓位倍率 **0.00**。
- 上涨家数占比 **8.21%**；中位涨跌 **-3.06%**；MA20 上方 **16.37%**；MA60 上方 **24.15%**；涨停/跌停 **36/34**。
- 市场读法：**当日上涨面偏弱；短中期趋势广度都偏弱**。这只是市场环境解释，不自行创造个股 BUY 权限。

### 中长期结构趋势

| 趋势 | 信心 | 结构 | 产业 | A股研究映射 |
|---|---:|---:|---:|---|
| digital_infrastructure | 70.16 | 57.06 | 71.06 | 尚未映射 |
| automotive_industry | 16.09 | 50.00 | 62.50 | 汽车 |
| software_digital_economy | 15.03 | 50.00 | 58.81 | 尚未映射 |
| equipment_investment | 14.65 | 50.00 | 56.89 | 尚未映射 |
| demographic_longevity | 14.64 | 60.32 | 50.00 | 医药 |
| urbanization_services | 14.18 | 58.08 | 50.00 | 尚未映射 |
| research_intensity | 13.95 | 55.04 | 50.00 | 尚未映射 |
| advanced_manufacturing | 11.11 | 48.19 | 45.69 | 专用设备、电气机械、工程机械 |

### 资金流证据覆盖

- 覆盖状态：**MULTI_LAYER_COVERED**；政策资本 **1**；产业资本 **6**；金融资本 **4**；真实需求 **5**。
- 金融资本已有直接证据，但仍需与政策、产业资本、真实需求和个股深算交叉验证。

### 近期市场行为代理

R86新闻和出版业(59.36)、J67资本市场服务(52.11)、C15酒、饮料和精制茶制造业(51.97)、J68保险业(46.04)、Q84卫生(42.96)、C24文教、工美、体育和娱乐用品制造业(39.85)、C14食品制造业(39.33)、J66货币金融服务(39.05)

- 已验证的趋势→A股研究交接：**0**。
- 这里不冒充‘主力净流入’；结构趋势、市场行为和个股深算必须分层验证。

## 3. 新机会：润贝型以及其他机会深算结果

- **本轮没有已授权新股 BUY。**
- **本轮没有合格 WAIT_PRICE。**

- Formal/Production Candidate Terminal REJECT：**93**（只做汇总；与下方 Deep Research Terminal 的 RESEARCH_GAP/REJECT 是不同层级）。

<!-- GEN_GE_DIVERSIFIED_RESEARCH_RADAR_START -->
### 行业去重研究雷达（研究候选，不是买单）

- 全量候选 **501** → 雷达合格 **102**；覆盖 **43** 个行业；同业备选保留 **59** 只。
- 投资者 Top **10** 只 / **10** 个不同行业；其中新研究候选 **9** 只、当前持仓 **1** 只。
- 选择规则：`ONE_REPRESENTATIVE_PER_OFFICIAL_INDUSTRY`；source run：`38762286190`。
- **这只是 RESEARCH_ONLY 研究入口，不是 BUY/WAIT_PRICE，更不会因为进 Top 就获得 Formal BUY。UNKNOWN 仍然不是 PASS。**

| Top | 全局雷达排名 | 股票 | 行业 | 与账户关系 | 研究层级 | PASS | UNKNOWN | Quant | 下一步 |
|---:|---:|---|---|---|---|---:|---:|---:|---|
| 1 | 1 | 伯特利 603596 | C36汽车制造业 | 新研究候选 | FULL_EVIDENCE | 5 | 0 | 56.1976 | VALUATION_CLOSURE |
| 2 | 2 | 洛阳钼业 603993 | B09有色金属矿采选业 | 当前持仓 | UNKNOWN_RESEARCH | 4 | 1 | 30.5767 | EVIDENCE_CLOSURE；待补：predictability |
| 3 | 3 | 百润股份 002568 | C15酒、饮料和精制茶制造业 | 新研究候选 | UNKNOWN_RESEARCH | 2 | 3 | 79.7504 | EVIDENCE_CLOSURE；待补：predictability、long_term_demand、moat |
| 4 | 4 | 宝立食品 603170 | C14食品制造业 | 新研究候选 | UNKNOWN_RESEARCH | 2 | 3 | 78.4577 | EVIDENCE_CLOSURE；待补：predictability、long_term_demand、moat |
| 5 | 6 | 宝钢股份 600019 | C31黑色金属冶炼和压延加工业 | 新研究候选 | UNKNOWN_RESEARCH | 2 | 3 | 76.2159 | EVIDENCE_CLOSURE；待补：predictability、long_term_demand、moat |
| 6 | 7 | 小熊电器 002959 | C38电气机械和器材制造业 | 新研究候选 | UNKNOWN_RESEARCH | 2 | 3 | 75.1164 | EVIDENCE_CLOSURE；待补：predictability、long_term_demand、moat |
| 7 | 8 | 新产业 300832 | C27医药制造业 | 新研究候选 | UNKNOWN_RESEARCH | 2 | 3 | 74.7001 | EVIDENCE_CLOSURE；待补：predictability、long_term_demand、moat |
| 8 | 9 | 白云机场 600004 | G56航空运输业 | 新研究候选 | UNKNOWN_RESEARCH | 2 | 3 | 73.6201 | EVIDENCE_CLOSURE；待补：predictability、long_term_demand、moat |
| 9 | 10 | 益丰药房 603939 | F52零售业 | 新研究候选 | UNKNOWN_RESEARCH | 2 | 3 | 72.6994 | EVIDENCE_CLOSURE；待补：predictability、long_term_demand、moat |
| 10 | 12 | 红塔证券 601236 | J67资本市场服务 | 新研究候选 | UNKNOWN_RESEARCH | 2 | 3 | 71.4798 | EVIDENCE_CLOSURE；待补：predictability、long_term_demand、moat |

- 每只股票的 `global_radar_rank + industry + diversified_rank + PASS/UNKNOWN` 都保留在机器数据里，用来回答“它为什么进榜、为什么不是同业另一只”。
<!-- GEN_GE_DIVERSIFIED_RESEARCH_RADAR_END -->

## 4. 今日账户资金怎么处理

- 可用现金：**¥50000.00**；可部署预算：**¥0.00**；本轮计划立即投入：**¥0.00**；计划后现金：**¥50000.00**。
- 盘中价覆盖：**0/4**；交易时段：**UNKNOWN**；行情状态：**DEGRADED**。
- **本轮没有已授权的新资金投入，约¥50000现金继续保留；已有持仓只按既有 Formal 动作管理，不为了凑交易而买入。**

### 今日最终操作表

| 股票 | 动作 | 股数 | 第一档最高价 | 第二档最高价 | 预计/预留金额 | 执行状态 |
|---|---|---:|---:|---:|---:|---|
| — | 无新增资金动作 | 0 | — | — | 0 | 现金保留；持仓动作见第1节 |

## 决策完整性

- 全部持仓显式深算完整：**False**
- 世界/社会结构趋势证据可用：**True**
- 已验证趋势→A股交接可用：**False**
- Terminal 机会结果可用：**True**

> UNKNOWN != PASS；研究趋势不自动变成 BUY；no_auto_trade=true。

## 今日汇报可执行性

- 行动结论完整：**True**；证据完整：**False**。
- 当前限制：DEEP_RESEARCH_EVIDENCE_PARTIAL、ERA_TO_A_SHARE_HANDOFF_NOT_VALIDATED、LIVE_EXECUTION_QUOTE_COVERAGE_INCOMPLETE_OR_OFF_SESSION。
- 证据不完整不会被冒充 PASS；但它必须被翻译成暂不买、等待、持有或保留现金等明确动作。

## 本次汇报真正用了哪些系统能力

| 能力 | 状态 | 当前真正产出的结果 |
|---|---|---|
| 市场大趋势 / 全A脉搏 | **ACTIVE** | RED / score=19.15 / 2026-10-15 |
| 持仓 + 估值 + Formal Action | **ACTIVE** | holdings=4 / valuation-covered=4 / formal-source=FINALIZED_CANONICAL_ONLY |
| 持仓估值连续性 / 价值区间 | **ACTIVE** | matched=4 / tracked=6 / formal-recomputed=False |
| Candidate Lifecycle 持续研究记忆 | **ACTIVE** | active=100 / dormant=26 / archived-invalidated=0 / events=14796 / focus=7 |
| Deep 五类硬门槛 + 官方证据 | **ACTIVE** | requested=31 / verified-pass=216 / unresolved=123 |
| Deep Provenance 证据审计 | **ACTIVE** | audit=True / run=38801222121 / unverified-pass=0 |
| 世界 / 社会 / 资本趋势雷达 | **MULTI_LAYER_COVERED** | POLICY_CAPITAL=1 / INDUSTRIAL_CAPITAL=6 / FINANCIAL_CAPITAL=4 / REAL_DEMAND=5 / TECHNOLOGY=0 / GLOBAL_STRUCTURE=6 |
| Deep Research Terminal | **ACTIVE** | BUY=1 / WAIT=0 / GAP=29 / REJECT=1 |
| 资金计划 + 执行价覆盖 | **ACTIVE** | cash=50000.0 / immediate=0.0 / quotes=0/4 |

- Candidate Lifecycle：当前 ACTIVE **100**；DORMANT **26**；ARCHIVED/INVALIDATED **0**；累计生命周期事件 **14796**。DORMANT 表示当前证据 epoch 的研究策略已耗尽，等待新研究证据；它不是归档或失效。
- 上表只统计已经进入生产链并影响最终汇报的能力；仅存在于设计文档、孤立模块或过期 artifact 的功能不算 ACTIVE。

### 当前持仓的持续研究记忆

- 国电南瑞 600406：ACTIVE / tier=PENDING / 历史被系统重新看见 282 次。
- 润贝航科 001316：ACTIVE / tier=PENDING / 历史被系统重新看见 284 次。
- 中国平安 601318：ACTIVE / tier=PENDING / 历史被系统重新看见 209 次。
- 洛阳钼业 603993：ACTIVE / tier=PENDING / 历史被系统重新看见 251 次。

## 自动深算运行状态

- 当前运行状态来源：**TERMINAL_STATUS**
- 深算资料来源：**AUTOMATIC_DEEP_CALCULATION**；资料 Lambda：`38800177466`；与当前运行一致：**True**
- 深算 profile lineage 与当前 runtime 一致。
- Lambda run：`38800177466`
- 触发来源：`EVERY_INDUSTRY_READY`
- 计算执行：**SUCCESS**
- 运行状态：**COMPLETED**
- 研究过程终态：**EVIDENCE_EXHAUSTED**
- 请求深算：**31**；已处理：**31**；完整：**1**；证据穷尽：**30**。
- Workset profile：总数 **501**；请求代码已落 profile **31**；handoff 未完成 **0**；覆盖可审计：**True**；完整覆盖：**True**。
- 同轮补证据尝试：**2**；取得证据：**67**；推进硬门槛：**10**。
- 尚未解决硬门槛：**123**。
- 未决原因摘要：涉及 30 只；门槛分布：predictability×28、moat×26、long_term_demand×25、earnings_authenticity×22、financial_safety×22；Top原因：OFFICIAL_EVIDENCE_RETRY_EXHAUSTED_OR_CORROBORATION_NOT_MET×25、INSUFFICIENT_CONSECUTIVE_COMPLETE_FISCAL_YEARS×24、SAME_RUN_PIT_EARNINGS_AUTHENTICITY_EVIDENCE_INSUFFICIENT×22、SAME_RUN_PIT_FINANCIAL_SAFETY_EVIDENCE_INSUFFICIENT×22、INSUFFICIENT_MULTI_YEAR_MOAT_EVIDENCE×19；样例：000096[earnings_authenticity:SAME_RUN_PIT_EARNINGS_AUTHENTICITY_EVIDENCE_INSUFFICIENT、financial_safety:SAME_RUN_PIT_FINANCIAL_SAFETY_EVIDENCE_INSUFFICIENT、long_term_demand:OFFICIAL_EVIDENCE_RETRY_EXHAUSTED_OR_CORROBORATION_NOT_MET]；000415[earnings_authenticity:SAME_RUN_PIT_EARNINGS_AUTHENTICITY_EVIDENCE_INSUFFICIENT、financial_safety:SAME_RUN_PIT_FINANCIAL_SAFETY_EVIDENCE_INSUFFICIENT、long_term_demand:OFFICIAL_EVIDENCE_RETRY_EXHAUSTED_OR_CORROBORATION_NOT_MET]；000557[long_term_demand:OFFICIAL_EVIDENCE_RETRY_EXHAUSTED_OR_CORROBORATION_NOT_MET、moat:INSUFFICIENT_MULTI_YEAR_MOAT_EVIDENCE]；000596[earnings_authenticity:SAME_RUN_PIT_EARNINGS_AUTHENTICITY_EVIDENCE_INSUFFICIENT、financial_safety:SAME_RUN_PIT_FINANCIAL_SAFETY_EVIDENCE_INSUFFICIENT、long_term_demand:OFFICIAL_EVIDENCE_RETRY_EXHAUSTED_OR_CORROBORATION_NOT_MET]；000703[earnings_authenticity:SAME_RUN_PIT_EARNINGS_AUTHENTICITY_EVIDENCE_INSUFFICIENT、financial_safety:SAME_RUN_PIT_FINANCIAL_SAFETY_EVIDENCE_INSUFFICIENT、long_term_demand:OFFICIAL_EVIDENCE_RETRY_EXHAUSTED_OR_CORROBORATION_NOT_MET]
- 请求但未进入本次研究工件：**无**。
- 上一次完整终态 run：`38800177466`；执行 **SUCCESS**；研究终态 **EVIDENCE_EXHAUSTED**。
- 是否需要你手工开启下一轮：**False**。
- **执行 SUCCESS 不等于研究 COMPLETE**；EVIDENCE_EXHAUSTED 只表示已进入 profile 的对象完成了有界补证；HANDOFF_INCOMPLETE 表示仍有请求代码未进入 profile，二者都不会把 UNKNOWN 当成 PASS。

## 五类硬门槛已通过的研究线索

- 当前 runtime 中非持仓、非 Formal BUY/WAIT_PRICE、五类硬门槛全部明确 PASS：**0**。
- 这是一层研究资格可见性，不是 BUY/WAIT_PRICE；不会改变阈值、不会把 UNKNOWN 当 PASS，也不会创建 Formal 交易权限。

## 深算终态研究决策

- 终态快照存在：**True**；与当前 Deep Lambda 一致：**True**。
- 终态来源 Lambda：`38800177466`；当前 Lambda：`38800177466`。
- 请求：**31**；研究 BUY：**1**；研究 WAIT_PRICE：**0**；研究 RESEARCH_GAP：**29**；研究 REJECT：**1**。
- 高吸引力但证据不足、优先补证：600406 国电南瑞(quant=45.7808；暂不投入新增资金；等待补齐：predictability、long_term_demand、moat、financial_safety、earnings_authenticity)；601318 中国平安(quant=32.938；暂不投入新增资金；等待补齐：predictability、long_term_demand、moat、financial_safety、earnings_authenticity)；001316 润贝航科(quant=22.1976；暂不投入新增资金；等待补齐：predictability、long_term_demand、moat)
- 风险预算层 BUILD/PROBE 候选：**2**；该层只把不确定性映射为仓位上限，不把 UNKNOWN 改成 PASS。
  - 603596 伯特利: **BUILD**；conviction=0.8974；建议账户上限=3.0%
  - 603198 迎驾贡酒: **PROBE**；conviction=0.6236；建议账户上限=0.75%
- **研究 BUY/WAIT_PRICE 与 Formal/Production 权限严格分离**；风险预算建议同样不创建 Formal BUY、持仓加仓授权或自动交易。

## Jev 买入判断（研究建议，不是 Formal BUY）

- 当前可用判断：**20**；其中 ENTRY_NOW **1**；Jev run：`38801513036`。
- **603596 伯特利**：**ENTRY_NOW**；触发=CURRENT_5_OF_5_PASS_TERMINAL_BUY_AND_PRICE_AT_OR_BELOW_RESEARCH_BUY_CEILING；买入价上限=37.3431；首仓=1.0%；最大研究仓位=3.0%；加仓条件=REVALIDATE_5_OF_5_PASS_AND_TERMINAL_BUY_WITH_PRICE_AT_OR_BELOW_CEILING；不追条件=PRICE_ABOVE_37.3431_REQUIRES_REVALUATION；失效条件=ANY_HARD_GATE_FAIL_OR_UNKNOWN_OR_STALE_LINEAGE_INVALIDATES_ENTRY。
- **001316 润贝航科**：**WAIT_EVIDENCE**；触发=RESOLVE_CURRENT_EVIDENCE_OR_HARD_GATE_GAPS_THEN_REVALUE；买入价上限=30.3172；首仓=0.0%；最大研究仓位=0.0%；加仓条件=NO_ADD_UNTIL_ENTRY_CONDITIONS_ARE_REVALIDATED；不追条件=PRICE_ABOVE_30.3172_REQUIRES_REVALUATION；失效条件=ANY_HARD_GATE_FAIL_OR_UNKNOWN_OR_STALE_LINEAGE_INVALIDATES_ENTRY。
- **002215 诺 普 信**：**WAIT_EVIDENCE**；触发=RESOLVE_CURRENT_EVIDENCE_OR_HARD_GATE_GAPS_THEN_REVALUE；买入价上限=11.1218；首仓=0.0%；最大研究仓位=0.0%；加仓条件=NO_ADD_UNTIL_ENTRY_CONDITIONS_ARE_REVALIDATED；不追条件=PRICE_ABOVE_11.1218_REQUIRES_REVALUATION；失效条件=ANY_HARD_GATE_FAIL_OR_UNKNOWN_OR_STALE_LINEAGE_INVALIDATES_ENTRY。
- **600523 贵航股份**：**WAIT_EVIDENCE**；触发=RESOLVE_CURRENT_EVIDENCE_OR_HARD_GATE_GAPS_THEN_REVALUE；买入价上限=13.5564；首仓=0.0%；最大研究仓位=0.0%；加仓条件=NO_ADD_UNTIL_ENTRY_CONDITIONS_ARE_REVALIDATED；不追条件=PRICE_ABOVE_13.5564_REQUIRES_REVALUATION；失效条件=ANY_HARD_GATE_FAIL_OR_UNKNOWN_OR_STALE_LINEAGE_INVALIDATES_ENTRY。
- **601069 西部黄金**：**WAIT_EVIDENCE**；触发=RESOLVE_CURRENT_EVIDENCE_OR_HARD_GATE_GAPS_THEN_REVALUE；买入价上限=45.6019；首仓=0.0%；最大研究仓位=0.0%；加仓条件=NO_ADD_UNTIL_ENTRY_CONDITIONS_ARE_REVALIDATED；不追条件=PRICE_ABOVE_45.6019_REQUIRES_REVALUATION；失效条件=ANY_HARD_GATE_FAIL_OR_UNKNOWN_OR_STALE_LINEAGE_INVALIDATES_ENTRY。
- **601318 中国平安**：**WAIT_EVIDENCE**；触发=RESOLVE_CURRENT_EVIDENCE_OR_HARD_GATE_GAPS_THEN_REVALUE；买入价上限=—；首仓=0.0%；最大研究仓位=0.0%；加仓条件=NO_ADD_UNTIL_ENTRY_CONDITIONS_ARE_REVALIDATED；不追条件=NO_VERIFIED_PRICE_CEILING_DO_NOT_CHASE；失效条件=ANY_HARD_GATE_FAIL_OR_UNKNOWN_OR_STALE_LINEAGE_INVALIDATES_ENTRY。
- **603038 华立股份**：**WAIT_EVIDENCE**；触发=RESOLVE_CURRENT_EVIDENCE_OR_HARD_GATE_GAPS_THEN_REVALUE；买入价上限=25.0909；首仓=0.0%；最大研究仓位=0.0%；加仓条件=NO_ADD_UNTIL_ENTRY_CONDITIONS_ARE_REVALIDATED；不追条件=PRICE_ABOVE_25.0909_REQUIRES_REVALUATION；失效条件=ANY_HARD_GATE_FAIL_OR_UNKNOWN_OR_STALE_LINEAGE_INVALIDATES_ENTRY。
- **603268 松发股份**：**WAIT_EVIDENCE**；触发=RESOLVE_CURRENT_EVIDENCE_OR_HARD_GATE_GAPS_THEN_REVALUE；买入价上限=224.6905；首仓=0.0%；最大研究仓位=0.0%；加仓条件=NO_ADD_UNTIL_ENTRY_CONDITIONS_ARE_REVALIDATED；不追条件=PRICE_ABOVE_224.6905_REQUIRES_REVALUATION；失效条件=ANY_HARD_GATE_FAIL_OR_UNKNOWN_OR_STALE_LINEAGE_INVALIDATES_ENTRY。
- **603986 兆易创新**：**WAIT_EVIDENCE**；触发=RESOLVE_CURRENT_EVIDENCE_OR_HARD_GATE_GAPS_THEN_REVALUE；买入价上限=515.7722；首仓=0.0%；最大研究仓位=0.0%；加仓条件=NO_ADD_UNTIL_ENTRY_CONDITIONS_ARE_REVALIDATED；不追条件=PRICE_ABOVE_515.7722_REQUIRES_REVALUATION；失效条件=ANY_HARD_GATE_FAIL_OR_UNKNOWN_OR_STALE_LINEAGE_INVALIDATES_ENTRY。
- **600338 西藏珠峰**：**WAIT_EVIDENCE**；触发=RESOLVE_CURRENT_EVIDENCE_OR_HARD_GATE_GAPS_THEN_REVALUE；买入价上限=—；首仓=0.0%；最大研究仓位=0.0%；加仓条件=NO_ADD_UNTIL_ENTRY_CONDITIONS_ARE_REVALIDATED；不追条件=NO_VERIFIED_PRICE_CEILING_DO_NOT_CHASE；失效条件=ANY_HARD_GATE_FAIL_OR_UNKNOWN_OR_STALE_LINEAGE_INVALIDATES_ENTRY。
- **000096 广聚能源**：**WAIT_EVIDENCE**；触发=RESOLVE_CURRENT_EVIDENCE_OR_HARD_GATE_GAPS_THEN_REVALUE；买入价上限=18.0111；首仓=0.0%；最大研究仓位=0.0%；加仓条件=NO_ADD_UNTIL_ENTRY_CONDITIONS_ARE_REVALIDATED；不追条件=PRICE_ABOVE_18.0111_REQUIRES_REVALUATION；失效条件=ANY_HARD_GATE_FAIL_OR_UNKNOWN_OR_STALE_LINEAGE_INVALIDATES_ENTRY。
- **000415 渤海租赁**：**WAIT_EVIDENCE**；触发=RESOLVE_CURRENT_EVIDENCE_OR_HARD_GATE_GAPS_THEN_REVALUE；买入价上限=—；首仓=0.0%；最大研究仓位=0.0%；加仓条件=NO_ADD_UNTIL_ENTRY_CONDITIONS_ARE_REVALIDATED；不追条件=NO_VERIFIED_PRICE_CEILING_DO_NOT_CHASE；失效条件=ANY_HARD_GATE_FAIL_OR_UNKNOWN_OR_STALE_LINEAGE_INVALIDATES_ENTRY。
- **600318 新力金融**：**WAIT_EVIDENCE**；触发=RESOLVE_CURRENT_EVIDENCE_OR_HARD_GATE_GAPS_THEN_REVALUE；买入价上限=—；首仓=0.0%；最大研究仓位=0.0%；加仓条件=NO_ADD_UNTIL_ENTRY_CONDITIONS_ARE_REVALIDATED；不追条件=NO_VERIFIED_PRICE_CEILING_DO_NOT_CHASE；失效条件=ANY_HARD_GATE_FAIL_OR_UNKNOWN_OR_STALE_LINEAGE_INVALIDATES_ENTRY。
- **601136 首创证券**：**WAIT_EVIDENCE**；触发=RESOLVE_CURRENT_EVIDENCE_OR_HARD_GATE_GAPS_THEN_REVALUE；买入价上限=—；首仓=0.0%；最大研究仓位=0.0%；加仓条件=NO_ADD_UNTIL_ENTRY_CONDITIONS_ARE_REVALIDATED；不追条件=NO_VERIFIED_PRICE_CEILING_DO_NOT_CHASE；失效条件=ANY_HARD_GATE_FAIL_OR_UNKNOWN_OR_STALE_LINEAGE_INVALIDATES_ENTRY。
- **603098 森特股份**：**WAIT_EVIDENCE**；触发=RESOLVE_CURRENT_EVIDENCE_OR_HARD_GATE_GAPS_THEN_REVALUE；买入价上限=—；首仓=0.0%；最大研究仓位=0.0%；加仓条件=NO_ADD_UNTIL_ENTRY_CONDITIONS_ARE_REVALIDATED；不追条件=NO_VERIFIED_PRICE_CEILING_DO_NOT_CHASE；失效条件=ANY_HARD_GATE_FAIL_OR_UNKNOWN_OR_STALE_LINEAGE_INVALIDATES_ENTRY。
- **000703 恒逸石化**：**WAIT_EVIDENCE**；触发=RESOLVE_CURRENT_EVIDENCE_OR_HARD_GATE_GAPS_THEN_REVALUE；买入价上限=24.0384；首仓=0.0%；最大研究仓位=0.0%；加仓条件=NO_ADD_UNTIL_ENTRY_CONDITIONS_ARE_REVALIDATED；不追条件=PRICE_ABOVE_24.0384_REQUIRES_REVALUATION；失效条件=ANY_HARD_GATE_FAIL_OR_UNKNOWN_OR_STALE_LINEAGE_INVALIDATES_ENTRY。
- **002758 浙农股份**：**WAIT_EVIDENCE**；触发=RESOLVE_CURRENT_EVIDENCE_OR_HARD_GATE_GAPS_THEN_REVALUE；买入价上限=9.5417；首仓=0.0%；最大研究仓位=0.0%；加仓条件=NO_ADD_UNTIL_ENTRY_CONDITIONS_ARE_REVALIDATED；不追条件=PRICE_ABOVE_9.5417_REQUIRES_REVALUATION；失效条件=ANY_HARD_GATE_FAIL_OR_UNKNOWN_OR_STALE_LINEAGE_INVALIDATES_ENTRY。
- **600406 国电南瑞**：**WAIT_EVIDENCE**；触发=RESOLVE_CURRENT_EVIDENCE_OR_HARD_GATE_GAPS_THEN_REVALUE；买入价上限=21.7675；首仓=0.0%；最大研究仓位=0.0%；加仓条件=NO_ADD_UNTIL_ENTRY_CONDITIONS_ARE_REVALIDATED；不追条件=PRICE_ABOVE_21.7675_REQUIRES_REVALUATION；失效条件=ANY_HARD_GATE_FAIL_OR_UNKNOWN_OR_STALE_LINEAGE_INVALIDATES_ENTRY。
- **603993 洛阳钼业**：**WAIT_EVIDENCE**；触发=RESOLVE_CURRENT_EVIDENCE_OR_HARD_GATE_GAPS_THEN_REVALUE；买入价上限=17.1026；首仓=0.0%；最大研究仓位=0.0%；加仓条件=NO_ADD_UNTIL_ENTRY_CONDITIONS_ARE_REVALIDATED；不追条件=PRICE_ABOVE_17.1026_REQUIRES_REVALUATION；失效条件=ANY_HARD_GATE_FAIL_OR_UNKNOWN_OR_STALE_LINEAGE_INVALIDATES_ENTRY。
- **000557 西部创业**：**INVALIDATED**；触发=NO_ENTRY_UNTIL_INVALIDATING_EVIDENCE_IS_REVERSED_AND_FULL_REVALIDATION_PASSES；买入价上限=—；首仓=0.0%；最大研究仓位=0.0%；加仓条件=NO_ADD_UNTIL_ENTRY_CONDITIONS_ARE_REVALIDATED；不追条件=NO_VERIFIED_PRICE_CEILING_DO_NOT_CHASE；失效条件=ANY_HARD_GATE_FAIL_OR_UNKNOWN_OR_STALE_LINEAGE_INVALIDATES_ENTRY。
- Jev 负责判断；价格阈值和仓位必须通过 deterministic 校验。该层 authority=ADVISORY_ONLY，Formal BUY=false，automatic execution=false。

> 自动触发、自动计算、同轮补证据/有界重试、自动终结、自动持久化、自动刷新决策中心；Formal BUY 权限仍只来自既有 Canonical/Production authority，no_auto_trade=true。

## 全球市场脉搏 / 复市前情报

- Global Pulse：**OK**；全球风险状态：**NEUTRAL**；A股最近有效交易日：**2026-10-15**。
- 休市累计外部缺口风险：**NORMAL**；正向累积：**NONE_IDENTIFIED**。
- 以下均为研究上下文，不产生 Formal BUY/SELL，不自动交易。

### A股休市以来关键外部变化

- **SP500**：休市以来 +0.02%；最近1日 +0.20%；5日 -1.13%；market_date=2026-10-15；freshness=FRESH。
- **NASDAQ**：休市以来 -0.43%；最近1日 -0.33%；5日 -2.84%；market_date=2026-10-15；freshness=FRESH。
- **SOX**：休市以来 -2.56%；最近1日 -2.77%；5日 -9.42%；market_date=2026-10-15；freshness=FRESH。
- **VIX**：休市以来 -4.31%；最近1日 -2.74%；5日 +12.26%；market_date=2026-10-15；freshness=FRESH。
- **US10Y**：休市以来 -1.91%；最近1日 -1.81%；5日 -2.92%；market_date=2026-10-15；freshness=FRESH。
- **DXY**：休市以来 -0.09%；最近1日 -0.54%；5日 -0.22%；market_date=2026-10-15；freshness=FRESH。
- **USDCNH**：休市以来 -0.03%；最近1日 -0.08%；5日 -0.03%；market_date=2026-10-15；freshness=FRESH。
- **HANGSENG**：休市以来 +0.19%；最近1日 -1.03%；5日 -0.61%；market_date=2026-10-15；freshness=LAST_VALID_MARKET_OBSERVATION。
- **COPPER**：休市以来 +0.00%；最近1日 -0.80%；5日 +0.61%；market_date=2026-10-15；freshness=LAST_VALID_MARKET_OBSERVATION。
- **GOLD**：休市以来 +0.00%；最近1日 +1.67%；5日 +0.47%；market_date=2026-10-15；freshness=LAST_VALID_MARKET_OBSERVATION。
- **CRUDE_OIL**：休市以来 +0.00%；最近1日 +1.60%；5日 +5.60%；market_date=2026-10-15；freshness=LAST_VALID_MARKET_OBSERVATION。
- **BTC**：休市以来 +0.79%；最近1日 +0.56%；5日 -1.05%；market_date=2026-10-15；freshness=FRESH。

### 对持仓 / 研究对象的明确传导

- **603993 洛阳钼业**：**NEUTRAL / LOW**；COPPER休市以来+0.00%(NEUTRAL)、GOLD休市以来+0.00%(NEUTRAL)；研究动作：**MONITOR_EXTERNAL_CONTEXT**。
- **601899 **：**NEUTRAL / LOW**；COPPER休市以来+0.00%(NEUTRAL)、GOLD休市以来+0.00%(NEUTRAL)、SILVER休市以来+0.00%(NEUTRAL)；研究动作：**MONITOR_EXTERNAL_CONTEXT**。
- **601168 **：**NEUTRAL / LOW**；COPPER休市以来+0.00%(NEUTRAL)、SILVER休市以来+0.00%(NEUTRAL)；研究动作：**MONITOR_EXTERNAL_CONTEXT**。
- **601020 **：**NEUTRAL / LOW**；GOLD休市以来+0.00%(NEUTRAL)、SILVER休市以来+0.00%(NEUTRAL)；研究动作：**MONITOR_EXTERNAL_CONTEXT**。
- **000426 **：**NEUTRAL / LOW**；SILVER休市以来+0.00%(NEUTRAL)；研究动作：**MONITOR_EXTERNAL_CONTEXT**。

### 下一次A股开盘最该盯什么

- No material holiday gap signal; use global pulse as context and keep company-level gates authoritative.

> 全球市场层只能强化/弱化研究和触发重算；Canonical/Formal authority 保持原样，no_auto_trade=true。
