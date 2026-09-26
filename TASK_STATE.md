# Current Mission

## Goal
Maintain two **independent** owner-approved tasks: living V4 investor report and trustworthy official-source research. Each uses its own generation/blob CAS cursor on `state/chatgpt-recovery`; this document is a cross-lane index, not a combined cursor. GitHub live refs, artifacts and code override this checkpoint.

## Current Phase
- **V4:** generation **4** (`recovery/tasks/investor-decision-report-v4.json`; last verified blob `7821a703d4b8202372196835ed14cb8c131ea353`). P0 merged; partial P1 fresh-main replacement PR #309 awaiting exact-head checks; V4 **not yet production verified**.
- **R:** generation **69** (`recovery/tasks/stock-system-convergence.json`; last verified blob `fd7b6d5d5fb760c525176122ceed760a663b4137`). Company-level official evidence coverage instrumentation PR #307 awaits exact-head checks. Canonical market freshness still stale.

## Last Verified Main
- Snapshot at replacement preparation: `4760a3609de3e8b7b02b213c5c91befb7cf2507d`; runtime persisted commits advanced main during this work. **Always reread live main** before writing.

## Active Branch
- V4 P1 replacement #309: `feat/v4-p1-dated-sources-main-sync-20260926` (head `4884b8a7869a71a2a8e74ad6761624ddd1cbcca5`). Old #306 unchanged and open until verified replacement.
- Independent R replacement #310: `fix/research-issuer-audit-main-sync-20260926` (head `aabf3df4d62e3db252b540d6938ec09af636255f`). Old #307 unchanged and open until verified replacement.
- Documentation replacement: `chore/dual-lane-task-state-main-sync-20260926`, old #308 retained open until verified replacement.

## Active PR
- #305 V4 P0: **merged**, squash commit `53641d376cafd08f0197a619250dae729d8699e1`, exact-head CI green.
- #306 V4 P1 **partial**: replacement #309 from main 4760a360 (old #306 preserved open for audit), fresh exact-head checks must pass; do not treat old PR success as replacement success.
- #307 research issuer coverage audit: replacement #310 from main 4760a360 (old #307 preserved open), fresh exact-head checks must pass.
- Docs-only replacement of old #308 from latest main; no cursor changes.

## CI
- PR #305 exact-head all applicable required checks SUCCESS; post-merge push CI `36235084280` was running at earlier check; reverify live.
- Old #306/#307 had successful exact-head CI but 85 commits behind main; replacement #309 head `4884b8a7869a71a2a8e74ad6761624ddd1cbcca5` and replacement #310 head `aabf3df4d62e3db252b540d6938ec09af636255f` require new exact-head CI before merging. Recheck current exact-head checks, reviews and conflicts before merging.
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
- V4 generation4 isolated partial P1 broker/event source mapping at PR306; the two sidecars remain separate.

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

## Guardrails
- `formal_trading_authority=false`, `formal_buy_authorized=false`, `automatic_execution_allowed=false`, `no_auto_trade=true`, `UNKNOWN != PASS`; existing genuinely fresh finalized Canonical is the only Formal decision authority.
- Never place brokerage orders, infer missing cash/fund positions, override stale source guards, or interpret Jev advisory/research BUY as automatic Formal BUY.
