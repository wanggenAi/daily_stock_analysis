# Current Mission

## Goal
Turn the stock research system into a convergent autonomous opportunity engine that surfaces reference-worthy stock codes without fabricating certainty or forcing BUY.

## Current Phase
RESEARCH_EXHAUSTION_DORMANCY_IMPLEMENTATION

## Source of Truth
- Live GitHub refs, Actions, artifacts, and persisted data override this checkpoint.
- Production bot persistence may advance main after any recorded SHA.

## Last Verified Main
- PR #288 merged as `3cd5d9040a2e279d973db5466107ff6e00b7ddb3`.
- Post-merge TypeSafe/Jev run `35826965359` succeeded and persisted exact routing lineage.
- Exact-source deterministic Orchestrator `35827144243` succeeded as NOOP with selected=0 / strategy_attempts=0; no redundant Deep dispatch.
- Main later advanced through runtime persistence; always re-read live main before merge/write verification.

## Active Branch
- `feat/research-exhaustion-dormancy-20260923`
- Core implementation commit: `274ed608245efe16f21570825d2739de2fdc7cec`.
- Scope: durable research-exhaustion DORMANT state plus deterministic evidence-epoch reactivation; no threshold or Formal strategy change.

## Active PR
- #289 `feat: converge exhausted research candidates into dormancy`.
- Head before this checkpoint: `adfce73e2fe0a80f6256bb2c5b40a589ae6aa565`.

## CI
- Initial #289 CI `35828339588` failed only in `ai-governance` because this checkpoint omitted the required `## CI` heading; backend/docker were skipped downstream of governance.
- Fix in progress: restore the required heading without changing implementation semantics.
- Jev/Opportunity/legacy research PR workflows were still running at the last observation.

## Production / Artifact
- Fresh Jev `35826965359`: 603105 exact Deep profile PASS on earnings_authenticity / financial_safety / predictability; only long_term_demand / moat remain UNKNOWN.
- Fresh Orchestrator `35827144243`: NOOP / WAIT_FOR_NEW_RESEARCH_STATE; no Deep capacity spent.
- Broad funnel: 4514 valid -> 843 valuation-research -> 500 Deep; 500/500 processed, complete=1, partial=499, unresolved requested hard gates=2291.
- Lifecycle before this branch: active=126 / dormant=0 / archived-invalidated=0.

## Actual TypeSafe/Jev Use
- TypeSafe/Jev live path executed in run `35826965359`.
- Persisted Jev lineage automatically triggered deterministic Orchestrator `35827144243`.
- Jev stayed advisory-only; deterministic ledger owned retry eligibility; Formal trading authority remained false.

## Completed
- #288 production verification: exact Deep PASS gates are authoritative over stale retry hints.
- TypeSafe/Jev `35826965359` -> deterministic Orchestrator `35827144243` completed without redundant Deep dispatch.
- #289 core dormancy implementation and focused contract tests are committed; first focused Orchestrator contract run passed.

## Current Findings
- #288 is production-verified: exact Deep PASS gates no longer reopen from stale routing missing-evidence text.
- Dominant funnel loss remains evidence closure, not broad recall/workset coverage.
- Existing lifecycle has no autonomous research-exhaustion state, so exhausted non-holdings can remain ACTIVE indefinitely.
- DORMANT must remain distinct from business-quality REJECT/INVALIDATED and must never apply to current holdings.

## In Progress
- Exact current-epoch exhaustion proof requires EXHAUSTED_NO_PROGRESS for every supported unresolved gate.
- DORMANT -> ACTIVE occurs only on a new schedulable evidence epoch, terminal research progress, or holding protection.
- DORMANT removes stale lifecycle-tier priority boost without filtering Broad Discovery.
- Jev orchestrator will persist lifecycle transitions through optimistic replay from latest main.

## Blockers
- No user/login/approval blocker.
- #289 blocking CI must be green before merge; current governance-only failure is being corrected.

## Next Action
1. Run branch PR CI/tests and resolve any contract regression.
2. Merge only after blocking CI is green.
3. Verify fresh Jev -> Orchestrator -> lifecycle reconciliation on production main.
4. Confirm holdings never dorm; confirm eligible exhausted non-holdings leave ACTIVE, or record truthful NO_CHANGE if none meet the exact exhaustion proof.
5. Continue funnel audit/Runbei tracing only after lifecycle convergence evidence is persisted.

## Do Not Repeat
- Do not reopen #268/#269/#270/#271/#283/#286/#287/#288 without a newly proven regression.
- Do not lower thresholds to force BUY/WAIT_PRICE.
- Do not label missing evidence as FAIL.
- Do not return to consumed old branches.

## Guardrails
- Jev is advisory research routing only; deterministic guards own dispatch.
- Formal actions remain Canonical-only; automatic Formal BUY=false.
- UNKNOWN != PASS; no_auto_trade=true.
- Missing evidence is not business-quality FAIL.
- Exact Deep PASS/FAIL cannot be reopened by stale routing text.
- Exhausted non-holdings may dorm only with exact current-epoch ledger proof; holdings must never silently leave ACTIVE.
