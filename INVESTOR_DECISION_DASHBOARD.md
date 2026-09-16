# 投资决策驾驶舱

> 市场=YELLOW；持仓减仓/退出=1；新股正式BUY=0；等价格=0；计划立即投入≈¥0；盘中价覆盖=0/4

## 1. 今天市场怎么样

- 市场状态：**YELLOW**；是否允许新买：**True**；仓位倍率：**0.50**
- 上涨家数比例：**20.32%**；数据质量：**OK**

## 2. 我的持仓怎么办

- 正式动作是 Canonical 持久状态；同一动作重复出现在后续报表中，不代表再次执行或累计执行。
| 股票 | 持仓 | 成本 | 参考价 | 盈亏% | 正式动作/权限 | 动作状态 | 现在怎么办 |
|---|---:|---:|---:|---:|---|---|---|
| 国电南瑞 600406 | 200 | 23.13 | 21.99 | -4.91 | REDUCE_25 | **UNCHANGED** | **维持减仓25%目标；本轮无新增减仓/退出信号；目标减50股，当前可执行0股（手数约束；禁止向上取整）** |
| 润贝航科 001316 | 200 | 25.75 | 28.05 | 8.95 | HOLD_REVIEW | **UNCHANGED** | **持有观察** |
| 中国平安 601318 | 400 | 55.97 | 53.90 | -3.69 | HOLD | **UNCHANGED** | **继续持有** |
| 洛阳钼业 603993 | 0 | — | 17.64 | — | HOLD | **UNCHANGED** | **继续持有；可分批加仓1手** |

## 3. 今天能直接买什么

| 股票 | 行业 | 当前价 | 估值信心 | 权限 |
|---|---|---:|---|---|
| — | — | — | — | 本轮没有已授权新股BUY |

## 4. WAIT_PRICE：跌到多少钱再买

| 股票 | 当前价 | 最高等待买价 |
|---|---:|---:|
| — | — | 本轮没有合格 WAIT_PRICE |

## 5. 资金怎么花

- 可规划现金：**¥57000.00**；最高部署预算：**¥28500.00**
- 计划立即投入：**¥0.00**；计划后现金：**¥57000.00**
- 只有当前可用 Canonical 持仓分批加仓授权或授权 Terminal BUY 才能立即分配；WAIT_PRICE 只预留，REJECT=0。

## 6. 最终操作表

| 股票 | 动作 | 股数 | 第一档最高价 | 第二档最高价 | 预计/预留金额 |
|---|---|---:|---:|---:|---:|
| 洛阳钼业 603993 | **ADD** | 100 | 17.64 | — | 1764.00 |

## 7. 当前强势方向（辅助，不代替BUY权限）

O81机动车、电子产品和日用产品修理业(STRONG)、E49建筑安装业(NEUTRAL)、G60邮政业(NEUTRAL)、B10非金属矿采选业(NEUTRAL)、B06煤炭开采和洗选业(NEUTRAL)、G58多式联运和运输代理业(NEUTRAL)、A03畜牧业(NEUTRAL)、D44电力、热力生产和供应业(NEUTRAL)

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
- 事件深算生产 run：`35106997734`；Finalizer：`35108518598`。

| 股票 | 闭环状态 | 正式结果 | 为什么没有BUY/ADD / 结果解释 |
|---|---|---|---|
| 润贝航科 001316 | **EVENT_TRIGGERED_NO_CHANGE** | **HOLD_REVIEW** | 价格已进入研究价值区，但这只代表研究触发；仍需完整 Hard/Confidence Gate 与正式估值通过后才可 BUY/ADD。 |
| 天融信 002212 | **EVENT_TRIGGERED_NO_CHANGE** | **—** | 当前正式动作仍为 NO_ACTION；没有足够证据跨过 BUY/ADD 的全部生产门槛。 |
| 奥特佳 002239 | **EVENT_TRIGGERED_NO_CHANGE** | **—** | 价格可以继续研究，但正式价值锚不可用；在估值与 Confidence Gate 补齐前不能升级 BUY/ADD。 |
| 华昌化工 002274 | **EVENT_TRIGGERED_NO_CHANGE** | **—** | 当前正式动作仍为 NO_ACTION；没有足够证据跨过 BUY/ADD 的全部生产门槛。 |
| 新疆交建 002941 | **EVENT_TRIGGERED_NO_CHANGE** | **—** | 价格可以继续研究，但正式价值锚不可用；在估值与 Confidence Gate 补齐前不能升级 BUY/ADD。 |
| 中国平安 601318 | **EVENT_TRIGGERED_NO_CHANGE** | **HOLD** | 价格已进入研究价值区，但这只代表研究触发；仍需完整 Hard/Confidence Gate 与正式估值通过后才可 BUY/ADD。 |
| 台华新材 603055 | **EVENT_TRIGGERED_NO_CHANGE** | **—** | 价格可以继续研究，但正式价值锚不可用；在估值与 Confidence Gate 补齐前不能升级 BUY/ADD。 |
| 伯特利 603596 | **EVENT_TRIGGERED_NO_CHANGE** | **—** | 价格可以继续研究，但正式价值锚不可用；在估值与 Confidence Gate 补齐前不能升级 BUY/ADD。 |
| 洛阳钼业 603993 | **EVENT_TRIGGERED_NO_CHANGE** | **HOLD** | 价格已进入研究价值区，但这只代表研究触发；仍需完整 Hard/Confidence Gate 与正式估值通过后才可 BUY/ADD。 |
| 600309 | **RAISE_ONLY** | **—** | 价格可以继续研究，但正式价值锚不可用；在估值与 Confidence Gate 补齐前不能升级 BUY/ADD。 |
| 国电南瑞 600406 | **RAISE_ONLY** | **REDUCE_25** | 当前 Canonical 正式动作是 REDUCE_25，本轮没有形成反向 BUY/ADD。 |
