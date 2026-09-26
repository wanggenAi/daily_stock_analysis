# Current Mission

## Goal
Maintain two **independent** owner-approved tasks: living V4 investor report and trustworthy official-source research. Each uses its own generation/blob CAS cursor on `state/chatgpt-recovery`; this document is a cross-lane index, not a combined cursor. GitHub live refs, artifacts and code override this checkpoint.

## Current Phase
- **V4:** generation **6** (`recovery/tasks/investor-decision-report-v4.json`; last verified blob `f14f78d1d96a3b224d6e5c1daf807ca53ee730ed`). P0 merged; partial P1 fresh-main replacement PR #309 awaiting exact-head checks; V4 **not yet production verified**.
- **R:** generation **71** (`recovery/tasks/stock-system-convergence.json`; last verified blob `3851726de1326d45bbf7861bf2593d5c2d48b1e9`). Company-level official evidence coverage instrumentation PR #307 awaits exact-head checks. Canonical market freshness still stale.

## Last Verified Main
- Snapshot at replacement preparation: `4760a3609de3e8b7b02b213c5c91befb7cf2507d`; runtime persisted commits advanced main during this work. **Always reread live main** before writing.

## Active Branch
- V4 P1 replacement #309: `feat/v4-p1-dated-sources-main-sync-20260926` (head `3c2d76939830e72384de3eb67c3aef2a49b3b98a`). Old #306 unchanged and open until verified replacement.
- Independent R replacement #310: `fix/research-issuer-audit-main-sync-20260926` (head `350a073d098cabea7ff3336a4c385bd9850e059c`). Old #307 unchanged and open until verified replacement.
- Documentation replacement: `chore/dual-lane-task-state-main-sync-20260926`, old #308 retained open until verified replacement.

## Active PR
- #305 V4 P0: **merged**, squash commit `53641d376cafd08f0197a619250dae729d8699e1`, exact-head CI green.
- #306 V4 P1 **partial**: replacement #309 from main 4760a360 (old #306 preserved), with negative tests requiring independently verified official originals and approval documents; latest head as recorded above needs fresh exact-head CI.
- #307 research issuer coverage audit: replacement #310 from main 4760a360 (old #307 preserved), now distinguishes 15 annual vs 30 material-event cached scans in real Sep24 sample; latest head needs fresh exact-head CI.
- Docs-only replacement of old #308 from latest main; no cursor changes.

## CI
- PR #305 exact-head all applicable required checks SUCCESS; post-merge push CI `36235084280` was running at earlier check; reverify live.
- Old #306/#307 had successful exact-head CI but 85 commits behind main; replacement #309 head `3c2d76939830e72384de3eb67c3aef2a49b3b98a` and replacement #310 head `350a073d098cabea7ff3336a4c385bd9850e059c` require new exact-head CI before merging. Recheck current exact-head checks, reviews and conflicts before merging.
- Do not treat a skipped downstream job or successful research workflow as fresh Canonical authorization.

## Production / Artifact
- P0 implementation **code merged only**; not wired into actual Web/API and no live V4 production acceptance.
- Latest verified genuine scheduled All-A run `36154161688`, artifact `10874605479`, triggered Sep25 but real market **as-of Sep24**: official universe 5,222, scanned 4,514, 80 Deep reviewed, 0 strict-ready, 77 company-evidence failures, 78 exit-confidence failures, 0 independently validated exit cohorts.
- Compared Sep23 artifact `10784936699` to Sep24: 41 noncached INDUSTRY-only attempts, zero confirmed fresh official issuer fetch; differing old archive records do not establish independently new Sep25 publications.
- Subsequent Deep `36228219860` SUCCESS artifact `10902085528` (18 processed/0 complete); its Finalizer `36228226920` FAILURE. Older Jev `36221808179` SUCCESS artifact `10899446912` (25 actual project advisory calls) and Overlay `36221815168` SUCCESS artifact `10899526494` were consumed once.
- Persisted decision-center market date last verified Sep24 (generated Sep26 09:56Z), 4 confirmed holdings, 0 new Formal BUY; Sep22 broker quote is historical only; no sufficiently current confirmed funds.

## Completed
- Consumed PR #299–304 and their previously dispatched same-epoch research; P0 #305 code merged.
- R generation68 independently compared real Sep23 vs Sep24 All-A artifacts and consumed older Jev/Overlay; R generation69 isolated coverage code at PR307.
- V4 generation6 hardened P1 issuer-original source/proposal outcome guardrails on replacement PR309; the two sidecars remain separate.

## Current Findings
- Production configuration: All-A research queue 80 vs separate `--fundamental-limit 30`, `--deep-review-size 30`, bounded `auto_evidence_limit <= 50`. An 80-name queue does NOT prove 80 real company fetches. Issuer collector has deterministic per-report-period cache with 6h FAILED and 24h MISSING retry TTL. PR307 exposes real issuer attempted, cache-only and unattempted counts; do not call a provider bug proven without artifact data.
- V4 P1 currently remains **read-only** and gives zero executable orders even with historical or same-session display quotes. It distinguishes consumed authority and proposal vs approved corporate outcome.

## Blockers
- Fresh real market Sep25 Canonical lineage is unproven; Finalizer correctly remains fail-closed. Strict-ready and independent exit-validation evidence gaps persist.
- P1 needs genuinely current user-confirmed funds, broker position/quote timing, independent original corporate event outcomes, authoritative lot/T+1/cash reconciliation before any feasibility display. Current PR306 is only a partial, conservative source integration.

## Next Action
1. At resume re-read current main, `AGENTS.md`, V4 plan, two **separate** recovery cursors/generations/blob SHAs, active PRs, CI, runs/artifacts and persisted Canonical.
2. **V4 ONLY:** verify replacement #309 exact head and required checks/reviews/mergeability; merge if genuinely green/authorized and verify postmerge main; CAS-update only `investor-decision-report-v4.json`. Continue P1 full current-source/lot/T+1/cash/event wiring, then P2–P5 with actual production proof.
3. **R ONLY:** verify replacement #310 exact head and required checks; if genuinely green, merge audit-only code and inspect NEXT real All-A production artifact with actual issuer coverage counts and source publication/fingerprint lineage. CAS-update only `stock-system-convergence.json`. Do not blindly rerun consumed Deep/Terminal.
4. After any stable milestone, update this compact summary without overwriting contemporary runtime data or task-scoped volatile cursors. A merged P1 source increment is NOT full V4 production.

## Do Not Repeat
- Do not replay #299–304, old upstream `35886039426`, duplicate Deep `35934671719`/`35955222216`, or already consumed newer industry/Deep/Terminal/Jev/Overlay source IDs. Do not force a new market date from a Sep25 trigger with Sep24 as-of, or assume green workflow = fresh official original documents.
- Do not run project Jev and claim it occurred if only supervisory external classification ran; current recovery chat actually used GitHub tools, project Jev **not used**.


- **Updated evidence checkpoint:** newer actual Deep artifact 10907432408 (run 36245831682) vs consumed 10902085528 has 37 stable (scope,code,original_url,date,content_hash) identities on both sides, 0 additions; 43 per-run evidence records are not independently new originals. Actual scheduled Sep24 All-A artifact 10874605479 has 80 unique queue codes, 15 cached annual issuer extractors, separate 30 cached material-event issuer scans, 30 unique issuer codes touched, 50 with neither collector; 41 noncached industry rows, 0 noncached company rows. Latest Finalizer 36245843960 fails same stale market-date guard.
- PR #309 now additionally rejects unverified original event URLs and unproven approvals with negative tests. PR #310 now distinguishes annual-report audit coverage from material-event collector coverage with a separate regression test; newer exact-head checks are pending and old PR success does not transfer.

## Guardrails
- `formal_trading_authority=false`, `formal_buy_authorized=false`, `automatic_execution_allowed=false`, `no_auto_trade=true`, `UNKNOWN != PASS`; existing genuinely fresh finalized Canonical is the only Formal decision authority.
- Never place brokerage orders, infer missing cash/fund positions, override stale source guards, or interpret Jev advisory/research BUY as automatic Formal BUY.
