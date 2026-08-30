<div align="center">

# 📈 股票智能分析系统

[![GitHub stars](https://img.shields.io/github/stars/ZhuLinsen/daily_stock_analysis?style=social)](https://github.com/ZhuLinsen/daily_stock_analysis/stargazers)
[![CI](https://github.com/ZhuLinsen/daily_stock_analysis/actions/workflows/ci.yml/badge.svg)](https://github.com/ZhuLinsen/daily_stock_analysis/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> 🤖 基于 AI 大模型的多市场股票智能分析系统。

</div>

## 根哥生产研究扩展

本 fork 在原项目能力之上维护生产级研究扩展。`GEN_GE_V3_1_1_PRODUCTION` 仍是正式股票研究/决策内核；新增的 **Era & Capital Trend Radar V1** 是其上游、只读的时代/产业趋势发现层。

Era Radar 从政策资本、产业资本、金融资本、真实需求、技术变化与全球结构六类证据中形成行业无关的趋势假设，并分别评估 10–20 年结构趋势、3–10 年产业趋势和 6–36 个月景气变化。趋势具有独立生命周期和 PIT/provenance 证据链。

Era Radar **没有 Formal BUY/ADD/HOLD/REDUCE/EXIT 权限**，不会绕过 V3.1.1 的护城河、盈利、估值、安全边际、Confidence Gate、Hard Gate、Canonical Authority、持仓核对与 no-auto-trade 约束。详细契约见 `docs/ERA_CAPITAL_TREND_RADAR_V1.md`。

> 上游原项目完整说明仍保留在 Git 历史与上游仓库；本 fork 的生产文档以 `docs/` 中的 GenGe/V3.1.1 契约为准。
