# 硬逻辑 × 当前价格预期地图

## 目标

这个报告只解决两个问题：

1. **公司本身有没有硬逻辑**：只判断公司/产业结构、持续盈利质量与明确公司级硬风险；不让大盘环境、均线、突破形态、入场条件、收益风险比、仓位、止损或退出画像把好公司从长期机会池里删掉。
2. **现在这个价格能不能买**：公司硬逻辑通过后，用反向估值计算当前价格已经要求公司未来做到多少利润增长，再判断市场预期是否已经打满。

因此系统不再要求从 5000 多只股票里强行压成“唯一一只”。多个真正有硬逻辑的公司可以同时保留，每家公司独立得到自己的价格结论。

## 第一层：硬逻辑边界

真正可以阻断公司的包括：

- 明确公司级结构性硬风险；
- 明确的 hard-logic `FAIL/BLOCKED`；
- 正常化持续核心利润非正。

旧严格交易系统中的以下项目在本层全部降级为 `non_veto_context`，只能辅助阅读，不能否决公司质量：

- 大盘/市场 regime；
- MA5 / MA10 / MA20 / MA60 与短期技术形态；
- 突破、回踩和具体 entry 条件；
- 短期异常涨幅；
- 止损、逻辑失效位；
- Reward/Risk；
- 仓位和 position sizing；
- execution 条件；
- 退出画像、退出样本和中期交易验证条件。

同时，“进入行业研究候选”本身不等于硬逻辑已经确认。若只拿到 `RESEARCH_CANDIDATE`，还要求反向估值数据可用，并且持续盈利质量不弱，才自动进入 `PASS`；否则保留为 `REVIEW`，不制造确定性。

## 第二层：反向估值

当 `current_pe` 与公司自身严格历史参考 PE 都有效时：

```text
required_profit_growth = current_pe / historical_reference_pe - 1
```

它回答的不是“股价明天涨不涨”，而是：

> 如果估值倍数回到公司的历史参考水平，当前股价已经要求正常化核心利润增长多少？

价格地图反推公式：

```text
target_price = current_price
             × (1 + target_required_profit_growth)
             / (1 + current_required_profit_growth)
```

所以报告会直接给出市场要求利润 `-20% / -10% / 0% / +10% / +20%` 时分别对应什么股价。

### 直接给出“多少钱能买”

报告额外输出两个最直接的字段：

- `buyable_price_ceiling`：按当前规则仍保有足够估值空间的最高可接受价格；
- `deep_value_price_ceiling`：进入深度低估区域的价格上限。

如果还没有可靠的未来利润增长区间，为避免编造预测：

```text
buyable_price_ceiling = 市场只要求 0% 利润增长时对应的价格
deep_value_price_ceiling = 市场隐含 -20% 利润增长时对应的价格
```

如果已有显式、可审计的硬逻辑基础增长率 `supported_base_growth`：

```text
buyable threshold required growth = supported_base_growth - 15pp
deep-value threshold required growth = supported_base_growth - 30pp
```

因此用户可以直接看到类似：

```text
当前价 = 40
最高可接受买入价 <= 45
深度低估价 <= 38
```

当前价格高于上限就等，不需要再用技术指标重新决定公司值不值得买。

## 价格结论

如果没有可靠的未来业务增长区间，系统绝不自行编造预测：

- `BUY_DEEP_VALUE`：当前价格在历史参考倍数下隐含至少 20% 的利润收缩；
- `BUYABLE`：当前价格在历史参考倍数下不要求利润增长；
- `NEED_HARD_LOGIC_GROWTH_SUPPORT`：当前价格要求利润增长，必须先用产业/公司硬逻辑证明该增长可实现；
- `VALUATION_REFERENCE_UNAVAILABLE`：历史估值参考不足，不能硬算。

如果研究层已经提供显式、可审计的硬逻辑利润增长区间，则直接计算：

```text
expectation_headroom = supported_base_profit_growth - market_required_profit_growth
```

当前分类规则：

- 预期差 ≥ 30 个百分点：`BUY_DEEP_VALUE`；
- 预期差 ≥ 15 个百分点：`BUYABLE_WITH_SUPPORTED_GROWTH`；
- 预期差 0～15 个百分点：`WAIT_FOR_BETTER_PRICE`；
- 预期差 < 0：`EXPECTATIONS_HIGH_WAIT`。

这些阈值是可审计的研究分类，不是自动交易授权。

## 历史回归：按当时信息做“低买高卖”

`hard_logic_historical_backtest.py` 使用同一套反向估值决策做 point-in-time walk-forward 回放，不允许拿未来数据优化过去的信号。

历史回放固定遵守：

- 财报只有在真实披露日之后才可见；若数据源缺少披露日，使用保守披露滞后，不把报告期日期冒充公开日期；
- 当前 PE 的历史参考只使用当前观测之前的正 PE，当前值绝不进入自己的参考分布；
- 信号在当日收盘数据完成后生成，交易只允许在下一观察交易日开盘执行；
- 买入必须先满足公司硬逻辑 `PASS` 和反向估值可买条件；
- 为明确落实“低位买”，普通 `BUYABLE` / `BUYABLE_WITH_SUPPORTED_GROWTH` 还要求当前 PE 位于自身严格历史分布的低半区（`historical_pe_percentile <= 50`）；`BUY_DEEP_VALUE` 因预期差本身已经达到深度低估标准，可直接通过这一额外分位门槛；
- 买入执行价若已经跳空高于信号日冻结的 `buyable_price_ceiling`，取消该次买入，不追价；
- 卖出优先发生在硬逻辑被可见新数据破坏，或市场隐含增长已经达到/超过硬逻辑可支撑增长时；没有可靠增长支持时，历史参考 PE 上方约 `+20%` 的隐含增长作为保守“预期偏满”退出线；
- 买卖均计入交易摩擦成本；
- 买卖点不会使用未来最高价、未来最低价或事后知道的牛股身份。

回归输出包括：

- `historical_signals.csv`：每个历史 BUY / SELL 信号及当时可见估值；
- `historical_trades.csv`：实际下一期开盘成交后的逐笔收益、持有期、最大回撤、最大上行和收益捕获率；
- `famous_case_results.csv`：著名股票逐只捕获结果；
- `data_failures.csv`：数据不足或历史估值不可用的案例，不得静默删除；
- `historical_backtest_summary.json` 与 `historical_backtest.md`：总体审计摘要。

著名股票案例集是**事后案例捕获审计**，用于回答“这套逻辑是否有机会在当时识别后来成为大牛股的公司”，不能把这一小组已经出名的赢家的平均收益冒充为全市场无偏预期收益。真正的策略总体收益必须进一步使用历史时点全市场股票池并处理退市股/幸存者偏差。

对于上市时间过短、没有至少一段可形成自身历史估值参考的股票，系统必须明确输出历史不足，而不是伪造历史 PE；此类公司需要走新股/同业可比估值路由后才能做当前价格判断。

## 输出文件

生产链在 `GenGe Postscan Research Pipeline` 成功后运行 `GenGe Hard Logic Price Map`，生成：

- `hard_logic_price_map.csv`：完整结构化价格—预期地图；
- `hard_logic_price_map.md`：适合人工快速阅读的当前结论；
- `hard_logic_price_map_summary.json`：候选数量、硬逻辑通过数量及各价格状态统计。

每一行都保留当前价、当前 PE、历史参考 PE、历史估值分位、当前价格隐含利润增长、`buyable_price_ceiling`、`deep_value_price_ceiling`，以及在 -20% / -10% / 0% / +10% / +20% 市场增长要求下对应的价格。若有显式硬逻辑利润增长区间，还会额外输出其 low/base/high 对应的价值价格。

报告明确保持：

- `global_top1_required = false`；
- `technical_context_is_non_veto = true`；
- `formal_signal_eligible = false`；
- `automatic_promotion_allowed = false`；
- `no_auto_trade = true`。

原有 Formal BUY、止损、仓位、退出画像等模块不会被删除；它们仍可作为独立的执行/风险审计视图，但不再决定这张长期“公司是否好 + 当前价格是否便宜”的地图。

## 数据纪律

- 正常化利润优先使用扣非/可持续核心利润；
- 周期公司不能把峰值利润直接当永久利润；
- 当前 PE 必须是当前状态，当前 PE 非正数时不偷偷回退到过去的正 PE；
- 历史参考 PE 严格排除当前观测，避免自我引用；
- 未来利润增长区间必须来自显式、可审计的硬逻辑证据，缺失时保持缺失；
- 技术与执行条件不能反向污染公司硬逻辑判断；
- 历史案例没有数据就是没有数据，禁止用后验信息补洞。

本功能的仓库级变更摘要同步记录在 `docs/CHANGELOG.md` 的 `[Unreleased]` 部分。