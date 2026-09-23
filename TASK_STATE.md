# Current Mission

## Goal
Turn the stock research system into a convergent autonomous opportunity engine that surfaces reference-worthy stock codes without fabricating certainty or forcing BUY.

## Current Phase
JEV_RESEARCH_PRIORITY_WAKE_HANDOFF

## Source of Truth
- Live GitHub refs, Actions, artifacts, and persisted data override this checkpoint.
- Production bot persistence may advance main after any recorded SHA.

## Last Verified Main
- PR #291 merged as `340dc244a8ea8c5ce75fcd6485e7b824238bf894`.
- Research Learning production run `35842953818` succeeded and persisted the Deep-qualified priority layer.
- Working branch was created from live main `021f76dad25264ecf7d17f234ba82016ae4be6ec`; re-read live main before merge and production verification.

## Active Branch
- `fix/jev-wake-on-research-priority-20260923`
- Scope: make persisted Research Learning priority changes wake the existing TypeSafe/Jev production route; no threshold or authority change.

## Active PR
- Pending creation from the active branch.

## CI
- Branch contract adds a regression test that requires `GenGe Jev Shadow Evaluation` main-push paths to include `data/research_priority/**`.
- PR blocking CI and same-repository Jev smoke must pass before merge.

## Production / Artifact
- Candidate lifecycle: ACTIVE=123, DORMANT=3, ARCHIVED/INVALIDATED=0.
- Canonical snapshot remains Formal-authoritative; automatic Formal BUY=false.
- Research Learning run `35842953818` places 603596 伯特利 at P1 with exact-current Deep 5/5 PASS lineage `35831920970`.
- 603596 has no Formal BUY/WAIT_PRICE; valuation/price/authority closure remains incomplete.
- Three-Pillar Decision Center already exposes 603596 only as a research-qualified lead with current account action 暂不买.
- Latest persisted Jev advisory still predates PR #291 and therefore has not consumed the new 603596 P1 state.

## Actual TypeSafe/Jev Use
- Persisted Jev path uses pinned `typesafe-sdk==0.7.0`, requested model `jev-latest`, and last observed served model `jev-1.13.0`.
- Existing combined selection is holdings -> persisted research-priority queue -> remaining Deep unresolved continuity; 603596 is inside the bounded 25-entity window after the P1 promotion.
- Root cause of the missing fresh cycle is wake-up wiring, not Jev selection order: the Jev workflow did not listen to `data/research_priority/**` main pushes.
- Jev remains advisory-only; deterministic guards own dispatch; Formal trading authority remains false.

## Completed
- #289 research-exhaustion dormancy merged and production-verified.
- #290 lifecycle visibility merged and production-verified.
- #291 Deep-qualified research visibility merged and production-verified through Research Learning and Three-Pillar output.
- 603596 is now visible as the sole nonholding current-runtime 5/5 PASS research lead and is P1 in the persisted priority queue.
- Missing automatic wake handoff from Research Learning persistence to Jev was isolated to the Jev workflow push-path contract.

## Current Findings
- Broad discovery recall is not the current blocker and thresholds must not be lowered.
- Jev selection already consumes the persisted priority queue in its existing order.
- The missing `data/research_priority/**` push path prevents a new priority-only production state from waking Jev.
- A fresh TypeSafe/Jev cycle is still required to record how 603596 is routed after its P1 promotion.

## In Progress
- Add `data/research_priority/**` to the Jev main-push wake contract.
- Add a workflow regression test and document the handoff.
- Open PR, require green CI, merge, then verify the resulting 25-entity production Jev run and exact deterministic Orchestrator lineage.

## Blockers
- No user/login/approval blocker.
- Merge is blocked only by the new PR's required CI.

## Next Action
1. Open the wake-handoff PR and verify its newest-head CI.
2. Merge only when blocking CI is green.
3. Verify the merge-triggered 25-entity TypeSafe/Jev production run contains 603596 and record its typed route, evidence state, attention priority, served model and lineage.
4. Verify the deterministic Orchestrator consumes that exact Jev lineage and reaches either a supported research dispatch or a truthful NOOP/HUMAN_REVIEW terminal state.
5. Re-read Three-Pillar output and confirm 603596 remains RESEARCH_ONLY / 暂不买 unless independent Canonical Formal authority has actually changed.
6. Persist the final production checkpoint; continue valuation/price closure only if a supported evidence/model path exists.

## Do Not Repeat
- Do not reopen consumed old branches or PRs without a newly proven regression.
- Do not lower thresholds to force BUY/WAIT_PRICE.
- Do not label missing evidence as FAIL.
- Do not treat a research-qualified lead as a trading recommendation or Formal action.
- Do not rerun old Jev lineage and call it fresh production verification.

## Guardrails
- Jev is advisory research routing only; deterministic guards own dispatch.
- Formal actions remain Canonical-only; automatic Formal BUY=false.
- UNKNOWN != PASS; no_auto_trade=true.
- Missing evidence is not business-quality FAIL.
- Exact Deep PASS/FAIL cannot be reopened by stale routing text.
- Deep-qualified priority is research-order only and requires exact current successful runtime lineage.
- Exhausted non-holdings may dorm only with exact current-epoch ledger proof; holdings must never silently leave ACTIVE.
