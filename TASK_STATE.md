# Current Mission

## Goal
Turn the stock research system into a convergent autonomous opportunity engine that surfaces reference-worthy stock codes without fabricating certainty or forcing BUY.

Solve together:
1. Autonomous research closure for active non-holding RESEARCH_GAP candidates: keep trying genuinely novel credible paths until progression, hard-gate FAIL, or deterministic exhaustion.
2. Candidate-funnel health: explain why broad All-A research has a large queue but no Terminal BUY/WAIT_PRICE before changing thresholds.

## Current Phase
AUTONOMOUS_RESEARCH_CLOSURE_AND_CANDIDATE_FUNNEL_AUDIT

## Last Verified Main
- Live GitHub remains the source of truth; runtime persistence may advance main after this checkpoint.
- PR #271 merged: restored TASK_STATE governance compliance.
- PR #272 merged: Jev shadow now consumes the live Research Priority queue after holdings.
- PR #273 merged: deterministic safe evidence refresh can continue for ruleable INSUFFICIENT P0/P1/P2/urgent/holding rows even below Jev confidence 0.50.
- PR #274 was superseded and closed without merge.
- PR #275 merged as `3162e8ae58df72364a063eef01d750d2f8cda67d`: durable gate-local evidence-epoch research strategy ledger.

## Active Branch
- `feat/jev-autonomous-continuation-20260922`
- Purpose: close the missing Deep -> downstream convergence -> fresh Jev reevaluation loop without changing research/trading thresholds.

## Active PR
- #276 `feat: continue Jev research after downstream convergence`.
- Re-read latest PR head/base/checks before merge; runtime bot commits can advance main independently.

## CI
- #276 must pass latest-head workflow/YAML/pytest/governance checks before merge.
- Do not infer green from prior PRs.

## Production / Artifact
- Jev source run `35705667064` succeeded and persisted 25 actionable routing rows.
- Deterministic orchestrator selected 12 bounded research codes and accepted 54 code × hard-gate strategy attempts.
- Accepted Deep run `35706039574` completed SUCCESS; Terminal for the same Deep lineage also completed SUCCESS.
- The 54 accepted ledger entries require a later Jev state that observes Deep 35706039574 before they can settle as resolved / evidence-changed / exhausted.
- Latest observed Research Priority queue remains 157 rows; P0 holdings include 001316, 601318, 603993, 600406.
- Candidate lifecycle remains broad-discovery-independent and still lacks research-exhaustion dormancy.
- Latest confirmed full All-A artifact for funnel audit remains Opportunity Discovery run `35626246535`, artifact id `10653595235`.

## Completed
- Recovery was reconciled against live GitHub rather than restarted from chat context.
- #271, #272, #273, and clean replay #275 were verified merged; superseded #274 was not reused.
- TypeSafe/Jev is live as typed shadow classification/routing; deterministic code owns eligibility and bounded Deep dispatch.
- #275 prevents the same supported code × hard-gate strategy from repeating in an unchanged gate-local evidence epoch.
- Exact accepted Deep lineage 35706039574 completed successfully and downstream Terminal handoff succeeded.

## Current Findings
- The ledger can reconcile an accepted attempt only when a fresh Jev evaluation sees the exact completed Deep run.
- Existing downstream convergence did not automatically schedule that fresh Jev evaluation, so autonomous research could stop after one accepted Deep cycle.
- #276 adds a Deep-run-id-keyed, deduplicated Jev reevaluation after exact Terminal + Investor Overlay + Three-Pillar convergence.
- That continuation still enters through Jev advisory routing; the reconciler never directly relaunches Deep.
- The orchestrator skips `NO_NOVEL_RESEARCH_STRATEGY_IN_EVIDENCE_EPOCH` rows and continues considering later priority rows.
- Durable dormant/excluded lifecycle semantics for exhausted non-holdings are still missing.
- Full All-A stage-by-stage attrition counts are still not computed.
- These are research diagnostics, not investment recommendations.

## Blockers
- #276 latest-head CI and mergeability are not yet final.
- Production proof is required after #276 merge: exactly one lineage-keyed Jev reevaluation must appear after Deep 35706039574 downstream convergence.
- Exhausted non-holdings still remain ACTIVE because DORMANT semantics are not implemented.
- Full funnel attrition from run 35626246535 still needs audit.

## Next Action
1. Finish #276: CI -> merge -> verify one deduplicated Jev continuation and ledger reconciliation on production lineage.
2. Use the reconciled ledger to define deterministic per-code research exhaustion.
3. Add DORMANT lifecycle semantics for exhausted non-holdings; holdings stay active, and changed gate-local evidence deterministically reactivates research.
4. Ensure DORMANT non-holdings do not consume the bounded Jev priority window while broad Discovery remains ledger-independent.
5. Surface attempts, evidence gain, exhaustion/reactivation reason, and shortlist state in Investor/Three-Pillar outputs.
6. Audit run 35626246535 stage-by-stage: universe -> quant -> recall -> valuation -> priority -> Deep -> Terminal.
7. Trace Runbei plus multiple P1/near-buy codes before considering any threshold change.

## Do Not Repeat
- Do not redo #268-#273 or #275.
- Do not reopen superseded #274.
- Do not dispatch duplicate Deep/Jev work when persisted lineage proves it already happened.
- Do not lower hard gates, valuation thresholds, or confidence rules merely to force BUY/WAIT_PRICE.
- Do not treat missing evidence as a business-quality FAIL.

## Guardrails
- Live GitHub refs/Actions/artifacts/persisted data > TASK_STATE > chat history.
- Jev is advisory research routing only; deterministic guards own dispatch eligibility.
- Formal actions remain Canonical-only; automatic Formal BUY=false.
- UNKNOWN != PASS and `no_auto_trade=true`.
- Exhausted non-holdings must eventually leave ACTIVE; holdings must never be silently dropped.
