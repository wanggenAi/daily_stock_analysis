# V31_DURABLE_HANDOFF

> Latest compact handoff for the production-grade GenGe V3.1.1 Shanghai/Shenzhen A-share scan. `GEN_GE_V3_1_1_PRODUCTION` promotes the validated Confidence Gate while retaining the original immediate V3.1 SELL contract. Repository `main`, `V31_CANDIDATE_LEDGER.md`, `CURRENT_HOLDINGS.md`, and the dated `MARKET_RESEARCH_LOG_*.md` files remain the evidence chain.

## Production promotion 2026-08-26

- Decision: `PROMOTE_CONFIDENCE_GATE_ONLY`.
- Production: `GEN_GE_V3_1_1_PRODUCTION`.
- LOW/INVALID valuation confidence now returns HOLD_REVIEW and cannot create mechanical valuation BUY/SELL.
- Hard Gate FAIL still overrides all other rules and returns EXIT.
- The two-month V3.2 SELL confirmation was rejected after Round 9; V3.1 immediate SELL thresholds remain active.
- Research stops after Round 9. No V3.3 work is authorized without a new explicit request.

## Holdings-universe integrity invariant — 2026-08-26 20:09 CST

- `CURRENT_HOLDINGS.md` is the **sole source of truth** for which securities receive holding-level HOLD/REDUCE/EXIT decisions.
- Every holding-risk refresh must rebuild the universe exclusively from the latest `CURRENT_HOLDINGS.md`.
- Never union or resurrect holdings from prior market logs, handoffs, research queues, historical screenshots, memory, or prior sessions unless they are still present in `CURRENT_HOLDINGS.md`.
- A historical log entry for a security not present in current holdings is research history only and cannot generate a current holding instruction.
- The 2026-08-26 19:07 log section that treated `600879 航天电子` and other stale names as current holdings is **SUPERSEDED / NON-CONTROLLING**. The issue is classified as `HOLDINGS_UNIVERSE_CONTEXT_DRIFT`; the authoritative 20:09 reconciliation found no REDUCE/EXIT among the four confirmed holdings.

## Latest authoritative refresh — 2026-08-26 20:09 CST

- Confirmed holdings from `CURRENT_HOLDINGS.md`: `603369 今世缘`, `001316 润贝航科`, `600276 恒瑞医药`, `600406 国电南瑞` only.
- Accepted 2026-08-26 closes recovered: 今世缘 **28.10**, 恒瑞医药 **46.74**, 国电南瑞 **23.42** CNY. 润贝航科 exact 2026-08-26 close remained independently unverified, so price-dependent action fails closed.
- Holding actions: 今世缘 **HOLD_REVIEW / NO ADD**; 润贝航科 **HOLD**; 恒瑞医药 **HOLD_REVIEW**; 国电南瑞 **HOLD**. **No current REDUCE/EXIT.**
- Latest durable execution-eligible candidate remains `603658 安图生物`, tier **WAIT**, Formal BUY **NO**.
- `603658` exact accepted close remains **34.17 CNY on 2026-08-25**. 2026-08-26 after-close reporting confirms a 2.22% decline, but the exact close chain remains incomplete/inconsistent; therefore Formal BUY/ADD stays blocked by fresh-data invariant.
- Fresh 2026H1 evidence for `603658`: revenue 20.58亿 (-0.12%), attributable profit 4.97亿 (-12.94%), operating cash flow 2.16亿 (-47.38%); the terminated capacity-expansion project and ~8.12亿元 R&D reallocation remain a capital-allocation/demand blocker until formally interpreted.
- Ledger delta: `603658` **RESEEN / PRICE_OBSERVED_ONLY**, seen_count 13. No NEW A1/A2, no tier/valuation/buy-band upgrade, no INVALIDATED name.

## Current deep-research priority

1. `603658 安图生物` — worth deeper study because price is around the observed entry area and IVD platform economics may be durable; upgrade is blocked by weakened H1 profit/cash conversion, unresolved capacity-to-R&D reallocation meaning, incomplete moat audit, normalized earnings and Bear/Base/Bull reverse valuation.

## Formal BUY

**NONE**
