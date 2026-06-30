# Evidence Quality Report

- files_scanned: 4
- industry_rows: 16
- company_rows: 20
- rejected_rows: 0
- skipped_rows: 0
- missing_source_rows: 0
- missing_date_rows: 0
- high_confidence_rows: 20

说明：缺少 source/date 或必需字段的证据不会进入正式 CSV，而是写入 rejected_evidence.csv；脚本只抽取结构化 evidence item，不采纳未标来源的叙述性结论，也不会从叙述文本自动推断 HIGH。

## Files

- research/industry_cycle/panel.json
- research/industry_cycle/pork.json
- research/industry_cycle/panel.md
- research/industry_cycle/pork.md
