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
- Main verified immediately before this checkpoint: `c170e828bb9a6ea5fb7a1995817f2ca1a9ad2e5b`.
- #271, #272, #273, and #275 are merged; #274 was superseded and closed.
- #276 contains the first autonomous-continuation implementation but diverged while production workflows advanced main; do not merge it.
- #277 is the clean replay of #276 static logic/tests/docs onto live main.

## Active Branch
- `feat/jev-autonomous-continuation-main-replay-20260922`
- Purpose: close Deep -> downstream convergence -> fresh Jev reevaluation without replaying stale production state.

## Active PR
- #277 `feat: replay autonomous Jev continuation on latest main`.
- #276 is superseded by #277 and must not be reused after closure.

## CI
- #277 latest-head checks must pass before merge.
- Re-read live head/checks/mergeability after every checkpoint; do not infer green from #276.

## Production / Artifact
- Jev source run `35705667064` succeeded with 25 typed advisory rows.
- Deterministic orchestrator run `35705893035` selected 12 bounded research codes.
- Accepted Deep run `35706039574` completed SUCCESS and converged through Terminal, Investor Overlay, and Three-Pillar.
- Current orchestration marker is `DECISION_CENTER_REFRESHED`, `next_expected_stage=COMPLETE`; this proves pre-#277 main still stops before a fresh Jev continuation.
- Research strategy ledger has 54 entries, all `DISPATCH_ACCEPTED`; exhausted=0, new-evidence=0, gate-changed=0.
- Current persisted Jev state is still run `35705667064` and observes old Deep `35700709571`, not accepted Deep `35706039574`.
- Research Priority remains broad (157 rows in latest verified queue); P0 holdings include 001316, 601318, 603993, 600406.
- Latest confirmed full All-A artifact for funnel audit remains Opportunity Discovery run `35626246535`, artifact id `10653595235`.

## Completed
- Recovered from the interrupted chat using live GitHub state rather than restarting completed work.
- Verified #275 ledger persistence is live on main.
- Proved the autonomous-loop gap remains real from persisted production data.
- Rejected direct merge of stale/diverged #276.
- Created clean replay branch from live main and replayed only #276 static workflow/test/docs changes.
- Opened #277 against live main.

## Current Findings
- TypeSafe/Jev is live as typed advisory classification/routing; deterministic code owns eligibility and bounded Deep dispatch.
- The ledger cannot settle the 54 accepted attempts until a later Jev state observes exact Deep `35706039574`.
- #277 schedules one Deep-run-id-keyed Jev reevaluation only after exact downstream convergence and deduplicates repeated reconciler wakeups.
- Jev continuation still returns through normal advisory routing; reconciler never directly relaunches Deep.
- Durable research-exhaustion -> DORMANT semantics for non-holdings are still missing.
- DORMANT non-holdings must eventually stop consuming the bounded Jev priority window; holdings must stay active.
- Full All-A stage-by-stage attrition counts are still not computed.
- These are research diagnostics, not investment recommendations.

## Blockers
- #277 latest-head CI and mergeability are not yet final.
- Production proof is required after #277 merge: exactly one Jev workflow-dispatch titled for Deep `35706039574` must run on main.
- The resulting Jev state must observe Deep `35706039574` and reconcile the 54 accepted ledger attempts before the loop is considered closed.
- Exhausted non-holdings still remain ACTIVE because DORMANT lifecycle semantics are not implemented.

## Next Action
1. Finish #277: latest-head CI -> merge -> live-main verification.
2. Verify one lineage-keyed Jev continuation for Deep `35706039574` and strategy-ledger reconciliation.
3. Define deterministic per-code research exhaustion from the reconciled ledger.
4. Add DORMANT lifecycle semantics for exhausted non-holdings; holdings stay active and changed gate-local evidence reactivates research.
5. Ensure DORMANT non-holdings do not consume the bounded Jev priority window while broad Discovery remains ledger-independent.
6. Surface attempts, evidence gain, exhaustion/reactivation reason, and shortlist state in Investor/Three-Pillar outputs.
7. Audit run `35626246535` stage-by-stage: universe -> quant -> recall -> valuation -> priority -> Deep -> Terminal.
8. Trace Runbei plus multiple P1/near-buy codes before considering any threshold change.

## Do Not Repeat
- Do not redo #268-#273 or #275.
- Do not reopen #274 or merge superseded #276.
- Do not dispatch duplicate Deep/Jev work when persisted lineage proves it already happened.
- Do not lower hard gates, valuation thresholds, or confidence rules merely to force BUY/WAIT_PRICE.
- Do not treat missing evidence as business-quality FAIL.

## Guardrails
- Live GitHub refs/Actions/artifacts/persisted data > TASK_STATE > chat history.
- Jev is advisory research routing only; deterministic guards own dispatch eligibility.
- Formal actions remain Canonical-only; automatic Formal BUY=false.
- UNKNOWN != PASS and `no_auto_trade=true`.
- Exhausted non-holdings must eventually leave ACTIVE; holdings must never be silently dropped.
