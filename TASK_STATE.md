# Current Mission

## Goal
Converge the existing stock system into one trustworthy daily decision surface before adding new models. Preserve Candidate Lifecycle, valuation/decision thresholds, Formal authority separation, UNKNOWN != PASS, and no_auto_trade=true.

## Live Source Of Truth
GitHub live main / PRs / Actions / artifacts / persisted data are authoritative. Chat history and this file are secondary recovery aids.

## Current Phase
Candidate continuity is production-proven. The current blocker is downstream decision convergence: a completed Deep run can persist new terminal state while Terminal Research Decision remains on an older Deep lineage, causing Three-Pillar to fail closed and expose zero research actions.

## Active Change
- Branch: `fix/deep-terminal-decision-convergence`
- PR: #196 — Fix deterministic Deep → Terminal → Three-Pillar convergence
- Base observed when branch was created: `a8979d560f6ed505aa5abe0094ca072936a1212b`
- Scope: workflow convergence + regression tests only; no investment-model thresholds or authority semantics changed.

## Production Proofs

### #188 — durable continuity materialization
- Merge commit: `4457ca8234b43f9ba55ad989fe2737382f999a56`.
- Production Opportunity Discovery: `35427591974`.
- Production Every-Industry: `35433551939`.
- candidate_count=853; ordinary_limit=500.
- deep_continuity_requested_count=850; covered=850; materialized_additive=353; unavailable=0.
- durable_lifecycle_recall_count=118; research_required_count=853.
- Every-Industry inline Deep produced 853 profiles.
- Former 351 missing requested codes are present; old 850→500→351 profile-loss defect is fixed.
- Same-run universe fallback remains research-only; no Formal/trading authority.

### #195 — truthful terminal semantics
- Merge commit: `54b0e52696534cf04b7b5b8066b9db5aa6512092`.
- Pre-#188 Deep `35427088755` correctly reported HANDOFF_INCOMPLETE instead of mislabeling missing profiles as evidence exhaustion.
- Provenance `35427944994` and Terminal `35427944773` converged on that lineage.
- Terminal decisions then were BUY=0, WAIT_PRICE=0, RESEARCH_GAP=849, REJECT=1.

### Fresh post-#188 Deep
- Deep Lambda: `35434165730`; source Every-Industry: `35433551939`.
- Workflow conclusion: SUCCESS.
- Terminal artifact: `genge-v31-deep-calculation-35434165730`.
- research_terminal_state=EVIDENCE_EXHAUSTED.
- requested=850; processed_requested=850; profile_count=853.
- missing_requested_codes=0; handoff_incomplete_requested_count=0.
- workset_coverage_known=true; workset_coverage_complete=true.
- evidence_exhausted_requested_count=850; complete_requested_count=0.
- evidence_collection_attempts=2; new_evidence_rows=1565; progressed_gates=0.
- unresolved_requested_gate_count=4036.
- Gate distribution: predictability×850; long_term_demand×849; moat×849; earnings_authenticity×744; financial_safety×744.

## Current Defect
- Three-Pillar run `35436456897` consumed current Deep `35434165730`.
- Persisted Terminal Research Decision still points to old Deep `35427088755`.
- Therefore terminal snapshot current_for_deep_runtime=false.
- Three-Pillar correctly fails closed: research BUY/WAIT_PRICE/REJECT/urgent queue are hidden rather than exposing stale decisions.
- Root cause: Deep directly refreshed Three-Pillar while Terminal/Provenance still depended on implicit downstream `workflow_run` propagation.

## PR #196 Fix
- Deep success explicitly dispatches Deep Provenance Audit and Terminal Research Decision.
- Deep no longer directly refreshes Three-Pillar before Terminal convergence.
- Terminal Research Decision explicitly refreshes Three-Pillar only after terminal decisions persist.
- Existing workflow_run triggers and scheduled Deep Terminal Reconciler remain idempotent fallbacks.
- Regression tests enforce both ordering contracts.

## CI
- First PR #196 CI run: `35437454217`.
- Initial blocker was ai-governance because this TASK_STATE.md exceeded the repository maximum of 120 lines.
- This checkpoint intentionally condenses the file instead of weakening governance.

## Next Action
1. Re-run/observe PR #196 CI after this checkpoint update.
2. Fix any real CI/review failures.
3. Merge #196 only after blocking checks pass.
4. Verify live main and post-merge workflow chain.
5. Require Provenance + Terminal + Three-Pillar to converge on the same current Deep lineage.
6. Verify terminal current_for_deep_runtime=true and research decisions are visible again without changing Formal authority.
7. Then quantify and improve the real evidence bottlenecks; do not loosen hard gates to manufacture BUY/WAIT_PRICE.

## Do Not Repeat
- Do not reopen the solved 351-profile continuity defect using pre-#188 evidence.
- Do not raise/remove ordinary limit=500 to hide lifecycle problems.
- Do not change valuation formulas or BUY/WAIT_PRICE/REJECT thresholds to force output.
- Do not change Candidate Lifecycle or Formal authority.
- Do not classify missing handoff as evidence exhaustion.
- Do not manufacture evidence or treat UNKNOWN as PASS.

## Guardrails
- Preserve exact run/profile/source lineage.
- Production artifacts are required in addition to tests.
- Formal/Production authority remains separate from Research outputs.
- no_auto_trade=true.
