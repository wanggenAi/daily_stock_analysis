# 硬逻辑 × 当前价格估值地图

## 目标

长期决策按固定顺序回答三个问题：

1. **公司有没有硬逻辑**：判断公司/产业结构、持续盈利质量和明确公司级硬风险。
2. **公司现在处于什么盈利阶段**：收缩、恶化、早期修复、扩张，或证据不足。
3. **当前价格能不能买**：优先用明确的未来盈利与合理估值假设形成 bear/base/bull 三情景，再用安全边际把“合理价”和“买入价”拆开。

核心顺序是：

```text
硬逻辑
  -> 当前盈利阶段
  -> 未来 EPS / 正常化利润
  -> 合理 PE 或专业估值模型重估
  -> bear / base / bull 公平价值
  -> 安全边际
  -> BUY / HOLD / WAIT 价格区间
```

系统不再把 5000 多只股票强行压成唯一一只。多个硬逻辑公司可以同时保留，每家公司独立得到价格结论。

## 硬逻辑边界

真正可以阻断公司的包括明确公司级结构性硬风险、显式 hard-logic `FAIL/BLOCKED`、正常化持续核心利润非正。

大盘 regime、MA5/10/20/60、突破/回踩、entry、止损、Reward/Risk、仓位、execution、退出画像等在本层全部是 `non_veto_context`，不能反向否决公司质量。

普通 `RESEARCH_CANDIDATE` 也不自动等于硬逻辑确认：至少还要有可用估值和不弱的持续盈利质量，否则保持 `REVIEW`。

## 盈利阶段

`earnings_stage` 优先读取上游明确证据。若没有明确阶段，但同时存在最新季度和上一季度利润同比数据，允许做最小化推断：

- 上一季度 <= 0、最新季度 > 0：`EARLY_RECOVERY`；
- 连续两个季度 > 0：`EXPANSION`；
- 连续两个季度 <= 0：`CONTRACTION`；
- 上一季度 > 0、最新季度 <= 0：`DETERIORATING`；
- 数据不足：`UNDETERMINED`。

盈利阶段本身不凭空生成合理 PE。它用于约束研究人员/上游模型为什么可以给某个 forward EPS、合理 PE 或专业模型公平价值，避免把历史高增长时期的估值直接套到当前低增长/修复阶段。

## 前瞻三情景估值：优先级最高

只要存在可审计的前瞻估值输入，价格判断优先使用 `FORWARD_SCENARIO`，不再由历史 PE 决定 BUY。

每个 bear/base/bull 情景可通过两种方式提供公平价：

```text
A. 直接提供 scenario_fair_price_*
   - 适用于 DCF、NAV、PB/ROE、EV/EBITDA、rNPV 等专业模型输出

B. forward_eps_* × reasonable_pe_*
   - 适用于 PE 确实适用且未来 EPS 与合理 PE 都有明确证据的公司
```

如果只有 forward EPS 而没有合理 PE，或者只有合理 PE 而没有 forward EPS，系统保持 `INPUTS_INCOMPLETE`，不会补一个“看起来差不多”的倍数。

**历史 PE 永远不自动成为 reasonable PE。** `historical_pe_is_reference_only = true` 是生产输出固定契约。

### 合理价 ≠ 买入价

base 公平价形成后，系统再应用安全边际：

```text
entry_price_ceiling = base_fair_price × (1 - buy_margin_of_safety)
ideal_price_ceiling = base_fair_price × (1 - deep_value_margin_of_safety)
```

默认研究策略参数：

- 普通买入安全边际：15%；
- 深度价值安全边际：25%。

这两个比例可以由上游显式覆盖，但未来盈利和合理估值假设不能由本层凭空创造。

价格区间：

- `current <= ideal_price_ceiling`：`BUY_DEEP_VALUE` / `DEEP_VALUE_ZONE`；
- `ideal < current <= entry_price_ceiling`：`BUYABLE` / `BUY_ZONE`；
- `entry < current <= base_fair_price`：`HOLD_FAIR_VALUE` / `HOLD_FAIR_ZONE`；
- `base < current <= bull_fair_price`：`EXPECTATIONS_HIGH_WAIT` / `EXPECTATIONS_FULL_ZONE`；
- `current > bull_fair_price`：`OVERVALUED_WAIT` / `OVERVALUED_ZONE`；
- base 有值但 bull 缺失、且当前价已经高于 base：`WAIT_FOR_BETTER_PRICE`，不编造额外上涨空间。

因此“公司硬逻辑强”只说明值得长期跟踪，**绝不再等价于当前价格可以买**。

### 今世缘式回归案例

若输入：

```text
current_price = 28.92
forward_eps_bear/base/bull = 2.00 / 2.08 / 2.15
reasonable_pe_bear/base/bull = 12 / 15 / 18
```

则：

```text
bear_fair = 24.00
base_fair = 31.20
bull_fair = 38.70
entry_price_ceiling (15% MOS) = 26.52
ideal_price_ceiling (25% MOS) = 23.40
```

28.92 元位于 entry 与 base fair 之间，因此输出 `HOLD_FAIR_VALUE`，而不是因为历史 PE 更高就输出 BUY。

## 历史 PE 反向估值：只做参考与兜底

当前瞻三情景输入不足时，系统才使用 `REFERENCE_ONLY_REVERSE_PE`：

```text
required_profit_growth = current_pe / historical_reference_pe - 1

target_price = current_price
             × (1 + target_required_profit_growth)
             / (1 + current_required_profit_growth)
```

其中历史参考 PE 严格排除当前观测。

报告继续输出：

- 当前价格隐含利润增长；
- `historical_reference_price`；
- -20% / -10% / 0 / +10% / +20% 隐含增长对应价格；
- 有显式业务增长证据时的 low/base/high 参考价格；
- 兼容字段 `buyable_price_ceiling`、`deep_value_price_ceiling`。

没有可靠未来增长区间时不编造预测：隐含增长 <= -20% 为 `BUY_DEEP_VALUE`，<= 0 为 `BUYABLE`，> 0 则保持 `NEED_HARD_LOGIC_GROWTH_SUPPORT`。这些结论明确属于 **reference-only fallback**，优先级低于前瞻公平价值。

若已有显式硬逻辑基础增长率，则按预期差分类：

- >= 30pp：`BUY_DEEP_VALUE`；
- >= 15pp：`BUYABLE_WITH_SUPPORTED_GROWTH`；
- 0–15pp：`WAIT_FOR_BETTER_PRICE`；
- < 0：`EXPECTATIONS_HIGH_WAIT`。

## 前瞻估值输入接口

生产链会额外查找可选的 `forward_scenario_valuation.csv`，按 `code` 合并到已有研究候选，不允许该文件单独把一只未进入研究池的股票塞进候选池。

主要字段：

- `earnings_stage`；
- `forward_eps_bear/base/bull`；
- `reasonable_pe_bear/base/bull`；
- 或 `scenario_fair_price_bear/base/bull`；
- 可选 `buy_margin_of_safety_required_pct`；
- 可选 `deep_value_margin_of_safety_required_pct`。

专业估值模型可以直接提供 `scenario_fair_price_*`，因此银行、保险、资源、地产、创新药等不需要被强迫套 PE。

## 历史回归：低估买入，预期打满后退出

`hard_logic_historical_backtest.py` 继续使用 point-in-time 的 reference-only reverse valuation 做历史捕获审计，因为历史上不能伪造当时不存在的分析师情景假设。当前生产的前瞻三情景层与该历史审计必须明确区分。

冻结规则：

- 财报只有真实披露后才可见；缺披露日时使用保守滞后，禁止把报告期日期当公开日期；
- `pd.NaT` 明确按“缺失披露日”处理，不能绕过保守披露滞后；
- 当前 PE 不进入自己的历史参考分布；
- 信号在收盘后生成，只在下一观察交易日开盘成交；
- 普通 `BUYABLE` / `BUYABLE_WITH_SUPPORTED_GROWTH` 必须同时满足 `historical_pe_percentile <= 50`；
- `BUY_DEEP_VALUE` 因预期差已经达到深度低估，可越过额外 50 分位门槛；
- 下一期开盘若高于信号日冻结的 `buyable_price_ceiling`，取消买入，不追价；
- 估值卖出必须同时满足“预期打满 + 历史 PE >= 70 分位”；
- 硬逻辑失效不等高估值，直接退出；
- 买卖均计 15 bps/side 摩擦成本；
- 不允许使用未来最高价、未来最低价或事后知道的牛股身份决定买卖点。

### 可重现案例捕获审计（2018-01-01 至 2026-08-18）

最新可重现著名股票案例面板：16 只案例中 15 只有足够历史数据，14 只产生交易；40 笔交易，36 盈 / 4 亏，单笔收益中位数 +48.3574%，均值 +130.0977%。这些数字存在显著 selection bias / survivorship bias，不能解释为未来全市场期望收益。

固定保存：

```text
famous_case_selection_bias_warning = true
headline_expected_return_allowed = false
```

## 生产输出与安全边界

生产链生成：

- `hard_logic_price_map.csv`；
- `hard_logic_price_map.md`；
- `hard_logic_price_map_summary.json`。

新增核心字段包括：

- `earnings_stage` / `earnings_stage_basis`；
- `valuation_framework`；
- `scenario_fair_price_bear/base/bull`；
- `base_upside_to_fair_pct` / `base_margin_of_safety_pct`；
- `watch_price_ceiling` / `entry_price_ceiling` / `ideal_price_ceiling`；
- `price_zone`；
- `historical_pe_is_reference_only`。

始终保持：

- `global_top1_required = false`；
- `technical_context_is_non_veto = true`；
- `formal_signal_eligible = false`；
- `automatic_promotion_allowed = false`；
- `no_auto_trade = true`。

原有 Formal BUY、止损、仓位、退出画像仍作为独立执行/风险审计视图；它们不能决定长期公司质量，也不能把“合理价”偷换成“买入价”。
