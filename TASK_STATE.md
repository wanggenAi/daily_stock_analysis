# Current Mission

## Goal
Make the existing stock system converge into one trustworthy daily decision surface before adding new models. Deep runtime must distinguish actual evidence exhaustion from upstream workset/profile handoff loss without changing valuation, selection thresholds, Candidate Lifecycle, Formal authority, or no-auto-trade.

## Current Phase
Post-#195 production verification and post-#188 continuity proof.

## Last Verified Main
`54b0e52696534cf04b7b5b8066b9db5aa6512092` is the verified merge commit for #195. Live `main` remains authoritative and may advance through persisted-state bot commits.

## Active Branch
None. #195 is merged.

## Active PR
None for this mission. #195 — `fix: separate deep handoff gaps from evidence exhaustion` — is merged.

## CI
- PR #195 blocking CI completed SUCCESS.
- PR #195 focused Three-Pillar Decision Center completed SUCCESS.
- PR #195 Opportunity Discovery fixture validation completed SUCCESS.
- PR #195 Legacy Risk-Capped Research completed SUCCESS.
- Post-merge main CI for `54b0e52696534cf04b7b5b8066b9db5aa6512092` is running; no failure has been observed at this checkpoint.

## Production / Artifact
- Latest persisted terminal Deep run at this checkpoint is `35424878380`, execution SUCCESS.
- It still uses Every-Industry source `35403243897`, which predates #188, so it is not valid post-#188 continuity proof.
- Run `35424878380` requested 850 codes, has 500 profiles, and still contains 351 `REQUESTED_CODE_NOT_PRESENT_IN_DEEP_PROFILE` reasons under the pre-#195 terminal semantics.
- Post-merge Deep run `35427088755` was automatically triggered from #195 merge SHA `54b0e52696534cf04b7b5b8066b9db5aa6512092` and is currently running evidence closure.
- Its persisted initial-pass artifact `genge-v31-deep-initial-35427088755` has been verified: source_run_id=`35403243897` (pre-#188), requested_count=850, processed_requested_count=499, profile_count=500 total, missing_requested_codes=351, unresolved_requested_gate_count=2285. Therefore this run is valid #195 terminal-semantics proof but not valid #188 continuity proof.
- The expected #195 terminal behavior for this old 500-profile upstream artifact is `HANDOFF_INCOMPLETE`, with 351 missing requested profiles separated from evidence-exhausted materialized profiles and excluded from unresolved hard-gate counts.
- No genuine post-#188 production Opportunity Discovery run from `schedule` or `workflow_dispatch` has completed yet. Push/PR Opportunity Discovery runs are fixture validation only and must not be treated as production All-A evidence.

## Completed
- #188 continuity materialization is merged.
- #193 decision-center convergence is merged.
- #194 partial-checkpoint workset observability is merged.
- #195 deep handoff terminal truthfulness is merged as `54b0e52696534cf04b7b5b8066b9db5aa6512092`.
- #195 regression coverage now distinguishes materialized-profile evidence exhaustion from requested codes that never entered a profile.
- #195 terminal status persists requested/profile/processed/missing coverage and excludes profile-handoff reasons from the hard-gate unresolved count.
- Production lineage was traced far enough to prove the recent 850→500 Deep runs still consumed pre-#188 Every-Industry source `35403243897`.

## Current Findings
- `v31_review_queue --limit 500` is an ordinary review budget, not by itself proof that #188 failed. Current #188 code additively materializes retained Deep continuity codes beyond that limit from same-run All-A sources.
- The latest completed production Deep artifacts are stale with respect to #188, so continuity still needs a fresh schedule/workflow_dispatch production-chain proof.
- Before #195, `close_profiles()` incorrectly counted requested codes with no profile as `EVIDENCE_EXHAUSTED` and also inflated `unresolved_requested_gate_count` with the synthetic `profile` reason.
- After #195, missing profiles use terminal state `HANDOFF_INCOMPLETE`; only materialized profiles whose hard gates remain UNKNOWN after bounded recovery count as evidence exhausted.
- Terminal Research continues to map absent profiles to research-only `RESEARCH_GAP / DEEP_PROFILE_MISSING`; no Formal or trading authority expansion was introduced.

## This Branch
Merged. #195 implemented:
1. `HANDOFF_INCOMPLETE` when requested codes are missing from the Deep profile workset.
2. `EVIDENCE_EXHAUSTED` only for materialized profiles whose hard gates remain UNKNOWN after bounded recovery.
3. Terminal `profile_count`, `requested_profile_count`, `processed_requested_count`, `handoff_incomplete_requested_count`, `missing_requested_codes`, and workset coverage flags.
4. Hard-gate unresolved counts that exclude profile-handoff reasons.
5. Separate handoff incompleteness rendering in the Three-Pillar decision center.
6. Completed/idempotent handoff-incomplete semantics that wait for a newer compatible upstream artifact instead of looping the same stale artifact.

## Blockers
- Post-merge Deep run `35427088755` must complete and demonstrate the #195 terminal semantics on live main. Its initial artifact already proves 499 requested profiles / 351 handoff gaps from pre-#188 source `35403243897`.
- A genuine post-#188 production Opportunity Discovery → Every-Industry → Deep chain is still required to validate that retained workset materialization removes the structural 351 missing-profile gap.
- Do not use push/PR fixture artifacts as production proof.

## Next Action
1. Finish verifying post-merge main CI and Deep run `35427088755`.
2. Confirm terminal persistence for the already-verified pre-#188 source `35403243897`: expect `HANDOFF_INCOMPLETE`, requested=850, processed_requested=499, handoff_incomplete=351, hard-gate unresolved count excluding synthetic profile reasons, and evidence-exhausted count limited to materialized unresolved profiles.
3. Verify the first later production `schedule` or `workflow_dispatch` Every-Industry source is post-#188 and includes continuity summary fields.
4. Verify the downstream Deep run against the old baseline: requested 850 / profiles 500 / missing-profile 351.
5. If missing-profile count reaches zero, continue from measured evidence bottlenecks; if not, diagnose remaining same-run source coverage rather than loosening gates.

## Do Not Repeat
- Do not claim #188 failed from Deep runs whose Every-Industry source is `35403243897`; that source predates #188.
- Do not remove the Every-Industry guard that rejects push/PR fixture Opportunity Discovery runs.
- Do not change valuation formulas, BUY/WAIT_PRICE/REJECT thresholds, Candidate Lifecycle semantics, or Formal authority.
- Do not classify `REQUESTED_CODE_NOT_PRESENT_IN_DEEP_PROFILE` as evidence exhaustion.
- Do not manufacture evidence or treat UNKNOWN as PASS.

## Guardrails
- Live GitHub main / PR / Actions / artifacts / persisted data are the source of truth.
- Preserve exact run/profile/source lineage.
- Production artifact evidence is required in addition to unit/CI tests.
- no_auto_trade=true.
