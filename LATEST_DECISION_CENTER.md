# 三支柱投资决策中心

> 最终页面回答四件事：我的持仓怎么办；社会/市场/资金往哪里去；哪些股票值得行动；今天账户里的钱具体怎么处理。

## 1. 我的持仓：深算后到底怎么办

- 持仓：**4**；已有显式深算：**4**；深算完整：**0**；仍有 gap：**4**。

| 股票 | 现价 | 价值中枢 | 盈亏% | 正式动作 | 现在怎么办 | 估值信心 | 持续研究 | 深算状态 |
|---|---:|---:|---:|---|---|---|---|---|
| 国电南瑞 600406 | 22.86 | 17.46 | -1.15 | REDUCE_25 | **维持减仓25%目标；本轮无新增减仓/退出信号；目标减50股，当前可执行0股（手数约束；禁止向上取整）** | HIGH | ACTIVE/seen=260 | DEEP_REVIEW_PARTIAL |
| 润贝航科 001316 | 26.61 | 49.37 | 3.36 | HOLD_REVIEW | **持有观察** | LOW | ACTIVE/seen=262 | DEEP_REVIEW_PARTIAL |
| 中国平安 601318 | 52.67 | 83.07 | -5.89 | HOLD | **继续持有** | MEDIUM | ACTIVE/seen=187 | DEEP_REVIEW_PARTIAL |
| 洛阳钼业 603993 | 16.61 | 28.13 | -10.82 | HOLD | **继续持有；历史分批加仓授权已消费，本轮新增可执行0股** | HIGH | ACTIVE/seen=229 | DEEP_REVIEW_PARTIAL |

### 估值折价观察（非买单）

100股仅用于展示追加仓位的现金/成本情景；任何正式新增动作都要重新核验市场、授权、已消费额度和即时券商数据。

- **洛阳钼业 603993**：2026-10-08收盘参考价¥16.61，低于模型估值下沿¥18.03约7.87%；现有1100股；假设额外100股约¥1661，平均成本约¥18.4565（未计费用）。**实际可执行0股；不产生新Formal BUY。** 阻断原因：MARKET_NEW_BUY_DISABLED, NO_CURRENT_FORMAL_HOLDING_ADD, DEEP_GATES_NOT_ALL_PASS, BROKER_CASH_UNVERIFIED_LIVE, EXECUTION_QUOTE_NOT_LIVE。

### 每只持仓的决策链

- **国电南瑞 600406**：现价 22.86 / 价值中枢 17.46（价/值 1.31；价值区间 12.84–26.09；区位 **UPPER_VALUE**）；估值信心 **HIGH**；Formal **REDUCE_25**；Deep **PASS 0 / FAIL 0 / UNKNOWN 5**；Lifecycle **ACTIVE / seen=260**；原因码：`V31_IMMEDIATE_VALUATION_SELL;REDUCE_25;SELL_RATIONALE_STABLE_VALUE_PRICE_OVEREXTENSION`。
- **润贝航科 001316**：现价 26.61 / 价值中枢 49.37（价/值 0.54；价值区间 21.64–70.29；区位 **FAIR_VALUE**）；估值信心 **LOW**；Formal **HOLD_REVIEW**；Deep **PASS 2 / FAIL 0 / UNKNOWN 3**；Lifecycle **ACTIVE / seen=262**；原因码：`VALUATION_CONFIDENCE_LOW;REALISTIC_GROWTH_UNSTABLE`。
- **中国平安 601318**：现价 52.67 / 价值中枢 83.07（价/值 0.63；价值区间 未形成完整区间；区位 **UNKNOWN**）；估值信心 **MEDIUM**；Formal **HOLD**；Deep **PASS 0 / FAIL 0 / UNKNOWN 5**；Lifecycle **ACTIVE / seen=187**；原因码：`INSURER_EVIDENCE_VALID;NO_ACTION_THRESHOLD;price_to_neutral=0.634<1.00`。
- **洛阳钼业 603993**：现价 16.61 / 价值中枢 28.13（价/值 0.59；价值区间 18.03–43.07；区位 **BELOW_VALUE**）；估值信心 **HIGH**；Formal **HOLD**；Deep **PASS 4 / FAIL 0 / UNKNOWN 1**；Lifecycle **ACTIVE / seen=229**；原因码：`FUNDAMENTALS_INTACT;NO_ACTION_THRESHOLD`。

## 2. 世界/社会/市场：钱可能在哪里

### 今日A股大盘脉搏

- 2026-10-08：市场 **RED**；数据质量 **OK**；市场分数 **29.22**；仓位倍率 **0.00**。
- 上涨家数占比 **30.97%**；中位涨跌 **-1.05%**；MA20 上方 **30.39%**；MA60 上方 **44.50%**；涨停/跌停 **42/16**。
- 市场读法：**当日上涨面偏弱；短中期趋势仍有分化**。这只是市场环境解释，不自行创造个股 BUY 权限。

### 中长期结构趋势

| 趋势 | 信心 | 结构 | 产业 | A股研究映射 |
|---|---:|---:|---:|---|
| digital_infrastructure | 53.10 | 57.06 | 72.44 | 尚未映射 |
| software_digital_economy | 31.92 | 50.00 | 62.44 | 尚未映射 |
| automotive_industry | 16.09 | 50.00 | 62.50 | 汽车 |
| equipment_investment | 14.65 | 50.00 | 56.89 | 尚未映射 |
| demographic_longevity | 14.64 | 60.32 | 50.00 | 医药 |
| urbanization_services | 14.18 | 58.08 | 50.00 | 尚未映射 |
| research_intensity | 13.95 | 55.04 | 50.00 | 尚未映射 |
| intelligent_ev_supply_chain | 13.91 | 50.00 | 53.63 | 汽车、锂电 |

### 资金流证据覆盖

- 覆盖状态：**MULTI_LAYER_COVERED**；政策资本 **2**；产业资本 **6**；金融资本 **4**；真实需求 **5**。
- 金融资本已有直接证据，但仍需与政策、产业资本、真实需求和个股深算交叉验证。

### 近期市场行为代理

O81机动车、电子产品和日用产品修理业(100.00)、B07石油和天然气开采业(89.34)、D45燃气生产和供应业(82.95)、J66货币金融服务(79.99)、G55水上运输业(78.28)、B06煤炭开采和洗选业(76.78)、G58多式联运和运输代理业(75.67)、D44电力、热力生产和供应业(71.41)

- 已验证的趋势→A股研究交接：**0**。
- 这里不冒充‘主力净流入’；结构趋势、市场行为和个股深算必须分层验证。

## 3. 新机会：润贝型以及其他机会深算结果

- **本轮没有已授权新股 BUY。**
- **本轮没有合格 WAIT_PRICE。**

- Formal/Production Candidate Terminal REJECT：**100**（只做汇总；与下方 Deep Research Terminal 的 RESEARCH_GAP/REJECT 是不同层级）。

## 4. 今日账户资金怎么处理

- 可用现金：**¥50000.00**；可部署预算：**¥0.00**；本轮计划立即投入：**¥0.00**；计划后现金：**¥50000.00**。
- 盘中价覆盖：**0/4**；交易时段：**CLOSED**；行情状态：**OFF_SESSION**。
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
| 市场大趋势 / 全A脉搏 | **ACTIVE** | RED / score=29.22 / 2026-10-08 |
| 持仓 + 估值 + Formal Action | **ACTIVE** | holdings=4 / valuation-covered=4 / formal-source=FINALIZED_CANONICAL_ONLY |
| 持仓估值连续性 / 价值区间 | **ACTIVE** | matched=4 / tracked=6 / formal-recomputed=False |
| Candidate Lifecycle 持续研究记忆 | **ACTIVE** | active=115 / dormant=11 / archived-invalidated=0 / events=13611 / focus=7 |
| Deep 五类硬门槛 + 官方证据 | **ACTIVE** | requested=11 / verified-pass=228 / unresolved=46 |
| Deep Provenance 证据审计 | **ACTIVE** | audit=True / run=37851640564 / unverified-pass=0 |
| 世界 / 社会 / 资本趋势雷达 | **MULTI_LAYER_COVERED** | POLICY_CAPITAL=2 / INDUSTRIAL_CAPITAL=6 / FINANCIAL_CAPITAL=4 / REAL_DEMAND=5 / TECHNOLOGY=0 / GLOBAL_STRUCTURE=6 |
| Deep Research Terminal | **ACTIVE** | BUY=1 / WAIT=0 / GAP=11 / REJECT=0 |
| 资金计划 + 执行价覆盖 | **ACTIVE** | cash=50000.0 / immediate=0.0 / quotes=0/4 |

- Candidate Lifecycle：当前 ACTIVE **115**；DORMANT **11**；ARCHIVED/INVALIDATED **0**；累计生命周期事件 **13611**。DORMANT 表示当前证据 epoch 的研究策略已耗尽，等待新研究证据；它不是归档或失效。
- 上表只统计已经进入生产链并影响最终汇报的能力；仅存在于设计文档、孤立模块或过期 artifact 的功能不算 ACTIVE。

### 当前持仓的持续研究记忆

- 国电南瑞 600406：ACTIVE / tier=PENDING / 历史被系统重新看见 260 次。
- 润贝航科 001316：ACTIVE / tier=PENDING / 历史被系统重新看见 262 次。
- 中国平安 601318：ACTIVE / tier=PENDING / 历史被系统重新看见 187 次。
- 洛阳钼业 603993：ACTIVE / tier=PENDING / 历史被系统重新看见 229 次。

## 自动深算运行状态

- 当前运行状态来源：**TERMINAL_STATUS**
- 深算资料来源：**AUTOMATIC_DEEP_CALCULATION**；资料 Lambda：`37851117013`；与当前运行一致：**True**
- 深算 profile lineage 与当前 runtime 一致。
- Lambda run：`37851117013`
- 触发来源：`GenGe V3.1.1 Hourly Deep Overlay`
- 计算执行：**SUCCESS**
- 运行状态：**COMPLETED**
- 研究过程终态：**EVIDENCE_EXHAUSTED**
- 请求深算：**11**；已处理：**11**；完整：**0**；证据穷尽：**11**。
- Workset profile：总数 **500**；请求代码已落 profile **11**；handoff 未完成 **0**；覆盖可审计：**True**；完整覆盖：**True**。
- 同轮补证据尝试：**2**；取得证据：**29**；推进硬门槛：**3**。
- 尚未解决硬门槛：**46**。
- 未决原因摘要：涉及 11 只；门槛分布：predictability×11、earnings_authenticity×9、financial_safety×9、moat×9、long_term_demand×8；Top原因：SAME_RUN_PIT_EARNINGS_AUTHENTICITY_EVIDENCE_INSUFFICIENT×9、SAME_RUN_PIT_FINANCIAL_SAFETY_EVIDENCE_INSUFFICIENT×9、OFFICIAL_EVIDENCE_RETRY_EXHAUSTED_OR_CORROBORATION_NOT_MET×8、INSUFFICIENT_CONSECUTIVE_COMPLETE_FISCAL_YEARS×7、INSUFFICIENT_MULTI_YEAR_MOAT_EVIDENCE×5；样例：000415[earnings_authenticity:SAME_RUN_PIT_EARNINGS_AUTHENTICITY_EVIDENCE_INSUFFICIENT、financial_safety:SAME_RUN_PIT_FINANCIAL_SAFETY_EVIDENCE_INSUFFICIENT、long_term_demand:OFFICIAL_EVIDENCE_RETRY_EXHAUSTED_OR_CORROBORATION_NOT_MET]；000703[earnings_authenticity:SAME_RUN_PIT_EARNINGS_AUTHENTICITY_EVIDENCE_INSUFFICIENT、financial_safety:SAME_RUN_PIT_FINANCIAL_SAFETY_EVIDENCE_INSUFFICIENT、long_term_demand:OFFICIAL_EVIDENCE_RETRY_EXHAUSTED_OR_CORROBORATION_NOT_MET]；000833[earnings_authenticity:SAME_RUN_PIT_EARNINGS_AUTHENTICITY_EVIDENCE_INSUFFICIENT、financial_safety:SAME_RUN_PIT_FINANCIAL_SAFETY_EVIDENCE_INSUFFICIENT、long_term_demand:OFFICIAL_EVIDENCE_RETRY_EXHAUSTED_OR_CORROBORATION_NOT_MET]；001309[earnings_authenticity:SAME_RUN_PIT_EARNINGS_AUTHENTICITY_EVIDENCE_INSUFFICIENT、financial_safety:SAME_RUN_PIT_FINANCIAL_SAFETY_EVIDENCE_INSUFFICIENT、moat:INSUFFICIENT_MULTI_YEAR_MOAT_EVIDENCE]；001316[long_term_demand:OFFICIAL_EVIDENCE_RETRY_EXHAUSTED_OR_CORROBORATION_NOT_MET、moat:DURABLE_MOAT_CORROBORATION_THRESHOLD_NOT_MET、predictability:INSUFFICIENT_CONSECUTIVE_COMPLETE_FISCAL_YEARS]
- 请求但未进入本次研究工件：**无**。
- 上一次完整终态 run：`37851117013`；执行 **SUCCESS**；研究终态 **EVIDENCE_EXHAUSTED**。
- 是否需要你手工开启下一轮：**False**。
- **执行 SUCCESS 不等于研究 COMPLETE**；EVIDENCE_EXHAUSTED 只表示已进入 profile 的对象完成了有界补证；HANDOFF_INCOMPLETE 表示仍有请求代码未进入 profile，二者都不会把 UNKNOWN 当成 PASS。

## 五类硬门槛已通过的研究线索

- 当前 runtime 中非持仓、非 Formal BUY/WAIT_PRICE、五类硬门槛全部明确 PASS：**0**。
- 这是一层研究资格可见性，不是 BUY/WAIT_PRICE；不会改变阈值、不会把 UNKNOWN 当 PASS，也不会创建 Formal 交易权限。

## 深算终态研究决策

- 终态快照存在：**True**；与当前 Deep Lambda 一致：**True**。
- 终态来源 Lambda：`37851117013`；当前 Lambda：`37851117013`。
- 请求：**12**；研究 BUY：**1**；研究 WAIT_PRICE：**0**；研究 RESEARCH_GAP：**11**；研究 REJECT：**0**。
- 高吸引力但证据不足、优先补证：600406 国电南瑞(quant=32.6435；暂不投入新增资金；等待补齐：predictability、long_term_demand、moat、financial_safety、earnings_authenticity)；601318 中国平安(quant=32.5186；暂不投入新增资金；等待补齐：predictability、long_term_demand、moat、financial_safety、earnings_authenticity)；001316 润贝航科(quant=23.3155；暂不投入新增资金；等待补齐：predictability、long_term_demand、moat)
- 风险预算层 BUILD/PROBE 候选：**1**；该层只把不确定性映射为仓位上限，不把 UNKNOWN 改成 PASS。
  - 603596 伯特利: **BUILD**；conviction=0.889；建议账户上限=3.0%
- **研究 BUY/WAIT_PRICE 与 Formal/Production 权限严格分离**；风险预算建议同样不创建 Formal BUY、持仓加仓授权或自动交易。

## Jev 买入判断（研究建议，不是 Formal BUY）

- 当前可用判断：**12**；其中 ENTRY_NOW **1**；Jev run：`37851831602`。
- **603596 伯特利**：**ENTRY_NOW**；触发=CURRENT_5_OF_5_PASS_TERMINAL_BUY_AND_PRICE_AT_OR_BELOW_RESEARCH_BUY_CEILING；买入价上限=40.9874；首仓=1.0%；最大研究仓位=3.0%；加仓条件=REVALIDATE_5_OF_5_PASS_AND_TERMINAL_BUY_WITH_PRICE_AT_OR_BELOW_CEILING；不追条件=PRICE_ABOVE_40.9874_REQUIRES_REVALUATION；失效条件=ANY_HARD_GATE_FAIL_OR_UNKNOWN_OR_STALE_LINEAGE_INVALIDATES_ENTRY。
- **601965 中国汽研**：**WAIT_EVIDENCE**；触发=RESOLVE_CURRENT_EVIDENCE_OR_HARD_GATE_GAPS_THEN_REVALUE；买入价上限=18.0041；首仓=0.0%；最大研究仓位=0.0%；加仓条件=NO_ADD_UNTIL_ENTRY_CONDITIONS_ARE_REVALIDATED；不追条件=PRICE_ABOVE_18.0041_REQUIRES_REVALUATION；失效条件=ANY_HARD_GATE_FAIL_OR_UNKNOWN_OR_STALE_LINEAGE_INVALIDATES_ENTRY。
- **603986 兆易创新**：**WAIT_EVIDENCE**；触发=RESOLVE_CURRENT_EVIDENCE_OR_HARD_GATE_GAPS_THEN_REVALUE；买入价上限=619.9203；首仓=0.0%；最大研究仓位=0.0%；加仓条件=NO_ADD_UNTIL_ENTRY_CONDITIONS_ARE_REVALIDATED；不追条件=PRICE_ABOVE_619.9203_REQUIRES_REVALUATION；失效条件=ANY_HARD_GATE_FAIL_OR_UNKNOWN_OR_STALE_LINEAGE_INVALIDATES_ENTRY。
- **001316 润贝航科**：**WAIT_EVIDENCE**；触发=RESOLVE_CURRENT_EVIDENCE_OR_HARD_GATE_GAPS_THEN_REVALUE；买入价上限=31.8996；首仓=0.0%；最大研究仓位=0.0%；加仓条件=NO_ADD_UNTIL_ENTRY_CONDITIONS_ARE_REVALIDATED；不追条件=PRICE_ABOVE_31.8996_REQUIRES_REVALUATION；失效条件=ANY_HARD_GATE_FAIL_OR_UNKNOWN_OR_STALE_LINEAGE_INVALIDATES_ENTRY。
- **601318 中国平安**：**WAIT_EVIDENCE**；触发=RESOLVE_CURRENT_EVIDENCE_OR_HARD_GATE_GAPS_THEN_REVALUE；买入价上限=—；首仓=0.0%；最大研究仓位=0.0%；加仓条件=NO_ADD_UNTIL_ENTRY_CONDITIONS_ARE_REVALIDATED；不追条件=NO_VERIFIED_PRICE_CEILING_DO_NOT_CHASE；失效条件=ANY_HARD_GATE_FAIL_OR_UNKNOWN_OR_STALE_LINEAGE_INVALIDATES_ENTRY。
- **603416 信捷电气**：**WAIT_EVIDENCE**；触发=RESOLVE_CURRENT_EVIDENCE_OR_HARD_GATE_GAPS_THEN_REVALUE；买入价上限=36.0288；首仓=0.0%；最大研究仓位=0.0%；加仓条件=NO_ADD_UNTIL_ENTRY_CONDITIONS_ARE_REVALIDATED；不追条件=PRICE_ABOVE_36.0288_REQUIRES_REVALUATION；失效条件=ANY_HARD_GATE_FAIL_OR_UNKNOWN_OR_STALE_LINEAGE_INVALIDATES_ENTRY。
- **000415 渤海租赁**：**WAIT_EVIDENCE**；触发=RESOLVE_CURRENT_EVIDENCE_OR_HARD_GATE_GAPS_THEN_REVALUE；买入价上限=—；首仓=0.0%；最大研究仓位=0.0%；加仓条件=NO_ADD_UNTIL_ENTRY_CONDITIONS_ARE_REVALIDATED；不追条件=NO_VERIFIED_PRICE_CEILING_DO_NOT_CHASE；失效条件=ANY_HARD_GATE_FAIL_OR_UNKNOWN_OR_STALE_LINEAGE_INVALIDATES_ENTRY。
- **000703 恒逸石化**：**WAIT_EVIDENCE**；触发=RESOLVE_CURRENT_EVIDENCE_OR_HARD_GATE_GAPS_THEN_REVALUE；买入价上限=28.1716；首仓=0.0%；最大研究仓位=0.0%；加仓条件=NO_ADD_UNTIL_ENTRY_CONDITIONS_ARE_REVALIDATED；不追条件=PRICE_ABOVE_28.1716_REQUIRES_REVALUATION；失效条件=ANY_HARD_GATE_FAIL_OR_UNKNOWN_OR_STALE_LINEAGE_INVALIDATES_ENTRY。
- **000833 粤桂股份**：**WAIT_EVIDENCE**；触发=RESOLVE_CURRENT_EVIDENCE_OR_HARD_GATE_GAPS_THEN_REVALUE；买入价上限=—；首仓=0.0%；最大研究仓位=0.0%；加仓条件=NO_ADD_UNTIL_ENTRY_CONDITIONS_ARE_REVALIDATED；不追条件=NO_VERIFIED_PRICE_CEILING_DO_NOT_CHASE；失效条件=ANY_HARD_GATE_FAIL_OR_UNKNOWN_OR_STALE_LINEAGE_INVALIDATES_ENTRY。
- **600406 国电南瑞**：**WAIT_EVIDENCE**；触发=RESOLVE_CURRENT_EVIDENCE_OR_HARD_GATE_GAPS_THEN_REVALUE；买入价上限=22.1256；首仓=0.0%；最大研究仓位=0.0%；加仓条件=NO_ADD_UNTIL_ENTRY_CONDITIONS_ARE_REVALIDATED；不追条件=PRICE_ABOVE_22.1256_REQUIRES_REVALUATION；失效条件=ANY_HARD_GATE_FAIL_OR_UNKNOWN_OR_STALE_LINEAGE_INVALIDATES_ENTRY。
- **001309 德明利**：**WAIT_EVIDENCE**；触发=RESOLVE_CURRENT_EVIDENCE_OR_HARD_GATE_GAPS_THEN_REVALUE；买入价上限=625.1495；首仓=0.0%；最大研究仓位=0.0%；加仓条件=NO_ADD_UNTIL_ENTRY_CONDITIONS_ARE_REVALIDATED；不追条件=PRICE_ABOVE_625.1495_REQUIRES_REVALUATION；失效条件=ANY_HARD_GATE_FAIL_OR_UNKNOWN_OR_STALE_LINEAGE_INVALIDATES_ENTRY。
- **603993 洛阳钼业**：**WAIT_EVIDENCE**；触发=RESOLVE_CURRENT_EVIDENCE_OR_HARD_GATE_GAPS_THEN_REVALUE；买入价上限=17.7658；首仓=0.0%；最大研究仓位=0.0%；加仓条件=NO_ADD_UNTIL_ENTRY_CONDITIONS_ARE_REVALIDATED；不追条件=PRICE_ABOVE_17.7658_REQUIRES_REVALUATION；失效条件=ANY_HARD_GATE_FAIL_OR_UNKNOWN_OR_STALE_LINEAGE_INVALIDATES_ENTRY。
- Jev 负责判断；价格阈值和仓位必须通过 deterministic 校验。该层 authority=ADVISORY_ONLY，Formal BUY=false，automatic execution=false。

> 自动触发、自动计算、同轮补证据/有界重试、自动终结、自动持久化、自动刷新决策中心；Formal BUY 权限仍只来自既有 Canonical/Production authority，no_auto_trade=true。

## 全球市场脉搏 / 复市前情报

- Global Pulse：**OK**；全球风险状态：**RISK_OFF**；A股最近有效交易日：**2026-10-08**。
- 休市累计外部缺口风险：**NORMAL**；正向累积：**NONE_IDENTIFIED**。
- 以下均为研究上下文，不产生 Formal BUY/SELL，不自动交易。

### A股休市以来关键外部变化

- **SP500**：休市以来 -0.73%；最近1日 -0.76%；5日 +0.26%；market_date=2026-10-08；freshness=FRESH。
- **NASDAQ**：休市以来 -1.52%；最近1日 -1.47%；5日 -0.26%；market_date=2026-10-08；freshness=FRESH。
- **SOX**：休市以来 -3.59%；最近1日 -3.31%；5日 -4.12%；market_date=2026-10-08；freshness=FRESH。
- **VIX**：休市以来 +1.47%；最近1日 +4.88%；5日 +3.79%；market_date=2026-10-08；freshness=FRESH。
- **US10Y**：休市以来 -0.83%；最近1日 -1.00%；5日 -0.83%；market_date=2026-10-08；freshness=FRESH。
- **DXY**：休市以来 -0.21%；最近1日 -0.16%；5日 +0.15%；market_date=2026-10-08；freshness=FRESH。
- **USDCNH**：休市以来 +0.01%；最近1日 +0.03%；5日 -0.01%；market_date=2026-10-08；freshness=FRESH。
- **HANGSENG**：休市以来 -0.10%；最近1日 -1.43%；5日 -0.78%；market_date=2026-10-08；freshness=LAST_VALID_MARKET_OBSERVATION。
- **COPPER**：休市以来 +0.00%；最近1日 -0.44%；5日 +1.32%；market_date=2026-10-08；freshness=FRESH。
- **GOLD**：休市以来 +0.00%；最近1日 +0.35%；5日 -1.12%；market_date=2026-10-08；freshness=FRESH。
- **CRUDE_OIL**：休市以来 +0.00%；最近1日 +3.78%；5日 -1.35%；market_date=2026-10-08；freshness=FRESH。
- **BTC**：休市以来 -2.82%；最近1日 -3.02%；5日 -5.16%；market_date=2026-10-08；freshness=FRESH。

### 对持仓 / 研究对象的明确传导

- **603993 洛阳钼业**：**NEUTRAL / LOW**；COPPER休市以来+0.00%(NEUTRAL)、GOLD休市以来+0.00%(NEUTRAL)；研究动作：**MONITOR_EXTERNAL_CONTEXT**。
- **601899 **：**NEUTRAL / LOW**；COPPER休市以来+0.00%(NEUTRAL)、GOLD休市以来+0.00%(NEUTRAL)、SILVER休市以来+0.00%(NEUTRAL)；研究动作：**MONITOR_EXTERNAL_CONTEXT**。
- **601168 **：**NEUTRAL / LOW**；COPPER休市以来+0.00%(NEUTRAL)、SILVER休市以来+0.00%(NEUTRAL)；研究动作：**MONITOR_EXTERNAL_CONTEXT**。
- **601020 **：**NEUTRAL / LOW**；GOLD休市以来+0.00%(NEUTRAL)、SILVER休市以来+0.00%(NEUTRAL)；研究动作：**MONITOR_EXTERNAL_CONTEXT**。
- **000426 **：**NEUTRAL / LOW**；SILVER休市以来+0.00%(NEUTRAL)；研究动作：**MONITOR_EXTERNAL_CONTEXT**。

### 下一次A股开盘最该盯什么

- No material holiday gap signal; use global pulse as context and keep company-level gates authoritative.

> 全球市场层只能强化/弱化研究和触发重算；Canonical/Formal authority 保持原样，no_auto_trade=true。
