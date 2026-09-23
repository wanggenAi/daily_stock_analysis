# 投资决策驾驶舱

> 市场=YELLOW；持仓减仓/退出=1；新股正式BUY=0；等价格=0；计划立即投入≈¥0；盘中价覆盖=4/4

## 1. 最新市场结构（日线）

- 数据日：**2026-09-22**；这是日线/上一可用交易日结构，**不是盘中全A广度**。盘中价格只用于执行参考，另由 Live Execution Quote 刷新。
- 市场状态：**YELLOW**；是否允许新买：**True**；仓位倍率：**0.50**
- 上涨家数比例：**43.13%**；数据质量：**OK**

- 盘中执行价覆盖：**4/4只**；行情状态：**OFF_SESSION**；最新行情时间：**2026-09-23T11:39:14+08:00**；正式动作仍来自冻结 Canonical；缺失/过期盘中价会阻断立即执行，不会把冻结价冒充实时价。

## 2. 我的持仓怎么办

- 正式动作是 Canonical 持久状态；同一动作重复出现在后续报表中，不代表再次执行或累计执行。
| 股票 | 持仓 | 成本 | 参考价 | 盈亏% | 正式动作/权限 | 动作状态 | 现在怎么办 |
|---|---:|---:|---:|---:|---|---|---|
| 国电南瑞 600406 | 200 | 23.13 | 22.31 | -3.53 | REDUCE_25 | **UNCHANGED** | **维持减仓25%目标；本轮无新增减仓/退出信号；目标减50股，当前可执行0股（手数约束；禁止向上取整）** |
| 润贝航科 001316 | 200 | 25.75 | 28.39 | 10.27 | HOLD_REVIEW | **UNCHANGED** | **持有观察** |
| 中国平安 601318 | 400 | 55.97 | 54.19 | -3.17 | HOLD | **UNCHANGED** | **继续持有** |
| 洛阳钼业 603993 | 1100 | 18.62 | 17.61 | -5.45 | HOLD | **UNCHANGED** | **继续持有；历史分批加仓授权已消费，本轮新增可执行0股** |

## 3. 今天能直接买什么

| 股票 | 行业 | 当前价 | 估值信心 | 权限 |
|---|---|---:|---|---|
| — | — | — | — | 本轮没有已授权新股BUY |

## 4. WAIT_PRICE：跌到多少钱再买

| 股票 | 当前价 | 最高等待买价 |
|---|---:|---:|
| — | — | 本轮没有合格 WAIT_PRICE |

## 5. 资金怎么花

- 可规划现金：**¥50000.00**；最高部署预算：**¥25000.00**
- 计划立即投入：**¥0.00**；计划后现金：**¥50000.00**
- 只有当前可用 Canonical 持仓分批加仓授权或授权 Terminal BUY 才能进入计划；WAIT_PRICE 只预留，REJECT=0。
- 上方“计划立即投入”只统计当前具备执行条件的动作；缺少有效盘中价、现价高于授权上限等暂不可执行计划不计入。
- 最终操作表会保留已授权计划供审计，并明确标记执行状态；保留计划不等于新增 BUY/ADD 信号。

## 6. 最终操作表

| 股票 | 动作 | 股数 | 第一档最高价 | 第二档最高价 | 预计/预留金额 | 执行状态 |
|---|---|---:|---:|---:|---:|---|
| — | — | 0 | — | — | 0 | — |

## 7. 当前强势方向（辅助，不代替BUY权限）

R86新闻和出版业(STRONG)、P83教育(STRONG)、I64互联网和相关服务(STRONG)、R87广播、电视、电影和录音制作业(STRONG)、I65软件和信息技术服务业(STRONG)、M73研究和试验发展(STRONG)、I63电信、广播电视和卫星传输服务(STRONG)、J68保险业(STRONG)

## 8. 其他已确认资产

- 基金状态：**LATEST_HOLDINGS_NOT_PERSISTED**

## 9. 系统状态（最后看）

- Canonical：**正常**；持仓同步：**HOLDINGS_IN_SYNC**；Terminal：**可用**；资金源：**USER_CONFIRMED_FLOOR**
- Formal Action：**持久状态，不因报表重跑而累计执行**；REDUCE 百分比执行层只允许向下取整，不得放大 Canonical 授权。
- Profit Protection Overlay 只展示盈利与价值/风险上下文；**profit alone 不是 SELL rationale，overlay 不得改写 Formal Action。**
- 工程 SHA / artifact / CI 不放首页；只有影响数据可信度时才升级提示。

- **no-auto-trade：true；所有订单必须人工确认。**

## 深算研究终态（Research-only，不等于正式交易授权）

- 本轮深算：**13** 只；研究 BUY **0** / WAIT_PRICE **0** / RESEARCH_GAP **13** / REJECT **0**。
- urgent research：**4** 只；这些标的仍是 RESEARCH_GAP，等待补证，不获得 Formal BUY。
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
