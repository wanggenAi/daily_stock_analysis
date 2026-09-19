# Current Mission

## Goal
Converge the existing stock system into one trustworthy daily decision surface before adding new models. Preserve Candidate Lifecycle, valuation/decision thresholds, Formal authority separation, UNKNOWN != PASS, and no_auto_trade=true.

## Current Phase
Candidate continuity is production-proven. Fix downstream decision convergence so a completed Deep run reliably reaches Provenance, Terminal Research Decision, and then Three-Pillar before evidence-bottleneck work continues.

## Last Verified Main
- Main observed at branch creation: `a8979d560f6ed505aa5abe0094ca072936a1212b`.
- Live GitHub refs / PRs / Actions / artifacts / persisted data always override this checkpoint.

## Active Branch
`fix/deep-terminal-decision-convergence`

## Active PR
- #196 — Fix deterministic Deep → Terminal → Three-Pillar convergence.
- Scope: workflow convergence, regression tests, and this recovery checkpoint only.
- No valuation formula, decision threshold, Candidate Lifecycle, or authority change.

## CI
- PR head before this checkpoint: `53a29b0642be947736aa96ee19a86ae6d509f2ab`.
- CI `35437454217`: failed because prior TASK_STATE.md exceeded 120 lines.
- CI `35437527659`: failed because the condensed checkpoint omitted required fixed headings.
- Current checkpoint restores the full required heading contract while remaining below 120 lines.
- Next CI must run backend/workflow regression gates after ai-governance passes.

## Production / Artifact
- Production Opportunity Discovery: `35427591974`.
- Production Every-Industry: `35433551939`.
- Fresh Deep Lambda: `35434165730`, SUCCESS.
- Deep terminal artifact: `genge-v31-deep-calculation-35434165730` (artifact id `10582920237`).
- Three-Pillar run `35436456897` consumed Deep `35434165730` but found stale Terminal lineage and correctly failed research output closed.

## Completed
### #188 continuity materialization
- Merge: `4457ca8234b43f9ba55ad989fe2737382f999a56`.
- candidate_count=853; ordinary_limit=500.
- deep continuity requested=850; covered=850; additive materialization=353; unavailable=0.
- durable lifecycle recall=118; research_required=853.
- Every-Industry inline Deep produced 853 profiles.
- Former 351 missing requested codes are present; the old 850→500→351 profile-loss defect is fixed.
- Same-run universe fallback remains research-only and carries no Formal/trading authority.

### #195 truthful terminal semantics
- Merge: `54b0e52696534cf04b7b5b8066b9db5aa6512092`.
- Pre-#188 Deep `35427088755` correctly reported HANDOFF_INCOMPLETE.
- Provenance `35427944994` and Terminal `35427944773` converged on that lineage.
- Terminal result was BUY=0, WAIT_PRICE=0, RESEARCH_GAP=849, REJECT=1.

### Fresh post-#188 Deep truth
- source Every-Industry=`35433551939`; Deep=`35434165730`.
- research_terminal_state=EVIDENCE_EXHAUSTED.
- requested=850; processed=850; profile_count=853.
- missing_requested_codes=0; handoff_incomplete_requested_count=0.
- workset coverage known=true and complete=true.
- evidence exhausted=850; complete=0.
- evidence attempts=2; new evidence rows=1565; progressed gates=0.
- unresolved hard gates=4036.

## Current Findings
- Profile/workset continuity is no longer the blocker.
- Current unresolved gate distribution: predictability×850, long_term_demand×849, moat×849, earnings_authenticity×744, financial_safety×744.
- Persisted Terminal Research Decision still points to old Deep `35427088755`.
- Three-Pillar current Deep is `35434165730`, so terminal current_for_deep_runtime=false.
- Three-Pillar therefore correctly hides stale research BUY/WAIT_PRICE/REJECT/urgent queue rather than exposing stale decisions.
- Root cause: Deep directly refreshed Three-Pillar while Terminal/Provenance depended on an implicit downstream workflow event.

## Blockers
- PR #196 must pass repository governance and workflow regression CI.
- Production verification is incomplete until Provenance, Terminal, and Three-Pillar share the same current Deep lineage.

## Next Action
1. Observe new PR #196 CI after this checkpoint.
2. Fix any real CI/review failures without weakening governance.
3. Merge #196 only after blocking checks pass.
4. Verify live main and post-merge workflow chain.
5. Require Provenance + Terminal + Three-Pillar to converge on the same current Deep lineage.
6. Verify terminal current_for_deep_runtime=true and research decisions become visible again.
7. Then improve measured evidence acquisition/interpretation; do not loosen hard gates.

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
