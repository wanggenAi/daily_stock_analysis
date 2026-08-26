# V31_CANDIDATE_LEDGER

> Durable cross-session ledger for V3.1 candidates that are genuinely worth deeper research. This is **not** the full scan universe and is not an automatic trading instruction.

## CURRENT DEEP RESEARCH QUEUE

| Priority | Code | Name | Tier | Formal BUY | Latest verified price | Trade date | Why research now | Missing step before upgrade |
| ---: | --- | --- | --- | --- | ---: | --- | --- | --- |
| 1 | 603658 | 安图生物 | WAIT | NO | 34.17 | 2026-08-25 | Latest production cycles repeatedly reproduce it as the only execution-eligible long-term second-pass/deep-review name; price remains near the observed entry band, but verified 2026H1 profit and cash-flow deterioration keep the hard gates unresolved. | Complete moat/long-term-demand and financial-safety audit, normalize earnings/cash conversion after H1 deterioration, then finish Bear/Base/Bull reverse valuation, expectation gap, downside and falsification review. |

Current queue rule: only execution-eligible Shanghai/Shenzhen A-share names with material research value belong here. A broad `PENDING` universe, technical-only setups, low-valuation-only names and research-only markets are excluded.

---

## Active candidate ledger

### 603658 安图生物

- **execution eligibility:** ELIGIBLE
- **first_seen:** 2026-08-26 01:10 CST durable hourly scan
- **last_seen:** 2026-08-26 14:11 CST production refresh
- **seen_count:** 8
- **first source run_id:** 32873471270
- **latest source run_id:** 32907982933
- **postscan source run_id:** 32907982947
- **current tier:** WAIT
- **Formal BUY:** NO
- **latest verified price:** 34.17 CNY
- **latest verified trade date:** 2026-08-25
- **observed entry band:** 33.58–34.15 CNY
- **Bear/Base/Bull / fair-value range:** PENDING_DEEP_RESEARCH; must be rebuilt using normalized earnings after the 2026H1 deterioration rather than a historical/production placeholder.
- **long-term demand logic:** PARTIALLY_SUPPORTED — IVD remains a durable diagnostic demand category; company has broad immunoassay/biochemistry/microbiology/molecular/POCT coverage, but the company-specific 5–10Y demand-growth case still needs evidence-backed quantification.
- **moat / ASML test:** PARTIALLY_SUPPORTED — broad instrument/reagent platform, registrations/patents/R&D and installed service base are supportive, but customer stickiness, reagent pull-through, domestic/import competition and replacement difficulty still require a formal V3.1 moat audit.
- **earnings / cash-flow conclusion:** DOWNGRADED / VERIFIED_WEAKENING — 2026H1 revenue 20.58 亿 RMB, YoY -0.12%; attributable net profit 4.97 亿 RMB, YoY -12.94%; operating cash flow 2.16 亿 RMB, YoY -47.38%. Earnings direction/quality is weaker and does not justify A-class promotion.
- **current blockers:** H1 earnings direction and cash-flow conversion weakened materially; predictability, company-level long-term demand, moat durability and financial-safety hard gates are not fully completed; normalized earnings must be recalculated; Bear/Base/Bull valuation, implied expectations, expectation gap, risk-adjusted 3Y CAGR, downside and falsification remain incomplete. The observed entry band alone is insufficient. No independently verified 2026-08-26 intraday price was accepted through the 14:11 scan, so fresh-data invariant also blocks Formal BUY/ADD.
- **invalidation conditions:** sustained multi-period decline in core reagent/instrument revenue or installed-base monetization; persistent cash-flow conversion deterioration without working-capital explanation; evidence that domestic/import competition materially erodes pricing, reagent pull-through or instrument placement economics; normalized Base value falling below the current/entry-band price after full V3.1 review.
- **confidence:** HIGH that Formal BUY is not justified now; MEDIUM on maintaining deep-research priority pending full moat/normalized-earnings audit.
- **next deep-research action:** read the full 2026H1 filing and segment/working-capital detail; complete company-level moat/long-term-demand audit; normalize sustainable profit and cash conversion; then run Bear/Base/Bull reverse valuation against a newly verified market price.

#### Delta history

- **2026-08-26 01:10 CST — NEW:** entered durable deep-research queue from production artifacts. Execution-eligible and near an indicated entry band, but still blocked by incomplete V3.1 evidence. Formal BUY = NO.
- **2026-08-26 03:06 CST — RESEEN:** production reproduced the same second-pass candidate and verified 2026-08-25 price/entry band. No tier, valuation band or Formal BUY upgrade.
- **2026-08-26 05:06 CST — DOWNGRADED_EVIDENCE / RESEEN:** fresh 2026H1 evidence resolved part of the financial gate negatively: revenue ~flat, attributable profit -12.94% YoY and operating cash flow -47.38% YoY. Tier remains WAIT and Formal BUY remains NO.
- **2026-08-26 06:09 CST — RESEEN:** production again reproduced the same three long-term second-pass names; `603658` remained the only execution-eligible durable candidate. No valuation/buy-band or thesis change.
- **2026-08-26 07:08 CST — RESEEN:** latest successful production workflows again reproduce `603658` as the only execution-eligible long-term second-pass/deep-review candidate. Verified close 34.17 on 2026-08-25; observed entry band 33.58–34.15. No tier, Formal BUY, valuation or entry-band change.
- **2026-08-26 12:08 CST — RESEEN:** hourly opportunity + holdings-risk scan retained `603658` as the only execution-eligible deep-research queue name. No fresh 2026-08-26 intraday quote was independently verified; H1 earnings/cash-flow downgrade remains controlling.
- **2026-08-26 13:08 CST — RESEEN:** no material candidate or holdings-risk change. No independently verified newer executable price was accepted; no tier, valuation, entry-band or Formal BUY change.
- **2026-08-26 14:11 CST — RESEEN:** repeated refresh found no new A1/A2 executable candidate and no accepted fresh intraday quote. `603658` remains WAIT / Formal BUY NO; H1 earnings/cash-flow blockers and required normalized valuation remain unchanged.

---

## Research-only observations retained outside executable queue

Latest production continues to surface `688526 科前生物` and `688687 凯因科技` in long-term second pass, but both are `RESEARCH_ONLY` for this execution universe and therefore are excluded from `CURRENT DEEP RESEARCH QUEUE` and actual-buy candidates.

---

## Archived / INVALIDATED

None yet.

---

## Ledger maintenance contract

Every hourly V3.1 scan must update this file when a candidate is `NEW`, `RESEEN`, `UPGRADED`, `DOWNGRADED`, `INVALIDATED`, or has a material `PRICE_ONLY_CHANGE` that changes entry readiness.

For repeated candidates, update `last_seen`, `seen_count`, source run id, price/trade date, tier, valuation/buy range, blockers and next action. Do not create duplicate stock entries. `INVALIDATED` names are archived rather than deleted so the evidence chain survives future sessions.

A new session asking “V3.1 最近跑出了哪些值得深入研究的股票” should read this file first, then the latest `MARKET_RESEARCH_LOG_*.md` for run-level detail.
