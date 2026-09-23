# ⚠️ 数据代际陈旧：STALE_UPSTREAM

> 新增仓位已 fail-closed；Formal 决策仅保留作审计/研究显示。原因：`CANONICAL_TRADE_DATE_BEHIND_COMPLETED_SESSION, MARKET_CONTEXT_BEHIND_COMPLETED_SESSION`

# 投资决策驾驶舱

> 数据代际=STALE_UPSTREAM；禁止新增仓位；市场=YELLOW；盘中价仅用于展示/审计；计划立即投入≈¥0

## 1. 最新市场结构（日线）

- 数据日：**2026-09-22**；这是日线/上一可用交易日结构，**不是盘中全A广度**。盘中价格只用于执行参考，另由 Live Execution Quote 刷新。
- 市场状态：**YELLOW**；是否允许新买：**False**；仓位倍率：**0.50**
- 上涨家数比例：**43.13%**；数据质量：**OK**

## 2. 我的持仓怎么办

- 正式动作是 Canonical 持久状态；同一动作重复出现在后续报表中，不代表再次执行或累计执行。
| 股票 | 持仓 | 成本 | 参考价 | 盈亏% | 正式动作/权限 | 动作状态 | 现在怎么办 |
|---|---:|---:|---:|---:|---|---|---|
| 国电南瑞 600406 | 200 | 23.13 | 22.23 | -3.87 | REDUCE_25 | **UNCHANGED** | **维持减仓25%目标；本轮无新增减仓/退出信号；目标减50股，当前可执行0股（手数约束；禁止向上取整）** |
| 润贝航科 001316 | 200 | 25.75 | 28.90 | 12.25 | HOLD_REVIEW | **UNCHANGED** | **持有观察** |
| 中国平安 601318 | 400 | 55.97 | 54.46 | -2.69 | HOLD | **UNCHANGED** | **继续持有** |
| 洛阳钼业 603993 | 1100 | 18.62 | 17.81 | -4.37 | HOLD | **UNCHANGED** | **继续持有；历史分批加仓授权已消费，本轮新增可执行0股** |

## 3. 今天能直接买什么

| 股票 | 行业 | 当前价 | 估值信心 | 权限 |
|---|---|---:|---|---|
| — | — | — | — | 本轮没有已授权新股BUY |

## 4. WAIT_PRICE：跌到多少钱再买

| 股票 | 当前价 | 最高等待买价 |
|---|---:|---:|
| — | — | 本轮没有合格 WAIT_PRICE |

## 5. 资金怎么花

- 可规划现金：**¥50000.00**；最高部署预算：**¥0.00**
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

- 本轮深算：**1** 只；研究 BUY **1** / WAIT_PRICE **0** / RESEARCH_GAP **0** / REJECT **0**。
- urgent research：**0** 只；这些标的仍是 RESEARCH_GAP，等待补证，不获得 Formal BUY。
- 权限：**RESEARCH_ONLY**；UNKNOWN != PASS；Formal/Production authority 未改变；no-auto-trade=true。
- 风险预算：BUILD **1** / PROBE **0** / WATCH **0** / BLOCK **0**；仅人工建议，不自动执行。

### 风险预算 BUILD / PROBE

- 伯特利 603596: **BUILD**；conviction=0.945；建议账户仓位上限=3.0%；研究结论仍为 BUY。

### 我的持仓深算

| 股票 | 研究结论 | 原因 | 剩余证据缺口 | Urgent |
|---|---|---|---|---|
| 600406 | — | 本轮 workset 未包含 | — | — |
| 001316 | — | 本轮 workset 未包含 | — | — |
| 601318 | — | 本轮 workset 未包含 | — | — |
| 603993 | — | 本轮 workset 未包含 | — | — |

### Urgent evidence queue

- 暂无。
