# 硬逻辑 × 当前价格预期地图

## 目标

长期决策只回答两个问题：

1. **公司有没有硬逻辑**：判断公司/产业结构、持续盈利质量和明确公司级硬风险。
2. **当前价格能不能买**：公司硬逻辑通过后，用反向估值计算当前价格已经要求多少利润增长，再判断预期是否已经打满。

系统不再把 5000 多只股票强行压成唯一一只。多个硬逻辑公司可以同时保留，每家公司独立得到价格结论。

## 硬逻辑边界

真正可以阻断公司的包括明确公司级结构性硬风险、显式 hard-logic `FAIL/BLOCKED`、正常化持续核心利润非正。

大盘 regime、MA5/10/20/60、突破/回踩、entry、止损、Reward/Risk、仓位、execution、退出画像等在本层全部是 `non_veto_context`，不能反向否决公司质量。

普通 `RESEARCH_CANDIDATE` 也不自动等于硬逻辑确认：至少还要有可用的反向估值和不弱的持续盈利质量，否则保持 `REVIEW`。

## 反向估值

```text
required_profit_growth = current_pe / historical_reference_pe - 1

target_price = current_price
             × (1 + target_required_profit_growth)
             / (1 + current_required_profit_growth)
```

其中历史参考 PE 严格排除当前观测。

报告直接输出：

- `buyable_price_ceiling`：最高可接受买入价；
- `deep_value_price_ceiling`：深度低估价；
- 当前价格隐含利润增长；
- 有显式业务增长证据时的 low/base/high 价值价格。

没有可靠未来增长区间时不编造预测：隐含增长 <= -20% 为 `BUY_DEEP_VALUE`，<= 0 为 `BUYABLE`，> 0 则保持 `NEED_HARD_LOGIC_GROWTH_SUPPORT`。

若已有显式硬逻辑基础增长率，则按预期差分类：

- >= 30pp：`BUY_DEEP_VALUE`；
- >= 15pp：`BUYABLE_WITH_SUPPORTED_GROWTH`；
- 0–15pp：`WAIT_FOR_BETTER_PRICE`；
- < 0：`EXPECTATIONS_HIGH_WAIT`。

## 历史回归：低位买，高位卖

`hard_logic_historical_backtest.py` 使用与当前价格地图相同的反向估值逻辑做 point-in-time walk-forward 回放。

冻结规则：

- 财报只有真实披露后才可见；缺披露日时使用保守滞后，禁止把报告期日期当公开日期；
- 当前 PE 不进入自己的历史参考分布；
- 信号在收盘后生成，只在下一观察交易日开盘成交；
- 普通 `BUYABLE` / `BUYABLE_WITH_SUPPORTED_GROWTH` 必须同时满足 `historical_pe_percentile <= 50`；
- `BUY_DEEP_VALUE` 因预期差已经达到深度低估，可越过额外 50 分位门槛；
- 下一期开盘若高于信号日冻结的 `buyable_price_ceiling`，取消买入，不追价；
- **估值卖出必须同时满足“预期打满 + 历史 PE >= 70 分位”**；
- **硬逻辑失效不等高估值，直接退出**；
- 买卖均计 15 bps/side 摩擦成本；
- 不允许使用未来最高价、未来最低价或事后知道的牛股身份决定买卖点。

### 历史案例捕获审计（2018-01-01 至 2026-08-18）

历史回放必须以 GitHub Actions 当前 head 的真实 artifact 为准，禁止把旧运行或不可复现的漂亮数字写成当前结果。此前文档中的 43 笔、90.70% 胜率及若干 700%+ 单笔收益，在最新可复现 artifact 中并不存在，已经撤销。

排查确认旧回放存在 `pd.NaT` 日期语义 bug：公开财务数据本身有数十个报告期，但缺失披露日被规范化为 `NaT` 后，历史 point-in-time 层误把 `NaT` 当有效披露日期，导致全部财报在后续 `dropna` 中被删除，所有公司均停留在 `HARD_LOGIC_REVIEW`。现在修复为“`NaT` 等同缺失披露日，使用保守披露滞后”，然后只以新 artifact 重新生成买卖点和收益。

长鑫科技（688825）于 2026 年 7 月上市，不能用于多年低位到高位的历史验证；只作为新上市标的捕获观察。著名股票案例面板本身仍是事后样本，只能回答“规则有没有能力在历史上识别这些公司”，不能当作全市场无偏预期收益。

在新的可复现 artifact 完成前，本节不发布任何胜率、平均收益或明星股单笔收益数字。

## 回归输出

- `historical_signals.csv`：历史 BUY / SELL 信号及当时可见估值；
- `historical_trades.csv`：下一期开盘真实回放的逐笔收益、最大回撤、最大上行、捕获率；
- `famous_case_results.csv`：著名股票逐只捕获结果；
- `data_failures.csv`：数据不足案例；
- `historical_backtest_summary.json`；
- `historical_backtest.md`。

## 生产输出与安全边界

生产链生成 `hard_logic_price_map.csv`、`hard_logic_price_map.md`、`hard_logic_price_map_summary.json`。

始终保持：

- `global_top1_required = false`；
- `technical_context_is_non_veto = true`；
- `formal_signal_eligible = false`；
- `automatic_promotion_allowed = false`；
- `no_auto_trade = true`。

原有 Formal BUY、止损、仓位、退出画像仍可作为独立执行/风险审计视图，但不能决定长期公司质量和估值地图。

本功能的仓库级变更摘要记录在 `docs/CHANGELOG.md` 的 `[Unreleased]` 部分。