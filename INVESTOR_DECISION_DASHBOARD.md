# 投资决策驾驶舱

> 市场=GREEN；持仓减仓/退出=1；新股正式BUY=0；等价格=0；计划立即投入≈¥1729；盘中价覆盖=4/4

## 1. 今天市场怎么样

- 市场状态：**GREEN**；是否允许新买：**True**；仓位倍率：**1.00**
- 上涨家数比例：**73.97%**；数据质量：**OK**

## 2. 我的持仓怎么办

- 正式动作是 Canonical 持久状态；同一动作重复出现在后续报表中，不代表再次执行或累计执行。
| 股票 | 持仓 | 成本 | 参考价 | 盈亏% | 正式动作/权限 | 动作状态 | 现在怎么办 |
|---|---:|---:|---:|---:|---|---|---|
| 国电南瑞 600406 | 200 | 23.13 | 21.95 | -5.08 | REDUCE_25 | **UNCHANGED** | **维持减仓25%目标；本轮无新增减仓/退出信号；目标减50股，当前可执行0股（手数约束；禁止向上取整）** |
| 润贝航科 001316 | 200 | 25.75 | 27.76 | 7.83 | HOLD_REVIEW | **UNCHANGED** | **持有观察** |
| 中国平安 601318 | 400 | 55.97 | 53.19 | -4.96 | HOLD | **UNCHANGED** | **继续持有** |
| 洛阳钼业 603993 | 0 | — | 17.29 | — | HOLD | **UNCHANGED** | **继续持有；可分批加仓1手** |

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
- 计划立即投入：**¥1729.00**；计划后现金：**¥55271.00**
- 只有当前可用 Canonical 持仓分批加仓授权或授权 Terminal BUY 才能立即分配；WAIT_PRICE 只预留，REJECT=0。

## 6. 最终操作表

| 股票 | 动作 | 股数 | 第一档最高价 | 第二档最高价 | 预计/预留金额 |
|---|---|---:|---:|---:|---:|
| 洛阳钼业 603993 | **ADD** | 100 | 17.29 | — | 1729.00 |

## 7. 当前强势方向（辅助，不代替BUY权限）

A02林业(STRONG)、E49建筑安装业(STRONG)、C43金属制品、机械和设备修理业(STRONG)、M73研究和试验发展(STRONG)、C39计算机、通信和其他电子设备制造业(STRONG)、B09有色金属矿采选业(STRONG)、C19皮革、毛皮、羽毛及其制品和制鞋业(STRONG)、A04渔业(STRONG)

## 8. 其他已确认资产

- 基金状态：**LATEST_HOLDINGS_NOT_PERSISTED**

## 9. 系统状态（最后看）

- Canonical：**正常**；持仓同步：**HOLDINGS_IN_SYNC**；Terminal：**可用**；资金源：**USER_CONFIRMED_FLOOR**
- Formal Action：**持久状态，不因报表重跑而累计执行**；REDUCE 百分比执行层只允许向下取整，不得放大 Canonical 授权。
- Profit Protection Overlay 只展示盈利与价值/风险上下文；**profit alone 不是 SELL rationale，overlay 不得改写 Formal Action。**
- 工程 SHA / artifact / CI 不放首页；只有影响数据可信度时才升级提示。

- **no-auto-trade：true；所有订单必须人工确认。**

## 深算研究终态（Research-only，不等于正式交易授权）

- 本轮深算：**762** 只；研究 BUY **0** / WAIT_PRICE **0** / REJECT **762**。
- urgent research：**20** 只；这些标的本轮仍是 REJECT，不获得 Formal BUY。
- 权限：**RESEARCH_ONLY**；UNKNOWN != PASS；Formal/Production authority 未改变；no-auto-trade=true。

### 我的持仓深算

| 股票 | 研究结论 | 原因 | 剩余证据缺口 | Urgent |
|---|---|---|---|---|
| 国电南瑞 600406 | **REJECT** | EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY | predictability, long_term_demand, moat, financial_safety, earnings_authenticity | 是 |
| 润贝航科 001316 | **REJECT** | EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY | predictability, long_term_demand, moat | 是 |
| 中国平安 601318 | **REJECT** | EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY | predictability, long_term_demand, moat, financial_safety, earnings_authenticity | 是 |
| 洛阳钼业 603993 | **REJECT** | EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY | predictability | 是 |

### Urgent evidence queue

- 新疆交建 002941: REJECT；gaps=predictability, long_term_demand, moat, financial_safety, earnings_authenticity；urgent=P0_EVIDENCE_BLOCKED
- 国电南瑞 600406: REJECT；gaps=predictability, long_term_demand, moat, financial_safety, earnings_authenticity；urgent=P0_EVIDENCE_BLOCKED
- 润贝航科 001316: REJECT；gaps=predictability, long_term_demand, moat；urgent=P0_EVIDENCE_BLOCKED
- 中国平安 601318: REJECT；gaps=predictability, long_term_demand, moat, financial_safety, earnings_authenticity；urgent=P0_EVIDENCE_BLOCKED
- 洛阳钼业 603993: REJECT；gaps=predictability；urgent=P0_EVIDENCE_BLOCKED
- 中航西飞 000768: REJECT；gaps=predictability, long_term_demand, moat, financial_safety, earnings_authenticity；urgent=QUANTITATIVELY_ATTRACTIVE_EVIDENCE_BLOCKED
- 国联股份 603613: REJECT；gaps=predictability, long_term_demand, moat, financial_safety, earnings_authenticity；urgent=QUANTITATIVELY_ATTRACTIVE_EVIDENCE_BLOCKED
- 甘化科工 000576: REJECT；gaps=predictability, long_term_demand, moat, financial_safety, earnings_authenticity；urgent=QUANTITATIVELY_ATTRACTIVE_EVIDENCE_BLOCKED
- 大参林 603233: REJECT；gaps=predictability, long_term_demand, moat；urgent=QUANTITATIVELY_ATTRACTIVE_EVIDENCE_BLOCKED
- 台华新材 603055: REJECT；gaps=predictability, long_term_demand, moat；urgent=QUANTITATIVELY_ATTRACTIVE_EVIDENCE_BLOCKED
- 新强联 300850: REJECT；gaps=predictability, long_term_demand, moat；urgent=QUANTITATIVELY_ATTRACTIVE_EVIDENCE_BLOCKED
- 深信服 300454: REJECT；gaps=predictability, long_term_demand, moat, financial_safety, earnings_authenticity；urgent=QUANTITATIVELY_ATTRACTIVE_EVIDENCE_BLOCKED
- 移远通信 603236: REJECT；gaps=predictability, long_term_demand, moat, financial_safety, earnings_authenticity；urgent=QUANTITATIVELY_ATTRACTIVE_EVIDENCE_BLOCKED
- 奥浦迈 688293: REJECT；gaps=predictability, long_term_demand, moat, financial_safety, earnings_authenticity；urgent=QUANTITATIVELY_ATTRACTIVE_EVIDENCE_BLOCKED
- 方正科技 600601: REJECT；gaps=predictability, long_term_demand, moat；urgent=QUANTITATIVELY_ATTRACTIVE_EVIDENCE_BLOCKED
- 睿创微纳 688002: REJECT；gaps=predictability, long_term_demand, moat；urgent=QUANTITATIVELY_ATTRACTIVE_EVIDENCE_BLOCKED
- 皖仪科技 688600: REJECT；gaps=predictability, long_term_demand, moat, financial_safety, earnings_authenticity；urgent=QUANTITATIVELY_ATTRACTIVE_EVIDENCE_BLOCKED
- 兴通股份 603209: REJECT；gaps=predictability, long_term_demand, moat, financial_safety, earnings_authenticity；urgent=QUANTITATIVELY_ATTRACTIVE_EVIDENCE_BLOCKED
- 吉华集团 603980: REJECT；gaps=predictability, long_term_demand, moat, financial_safety, earnings_authenticity；urgent=QUANTITATIVELY_ATTRACTIVE_EVIDENCE_BLOCKED
- 汇顶科技 603160: REJECT；gaps=predictability, long_term_demand, moat, financial_safety, earnings_authenticity；urgent=QUANTITATIVELY_ATTRACTIVE_EVIDENCE_BLOCKED
