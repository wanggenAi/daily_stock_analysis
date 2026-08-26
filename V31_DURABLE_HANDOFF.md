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

## Latest authoritative refresh — 2026-08-27 06:09 CST

- Latest completed A-share session remains 2026-08-26; this refresh is overnight filing/news + production-health verification.
- Confirmed holdings from `CURRENT_HOLDINGS.md`: `603369 今世缘`, `001316 润贝航科`, `600276 恒瑞医药`, `600406 国电南瑞` only.
- Accepted 2026-08-26 closes: 今世缘 **28.10**, 润贝航科 **26.69**, 恒瑞医药 **46.74**, 国电南瑞 **23.42** CNY.
- Holding actions remain: 今世缘 **HOLD_REVIEW / NO ADD**; 润贝航科 **HOLD_REVIEW**; 恒瑞医药 **HOLD_REVIEW**; 国电南瑞 **HOLD_REVIEW**. **No new REDUCE/EXIT and no newly established hard-thesis invalidation.**
- Latest durable execution-eligible candidate remains `603658 安图生物`, tier **WAIT**, Formal BUY **NO**. Accepted execution-grade close remains **34.17 CNY on 2026-08-25** because a second independently accepted exact 2026-08-26 close is still unavailable under the fresh-data invariant.
- `603658` blockers remain: company-confirmed slower IVD demand growth / procurement-price pressure, weaker 2026H1 profit and cash conversion, unresolved moat strength under homogeneous competition, and incomplete normalized Bear/Base/Bull reverse valuation.
- Ledger delta: `603658` **RESEEN / NO MATERIAL CHANGE**, seen_count 21. No NEW A1/A2, no tier/valuation/buy-band upgrade, no INVALIDATED executable name.

## Production / CI health — RECOVERED 2026-08-27 06:09 CST

- Previous downstream failure (`PRODUCTION_VALIDATOR_EXECUTION_SCOPE_DRIFT`) was repaired without changing V3.1/V3.1.1 ranking, valuation, BUY/SELL thresholds or user trading eligibility.
- Latest `main` workflow runs on head `e1f5699f1ebf6df625265d4375a32cc6e043adba` completed successfully:
  - `GenGe V3.1.1 Every-Industry Research` run `33017580568`: **SUCCESS**.
  - `GenGe Postscan Research Pipeline` run `33017580700`: **SUCCESS**.
- The successful postscan artifact reports **0 long-term Formal BUY**, **0 execution-eligible candidate rows**, and **4 holding rows**, all `HOLD_REVIEW` under invalid/incomplete valuation confidence. The four second-pass names are `688526`, `688739`, `688247`, `688687` and remain RESEARCH_ONLY / ineligible for actual user trading candidates.
- Automated opportunity discovery is therefore no longer marked DEGRADED for this repaired workflow revision. Fresh-data and confidence fail-closed rules remain active.

## Current deep-research priority

1. `603658 安图生物` — worth deeper study because price is around the observed entry area and IVD platform economics may be durable; upgrade remains blocked by weaker H1 profit/cash conversion, company-confirmed demand/pricing pressure, incomplete moat audit, normalized earnings and Bear/Base/Bull reverse valuation.

## Formal BUY

**NONE**
