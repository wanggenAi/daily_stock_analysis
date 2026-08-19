# 硬逻辑 × 当前价格预期地图

## 目标

这个报告解决两个彼此独立的问题：

1. **公司值不值得长期研究**：只看公司/产业的硬逻辑与结构性风险，不让短期均线、突破形态、60 日退出画像等交易时点条件把公司从长期机会池里删掉。
2. **现在这个价格能不能买**：对已经通过硬逻辑边界的公司，用反向估值计算当前价格已经要求公司未来做到多少利润增长，再判断预期是否已经打满。

因此系统不再要求从 5000 多只股票里强行压成“唯一一只”。符合硬逻辑的公司都可以保留；每家公司独立得到自己的价格结论。

## 核心公式

当 `current_pe` 与公司自身严格历史参考 PE 都有效时：

```text
required_profit_growth = current_pe / historical_reference_pe - 1
```

它回答的不是“股价明天涨不涨”，而是：

> 如果估值倍数回到公司的历史参考水平，当前股价要求核心利润相对正常化利润增长多少？

价格地图反推公式为：

```text
target_price = current_price
             × (1 + target_required_profit_growth)
             / (1 + current_required_profit_growth)
```

因此报告会直接给出“市场要求利润 -20% / -10% / 0% / +10% / +20%”分别对应什么股价。

## 硬逻辑与技术条件的边界

结构性公司风险仍然可以阻断硬逻辑，例如真实的财务完整性、持续经营或其他公司级硬风险。

以下信息在本层只作为上下文，不作为公司质量否决：

- MA5 / MA10 / MA20 / MA60 形态；
- 短期异常涨幅；
- `price_too_high` 等技术形态条件；
- 退出画像、退出样本和中期交易验证条件。

原有 Formal BUY、止损、仓位、退出画像等模块不会被删除；它们仍用于独立的执行/风险审计，但不再决定这张长期“公司是否好 + 当前价格是否便宜”的地图。

## 价格结论

如果没有可靠的未来业务增长区间，系统不会编造预测：

- `BUY_DEEP_VALUE`：当前价格在历史参考倍数下隐含至少 20% 的利润收缩；
- `BUYABLE`：当前价格在历史参考倍数下不要求利润增长；
- `NEED_HARD_LOGIC_GROWTH_SUPPORT`：当前价格要求利润增长，需要先用产业/公司硬逻辑给出可验证的增长支持；
- `VALUATION_REFERENCE_UNAVAILABLE`：历史估值参考不足，不能用这套 PE 倒推。

如果研究层已经提供显式的硬逻辑利润增长区间，则直接比较：

```text
expectation_headroom = supported_base_profit_growth - market_required_profit_growth
```

当前规则：

- 预期差 ≥ 30 个百分点：`BUY_DEEP_VALUE`；
- 预期差 ≥ 15 个百分点：`BUYABLE_WITH_SUPPORTED_GROWTH`；
- 预期差 0～15 个百分点：`WAIT_FOR_BETTER_PRICE`；
- 预期差 < 0：`EXPECTATIONS_HIGH_WAIT`。

这些阈值是可审计的研究分类，不是自动交易授权。

## 输出文件

生产链在 `GenGe Postscan Research Pipeline` 成功后运行 `GenGe Hard Logic Price Map`，生成：

- `hard_logic_price_map.csv`：完整结构化价格地图；
- `hard_logic_price_map.md`：适合人工快速阅读的当前结论；
- `hard_logic_price_map_summary.json`：候选数量、硬逻辑通过数量及各价格状态统计。

报告明确保持：

- `global_top1_required = false`；
- `technical_context_is_non_veto = true`；
- `formal_signal_eligible = false`；
- `automatic_promotion_allowed = false`；
- `no_auto_trade = true`。

## 数据纪律

- 正常化利润优先使用扣非/可持续核心利润；
- 周期公司不能把峰值利润直接当永久利润；
- 当前 PE 必须是当前状态，当前 PE 非正数时不偷偷回退到过去的正 PE；
- 历史参考 PE 严格排除当前观测，避免自我引用；
- 未来利润增长区间必须来自显式、可审计的硬逻辑证据，缺失时保持缺失。
