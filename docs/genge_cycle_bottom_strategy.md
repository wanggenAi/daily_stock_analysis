# 根哥周期底部硬逻辑策略

`genge_cycle_bottom` 是一个独立的历史滚动验证模块，用来验证“低位 + 估值 + 财务安全 + 止跌确认 + 市场环境”的确定性策略。

本模块只读取公开行情与财务数据，不接入券商账户，不自动下单，也不让 LLM 直接决定买入或卖出。

## 运行命令

```bash
python -m src.strategies.genge_cycle_bottom.cli \
  --codes 002714,000100 \
  --years 5 \
  --benchmark 000300 \
  --output-dir reports/genge_cycle_bottom
```

```bash
python -m src.strategies.genge_cycle_bottom.cli \
  --stock-pool-file stock_pool_genge.txt \
  --years 10 \
  --benchmark 000300 \
  --output-dir reports/genge_cycle_bottom
```

也可以使用本地 CSV 做离线验证：

```bash
python -m src.strategies.genge_cycle_bottom.cli \
  --codes 002714,000100 \
  --years 5 \
  --benchmark 000300 \
  --price-data-dir /path/to/price_csv \
  --valuation-data-dir /path/to/valuation_csv \
  --financial-data-dir /path/to/financial_csv \
  --output-dir reports/genge_cycle_bottom
```

价格 CSV 至少需要 `date,open,high,low,close,volume`。估值 CSV 可包含 `date,pb,pe,ps,market_cap`。财务 CSV 可包含 `report_date,debt_ratio,net_profit,operating_cash_flow,roe`。

## 信号类型

- `REJECT`：不符合，放弃
- `WATCH`：观察
- `LEFT_SMALL_BUY`：左侧小仓试错
- `CONFIRM_BUY`：右侧确认买入
- `HOLD`：持有
- `ADD`：加仓
- `REDUCE`：减仓
- `SELL`：卖出

第一版回测只对 `LEFT_SMALL_BUY`、`CONFIRM_BUY`、`ADD` 做未来收益验证。

## 防未来函数

策略每次生成信号都必须传入 `as_of_date`。特征层会把价格、估值、财务和基准数据截断到 `as_of_date` 当天及以前。未来 20/60/120/250 日收益只在信号生成之后由回测层计算。

如果财务数据无法确认披露日期，第一版会保守使用 `report_date <= as_of_date` 的记录；拿不到的字段会进入 `missing_fields`，不会编造数据。

## 输出文件

每次运行会在 `reports/genge_cycle_bottom/<时间戳>/` 下生成：

- `signal_details.csv`：每条历史信号明细
- `summary.json`：胜率、平均收益、中位数收益、回撤、跑赢基准比例、诊断信息
- `summary.md`：中文摘要与第一版结论

## 当前限制

- 估值和财务字段取决于数据源可得性，缺失会降低置信度。
- 第一版没有考虑交易费用、滑点和停牌无法成交。
- 行业硬逻辑只以财务安全、估值和趋势代理表达，尚未接入行业景气度数据库。
- 输出里的仓位和止损是策略验证参数，不是实盘指令。
