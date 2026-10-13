# Current Mission

## Goal
Deliver one **useful, continuously evidence-backed holdings-first stock report** through the existing deterministic Web and user-initiated ChatGPT Web; never use GPT API in new automation, never infer live broker holdings/cash/fills or create automatic trades. This file is an **index**, NOT either independently owned CAS state machine on `state/chatgpt-recovery`. On every restart re-read live main, AGENTS.md, both sidecars, current PRs/Actions and persisted artifacts; live GitHub wins over dated text here.

## Current Phase
- V4 only: `recovery/tasks/investor-decision-report-v4.json` is independently CAS verified **generation 25**, state commit `48fa2fffe6abe7fd4db98a66dc43a15990d60e45`. #326 holiday-freshness code is merged and real postmerge H1/Dashboard production is proven for the Sep30 market epoch.
- Research only: `recovery/tasks/stock-system-convergence.json` remains separately read **generation 83**, status `GEN83_TRUE_SEP29_POSTCLOSE_ALL_A_AUDITED_ALL_COMPANY_COLLECTION_CACHE_ONLY_ZERO_ORIGINALS`. Do not write that cursor from this root-index task.
- H3 website deployment remains optional and is not required for the primary connected-GitHub ChatGPT Web report.

## Last Verified Main
- Main `0e8bd80c03b7f5f700bef955467bc778ff2e84a8`, generated 2026-10-02 09:38 Beijing by the real Investor Decision Brief publisher after #326. Runtime writers can advance main again; always re-read live refs before action.

## Active Branch
- Root index only: `docs/task-state-pr326-holiday-freshness-20261002`, based exactly on main `0e8bd80c...`.
- Independent research PR #323 remains a separate owner/lane; no merge, rerun or research-cursor mutation is authorized by this docs refresh.

## Active PR
- #326 **MERGED** as `46e2b334c94c147cc253f96ea7d1515e5e90e4a6`: official 2026 SSE closure calendar now drives generation freshness; Oct1-7 keeps Sep30 as latest completed session and Oct8 is required only after the existing 16:00 settlement cutoff.
- #324 prior root-index replacement **MERGED**; this one-file refresh supersedes only its dated status.
- #323 research repair remains separate/open at last inspection. Old #318 must not be reintroduced.

## CI
- #326 exact head `f2fa0bd68e1f6233fb4c7a9409721740b07de557`: full CI run `36950137328` **SUCCESS** (ai-governance/backend/docker; Web correctly skipped), Postclose Source Recovery `36950137361` **SUCCESS**, Opportunity Discovery and Legacy Risk-Capped PR checks **SUCCESS**.
- Postmerge main CI run `36951821948` on merge commit `46e2b334...` is still in progress at this checkpoint; do not convert that into a green claim.
- Any new root-index PR must preserve the exact required headings, stay <=120 lines, and pass governance/review before merge.

## Production / Artifact
- Real postmerge Investor Decision Brief rerun `36945357562` attempt 2 **SUCCESS** and persisted main `0e8bd80c...`.
- Current Dashboard blob `453bae4a8c148c7a861730b774d48c111532e174`: generated `2026-10-02T01:38:11Z`, genuine market/CANONICAL as-of **2026-09-30**, freshness `OK`, `expected_min_trade_date=2026-09-30`, `holiday_calendar_mode=OFFICIAL_SSE_2026`; no stale fail-closed overlay.
- Current H1 blob `8fa3986a9c1ac06ebfe022ca9e918fb2dfc6aa21`: market EOD `UPSTREAM_FRESH_CALENDAR_UNVERIFIED` with upstream `OK`; stale-session blocker is gone. Remaining blockers are fund-position confirmation, live broker cash/positions, executable quotes and independent exchange-calendar verification.
- Formal BUY=0, Formal WAIT_PRICE=0, immediate operations=0. Research terminal has BUY=1 and RESEARCH_GAP=12; research authority remains advisory-only.

## Completed
- #319 monotonic market-date publication guard, #320 postclose recovery, #321 holding-value-watch, #322 V4 H3 and #325 H1 real-status contract are merged and previously verified.
- #326 fixed the verified Oct1 holiday false-stale defect without changing valuation, BUY/WAIT_PRICE/REJECT thresholds, broker assumptions, GPT API policy or trading authority.
- V4 cursor generation 25 records #326 exact-head CI, merge, real production publisher and current H1/Dashboard blobs. Independent research cursor remains generation 83 untouched.

## Current Findings
- Sep30 is correctly treated as the latest completed mainland session during Oct1-7 under the pinned official 2026 SSE calendar. On Oct8 before 16:00 Shanghai, Sep30 remains sufficient; after 16:00 Oct8 is required.
- Dashboard may now allow new exposure at the **freshness** layer, but that is not a trade recommendation or proof of executable buying: Canonical Formal BUY/WAIT remain zero, H1 has no formal buy rows, broker cash and executable quotes remain unverified.
- The current research-only BUY is still one candidate among 13 requested research objects; it must never be promoted to Formal authority merely because freshness is now OK.
- Planning cash 50,000 CNY dated Sep20 is not current brokerage cash. Existing holding actions and reference prices remain frozen Canonical evidence unless newer verified broker/execution inputs exist.

## Blockers
- Live broker cash/positions/fills, fund shares and executable quotes are unverified; independent exchange-calendar verification remains distinct from the pinned deterministic 2026 SSE calendar used by the freshness evaluator.
- Official issuer-original coverage remains incomplete in the independent research lane; gen83 proved zero new independently verified uncached issuer originals in its consumed Sep29 source epoch.
- H1 publication-time source pins can diverge from a later mutable Decision Center write; every owner report must re-read live Git blobs and lineage instead of trusting an old boolean.
- Historical corporate-action-adjusted, benchmarked 5/20/60 recommendation outcomes are not fully accepted; do not label historical correlations as verified personal P&L.

## Next Action
0. Owner report path: re-read newest live H1/Dashboard/Decision Center/Canonical and compare immutable lineage. Do not rerun a full-A scan merely because Oct1-7 has no new A-share session.
1. On Oct8, keep fail-closed time semantics: before 16:00 Shanghai the completed-session minimum remains Sep30; after 16:00 require genuine Oct8 market/CANONICAL evidence before treating freshness as current.
2. Research lane only: consume only later naturally eligible genuine issuer/Deep artifacts after gen83; explain/fix proven original-source gaps without reconsuming `36598810901` or weakening UNKNOWN!=PASS.
3. Continue user-value work from the current result layer: holdings-first evidence, research gaps, event evidence and executable constraints; do not create a second scoring/valuation system or change BUY thresholds.
4. H4 remains separate: prove date-valid, corporate-action-adjusted, benchmarked 5/20/60 market recommendation outcomes before any performance claim.
5. Only each lane owner may CAS-advance its own sidecar. Root TASK_STATE is an index and must not overwrite either task cursor.

## Do Not Repeat
- Do not rerun consumed premarket/postclose All-A epochs solely to refresh timestamps; do not reconsume Sep29 gen83 source run `36598810901`.
- Do not claim generated_at as price-source date, cached issuer URLs as new originals, planning cash as live broker cash, research BUY as Formal BUY, or an old center pin as the newest live center.
- Do not reopen/merge superseded #315 or old root #318.

## Guardrails
- Formal authority is FINALIZED_CANONICAL_ONLY with verified holdings reconciliation. `UNKNOWN != PASS`. Research/Jev is advisory and may never create Formal action; existing BUY/WAIT_PRICE/REJECT thresholds and valuation remain untouched; `no_auto_trade=true`; no newly added GPT API. User makes investment choices.
