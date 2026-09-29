# Current Mission

## Goal
Deliver one **useful, continuously evidence-backed holdings-first stock report** through the existing deterministic Web and user-initiated ChatGPT Web; never use GPT API in new automation, never infer live broker holdings/cash/fills or create automatic trades. This file is an **index**, NOT either of the two independently owned CAS state machines on `state/chatgpt-recovery`. On EVERY restart re-read actual main, AGENTS.md, both LIVE sidecars, current PRs/reviews/exact-head CI, current persisted JSON **and real run artifacts**; current live evidence wins over these dated facts.

## Current Phase
- V4 only: `recovery/tasks/investor-decision-report-v4.json` on `state/chatgpt-recovery`, independently CAS verified **generation 21** at commit `8b0c4cfa6fa0327406848af8070378f07b308e3a` (2026-09-30 07:28 +08). **H3 code is MERGED**, postmerge full CI is SUCCESS; actual deployed Web/API/screenshot remain OPTIONAL unverified, NOT required for the primary ChatGPT Web task. H1 original source-validated read-only manifest was previously independently production proven.
- Research only: `recovery/tasks/stock-system-convergence.json` on the same state branch, separately read **generation 83**, status `GEN83_TRUE_SEP29_POSTCLOSE_ALL_A_AUDITED_ALL_COMPANY_COLLECTION_CACHE_ONLY_ZERO_ORIGINALS`. Read exact live blob again before any research write. Do not cross-update cursors, nor recreate old Scan/Deep source epochs.

## Last Verified Main
- Main `ddd81b350fd9ea7c3af09f2ea42d5f077fafa943`, verified 2026-09-30 ~07:30 Beijing, merges H3 #322. Runtime-generated main moves rapidly; inspect live each operation, do not insist current main always equals the original Canonical producer SHA.

## Active Branch
- This one-file docs-only root index refresh: `chore/fresh-dual-task-stock-index-20260930`, based on independently checked main `ddd81b35`, superseding conflicting old index #318 after its own safe review and merge.
- Active independent research PR #323 remains separate; no reruns, merges or cursor mutation by this root index.

## Active PR
- #322 V4 H3 replacement **MERGED** in main `ddd81b35`, exact head `ae2149ae`. Original H3 #315 now **CLOSED unmerged** after comparing identical code files (only CHANGELOG differed for current main).
- #325 V4 H1 real-freshness enum fix OPEN at head `a876dff9`: current genuine Sep29 dashboard `freshness.status=OK/fresh=true` was incorrectly declared `STALE_OR_UNVERIFIED` by H1's impossible `status==FRESH` comparison; scoped code/real evaluator+negative tests/Markdown/CHANGELOG committed, exact-head CI pending. This fixes *upstream label only*; no independent exchange-calendar/broker or actual orders proof.
- #323 research exhausted-gap/2023 annual comparative repair still OPEN at last check head `b2e04fd`, latest main mergeability fluctuates with runtime drift. Its separate owner must reverify exact head, all tests and original evidence postmerge; do not infer that old CI equals production.
- Old root index #318 is OPEN but `mergeable=false` and contains outdated cross-lane data; do NOT force it into main. Replace only with fully checked up-to-date one-file index from recent main.

## CI
- H3 #322 exact-head global CI `36502191593` and separate Web contract `36502191557`: SUCCESS. Postmerge main H3 Web contract `36645259946`: SUCCESS. Postmerge full main global CI `36645259874`: independently verified **completed/SUCCESS** including backend/docker/governance/web; merged code validation only, NOT deployed website evidence.
- Any new root-index PR must satisfy required `TASK_STATE.md` exact headings / at most 120 lines, AI governance check, latest main scope and review. No green CI claims before actual run inspection.

## Production / Artifact
- Genuine 2026-09-29 EOD is in Canonical `d1081f09e9e6ad2aec26` / source run `36600662837`; latest persisted `data/investor_decision_dashboard/latest.json` and H1 `data/investor_chatgpt_handoff/latest.json` as-of **Sep29**. The source day is real, not a Sep30 report-generation timestamp. Previously proven source-date guard PR319 and postclose recovery PR320 are MERGED; PR321 holding valuation watch MERGED.
- **H1 currentness audit:** a genuine later Investor Brief at `2026-09-29T23:31:36Z` reissued latest Dashboard (Git blob `93eeda39...`) plus H1 manifest (blob `be813832...`) against live Decision Center blob `5602c048...` (center generated `22:39:47Z`), all under authentic Sep29 Canonical `d1081f09...`. Independently re-read the three live main files and confirm H1 `source_files.dashboard.immutable_git_blob_sha=93eeda39...` and `source_files.decision_center.immutable_git_blob_sha=5602c048...` matched **at this checkpoint**; old earlier 19:24 H1 had diverged after later center regeneration. An H1 `center_matches_dashboard=true` is publication-time, NOT a permanent promise that the rapidly rewritten center remains identical. At every future owner request, recompare exact current live blobs before live-current claims.
- Last independently audited genuine Sep28 postclose full All-A run `36463680012`, artifact `10990169398`: bounded Deep queue80, annual official source16 noncached attempts (15 missing,1 failed), event30 attempted OK at collector-level but 0 verifiable original_url; unique touched30/80, untouched50, **zero independently proven new official issuer originals**, strict-ready0. Do not confuse collectors' OK with a genuine published filing, or repeat consumed runs.
- Last verified center run on Sep29 market has 4 holdings, deep-complete0, new Formal BUY0/WAIT_PRICE0 and no immediate invested planning cash. Research BUY=1 among8 current-terminal research objects, remaining 7 gaps, unresolved Deep gate count29 **at that specific runtime**; this workset can change and counts are not proof of stable market opportunities.

## Completed
- #319 monotonic market-date publication guard merged; #320 calendar-aware postclose recovery merged; actual Sep28 and then Sep29 EOD successfully reached Canonical; #321 read-only holding-value-watch merged.
- New research gen83 completed a genuine Sep29 postclose All-A read-only artifact audit: scheduled run `36598810901` / original artifact `11048833345`, real trade date Sep29, universe5,223/effective scan4,500/Deep80/strict-ready0. Raw audit CSV has annual16 CACHE-ONLY (15 SSE MISSING,1 SZSE FAILED), event30 CACHE-ONLY OK but zero original URLs; only30/80 company codes touched,50/80 untouched, ZERO new uncached original issuer material in this run. Negative-cache TTL is max24h MISSING/max6h FAILED, event key asof-dated. Do not rerun this consumed source epoch.
- #322 V4 H3 code merged with independent exact-head safety audit: all 16 changed paths matched old base-to-premerge main content (or were absent in both), preserving 420 newer runtime commits; required exact-head backend/docker/web/governance+H3 checks succeeded; postmerge H3 Web contract succeeded. #315 duplicate closed with audit comment. V4 CAS generation19 saved for this verified milestone.

## Current Findings
- Actual independently observed H1 contract bug: Sep29 dashboard's `freshness_contract={status:OK,fresh:true,formal_new_exposure_allowed:true}` under same Canonical while latest pinned H1 `feeds.market_eod.status=STALE_OR_UNVERIFIED` and upstream_status=OK. New PR325 corrects the enum, rejects invalid/future expected_min_trade_date, and requires both upstream and downstream safety flags, while maintaining `UPSTREAM_FRESH_CALENDAR_UNVERIFIED`, original issuer/broker UNKNOWN and explicit zero H1 execution. Pending real postmerge artifact and exact CI.
- Financial behavior: research BUY is advisory-only. Formal new BUY/WAIT_PRICE both0, immediate new cash deployment0, no auto trade. All 4 recorded holding actions remain from frozen Canonical, no inferred newest lot/fill/cash. Sep20 planned 50,000 CNY **not current brokerage cash**; funds/actual fills/current broker positions UNKNOWN.
- Actual postmerge deployment is not yet proven. Repo homepage metadata suggests `https://dsa.zhulinsen.tech`, but public access to `/investor-v4` and `/api/v1/investor-v4/latest` could not be verified from current browsing tool. This is NOT a confirmed live deployment or screenshot.

## Blockers
- **Primary ChatGPT Web task does NOT require any website deployment**: connected GitHub H1/Dashboard/Center live hash + asof verification is its acceptance path. Existing optional V4 stock-site deployment and screenshot remain unverified, but merged H3 code's postmerge full CI passed. No new hosting, browser automation or GPT API.
- H1 same-Canonical newer Decision Center publication races dashboard/handoff source pin; recorded lineage booleans are point-in-time, not current-live proof. Do not add cyclical expensive publisher dispatch blindly.
- Issuer collector bounded routing 30 touched/50 untouched and 0 verified new original company docs remain research lane. Broker/fund/fill and independent exchange-calendar/quote provenance remain unknown; historical adjusted 5/20/60 trading outcomes not fully accepted.

## Next Action
0. V4: validate PR325 exact-head global CI and real Investor Brief contract, review source+tests and concurrent #323 CHANGELOG; merge only when all required checks pass, then independently validate a true *postmerge* Sep29 source-consistent H1 manifest/Markdown emits UPSTREAM_FRESH_CALENDAR_UNVERIFIED (not broker/exchange-trade-ready) and original H1 immutable source hashes.
1. MAIN ChatGPT Web task: on every owner report request directly re-read newest live H1/Dashboard/Decision Center/Canonical and compare current main file Git-blob hashes against H1 pinned immutable versions; independently validate same asof Canonical and distinguish newer research overlay from prior pinned publication if center changed. Correct upstream H1 false stale only through tested PR325; do NOT require stock-site deployment to analyze connected GitHub.
2. V4: real consumer-time audit: compare current GitHub H1 pinned immutable center/dashboard blobs against live current main, flag newest center epoch mismatch if it occurs; trace Three-Pillar scheduled/overlay persistence and H1 producer cadence. Implement only minimal independently tested non-cyclic source co-publication or fail-closed consumer change on a fresh scoped PR after checking other active branches. Preserve source timing and immutable references.
3. Research: current gen83 ALREADY independently audited Sep29 full All-A `36598810901`/artifact`11048833345`; read only *later* genuine naturally eligible official issuer artifacts (not consumed `36362003421`, `36463680012`, `36598810901`) and current real Deep provenance; determine why 16 annual failed/missing and 30 event lacked original_url, why 50 untouched given budget/routing. Fix only proven cause with original publication URL/date/hash and true postmerge production proof. No UNKNOWN->PASS or BUY threshold changes.
4. H4 only after current source-consistent H1: independently prove corporate-action adjusted, benchmarked, date-valid 5/20/60 market recommendation outcomes. Do not label historical correlation as verified personal actual P&L without original broker fills.
5. Only each lane owner may CAS-advance its own live-generation task cursor after real proof. Root index should be refreshed after verified milestones, not used to overwrite separate sidecars. Old #318 must not reintroduce obsolete PR #313/H1 or Sep24-as-current states.

## Do Not Repeat
- Do not rerun consumed premarket full All-A `36362003421`, audited postclose `36463680012`, already consumed Deep/Terminal/Jev, or closed/superseded #315. Do not merge old #318 over this index.
- Do not claim last generated_at as price-source date, cached issuer URLs as new evidence, live cash from planning snapshot or old center snapshot as the current live center.

## Guardrails
- Formal authority is FINALIZED_CANONICAL_ONLY and verified hold reconciliation. `UNKNOWN != PASS`. Research/Jev advisory may never create Formal action; existing BUY/WAIT_PRICE/REJECT thresholds and valuation untouched; `no_auto_trade=true`; no newly added GPT API. User makes investment choices.
