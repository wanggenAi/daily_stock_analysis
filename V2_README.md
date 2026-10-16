# GenGe Stock V2 Clean

V2 的唯一目标：每天扫描 A 股并维护一个可读、可比较、可执行研究的动态候选池。

生产链只有一条：

`全A事实/价格 -> Top候选 -> V2排名/买区 -> V2_DASHBOARD.md`

## 设计约束

- 复用成熟的全 A 数据、量化、基本面和价格计划代码。
- 不依赖 Finalizer、Canonical、Reconciler、JEV authority 才能生成投资候选。
- `HARD_REJECT` 仍然是硬否决。
- 普通证据缺口只降低 `confidence`，不把候选从研究池抹掉。
- BUY 不凑数；候选池有充足来源时目标展示 30 只。
- 没有可靠价格计划时不编造买价，只给 WATCH。
- 行业默认最多 3 只优先占位，候选不足时自动补齐。
- 旧 V3 仍保留为 legacy，不参与 V2 最终输出。

## 唯一投资输出

- `V2_DASHBOARD.md`
- `data/v2/latest_run.json`

## 本地运行

```bash
python -m unittest tests.test_stock_v2 -v
python -m stock_v2.pipeline --top 30 --industry-cap 3
```

GitHub Actions 入口：`GenGe V2 Clean A-Share Decision`。
