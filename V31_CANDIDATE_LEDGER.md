# V31_CANDIDATE_LEDGER

> Durable cross-session ledger for V3.1 candidates that are genuinely worth deeper research. This is **not** the full scan universe and is not an automatic trading instruction.

## CURRENT DEEP RESEARCH QUEUE

| Priority | Code | Name | Tier | Formal BUY | Latest verified price | Trade date | Why research now | Missing step before upgrade |
| ---: | --- | --- | --- | --- | ---: | --- | --- | --- |
| 1 | 603658 | 安图生物 | WAIT | NO | 34.17 | 2026-08-25 | Reappeared in production near the observed entry band, and the 2026H1 report resolves part of the evidence gap: long-term IVD scale/R&D remain research-worthy, but H1 revenue was flat and profit/cash flow weakened materially. | Complete moat/long-term-demand and financial-safety audit, normalize earnings after the H1 deterioration, then finish Bear/Base/Bull reverse valuation, expectation gap, downside and falsification review. |

Current queue rule: only execution-eligible Shanghai/Shenzhen A-share names with material research value belong here. A broad `PENDING` universe, technical-only setups, low-valuation-only names and research-only markets are excluded.

---

## Active candidate ledger

### 603658 安图生物

- **execution eligibility:** ELIGIBLE
- **first_seen:** 2026-08-26 01:10 CST durable hourly scan
- **last_seen:** 2026-08-26 06:09 CST production refresh
- **seen_count:** 4
- **first source run_id:** 32873471270
- **latest source run_id:** 32902392600
- **postscan source run_id:** 32902392565
- **current tier:** WAIT
- **Formal BUY:** NO
- **latest verified price:** 34.17 CNY
- **latest verified trade date:** 2026-08-25
- **observed entry band:** 33.58–34.15 CNY
- **Bear/Base/Bull / fair-value range:** PENDING_DEEP_RESEARCH; must be rebuilt using normalized earnings after the 2026H1 deterioration rather than the prior production placeholder.
- **long-term demand logic:** PARTIALLY_SUPPORTED — IVD remains a durable diagnostic demand category; company has broad immunoassay/biochemistry/microbiology/molecular/POCT coverage, but the company-specific 5–10Y demand-growth case still needs evidence-backed quantification.
- **moat / ASML test:** PARTIALLY_SUPPORTED — company reports 1000+ product registrations, 2000+ patents, R&D intensity 18.16% of 2025 revenue, broad instrument/reagent platform and a large installed service base; customer stickiness, reagent pull-through, domestic/import competition and replacement difficulty still require a formal V3.1 moat audit.
- **earnings / cash-flow conclusion:** DOWNGRADED / VERIFIED_WEAKENING — 2026H1 revenue 20.58bn? **Unit normalization: 20.58 亿 RMB = 2.058bn RMB**, YoY -0.12%; attributable net profit 4.97 亿 RMB, YoY -12.94%; operating cash flow 2.16 亿 RMB, YoY -47.38%. Earnings authenticity is no longer simply unknown, but the direction/quality is weaker and fails to justify an A-class promotion today.
- **current blockers:** H1 earnings direction and cash-flow conversion weakened materially; predictability, company-level long-term demand, moat durability and financial-safety hard gates are not fully completed; normalized earnings must be recalculated; Bear/Base/Bull valuation, implied expectations, expectation gap, risk-adjusted 3Y CAGR, downside and falsification remain incomplete. The observed entry band alone is insufficient.
- **invalidation conditions:** sustained multi-period decline in core reagent/instrument revenue or installed-base monetization; persistent cash-flow conversion deterioration without working-capital explanation; evidence that domestic/import competition materially erodes pricing, reagent pull-through or instrument placement economics; normalized Base value falling below the current/entry-band price after full V3.1 review.
- **confidence:** HIGH that Formal BUY is not justified now; MEDIUM on maintaining deep-research priority pending full moat/normalized-earnings audit.
- **next deep-research action:** read the full 2026H1 filing and segment/working-capital detail; complete company-level moat/long-term-demand audit; normalize sustainable profit and cash conversion; then run Bear/Base/Bull reverse valuation against the fresh 34.17 close.

#### Delta history

- **2026-08-26 01:10 CST — NEW:** entered durable deep-research queue from production artifacts. Execution-eligible and near an indicated entry band, but still blocked by incomplete V3.1 evidence. Formal BUY = NO.
- **2026-08-26 03:06 CST — RESEEN:** latest successful V3.1 production run `32885281412` and Postscan `32885281466` reproduced the same second-pass candidate and the same verified 2026-08-25 price/entry band. No tier, valuation band or Formal BUY upgrade; hard-gate evidence remains incomplete.
- **2026-08-26 05:06 CST — DOWNGRADED_EVIDENCE / RESEEN:** fresh 2026H1 filing evidence resolves part of the prior unknown financial gate but is negative: revenue ~flat, attributable profit -12.94% YoY and operating cash flow -47.38% YoY. Tier remains WAIT, Formal BUY remains NO, and the blocker set is now stronger and more explicit. The current price remains 34.17 on 2026-08-25, so there is no price-only upgrade.
- **2026-08-26 06:09 CST — RESEEN:** latest successful production cycle (`Every-Industry run_id=32902392600`, `Postscan run_id=32902392565`, upstream full-A `run_id=32900338757`) reproduced the same three long-term second-pass names. `603658` remains the only execution-eligible durable candidate; verified price/trade date and observed entry band are unchanged, tier remains WAIT and Formal BUY remains NO. The 05:06 H1 downgrade evidence remains fully effective; no valuation/buy-band or thesis change occurred.

---

## Research-only observations retained outside executable queue

The latest production cycle again surfaced `688526 科前生物` and `688687 凯因科技` in long-term second pass, but both are `RESEARCH_ONLY` for this user's execution universe and therefore are not part of `CURRENT DEEP RESEARCH QUEUE`.

---

## Archived / INVALIDATED

None yet.

---

## Ledger maintenance contract

Every hourly V3.1 scan must update this file when a candidate is `NEW`, `RESEEN`, `UPGRADED`, `DOWNGRADED`, `INVALIDATED`, or has a material `PRICE_ONLY_CHANGE` that changes entry readiness.

For repeated candidates, update `last_seen`, `seen_count`, source run id, price/trade date, tier, valuation/buy range, blockers and next action. Do not create duplicate stock entries. `INVALIDATED` names are archived rather than deleted so the evidence chain survives future sessions.

A new session asking “V3.1 最近跑出了哪些值得深入研究的股票” should read this file first, then the latest `MARKET_RESEARCH_LOG_*.md` for run-level detail.
