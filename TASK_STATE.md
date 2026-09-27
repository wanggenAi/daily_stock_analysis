# Current Mission

## Goal
Maintain two **independent** owner-approved tasks: living V4 investor report and trustworthy official-source research. Each uses its own generation/blob CAS cursor on `state/chatgpt-recovery`; this document is a cross-lane index, not a combined cursor. GitHub live refs, artifacts and code override this checkpoint.

## Current Phase
- V4 cursor: recovery/tasks/investor-decision-report-v4.json (last read generation 7, stale relative to live merged code). P0 #305 and partial P1 #309 merged; owner operating contract #312 merged 655cf27434dda14d3dd9edb9d6cd6e6c83898ae0. H1 implementation PR #313 open, head 79fde649e78698d14b3b60bb98caf42a8d6d6c48 at last check, exact-head CI pending. No proven live H1 or V4 website.
- Independent R cursor: recovery/tasks/stock-system-convergence.json (last read generation 72, stale relative to main). Issuer coverage PR #310 merged e84b184b3f6f47c8315c6144bb1dd43c614f30eb after exact-head backend/docker/governance success. Production coverage artifact and net-new independent issuer evidence NOT YET verified. Read live separate cursor blobs before any owner-scoped mutation.

## Last Verified Main
- 0fd9a933b63d4500df2816771e0b0108ec2b5a78, observed 2026-09-28 morning China time. Runtime commits move main rapidly: reread before operations; do not treat this observed SHA as permanent.

## Active Branch
- V4 H1: feat/v4-h1-validated-github-handoff-20260928, PR #313. This branch only adds a bounded handoff builder, tests, docs and integration into the existing publisher.
- This cross-task index: chore/dual-lane-task-state-main-sync-20260926, PR #311; no independent recovery cursor changes.
- V4 #309 and research #310 branches are consumed/merged. Original old #306/#307 and old docs #308 are superseded, not targets for replay.

## Active PR
- #313 V4 H1 OPEN: source-validated read-only JSON/Markdown handoff in the existing investor brief; exact-head CI and postmerge genuine production proof still required.
- #311 docs checkpoint OPEN: update cross-lane index from verified GitHub evidence. #312 operating contract MERGED and #310 research coverage MERGED; do not treat them as pending.
- Unrelated older open PRs must not be silently folded into either lane.

## CI
- #312 exact head 531d69ecf716177a18ec38616476cbfac55d4566: backend/docker/governance SUCCESS, web skipped (docs); squash merge verified.
- #310 exact head d74fd2d88f14eb4c561aae631afb4de5b26a596f: backend/docker/governance SUCCESS; merge verified.
- #313 head 79fde649e78698d14b3b60bb98caf42a8d6d6c48: exact-head CI launched including Investor dashboard contract. Inspect completed required checks, reviews, mergeability and branch drift before merge. CI green does not prove current trading session or real output.

## Production / Artifact
- Latest independently reread Investor Decision Brief: data/investor_decision_dashboard/latest.json generated 2026-09-27T22:45:23Z, market as-of 2026-09-24, freshness STALE_UPSTREAM, formal_new_exposure_allowed=false, 0 new Formal buy_now. A new generated timestamp does not change market date. H1 handoff files NOT YET verified on production main.
- Last audited genuinely scheduled All-A run 36154161688 / artifact 10874605479: triggered Sep25 but as-of Sep24; universe 5,222, scanned 4,514, 80 Deep, 0 strict-ready, 77 company-evidence failures, 78 exit-confidence failures and 0 independently validated exit cohorts. Prior audit counted 15 annual company codes and 30 event codes cached-only, union 30/80 touched, 50 untouched; no proven fresh official company document or Sep25 market source.
- Newer independently audited Deep 10907432408 versus 10902085528: 37 stable fingerprint IDs each, 0 net additions; reported per-run evidence counts alone do not prove newly published official issuer material. PR310 coverage instrumentation is merged but needs a next actual All-A production artifact.
- Existing broker quote evidence was dated Sep22; confirmed funds missing, capital is a dated planning floor rather than live broker cash. No currently executable shares can be inferred.

## Completed
- Previously consumed #299-304; V4 P0 #305 MERGED, partial P1 #309 MERGED, owner operating contract #312 MERGED. Independent issuer instrumentation #310 MERGED.
- H1 #313 has actual code/tests/docs on open PR; not merged and not production. Maintain distinct research and V4 recovery sidecars and no overlapping cursor writes.

## Current Findings
- Original investor publisher is running but latest verified report remains market-as-of Sep24. V4 P0 and partial P1 code is read-only; neither live Web/API V4 nor H1 production verified. Opening separate stock site never auto-invokes ChatGPT Web; user prompts ChatGPT Web on demand after automated source data update, without adding GPT API.
- Issuer collection remains bounded: 80 research queue, ~30 fundamental/deep budget and bounded auto evidence. #310 instrumented annual/event attempted/cached/untouched coverage; do not infer provider failure or source novelty without the next real artifact.

## Blockers
- Fresh real market Sep25 Canonical lineage is unproven; Finalizer correctly remains fail-closed. Strict-ready and independent exit-validation evidence gaps persist.
- P1 needs genuinely current user-confirmed funds, broker position/quote timing, independent original corporate event outcomes, authoritative lot/T+1/cash reconciliation before any feasibility display. Merged PR #309 is only a partial, conservative source integration; production feed wiring is still pending.

## Next Action
1. Always reread live main, AGENTS, parent V4/operating docs, both distinct recovery task blobs/generations, exact-head PR/CI and real artifacts. Live GitHub outranks all checkpoint prose.
2. V4 H1: finish PR #313 required exact-head backend/docker/governance AND Investor dashboard contract, review changes/threads and current base, merge only when safe; then verify a real existing Investor Brief publisher run persisted BOTH new handoff files and matching dashboard to main with Canonical ID/checksum, source hashes, honest Sep24-vs-current freshness and genuine artifact IDs. Tests/merge alone are not production acceptance.
3. V4 H2–H5 after H1: user-initiated ChatGPT Web live handoff; existing Web/API V4 deployment with source drilldowns and no new GPT API; separated, independently measured 5/20/60-session recommendation outcomes versus actual broker-realized P&L only with verified fills; real end-to-end proof. Missing positions/funds and old prices must remain labeled.
4. R independent: inspect the next genuine All-A artifact after merged #310 for issuer coverage and independent immutable official source fingerprints, then resolve only proven source/freshness issues. No duplicate dispatch or changed buy thresholds. CAS-update ONLY the R-owned cursor on verified milestones.
5. After real completion persist only the owning task cursor and reconcile root index. Old #306/#307/#308 may be closed as superseded once audit continuity and replacements are confirmed.

## Do Not Repeat
- Do not replay #299–304, old upstream `35886039426`, duplicate Deep `35934671719`/`35955222216`, or already consumed newer industry/Deep/Terminal/Jev/Overlay source IDs. Do not force a new market date from a Sep25 trigger with Sep24 as-of, or assume green workflow = fresh official original documents.
- Do not run project Jev and claim it occurred if only supervisory external classification ran; current recovery chat actually used GitHub tools, project Jev **not used**.


- **Updated evidence checkpoint:** newer actual Deep artifact 10907432408 (run 36245831682) vs consumed 10902085528 has 37 stable (scope,code,original_url,date,content_hash) identities on both sides, 0 additions; 43 per-run evidence records are not independently new originals. Actual scheduled Sep24 All-A artifact 10874605479 has 80 unique queue codes, 15 cached annual issuer extractors, separate 30 cached material-event issuer scans, 30 unique issuer codes touched, 50 with neither collector; 41 noncached industry rows, 0 noncached company rows. Latest Finalizer 36245843960 fails same stale market-date guard.
- PR #309 now additionally rejects unverified original event URLs and unproven approvals with negative tests. PR #310 now distinguishes annual-report audit coverage from material-event collector coverage with a separate regression test; newer exact-head checks are pending and old PR success does not transfer.

## Guardrails
- `formal_trading_authority=false`, `formal_buy_authorized=false`, `automatic_execution_allowed=false`, `no_auto_trade=true`, `UNKNOWN != PASS`; existing genuinely fresh finalized Canonical is the only Formal decision authority.
- Never place brokerage orders, infer missing cash/fund positions, override stale source guards, or interpret Jev advisory/research BUY as automatic Formal BUY.
