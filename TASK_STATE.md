# Current Mission

## Goal
Turn the stock research system into a convergent autonomous opportunity engine that surfaces reference-worthy stock codes without fabricating certainty or forcing BUY.

Solve together:
1. Autonomous research closure for active non-holding RESEARCH_GAP candidates: keep trying genuinely novel credible paths until progression, hard-gate FAIL, or deterministic exhaustion.
2. Candidate-funnel health: explain why broad All-A research has a large queue but no Terminal BUY/WAIT_PRICE before changing thresholds.

## Current Phase
AUTONOMOUS_RESEARCH_CLOSURE_AND_CANDIDATE_FUNNEL_AUDIT

## Last Verified Main
- Live GitHub remains source of truth; bot persistence can advance main after this checkpoint.
- Main observed immediately before this governance rebase: `5ed723fd0b44f98dc5094dded8b35b48c8260987`.
- PR #270 is merged and completed as `a0e8c44713ea3491d7eb33c2afc74daa55befada`. Do not reopen it without a newly proven regression.
- #269 generic-certification moat false-positive fix is complete and production-verified.

## Active Branch
- `fix/task-state-governance-20260922`
- Purpose: restore machine-checkable TASK_STATE governance only; no business/runtime strategy change.

## Active PR
- #271 `fix: restore task-state governance compliance`.
- Branch was rebased onto live main after production persistence advanced the base; current head must be read live.

## CI
- Main CI failures observed before #271 were `ai-governance` only.
- Root cause: TASK_STATE exceeded the 120-line limit enforced by `scripts/check_ai_assets.py`.
- A prior #271 head already proved the compact structure passes `ai-governance`.
- Re-read latest-head checks before merge; never infer green from this checkpoint.

## Production / Artifact
- Latest completed Deep verified in this mission: lambda `35689369644`, SUCCESS; requested=24, processed=24, complete=0, evidence-exhausted=24.
- Deep gap closure: attempts=2, new evidence=58, progressed gates=6, unresolved requested gates=98.
- Terminal is aligned to Deep 35689369644: BUY=0 / WAIT_PRICE=0 / RESEARCH_GAP=24 / REJECT=0.
- Research Priority observed: queue=157, P0=4, P1=8, near-buy recovery=110, success-archetype recall=0, mapping gaps=39 + 1 partial.
- Candidate lifecycle observed: active=125, archived/invalidated=0.
- Latest confirmed full All-A production artifact found: Opportunity Discovery run `35626246535`, artifact `genge-all-a-production-report` id `10653595235`.

## Completed
- Reconciled recovery checkpoint against live GitHub instead of repeating completed work.
- Verified and completed PR #270; its execution/display consistency fix is merged.
- Diagnosed post-merge red main CI as TASK_STATE governance failure, not an execution-display regression.
- Located the latest successful scheduled All-A production artifact for funnel analysis.
- Verified latest Deep and Terminal lineage are aligned on 35689369644.
- Rebased #271 onto the then-live main instead of creating a duplicate governance PR.

## Current Findings
- Upstream research population is large: 157 priority rows and 110 near-buy recovery rows.
- Deep consumes only 24 in the observed cycle; all 24 terminate as RESEARCH_GAP after bounded evidence retry.
- Deep gained real evidence and gate progress, so the pipeline is not inert, but 98 requested hard gates remain unresolved.
- Lifecycle keeps 125 candidates ACTIVE and currently shows zero archived/invalidated; exhaustion-to-dormancy semantics are not yet present.
- Success-archetype recall is currently zero despite the stored Runbei archetype.
- Example bottlenecks already observed:
  - 001316 Runbei: 2 hard gates PASS; predictability/long-term-demand/moat UNKNOWN; low-confidence Jev evidence-refresh route.
  - 002042 Huafu: P1 near-buy B; all five hard gates UNKNOWN; not in the observed old Jev selected set.
  - 000576 Ganhua: quantitatively attractive; 2 hard gates PASS; remaining financial/predictability evidence gaps.
  - 688162 Juyi: quantitatively attractive; all five hard gates UNKNOWN; earnings-quality score 69 vs machine pass threshold 70.
- These are research diagnostics, not investment recommendations.

## Blockers
- #271 must pass latest-head blocking CI and become mergeable before merge.
- Full funnel attrition counts still need to be computed from the confirmed All-A production artifact.
- Current generic bounded Deep retry cannot prove policy/source exhaustion per code × hard gate.
- No durable dormant/excluded candidate state exists for exhausted non-holdings.

## Next Action
1. Finish and merge #271 only after latest-head blocking CI is green.
2. Audit run 35626246535 artifact stage-by-stage: universe -> quant -> recall -> valuation -> priority -> Deep -> Terminal.
3. Trace Runbei plus multiple P1/near-buy codes end-to-end and identify the largest real attrition point.
4. Implement a durable per-code × hard-gate research strategy ledger with novelty/source/query fingerprints and bounded budgets.
5. Add deterministic Jev-assisted strategy planning and autonomous repeat-until-resolved/exhausted control.
6. Add dormant/excluded semantics and deterministic reactivation for exhausted non-holdings.
7. Surface strategy attempts, evidence gain, progression/exclusion reasons, and current shortlist in Investor/Three-Pillar output.

## Do Not Repeat
- Do not redo #268, #269, or #270.
- Do not rerun completed moat proof merely because chat context was lost.
- Do not dispatch duplicate Deep/Jev work when persisted lineage proves it already happened.
- Do not lower thresholds just to force a non-zero BUY/WAIT result.

## Guardrails
- Live GitHub refs/Actions/artifacts/persisted data > recovery checkpoint > TASK_STATE > chat history.
- Jev is advisory research routing only; deterministic guards own dispatch eligibility.
- Formal actions remain Canonical-only; automatic Formal BUY=false.
- UNKNOWN != PASS and `no_auto_trade=true`.
- Missing evidence is not business-quality FAIL.
- Exhausted non-holdings must eventually leave ACTIVE; holdings must never be silently dropped.
