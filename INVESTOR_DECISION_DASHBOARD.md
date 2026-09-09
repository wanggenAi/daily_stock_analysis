# 投资决策驾驶舱

> 市场=YELLOW；持仓减仓/退出=1；新股正式BUY=0；等价格=0；计划立即投入≈¥1909；盘中价覆盖=0

## 1. 今天市场怎么样

- 市场状态：**YELLOW**；是否允许新买：**True**；仓位倍率：**0.50**
- 上涨家数比例：**34.91%**；数据质量：**OK**

- 盘中执行价覆盖：**0只**；最新行情时间：**—**；正式动作仍来自冻结 Canonical，盘中价只用于当前盈亏与人工下单价格/股数。

## 2. 我的持仓怎么办

- 正式动作是 Canonical 持久状态；同一动作重复出现在后续报表中，不代表再次执行或累计执行。
| 股票 | 持仓 | 成本 | 参考价 | 盈亏% | 正式动作 | 动作状态 | 现在怎么办 |
|---|---:|---:|---:|---:|---|---|---|
| 国电南瑞 600406 | 200 | 23.13 | 22.45 | -2.92 | REDUCE_25 | **UNCHANGED** | **维持减仓25%目标；本轮无新增减仓/退出信号；目标减50股，当前可执行0股（手数约束；禁止向上取整）** |
| 润贝航科 001316 | 200 | 25.75 | 31.01 | 20.45 | HOLD_REVIEW | **UNCHANGED** | **持有观察** |
| 中国平安 601318 | 300 | 57.17 | 56.26 | -1.59 | HOLD | **UNCHANGED** | **继续持有** |
| 洛阳钼业 603993 | 900 | 18.91 | 19.09 | 0.94 | HOLD | **UNCHANGED** | **继续持有；可分批加仓1手** |

## 3. 今天能直接买什么

| 股票 | 行业 | 当前价 | 估值信心 | 权限 |
|---|---|---:|---|---|
| — | — | — | — | 本轮没有已授权新股BUY |

## 4. WAIT_PRICE：跌到多少钱再买

| 股票 | 当前价 | 最高等待买价 |
|---|---:|---:|
| — | — | 本轮没有合格 WAIT_PRICE |

## 5. 资金怎么花

- 可规划现金：**¥70000.00**；最高部署预算：**¥35000.00**
- 计划立即投入：**¥1909.00**；计划后现金：**¥68091.00**
- 只有 Canonical 持仓分批加仓授权或授权 Terminal BUY 才能立即分配；WAIT_PRICE 只预留，REJECT=0。

## 6. 最终操作表

| 股票 | 动作 | 股数 | 第一档最高价 | 第二档最高价 | 预计/预留金额 |
|---|---|---:|---:|---:|---:|
| 洛阳钼业 603993 | **ADD** | 100 | 19.09 | — | 1909.00 |

## 7. 当前强势方向（辅助，不代替BUY权限）

G55水上运输业(STRONG)、B06煤炭开采和洗选业(STRONG)、B08黑色金属矿采选业(STRONG)、A04渔业(STRONG)、C25石油、煤炭及其他燃料加工业(STRONG)、G59装卸搬运和仓储业(STRONG)、C31黑色金属冶炼和压延加工业(STRONG)、A01农业(STRONG)

## 8. 其他已确认资产

- 基金状态：**LATEST_HOLDINGS_NOT_PERSISTED**

## 9. 系统状态（最后看）

- Canonical：**正常**；Terminal：**可用**；资金源：**USER_CONFIRMED_FLOOR**
- Formal Action：**持久状态，不因报表重跑而累计执行**；REDUCE 百分比执行层只允许向下取整，不得放大 Canonical 授权。
- 工程 SHA / artifact / CI 不放首页；只有影响数据可信度时才升级提示。

- **no-auto-trade：true；所有订单必须人工确认。**

## 深算研究终态（Research-only，不等于正式交易授权）

- 本轮深算：**34** 只；研究 BUY **0** / WAIT_PRICE **0** / REJECT **34**。
- urgent research：**11** 只；这些标的本轮仍是 REJECT，不获得 Formal BUY。
- 权限：**RESEARCH_ONLY**；UNKNOWN != PASS；Formal/Production authority 未改变；no-auto-trade=true。

### 我的持仓深算

| 股票 | 研究结论 | 原因 | 剩余证据缺口 | Urgent |
|---|---|---|---|---|
| 国电南瑞 600406 | **REJECT** | EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY | predictability, long_term_demand, moat, financial_safety, earnings_authenticity | 是 |
| 润贝航科 001316 | **REJECT** | EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY | predictability, long_term_demand, moat | 是 |
| 中国平安 601318 | **REJECT** | EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY | predictability, long_term_demand, moat, financial_safety, earnings_authenticity | 是 |
| XD洛阳钼 603993 | **REJECT** | EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY | predictability | 是 |

### Urgent evidence queue

- 台华新材 603055: REJECT；gaps=predictability, long_term_demand, moat；urgent=P0_EVIDENCE_BLOCKED
- 中国平安 601318: REJECT；gaps=predictability, long_term_demand, moat, financial_safety, earnings_authenticity；urgent=P0_EVIDENCE_BLOCKED
- 国电南瑞 600406: REJECT；gaps=predictability, long_term_demand, moat, financial_safety, earnings_authenticity；urgent=P0_EVIDENCE_BLOCKED
- 润贝航科 001316: REJECT；gaps=predictability, long_term_demand, moat；urgent=P0_EVIDENCE_BLOCKED
- XD洛阳钼 603993: REJECT；gaps=predictability；urgent=P0_EVIDENCE_BLOCKED
- 伯特利 603596: REJECT；gaps=predictability, long_term_demand, moat；urgent=QUANTITATIVELY_ATTRACTIVE_EVIDENCE_BLOCKED
- 锦江酒店 600754: REJECT；gaps=predictability, long_term_demand, moat；urgent=QUANTITATIVELY_ATTRACTIVE_EVIDENCE_BLOCKED
- 学大教育 000526: REJECT；gaps=predictability, long_term_demand, moat；urgent=QUANTITATIVELY_ATTRACTIVE_EVIDENCE_BLOCKED
- 奥特佳 002239: REJECT；gaps=predictability, long_term_demand, moat；urgent=QUANTITATIVELY_ATTRACTIVE_EVIDENCE_BLOCKED
- 金诚信 603979: REJECT；gaps=predictability, long_term_demand, moat；urgent=QUANTITATIVELY_ATTRACTIVE_EVIDENCE_BLOCKED
- 朗姿股份 002612: REJECT；gaps=predictability, long_term_demand, moat；urgent=QUANTITATIVELY_ATTRACTIVE_EVIDENCE_BLOCKED
