# V31_DURABLE_HANDOFF

> Latest compact handoff for the production-grade GenGe V3.1.1 Shanghai/Shenzhen A-share scan. `GEN_GE_V3_1_1_PRODUCTION` promotes the validated Confidence Gate while retaining the original immediate V3.1 SELL contract. Repository `main`, `V31_CANDIDATE_LEDGER.md`, `CURRENT_HOLDINGS.md`, and the dated `MARKET_RESEARCH_LOG_*.md` files remain the evidence chain.

## Production promotion 2026-08-26

- Decision: `PROMOTE_CONFIDENCE_GATE_ONLY`.
- Production: `GEN_GE_V3_1_1_PRODUCTION`.
- LOW/INVALID valuation confidence returns HOLD_REVIEW and cannot create mechanical valuation BUY/SELL.
- Hard Gate FAIL still overrides all other rules and returns EXIT.
- The two-month V3.2 SELL confirmation was rejected after Round 9; V3.1 immediate SELL thresholds remain active.
- Research stops after Round 9. No V3.3 work is authorized without a new explicit request.

## Holdings-universe integrity invariant

- `CURRENT_HOLDINGS.md` is the sole source of truth for which securities receive holding-level HOLD/REDUCE/EXIT decisions.
- Every holding-risk refresh must rebuild the universe exclusively from the latest `CURRENT_HOLDINGS.md`.
- Never union or resurrect holdings from prior market logs, handoffs, research queues, historical screenshots, memory, or prior sessions unless they are still present in `CURRENT_HOLDINGS.md`.
- A historical log entry for a security not present in current holdings is research history only and cannot generate a current holding instruction.
- The 2026-08-26 19:07 log section that treated `600879 航天电子` and other stale names as current holdings is SUPERSEDED / NON-CONTROLLING.

## Latest authoritative refresh — 2026-08-27 07:08 CST

- Latest completed A-share session remains 2026-08-26; this refresh is pre-open filing/news + production-health verification.
- Confirmed holdings from `CURRENT_HOLDINGS.md`: `603369 今世缘`, `001316 润贝航科`, `600276 恒瑞医药`, `600406 国电南瑞` only.
- Accepted 2026-08-26 closes remain: 今世缘 **28.10**, 润贝航科 **26.69**, 恒瑞医药 **46.74**, 国电南瑞 **23.42** CNY.
- Holding actions remain: 今世缘 **HOLD_REVIEW / NO ADD**; 润贝航科 **HOLD_REVIEW**; 恒瑞医药 **HOLD_REVIEW**; 国电南瑞 **HOLD_REVIEW**. **No new REDUCE/EXIT and no newly established hard-thesis invalidation.**
- 今世缘: H1 revenue/profit weakness and structural baijiu demand/channel pressure remain active; Q2 partial recovery and stronger H1 operating cash flow prevent escalation to REDUCE/EXIT in this refresh.
- 润贝航科: previously logged management/shareholder reduction overhang remains a governance/supply watch, but H1 revenue, profit and operating cash flow remain strongly positive YoY; no new order/margin/cash-conversion/management-continuity break found.
- 恒瑞医药: H1 earnings/cash-conversion pressure remains under review; recent drug-registration/marketing-application progress remains pipeline-supportive. No new innovation-pipeline or moat break found.
- 国电南瑞: newly published H1 summary confirms revenue **277.67亿 (+14.54%)** and attributable profit **30.73亿 (+4.08%)**, with proposed interim dividend **0.153 CNY/share**. Profit growth lagging revenue and previously identified cash-conversion/margin pressure remain review items, but grid digitization/UHV demand and grid-control/customer-certification moat are not falsified. No escalation to REDUCE/EXIT.
- Latest durable execution-eligible candidate remains `603658 安图生物`, tier **WAIT**, Formal BUY **NO**. Accepted execution-grade close remains **34.17 CNY on 2026-08-25** because a second independently accepted exact 2026-08-26 15:00 close is still unavailable under the fresh-data invariant.
- `603658` H1 blockers remain: company-confirmed slower IVD demand growth / procurement-price pressure, weaker profit and cash conversion, unresolved moat strength under homogeneous competition, and incomplete normalized Bear/Base/Bull reverse valuation. Q2 revenue being approximately flat/slightly positive YoY is only a marginal stabilization signal and does not remove these blockers.
- Ledger delta: `603658` **RESEEN / NO MATERIAL CHANGE**, seen_count **22**, last_seen **2026-08-27 07:08 CST**. No NEW A1/A2, no tier/valuation/buy-band upgrade, no INVALIDATED executable name.

## Production / CI health — HEALTHY 2026-08-27 07:08 CST

- Previous downstream execution-scope failure remains repaired without changing V3.1/V3.1.1 ranking, valuation, BUY/SELL thresholds or user trading eligibility.
- Latest visible `main` workflow runs completed successfully:
  - `GenGe V3.1.1 Every-Industry Research` run `33021974261`: **SUCCESS**.
  - `GenGe Postscan Research Pipeline` run `33021974263`: **SUCCESS**.
- No fresh production-chain, data-source or CI fault was found that would invalidate this refresh. Fresh-data and confidence fail-closed rules remain active.

## Current deep-research priority

1. `603658 安图生物` — worth deeper study because price is around the observed entry area and IVD platform economics may be durable; upgrade remains blocked by weaker H1 profit/cash conversion, company-confirmed demand/pricing pressure, incomplete moat audit, normalized earnings and Bear/Base/Bull reverse valuation.

## Formal BUY

**NONE**
