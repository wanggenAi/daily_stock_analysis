# V31_DURABLE_HANDOFF

> Latest compact handoff for the production-grade GenGe V3.1.1 Shanghai/Shenzhen A-share scan. `GEN_GE_V3_1_1_PRODUCTION` promotes the validated Confidence Gate while retaining the original immediate V3.1 SELL contract. Repository `main`, `V31_CANDIDATE_LEDGER.md`, `CURRENT_HOLDINGS.md`, and dated market-research logs remain the evidence chain.

## Production promotion 2026-08-26

- Decision: `PROMOTE_CONFIDENCE_GATE_ONLY`; production=`GEN_GE_V3_1_1_PRODUCTION`.
- LOW/INVALID valuation confidence -> HOLD_REVIEW; Hard Gate FAIL -> EXIT.
- V3.2 sell confirmation remains research-only/rejected; no threshold drift is authorized.

## Holdings-universe integrity invariant

- `CURRENT_HOLDINGS.md` is the sole source of truth for holding-level HOLD/REDUCE/EXIT decisions.
- Rebuild holdings every refresh exclusively from that file; never resurrect historical holdings from logs, handoffs, screenshots, memory or old sessions.

## Candidate metabolism invariant — 2026-08-27

- Every refresh runs two loops: (A) re-underwrite/reprice durable old candidates; (B) discover new Shanghai/Shenzhen main-board candidates.
- Old candidates are not forgotten merely because one run produced no BUY, but they are not protected by prior selection. Weak names must be downgraded or archived/INVALIDATED with evidence.
- `CURRENT DEEP RESEARCH QUEUE` is a live priority queue, not a historical collection.
- Price weakness alone does not invalidate a thesis; price strength alone does not justify a BUY.

## Latest authoritative refresh — 2026-08-27 09:07 CST

- Latest completed A-share session: **2026-08-26**. This refresh is pre-open; no 2026-08-27 price-dependent BUY/ADD/REDUCE/EXIT is allowed before fresh same-day quotes.
- Confirmed holdings remain `603369 今世缘`, `001316 润贝航科`, `600276 恒瑞医药`, `600406 国电南瑞` only. No new REDUCE/EXIT or new hard-thesis invalidation was established pre-open.

### Candidate metabolism delta

- **NEW — 603416 信捷电气: WATCH / Formal BUY NO.** 2026H1 revenue 11.02亿 (+25.60%), attributable profit 1.55亿 (+21.98%), recurring profit 1.32亿 (+12.54%); operating cash flow turned to +0.4938亿 from -0.0722亿. Drive systems +30.27%, PLC +16.57%; robot business is a strategic focus and frameless torque motors are reported in scaled batch supply. Fresh 2026-08-26 close **45.40**. Upgrade is blocked by moat/customer-stickiness/pricing-power proof, capital-needs review and incomplete normalized Bear/Base/Bull reverse valuation.
- **RESEEN — 600312 平高电气: WATCH / BUY_REVIEW / Formal BUY NO.** 8/26 close **20.43**. Working conservative fair prices remain about **17.9 / 23.5 / 31.6** Bear/Base/Bull; H2 backlog-to-revenue/cash conversion and margin durability remain blockers.
- **RECOVERED — 600309 万华化学: A1-QUALITY / WAIT_PRICE / Formal BUY NO.** 8/26 close **74.49**. H1 revenue 1193.16亿 (+31.26%), profit 100.63亿 (+64.35%), operating cash flow 117.84亿 (+11.93%). Global MDI/TDI process/scale/integration moat remains strong; through-cycle segment normalization and explicit MOS/buy band are still required.
- **RECOVERED / PRICE_ONLY_CHANGE — 603993 洛阳钼业: A1 / WAIT_PRICE / Formal BUY NO.** 8/26 close **19.59 (+6.35%)**. World-class resource thesis remains intact, but the rally moved price away from the prior **17–18** first-entry research zone. Re-run through-cycle copper/cobalt normalization; do not chase commodity strength.
- **RECOVERED — 601899 紫金矿业: A1 / WAIT_PRICE / Formal BUY NO.** 8/26 close **34.47 (+2.35%)**. Global copper/gold resource and execution moat remain top-tier; normalized commodity assumptions and explicit MOS remain required.
- **RECOVERED / PRICE_ONLY_CHANGE — 601168 西部矿业: A2 / WAIT_PRICE / Formal BUY NO.** 8/26 close **39.26 (+7.62%)**. Strong resource/earnings thesis remains, but sharp price appreciation lowers immediate odds and copper-cycle normalization is mandatory.
- **DOWNGRADED_QUEUE_PRIORITY — 603658 安图生物: WAIT / Formal BUY NO.** H1 profit/cash conversion weakened and company-confirmed slower IVD demand/pricing pressure remains. It stays Active for one more normalized-earnings/moat review but is no longer the top research priority; if A-grade economics cannot be re-established it should leave CURRENT DEEP RESEARCH QUEUE. Exact accepted execution-grade close remains 34.17 on 2026-08-25.
- **INVALIDATED:** none this refresh.

### New-discovery coverage

- Industrial automation/robotics: promoted `603416 信捷电气` to WATCH.
- Main-board chemicals: screened strong H1 reporters including `000703 恒逸石化`; no promotion yet because the profit surge is heavily cycle-sensitive and recurring/core-profit plus through-cycle normalization must precede qualification.
- Resources: 8/26 non-ferrous strength triggered price-only rechecks, not new BUY signals.

## Production / CI health

- Latest repaired Every-Industry and Postscan chains remain the controlling successful production evidence. No new production/data-source/CI failure was found in this refresh.
- Fresh-data and confidence fail-closed rules remain active.

## Current deep-research priority

1. `600312 平高电气` — near conservative Base discount zone; needs H2 delivery/cash confirmation and final production expectation-gap/downside gates.
2. `603416 信捷电气` — NEW; operating and cash-flow evidence improved, but moat and reverse valuation are incomplete.
3. `600309 万华化学` — A1-quality non-resource diversification; needs segment-aware through-cycle valuation and explicit MOS.
4. `603993 洛阳钼业` — A1 resource quality; current price moved above prior preferred entry research band after 8/26 rally.
5. `601899 紫金矿业` — A1 resource quality; explicit normalized commodity downside/MOS needed.
6. `601168 西部矿业` — A2; sharp 8/26 rally lowers immediate entry odds.
7. `603658 安图生物` — downgraded queue priority; one more moat/normalized-earnings review before removal if A-grade economics cannot be re-established.

## Formal BUY / holding risk

- **Formal BUY / ADD: NONE pre-open.**
- **New holding REDUCE / EXIT: NONE pre-open.**
- Next required action after 09:30: refresh all queue names and holdings with verified 2026-08-27 prices, calculate distance to entry/overvaluation bands, then persist PRICE_ONLY_CHANGE / UPGRADED / DOWNGRADED as applicable.
