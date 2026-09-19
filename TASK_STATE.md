# Current Mission

## Goal
Make the existing stock system converge into one trustworthy daily decision surface before adding new models. Deep runtime must distinguish actual evidence exhaustion from upstream workset/profile handoff loss without changing valuation, selection thresholds, Candidate Lifecycle, Formal authority, or no-auto-trade.

## Current Phase
Deep terminal truthfulness and post-#188 production continuity verification.

## Last Verified Main
`0fd28170a2c76bfb7378a8771785e07480782a6b` when branch `fix/deep-handoff-terminal-truth` was created. Live `main` remains authoritative and may advance through persisted-state bot commits.

## Active Branch
`fix/deep-handoff-terminal-truth`.

## Active PR
#195 — `fix: separate deep handoff gaps from evidence exhaustion`.

## CI
- PR #194 is merged as `b2f4f4e58f3db83cbb2ec7cb74b9e75a27aac26b`; its blocking CI was green.
- PR #195 adds regression coverage for missing-profile handoff semantics plus the Deep workflow terminal-state contract.
- Merge #195 only after focused Deep/Three-Pillar checks and blocking CI are green.

## Production / Artifact
- Latest persisted terminal Deep run is `35422187150`, execution SUCCESS.
- It requested 850 codes, persisted 500 total profiles, and reports 351 requested codes as `REQUESTED_CODE_NOT_PRESENT_IN_DEEP_PROFILE`.
- That Deep run used Every-Industry source `35403243897`, created 2026-09-18T22:50:01Z, before #188 merged at 2026-09-19T01:37:38Z.
- Therefore run `35422187150` is not valid post-#188 proof of the continuity materialization fix.
- No post-#188 production Opportunity Discovery run from `schedule` or `workflow_dispatch` has completed yet. Push/PR Opportunity Discovery runs are fixture validation only and must not be treated as production All-A evidence.

## Completed
- #188 continuity materialization is merged.
- #193 decision-center convergence is merged.
- #194 partial-checkpoint workset observability is merged.
- Production lineage was traced far enough to prove the latest 850→500 result consumed a pre-#188 Every-Industry artifact.
- PR #195 now separates missing-profile handoff gaps from genuine evidence exhaustion in terminal status and the decision center.

## Current Findings
- `v31_review_queue --limit 500` is an ordinary review budget, not by itself the post-#188 defect: current #188 code additively materializes retained Deep continuity codes beyond that limit from same-run All-A sources.
- The latest production Deep artifact is stale with respect to that fix, so continuity still needs a fresh production-chain proof.
- Independent correctness bug: `close_profiles()` previously appended missing profiles to `exhausted_codes`, causing 351 codes that never entered a profile to be reported as evidence exhausted.
- The same bug inflated `unresolved_requested_gate_count` by counting `profile` handoff reasons as hard gates.
- Terminal Research already maps absent profiles to research-only `RESEARCH_GAP / DEEP_PROFILE_MISSING`; no Formal or trading authority expansion is needed.

## This Branch
1. Add terminal state `HANDOFF_INCOMPLETE` when requested codes are missing from the Deep profile workset.
2. Keep `EVIDENCE_EXHAUSTED` only for materialized profiles whose hard gates remain UNKNOWN after bounded recovery.
3. Persist `profile_count`, `requested_profile_count`, `processed_requested_count`, `handoff_incomplete_requested_count`, `missing_requested_codes`, and workset coverage flags in terminal status.
4. Exclude profile-handoff reasons from the unresolved hard-gate count.
5. Render handoff incompleteness separately in the Three-Pillar decision center.
6. Preserve idempotence: HANDOFF_INCOMPLETE is a completed run state that waits for newer compatible upstream work rather than looping the same stale artifact.

## Blockers
- PR #195 CI must pass.
- A genuine post-#188 production Opportunity Discovery → Every-Industry → Deep chain is still required to validate that retained workset materialization removes the structural 351 missing-profile gap.
- Do not use push/PR fixture artifacts as production proof.

## Next Action
1. Observe/fix PR #195 CI until all blocking checks are green.
2. Merge #195 and verify live main.
3. Verify the first later production `schedule` or `workflow_dispatch` Every-Industry source is post-#188 and includes continuity summary fields.
4. Verify the downstream Deep run reports truthful requested/profile/processed/handoff counts.
5. If missing-profile count reaches zero, continue from the measured evidence bottlenecks; if not, diagnose the remaining same-run source coverage rather than loosening gates.

## Do Not Repeat
- Do not claim #188 failed from Deep run `35422187150`; its Every-Industry source predates #188.
- Do not remove the Every-Industry guard that rejects push/PR fixture Opportunity Discovery runs.
- Do not change valuation formulas, BUY/WAIT_PRICE/REJECT thresholds, Candidate Lifecycle semantics, or Formal authority.
- Do not classify `REQUESTED_CODE_NOT_PRESENT_IN_DEEP_PROFILE` as evidence exhaustion.
- Do not manufacture evidence or treat UNKNOWN as PASS.

## Guardrails
- Live GitHub main / PR / Actions / artifacts / persisted data are the source of truth.
- Preserve exact run/profile/source lineage.
- Production artifact evidence is required in addition to unit/CI tests.
- no_auto_trade=true.
