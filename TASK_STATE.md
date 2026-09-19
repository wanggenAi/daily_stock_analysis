# Current Mission

## Goal
Make the existing stock system converge into one trustworthy daily decision surface before adding new models: expose the real A-share market regime, show the newest Deep runtime truth, keep historical/current candidates continuous, and turn evidence gaps into bounded diagnostics instead of an unreadable wall of UNKNOWN reasons.

Do not change valuation formulas, Candidate Lifecycle semantics, BUY/WAIT_PRICE/REJECT thresholds, Formal authority, or no-auto-trade.

## Current Phase
Decision-center state convergence and post-#188 production verification.

## Last Verified Main
`6d43ce93ee4e96df1e8cbea87adddf639cb5d1db` when this branch was created. Live `main` remains authoritative and may advance through persisted-state bot commits.

## Active Branch
`fix/decision-center-state-convergence`.

## Active PR
#193 — `fix: converge decision center on current system truth`.

## CI
- PR #193 runs focused Three-Pillar, Opportunity Discovery, legacy risk-capped, PR Review, and full CI.
- First full-CI attempt exposed this checkpoint document missing the required `## CI` recovery heading; this update restores the repository contract.
- Merge only after focused and blocking checks are green.

## Production / Artifact
- #188 (`fix: preserve deep workset through bounded review handoff`) is merged.
- The latest terminal Deep state on main is still run `35412424204`, head `aaac167ce81102fc8397822f840c7c9f6088f5a0`: SUCCESS / EVIDENCE_EXHAUSTED, requested 850, profiles 500, unresolved gates 2636.
- That run predates the #188 merge, so it is **not** production proof that the 850→500 continuity defect is fixed.
- A newer Deep run `35412428540` persisted `latest_partial_status.json`: PARTIAL / NOT_COMPLETED after the initial checkpoint. The old decision center ignored this newer partial checkpoint and therefore could display the older SUCCESS run as if it were current.
- Current investor dashboard has usable A-share market breadth data (GREEN, advance ratio, MA20/MA60 breadth, limit-up/down counts), but the three-pillar report previously buried it and led with structural trend IDs / industry proxies instead.
- Era Radar has structural trend evidence, but validated trend→A-share handoff queue is currently 0.
- Current decision output has no new Formal BUY and no WAIT_PRICE; holdings all still have incomplete Deep review.

## This Branch
1. Surface the existing A-share market pulse at the top of Pillar 2 without creating new trading authority.
2. Select the newest durable Deep runtime checkpoint across terminal and partial states.
3. Make profile/runtime lineage explicit so an older completed profile cannot masquerade as the current failed/partial run.
4. Collapse unresolved evidence output into bounded reason/gate distributions plus a few examples.
5. Preserve all fail-closed authority rules.

## Blockers
- Post-#188 production Deep verification is still required. Compare requested_count, profile_count, REQUESTED_CODE_NOT_PRESENT_IN_DEEP_PROFILE and continuity coverage against the old 850/500/351 baseline.
- The current evidence-closure path can still end in PARTIAL after the initial checkpoint; after continuity is verified, diagnose the measured top evidence bottlenecks rather than loosening gates.
- The full legacy Daily Market Review capability exists separately from GenGe; this branch exposes the deterministic market pulse first. A later integration should persist/hand off the richer daily market narrative only if it can reuse existing components rather than build a parallel system.

## Next Action
1. Run branch CI and the focused three-pillar tests.
2. Merge only when green.
3. Let the merged decision-center workflow regenerate `LATEST_DECISION_CENTER.md` from live persisted state and verify it shows run `35412428540` as the newest PARTIAL checkpoint while retaining `35412424204` as the last terminal run.
4. Trigger/observe the first post-#188 Deep production run on current main and verify the 850→500 profile-loss defect is actually closed.
5. Continue from the next measured bottleneck: profile continuity first, then official-evidence coverage, then trend→A-share handoff quality.
6. After the main chain is healthy, clean stale PRs and legacy root reports without deleting audit history needed for reproducibility.

## Do Not Repeat
- Do not change valuation, BUY/WAIT_PRICE/REJECT, Candidate Lifecycle, Capital Flow Routing, or Formal authority as part of this convergence work.
- Do not turn retained continuity, Era Radar, market breadth, Near-BUY, or research-only BUY into automatic promotion/trading authority.
- Do not manufacture missing evidence or treat UNKNOWN as PASS.
- Do not judge #188 fixed from unit tests alone; require post-merge production artifact evidence.
- Do not add another parallel “latest dashboard” while `LATEST_DECISION_CENTER.md` can be improved in place.

## Guardrails
- Live GitHub main / PR / Actions / artifacts / persisted data are the source of truth.
- Preserve same-run provenance and explicit freshness/lineage.
- Tests are necessary but production artifact evidence is required.
- no_auto_trade=true.
