# 行业周期证据层

本层用于给“低位修复”信号补充公开资料证据。它只读取本地 CSV、schema 和公开行情/财务数据，不接入券商账户，不读取资产、持仓、密码、验证码，不自动下单。

## 目标

- 把行业周期判断从单一分数扩展为可审计证据。
- 区分行业证据和公司证据，避免只靠价格或均线给出硬逻辑。
- 对证据缺失、模板来源、过期、冲突、负向证据做保守降级。
- 输出行业证据卡片和周期拐点研究观察候选，供人工复核。

## Schema

行业证据 schema 位于：

```text
config/industry_evidence_schema.yaml
```

当前覆盖行业：

- 猪肉
- 面板
- 稀土
- 光伏
- 锂电
- 化工
- 有色

每个行业至少包含 5 个指标。指标字段包括：

- `name`
- `description`
- `direction_rule`
- `positive_condition`
- `negative_condition`
- `source_hint`
- `default_weight`
- `freshness_limit_days`
- `required_or_optional`

当前别名包含 `养殖 -> 猪肉`，用于把股票行业映射到 schema 行业。

## CSV 输入

行业证据模板：

```text
data/examples/industry_cycle_evidence_template.csv
```

列：

```text
date,industry,evidence_name,evidence_value,evidence_direction,source,source_type,confidence,note
```

公司证据模板：

```text
data/examples/company_cycle_evidence_template.csv
```

列：

```text
date,code,stock_name,industry,evidence_name,evidence_value,evidence_direction,source,source_type,confidence,note
```

`source_type` 支持：

- `manual_template`
- `user_supplied`
- `provider_derived`
- `verified_multi_source`

模板或样例证据最多只能支持 `MEDIUM` 硬逻辑；缺失证据默认 `industry_evidence_score=50`、`confidence=LOW`、`hard_logic_level=NONE/WEAK`。

## 本地研究记录转换

脚本：

```bash
python scripts/update_industry_evidence_from_research.py \
  --research-dir research/industry_cycle/ \
  --output data/user_supplied/industry_cycle_evidence.csv \
  --company-output data/user_supplied/company_cycle_evidence.csv
```

支持 `.json` 和包含 `key=value` 或 `key: value` 的 `.md`。脚本只抽取结构化 evidence item，不采纳叙述性结论；缺少 `source` 的证据会降级为 `manual_template/LOW`，并生成：

```text
data/user_supplied/evidence_quality_report.md
```

## 策略字段

逐条信号会新增：

- `industry_evidence_score`
- `industry_cycle_phase`
- `industry_evidence_confidence`
- `industry_evidence_quality`
- `industry_evidence_source_type`
- `industry_evidence_summary`
- `industry_evidence_warning_flags`
- `company_evidence_score`
- `company_evidence_source_type`
- `company_evidence_summary`
- `hard_logic_score`
- `hard_logic_level`

`hard_logic_level` 为：

- `NONE`
- `WEAK`
- `MEDIUM`
- `STRONG`

`STRONG` 必须来自行业证据和公司证据相对一致，不能只靠价格、均线、低位分位或总分。过期、冲突、模板来源或负向证据都会阻止升级。

## 输出

开启输出参数后，会新增：

```text
industry_evidence_cards.md
industry_evidence_cards.json
cycle_turning_point_candidates.csv
```

`industry_evidence_cards.*` 包含：

- `industry`
- `as_of_date`
- `cycle_phase`
- `evidence_score`
- `confidence`
- `positive_evidence`
- `negative_evidence`
- `missing_required_evidence`
- `stale_evidence`
- `warning_flags`
- `summary`
- `candidate_stocks`
- `risk_notes`

`summary.json` 同时输出：

- `industry_evidence_source_type_summary`
- `company_evidence_source_type_summary`
- `evidence_source_type_distribution`

`cycle_turning_point_candidates.csv` 包含：

```text
code,stock_name,industry,as_of_date,cycle_phase,hard_logic_level,industry_evidence_score,industry_evidence_confidence,price_percentile_5y,valuation_score,financial_safety_score,trend_confirmation_level,signal_type,balanced_exit_net_return_60d_backtest_profile,risk_flags,reason,missing_evidence,disclaimer
```

该文件只表示“周期拐点研究观察候选”，不是交易指令。

## 一键运行

fixture smoke：

```bash
python -m src.strategies.genge_cycle_bottom.cli \
  --codes 000001,000002 \
  --years 5 \
  --benchmark 000300 \
  --price-data-dir tests/fixtures/genge_cycle_bottom/prices \
  --valuation-data-dir tests/fixtures/genge_cycle_bottom/valuation \
  --financial-data-dir tests/fixtures/genge_cycle_bottom/financial \
  --industry-cycle-file tests/fixtures/genge_cycle_bottom/industry_cycle.csv \
  --stock-industry-map tests/fixtures/genge_cycle_bottom/stock_industry_map.csv \
  --industry-evidence-file tests/fixtures/genge_cycle_bottom/industry_evidence.csv \
  --company-evidence-file tests/fixtures/genge_cycle_bottom/company_evidence.csv \
  --industry-evidence-schema config/industry_evidence_schema.yaml \
  --output-dir reports/genge_cycle_bottom_ci_smoke
```

真实宽池研究：

```bash
python scripts/run_genge_real_research.py \
  --stock-pool-file stock_pools/genge_broad_pool.txt \
  --years 5 \
  --benchmark 000905 \
  --output-dir reports/genge_industry_evidence_broad \
  --max-codes 100 \
  --step-days 1 \
  --auto-fetch-valuation \
  --auto-fetch-financial \
  --industry-evidence-file data/user_supplied/industry_cycle_evidence.csv \
  --company-evidence-file data/user_supplied/company_cycle_evidence.csv \
  --industry-evidence-schema config/industry_evidence_schema.yaml \
  --output-industry-evidence-cards \
  --output-cycle-turning-point-candidates \
  --fixture-smoke-passed \
  --ci-passed
```

如果 `data/user_supplied` 文件不存在，运行脚本会退回 examples/template。报告会标记为 `manual_template`，最终验收只能保守停在 `PASS_INDUSTRY_EVIDENCE_FRAMEWORK`。

## 验收枚举

行业证据层启用时，本层最终枚举只使用：

- `FAIL_EVIDENCE_LAYER`
- `PASS_INDUSTRY_EVIDENCE_FRAMEWORK`
- `PASS_HARD_LOGIC_RESEARCH_READY`
- `PASS_CYCLE_TURNING_POINT_SCREENER`
- `PASS_PAPER_TRADING_CANDIDATE`
- `PASS_PAPER_TRADING_READY`

第一版优先目标是 `PASS_INDUSTRY_EVIDENCE_FRAMEWORK`：代表字段、schema、报告、证据卡、候选文件和保守降级链路可运行。
