# Current Mission

## Goal
Maintain two **independent** owner-approved tasks: living V4 investor report and trustworthy official-source research. Each uses its own generation/blob CAS cursor on `state/chatgpt-recovery`; this document is a cross-lane index, not a combined cursor. GitHub live refs, artifacts and code override this checkpoint.

## Current Phase
- **V4:** generation **7** (`recovery/tasks/investor-decision-report-v4.json`; last verified blob `cf9378858fc958823a09e2c81bb4609f30c9ab57`). P0 merged; partial P1 PR #309 squash-merged as 6dddf93fb299303da7bfb2748d2d0b19aad98f21; post-merge CI pending; V4 **not yet production verified**.
- **R:** generation **72** (`recovery/tasks/stock-system-convergence.json`; last verified blob `08e7b3a99e33b1b7e1f6df9e4133e30ed06e0dc4`). Research-only issuer coverage PR #310 safely merged main into feature branch without force-push; new exact-head CI pending. Canonical market freshness still stale.

## Last Verified Main
- Post V4 #309 merge: `6dddf93fb299303da7bfb2748d2d0b19aad98f21`; runtime persisted commits advanced main during this work. **Always reread live main** before writing.

## Active Branch
- V4 P1 PR #309 merged: head `3c2d76939830e72384de3eb67c3aef2a49b3b98a`, main squash `6dddf93fb299303da7bfb2748d2d0b19aad98f21`; old #306 still open for traceability pending close.
- Independent R replacement #310: `fix/research-issuer-audit-main-sync-20260926` (head `d74fd2d88f14eb4c561aae631afb4de5b26a596f`). Old #307 unchanged and open until verified replacement.
- Documentation replacement: `chore/dual-lane-task-state-main-sync-20260926`, old #308 retained open until verified replacement.

## Active PR
- #305 V4 P0: **merged**, squash commit `53641d376cafd08f0197a619250dae729d8699e1`, exact-head CI green.
- #309 V4 P1 **partial**: merged into main at 6dddf93f with new exact-head checks SUCCESS and reviewed source guardrails; post-merge main CI pending; original #306 is superseded.
- #310 research issuer coverage audit: safe nonforce two-parent merge of main 6dddf93f and original PR #310 head resolved shared CHANGELOG; new head d74fd2d88f requires new exact-head CI, old #307 remains open.
- Docs-only replacement of old #308 from latest main; no cursor changes.

## CI
- PR #305 exact-head all applicable required checks SUCCESS; post-merge push CI `36235084280` was running at earlier check; reverify live.
- Old #306/#307 had successful exact-head CI but 85 commits behind main; merged #309 head `3c2d76939830e72384de3eb67c3aef2a49b3b98a` and research #310 new head `d74fd2d88f14eb4c561aae631afb4de5b26a596f` research #310 requires new exact-head CI before merge. #309 already merged; verify postmerge push CI.
- Do not treat a skipped downstream job or successful research workflow as fresh Canonical authorization.

## Production / Artifact
- P0 implementation **code merged only**; not wired into actual Web/API and no live V4 production acceptance.
- Latest verified genuine scheduled All-A run `36154161688`, artifact `10874605479`, triggered Sep25 but real market **as-of Sep24**: official universe 5,222, scanned 4,514, 80 Deep reviewed, 0 strict-ready, 77 company-evidence failures, 78 exit-confidence failures, 0 independently validated exit cohorts.
- Compared Sep23 artifact `10784936699` to Sep24: 41 noncached INDUSTRY-only attempts, zero confirmed fresh official issuer fetch; differing old archive records do not establish independently new Sep25 publications.
- Subsequent Deep `36228219860` SUCCESS artifact `10902085528` (18 processed/0 complete); its Finalizer `36228226920` FAILURE. Older Jev `36221808179` SUCCESS artifact `10899446912` (25 actual project advisory calls) and Overlay `36221815168` SUCCESS artifact `10899526494` were consumed once.
- Persisted decision-center market date last verified Sep24 (generated Sep26 09:56Z), 4 confirmed holdings, 0 new Formal BUY; Sep22 broker quote is historical only; no sufficiently current confirmed funds.

## Completed
- Consumed PR #299–304 and their previously dispatched same-epoch research; P0 #305 code merged.
- R generation68 independently compared real Sep23 vs Sep24 All-A artifacts and consumed older Jev/Overlay; R generation72 independently resolved PR310 conflict after #309 merge, using nonforce two-parent merge commit; new CI pending.
- V4 generation7 merged hardened P1 issuer-original source/proposal outcome guardrails on replacement PR309; the two sidecars remain separate.

## Current Findings
- Production configuration: All-A research queue 80 vs separate `--fundamental-limit 30`, `--deep-review-size 30`, bounded `auto_evidence_limit <= 50`. An 80-name queue does NOT prove 80 real company fetches. Issuer collector has deterministic per-report-period cache with 6h FAILED and 24h MISSING retry TTL. PR307 exposes real issuer attempted, cache-only and unattempted counts; do not call a provider bug proven without artifact data.
- V4 P1 currently remains **read-only** and gives zero executable orders even with historical or same-session display quotes. It distinguishes consumed authority and proposal vs approved corporate outcome.

## Blockers
- Fresh real market Sep25 Canonical lineage is unproven; Finalizer correctly remains fail-closed. Strict-ready and independent exit-validation evidence gaps persist.
- P1 needs genuinely current user-confirmed funds, broker position/quote timing, independent original corporate event outcomes, authoritative lot/T+1/cash reconciliation before any feasibility display. Current PR306 is only a partial, conservative source integration.

## Next Action
1. At resume re-read current main, `AGENTS.md`, V4 plan, two **separate** recovery cursors/generations/blob SHAs, active PRs, CI, runs/artifacts and persisted Canonical.
2. **V4 ONLY:** verify merged #309 postmerge main CI, keep source integration read-only; CAS-update only V4 cursor. Continue P1 live confirmed inputs/lot/T+1/cash/event wiring, then P2-P5 with production proof.
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
