# 三支柱投资决策中心

> 最终页面只回答三件事：我的持仓怎么办；钱可能往哪里去；还有什么股票值得行动。

## 1. 我的持仓：深算后到底怎么办

- 持仓：**4**；已有显式深算：**0**；深算完整：**0**；仍有 gap：**4**。

| 股票 | 盈亏% | 正式动作 | 现在怎么办 | 估值信心 | 深算状态 |
|---|---:|---|---|---|---|
| 国电南瑞 600406 | -4.65 | REDUCE_25 | **维持减仓25%目标；本轮无新增减仓/退出信号；目标减50股，当前可执行0股（手数约束；禁止向上取整）** | HIGH | STALE_PROFILE_LAST_TERMINAL |
| 润贝航科 001316 | 9.19 | HOLD_REVIEW | **持有观察** | LOW | STALE_PROFILE_LAST_TERMINAL |
| 中国平安 601318 | -4.64 | HOLD | **继续持有** | MEDIUM | STALE_PROFILE_LAST_TERMINAL |
| 洛阳钼业 603993 | -5.98 | HOLD | **继续持有；历史分批加仓授权已消费，本轮新增可执行0股** | HIGH | STALE_PROFILE_LAST_TERMINAL |

## 2. 世界/社会/市场：钱可能在哪里

### 今日A股大盘脉搏

- 2026-09-18：市场 **GREEN**；数据质量 **OK**；市场分数 **73.83**；仓位倍率 **1.00**。
- 上涨家数占比 **75.69%**；中位涨跌 **1.04%**；MA20 上方 **39.62%**；MA60 上方 **52.54%**；涨停/跌停 **67/0**。
- 市场读法：**当日上涨面较广；短周期尚未全面修复，但中期广度仍有支撑；极端分化/派发代理暂不高**。这只是市场环境解释，不自行创造个股 BUY 权限。

### 中长期结构趋势

| 趋势 | 信心 | 结构 | 产业 | A股研究映射 |
|---|---:|---:|---:|---|
| digital_infrastructure | 33.69 | 57.06 | 62.50 | 尚未映射 |
| software_digital_economy | 31.92 | 50.00 | 62.44 | 尚未映射 |
| automotive_industry | 16.09 | 50.00 | 62.50 | 汽车 |
| demographic_longevity | 14.64 | 60.32 | 50.00 | 医药 |
| urbanization_services | 14.18 | 58.08 | 50.00 | 尚未映射 |
| research_intensity | 13.95 | 55.04 | 50.00 | 尚未映射 |
| advanced_manufacturing | 11.11 | 48.19 | 45.69 | 专用设备、电气机械、工程机械 |
| electrification_infrastructure | 0.00 | 50.00 | 50.00 | 电力设备 |

### 近期市场行为代理

O81机动车、电子产品和日用产品修理业(99.35)、E49建筑安装业(98.83)、M75科技推广和应用服务业(87.50)、M73研究和试验发展(87.16)、C20木材加工和木、竹、藤、棕、草制品业(86.17)、C40仪器仪表制造业(83.81)、C41其他制造业(83.53)、C43金属制品、机械和设备修理业(81.60)

- 已验证的趋势→A股研究交接：**0**。
- 这里不冒充‘主力净流入’；结构趋势、市场行为和个股深算必须分层验证。

## 3. 新机会：润贝型以及其他机会深算结果

- **本轮没有已授权新股 BUY。**
- **本轮没有合格 WAIT_PRICE。**

- Formal/Production Candidate Terminal REJECT：**171**（只做汇总；与下方 Deep Research Terminal 的 RESEARCH_GAP/REJECT 是不同层级）。

## 决策完整性

- 全部持仓显式深算完整：**False**
- 世界/社会结构趋势证据可用：**True**
- 已验证趋势→A股交接可用：**False**
- Terminal 机会结果可用：**True**

> UNKNOWN != PASS；研究趋势不自动变成 BUY；no_auto_trade=true。

## 自动深算运行状态

- 当前运行状态来源：**PARTIAL_CHECKPOINT**
- 深算资料来源：**AUTOMATIC_DEEP_CALCULATION**；资料 Lambda：`35605616205`；与当前运行一致：**False**
- ⚠️ 最新自动 profiles 属于上一轮 Deep runtime；顶部持仓/机会的深算完整度已按当前 runtime 视为未完成，旧 profile 状态仅保留为 last_profile_status 供审计。
- Lambda run：`35599856461`
- 触发来源：`EVIDENCE_LAYER_CHANGE`
- 计算执行：**PARTIAL**
- 运行状态：**PARTIAL_CHECKPOINT**
- 研究过程终态：**NOT_COMPLETED**
- 请求深算：**852**；已处理：**852**；完整：**未携带**；证据穷尽：**未携带**。
- Workset profile：总数 **853**；请求代码已落 profile **852**；handoff 未完成 **未携带**；覆盖可审计：**True**；完整覆盖：**True**。
- 同轮补证据尝试：**0**；取得证据：**0**；推进硬门槛：**0**。
- 尚未解决硬门槛：**未携带**。
- 未决原因摘要：当前 checkpoint 未携带逐股未决明细
- 请求但未进入本次研究工件：**无**。
- 上一次完整终态 run：`35605616205`；执行 **SUCCESS**；研究终态 **EVIDENCE_EXHAUSTED**。
- 是否需要你手工开启下一轮：**True**。
- **执行 SUCCESS 不等于研究 COMPLETE**；EVIDENCE_EXHAUSTED 只表示已进入 profile 的对象完成了有界补证；HANDOFF_INCOMPLETE 表示仍有请求代码未进入 profile，二者都不会把 UNKNOWN 当成 PASS。

## 深算终态研究决策

- 终态快照存在：**True**；与当前 Deep Lambda 一致：**False**。
- 终态来源 Lambda：`35605616205`；当前 Lambda：`35599856461`。
- 请求：**0**；研究 BUY：**0**；研究 WAIT_PRICE：**0**；研究 RESEARCH_GAP：**0**；研究 REJECT：**0**。
- 高吸引力但证据不足、优先补证：无
- **研究 BUY/WAIT_PRICE 与 Formal/Production 权限严格分离**；这里只提供研究动作，不会创建 Formal BUY、持仓加仓授权或自动交易。

> 自动触发、自动计算、同轮补证据/有界重试、自动终结、自动持久化、自动刷新决策中心；Formal BUY 权限仍只来自既有 Canonical/Production authority，no_auto_trade=true。
