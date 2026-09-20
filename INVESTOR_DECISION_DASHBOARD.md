# 投资决策驾驶舱

> 市场=GREEN；持仓减仓/退出=1；新股正式BUY=0；等价格=0；计划立即投入≈¥0；盘中价覆盖=0/4

## 1. 今天市场怎么样

- 市场状态：**GREEN**；是否允许新买：**True**；仓位倍率：**1.00**
- 上涨家数比例：**75.69%**；数据质量：**OK**

- 盘中执行价覆盖：**0/4只**；行情状态：**DEGRADED**；最新行情时间：**—**；正式动作仍来自冻结 Canonical；缺失/过期盘中价会阻断立即执行，不会把冻结价冒充实时价。

## 2. 我的持仓怎么办

- 正式动作是 Canonical 持久状态；同一动作重复出现在后续报表中，不代表再次执行或累计执行。
| 股票 | 持仓 | 成本 | 参考价 | 盈亏% | 正式动作/权限 | 动作状态 | 现在怎么办 |
|---|---:|---:|---:|---:|---|---|---|
| 国电南瑞 600406 | 200 | 23.13 | 22.05 | -4.65 | REDUCE_25 | **UNCHANGED** | **维持减仓25%目标；本轮无新增减仓/退出信号；目标减50股，当前可执行0股（手数约束；禁止向上取整）** |
| 润贝航科 001316 | 200 | 25.75 | 28.11 | 9.19 | HOLD_REVIEW | **UNCHANGED** | **持有观察** |
| 中国平安 601318 | 400 | 55.97 | 53.37 | -4.64 | HOLD | **UNCHANGED** | **继续持有** |
| 洛阳钼业 603993 | 0 | — | 17.51 | — | HOLD | **UNCHANGED** | **继续持有；可分批加仓1手** |

## 3. 今天能直接买什么

| 股票 | 行业 | 当前价 | 估值信心 | 权限 |
|---|---|---:|---|---|
| — | — | — | — | 本轮没有已授权新股BUY |

## 4. WAIT_PRICE：跌到多少钱再买

| 股票 | 当前价 | 最高等待买价 |
|---|---:|---:|
| — | — | 本轮没有合格 WAIT_PRICE |

## 5. 资金怎么花

- 可规划现金：**¥57000.00**；最高部署预算：**¥39900.00**
- 计划立即投入：**¥0.00**；计划后现金：**¥57000.00**
- 只有当前可用 Canonical 持仓分批加仓授权或授权 Terminal BUY 才能进入计划；WAIT_PRICE 只预留，REJECT=0。
- 上方“计划立即投入”只统计当前具备执行条件的动作；缺少有效盘中价、现价高于授权上限等暂不可执行计划不计入。
- 最终操作表会保留已授权计划供审计，并明确标记执行状态；保留计划不等于新增 BUY/ADD 信号。

## 6. 最终操作表

| 股票 | 动作 | 股数 | 第一档最高价 | 第二档最高价 | 预计/预留金额 | 执行状态 |
|---|---|---:|---:|---:|---:|---|
| 洛阳钼业 603993 | **ADD** | 100 | 17.51 | — | 1751.00 | 暂不可立即执行：缺少有效盘中价 |

## 7. 当前强势方向（辅助，不代替BUY权限）

O81机动车、电子产品和日用产品修理业(STRONG)、E49建筑安装业(STRONG)、M75科技推广和应用服务业(STRONG)、M73研究和试验发展(STRONG)、C20木材加工和木、竹、藤、棕、草制品业(STRONG)、C40仪器仪表制造业(STRONG)、C41其他制造业(STRONG)、C43金属制品、机械和设备修理业(STRONG)

## 8. 其他已确认资产

- 基金状态：**LATEST_HOLDINGS_NOT_PERSISTED**

## 9. 系统状态（最后看）

- Canonical：**正常**；持仓同步：**HOLDINGS_IN_SYNC**；Terminal：**可用**；资金源：**USER_CONFIRMED_FLOOR**
- Formal Action：**持久状态，不因报表重跑而累计执行**；REDUCE 百分比执行层只允许向下取整，不得放大 Canonical 授权。
- Profit Protection Overlay 只展示盈利与价值/风险上下文；**profit alone 不是 SELL rationale，overlay 不得改写 Formal Action。**
- 工程 SHA / artifact / CI 不放首页；只有影响数据可信度时才升级提示。

- **no-auto-trade：true；所有订单必须人工确认。**

## 7. 事件深算闭环：到底算完没有

- 总状态：**EVENT_TRIGGERED_FINALIZED**。正式动作只来自 finalized Canonical，事件层不会偷改买卖结论。
- 事件深算生产 run：`35443656183`；Finalizer：`35444480045`。

| 股票 | 闭环状态 | 正式结果 | 为什么没有BUY/ADD / 结果解释 |
|---|---|---|---|
| 润贝航科 001316 | **EVENT_TRIGGERED_NO_CHANGE** | **HOLD_REVIEW** | 价格已进入研究价值区，但这只代表研究触发；仍需完整 Hard/Confidence Gate 与正式估值通过后才可 BUY/ADD。 |
| 中国平安 601318 | **EVENT_TRIGGERED_NO_CHANGE** | **HOLD** | 价格已进入研究价值区，但这只代表研究触发；仍需完整 Hard/Confidence Gate 与正式估值通过后才可 BUY/ADD。 |
| 洛阳钼业 603993 | **EVENT_TRIGGERED_NO_CHANGE** | **HOLD** | 价格已进入研究价值区，但这只代表研究触发；仍需完整 Hard/Confidence Gate 与正式估值通过后才可 BUY/ADD。 |
| 002612 | **RAISE_ONLY** | **—** | 价格可以继续研究，但正式价值锚不可用；在估值与 Confidence Gate 补齐前不能升级 BUY/ADD。 |
| 国电南瑞 600406 | **RAISE_ONLY** | **REDUCE_25** | 当前 Canonical 正式动作是 REDUCE_25，本轮没有形成反向 BUY/ADD。 |
| 600640 | **RAISE_ONLY** | **—** | 价格可以继续研究，但正式价值锚不可用；在估值与 Confidence Gate 补齐前不能升级 BUY/ADD。 |
| 603105 | **RAISE_ONLY** | **—** | 价格可以继续研究，但正式价值锚不可用；在估值与 Confidence Gate 补齐前不能升级 BUY/ADD。 |

## 深算研究终态（Research-only，不等于正式交易授权）

- 本轮深算：**852** 只；研究 BUY **0** / WAIT_PRICE **0** / RESEARCH_GAP **841** / REJECT **11**。
- urgent research：**26** 只；这些标的仍是 RESEARCH_GAP，等待补证，不获得 Formal BUY。
- 权限：**RESEARCH_ONLY**；UNKNOWN != PASS；Formal/Production authority 未改变；no-auto-trade=true。

### 我的持仓深算

| 股票 | 研究结论 | 原因 | 剩余证据缺口 | Urgent |
|---|---|---|---|---|
| 国电南瑞 600406 | **RESEARCH_GAP** | EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY | predictability, long_term_demand, moat, financial_safety, earnings_authenticity | 是 |
| 润贝航科 001316 | **RESEARCH_GAP** | EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY | predictability, long_term_demand, moat | 是 |
| 中国平安 601318 | **RESEARCH_GAP** | EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY | predictability, long_term_demand, moat, financial_safety, earnings_authenticity | 是 |
| 洛阳钼业 603993 | **RESEARCH_GAP** | EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY | predictability | 是 |

### Urgent evidence queue

- 国电南瑞 600406: RESEARCH_GAP；gaps=predictability, long_term_demand, moat, financial_safety, earnings_authenticity；urgent=P0_EVIDENCE_BLOCKED
- 润贝航科 001316: RESEARCH_GAP；gaps=predictability, long_term_demand, moat；urgent=P0_EVIDENCE_BLOCKED
- 中国平安 601318: RESEARCH_GAP；gaps=predictability, long_term_demand, moat, financial_safety, earnings_authenticity；urgent=P0_EVIDENCE_BLOCKED
- 洛阳钼业 603993: RESEARCH_GAP；gaps=predictability；urgent=P0_EVIDENCE_BLOCKED
- 国联股份 603613: RESEARCH_GAP；gaps=predictability, long_term_demand, moat, financial_safety, earnings_authenticity；urgent=QUANTITATIVELY_ATTRACTIVE_EVIDENCE_BLOCKED
- 台华新材 603055: RESEARCH_GAP；gaps=predictability, long_term_demand, moat；urgent=QUANTITATIVELY_ATTRACTIVE_EVIDENCE_BLOCKED
- 金杯汽车 600609: RESEARCH_GAP；gaps=predictability, long_term_demand, moat, financial_safety, earnings_authenticity；urgent=QUANTITATIVELY_ATTRACTIVE_EVIDENCE_BLOCKED
- 大参林 603233: RESEARCH_GAP；gaps=predictability, long_term_demand, moat；urgent=QUANTITATIVELY_ATTRACTIVE_EVIDENCE_BLOCKED
- 甘化科工 000576: RESEARCH_GAP；gaps=predictability, long_term_demand, moat, financial_safety, earnings_authenticity；urgent=QUANTITATIVELY_ATTRACTIVE_EVIDENCE_BLOCKED
- 华阳集团 002906: RESEARCH_GAP；gaps=predictability, long_term_demand, moat；urgent=QUANTITATIVELY_ATTRACTIVE_EVIDENCE_BLOCKED
- 新强联 300850: RESEARCH_GAP；gaps=predictability, long_term_demand, moat；urgent=QUANTITATIVELY_ATTRACTIVE_EVIDENCE_BLOCKED
- 深信服 300454: RESEARCH_GAP；gaps=predictability, long_term_demand, moat, financial_safety, earnings_authenticity；urgent=QUANTITATIVELY_ATTRACTIVE_EVIDENCE_BLOCKED
- 恒誉科技 688309: RESEARCH_GAP；gaps=predictability, long_term_demand, moat, financial_safety, earnings_authenticity；urgent=QUANTITATIVELY_ATTRACTIVE_EVIDENCE_BLOCKED
- 移远通信 603236: RESEARCH_GAP；gaps=predictability, long_term_demand, moat, financial_safety, earnings_authenticity；urgent=QUANTITATIVELY_ATTRACTIVE_EVIDENCE_BLOCKED
- 松发股份 603268: RESEARCH_GAP；gaps=predictability, long_term_demand, moat；urgent=QUANTITATIVELY_ATTRACTIVE_EVIDENCE_BLOCKED
- 奥浦迈 688293: RESEARCH_GAP；gaps=predictability, long_term_demand, moat, financial_safety, earnings_authenticity；urgent=QUANTITATIVELY_ATTRACTIVE_EVIDENCE_BLOCKED
- XD睿创微 688002: RESEARCH_GAP；gaps=predictability, long_term_demand, moat；urgent=QUANTITATIVELY_ATTRACTIVE_EVIDENCE_BLOCKED
- 皖仪科技 688600: RESEARCH_GAP；gaps=predictability, long_term_demand, moat, financial_safety, earnings_authenticity；urgent=QUANTITATIVELY_ATTRACTIVE_EVIDENCE_BLOCKED
- 广大特材 688186: RESEARCH_GAP；gaps=predictability, long_term_demand, moat, financial_safety, earnings_authenticity；urgent=QUANTITATIVELY_ATTRACTIVE_EVIDENCE_BLOCKED
- 吉华集团 603980: RESEARCH_GAP；gaps=predictability, long_term_demand, moat, financial_safety, earnings_authenticity；urgent=QUANTITATIVELY_ATTRACTIVE_EVIDENCE_BLOCKED
- 方正科技 600601: RESEARCH_GAP；gaps=predictability, long_term_demand, moat；urgent=QUANTITATIVELY_ATTRACTIVE_EVIDENCE_BLOCKED
- 兴通股份 603209: RESEARCH_GAP；gaps=predictability, long_term_demand, moat, financial_safety, earnings_authenticity；urgent=QUANTITATIVELY_ATTRACTIVE_EVIDENCE_BLOCKED
- 科锐国际 300662: RESEARCH_GAP；gaps=predictability, long_term_demand, moat, financial_safety, earnings_authenticity；urgent=QUANTITATIVELY_ATTRACTIVE_EVIDENCE_BLOCKED
- 朗姿股份 002612: RESEARCH_GAP；gaps=predictability, long_term_demand, moat；urgent=QUANTITATIVELY_ATTRACTIVE_EVIDENCE_BLOCKED
- 汇顶科技 603160: RESEARCH_GAP；gaps=predictability, long_term_demand, moat, financial_safety, earnings_authenticity；urgent=QUANTITATIVELY_ATTRACTIVE_EVIDENCE_BLOCKED
- 巨一科技 688162: RESEARCH_GAP；gaps=predictability, long_term_demand, moat, financial_safety, earnings_authenticity；urgent=QUANTITATIVELY_ATTRACTIVE_EVIDENCE_BLOCKED
