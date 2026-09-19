# Current Mission

## Goal
Make the existing stock system converge into one trustworthy daily decision surface before adding new models. Preserve Candidate Lifecycle, valuation/decision thresholds, Formal authority, UNKNOWN != PASS, and no_auto_trade=true.

## Current Phase
Post-#188 continuity production proof is established at the workset/initial-Deep boundary. Finish the post-#188 Deep terminal chain, then move to measured evidence bottlenecks instead of changing thresholds.

## Live Source Of Truth
GitHub current main / Actions / artifacts / persisted data are authoritative. This checkpoint was written after live main advanced through persisted-state bot commits; latest observed main commit before this checkpoint was `f4f33bd94da179f01b4d9b4f164a78ec76f92308`.

## Active Branch / PR
None for the current mission.

## Completed Production Proofs

### #195 — truthful Deep terminal semantics
- Merge commit: `54b0e52696534cf04b7b5b8066b9db5aa6512092`.
- Production Deep run `35427088755` completed SUCCESS using stale pre-#188 Every-Industry source `35403243897`.
- Final persisted terminal truth:
  - research_terminal_state=`HANDOFF_INCOMPLETE`
  - requested_count=850
  - profile_count=500
  - requested_profile_count=499
  - processed_requested_count=499
  - evidence_exhausted_requested_count=499
  - handoff_incomplete_requested_count=351
  - missing_requested_codes=351
  - unresolved_requested_gate_count=2285
  - workset_coverage_known=true
  - workset_coverage_complete=false
- Provenance Audit run `35427944994` completed SUCCESS.
- Terminal Research Decision run `35427944773` completed SUCCESS: BUY=0, WAIT_PRICE=0, RESEARCH_GAP=849, REJECT=1.
- Three-Pillar Decision Center subsequently converged to the same Deep lineage and no longer displayed the old run.
- Therefore #195 is production-proven: missing profiles are no longer mislabeled as evidence exhaustion and no synthetic profile reason is counted as a hard gate.

### #188 — continuity materialization
- Merge commit: `4457ca8234b43f9ba55ad989fe2737382f999a56`.
- Fresh production Opportunity Discovery run `35427591974`, event=`workflow_dispatch`, completed SUCCESS.
- Its `genge-all-a-production-report` artifact is valid production evidence:
  - as_of_date=2026-09-18
  - official_universe_count=5221
  - effective_scan_count=4505
  - price_data_coverage_ratio=1.0
  - fatal_data_failure_count=0
  - recoverable_price_failure_count=0
  - market_regime_status=GREEN
  - market_regime_score=73.83
  - acceptance_enum=`PASS_ALL_A_PRODUCTION_RESEARCH_READY`
- Old 351 missing Deep codes were checked against this same-run source:
  - 351/351 are present in current All-A universe.
  - 349/351 are present in current All-A quant screen.
  - `601995` and `605050` are universe-only and therefore exercise the intended metadata fallback.
- Automatic workflow_run handoff did not appear promptly, so the existing production bridge was explicitly pointed at upstream run `35427591974`.
- Fresh Every-Industry run `35433551939`, event=`workflow_dispatch`, completed SUCCESS and consumed the fresh All-A production artifact.
- Its `v31_review_queue_summary.json` proves:
  - candidate_count=853
  - ordinary_limit=500
  - deep_continuity_requested_count=850
  - deep_continuity_covered_count=850
  - deep_continuity_materialized_additive_count=353
  - deep_continuity_unavailable_count=0
  - durable_lifecycle_recall_count=118
  - research_required_count=853
  - formal_signal_eligible=false
  - automatic_promotion_allowed=false
  - no_auto_trade=true
- The two universe-only codes `601995` and `605050` were materialized with:
  - deep_continuity_recall=true
  - deep_continuity_source=`CURRENT_ALL_A_UNIVERSE`
  - deep_continuity_research_only=true
  - formal_signal_eligible=false
  - automatic_promotion_allowed=false
  - no_auto_trade=true
- Every-Industry inline Deep produced 853 profiles and no missing requested profiles.
- All old 351 missing codes are present in the new queue and in the new profiles.
- Therefore the old structural `850 requested -> 500 profiles -> 351 missing` handoff defect is production-proven fixed at the Every-Industry boundary.

## Active Deep Verification
- Fresh Deep Lambda: `35434165730`
- Trigger: `EVERY_INDUSTRY_READY`
- Exact Every-Industry source: `35433551939`
- Initial checkpoint artifact `genge-v31-deep-initial-35434165730` is verified:
  - source_run_id=35433551939
  - requested_count=850
  - processed_requested_count=850
  - profiles_count=853
  - missing_requested_codes=0
  - complete_requested_count=0
  - partial_requested_count=850
  - unresolved_requested_gate_count=4036
- It is currently in bounded official-evidence closure.
- This independent Lambda initial checkpoint confirms #188 continuity survives the separate downstream handoff: the former 351 profile holes are zero.

## Current Findings
- `--limit 500` is only the ordinary V3.1 review budget. It must not cap retained Deep continuity.
- Same-run universe fallback is necessary for listed codes without same-day quant rows; it is research-only and carries no Formal/trading authority.
- #188 and #195 now solve different defects:
  - #188 prevents retained requested codes from disappearing before Deep profiles are created.
  - #195 truthfully distinguishes any future handoff loss from genuine evidence exhaustion.
- Remaining bottleneck is now substantive evidence closure, not profile/workset handoff.
- New initial Deep has 4036 unresolved requested hard gates across 850 requested codes; do not loosen gates just to manufacture BUY/WAIT_PRICE output.

## Next Action
1. Follow Deep run `35434165730` through terminal persistence and artifact upload.
2. Verify terminal state has missing_requested_codes=0 and handoff_incomplete_requested_count=0.
3. Verify terminal evidence-exhausted/complete counts apply only to the 850 fully materialized requested profiles.
4. Verify Provenance Audit, Terminal Research Decision, and Three-Pillar Decision Center converge to Deep `35434165730`.
5. Then quantify the real evidence bottlenecks (predictability, long_term_demand, moat, earnings_authenticity, financial_safety) and improve evidence acquisition/interpretation without changing formal thresholds or fabricating evidence.
6. After continuity/evidence closure, revisit unrelated recurring Terminal Research Overlay reliability failures separately.

## Do Not Repeat
- Do not diagnose #188 from pre-#188 source `35403243897`.
- Do not treat push/PR Opportunity Discovery fixtures as production evidence.
- Do not remove the Every-Industry guard rejecting fixture upstreams.
- Do not raise/remove the ordinary 500 limit merely to hide continuity defects.
- Do not change valuation formulas or BUY/WAIT_PRICE/REJECT thresholds to force output.
- Do not change Candidate Lifecycle or Formal authority.
- Do not classify profile-handoff absence as evidence exhaustion.
- Do not manufacture evidence or treat UNKNOWN as PASS.

## Guardrails
- Preserve exact run/profile/source lineage.
- Production artifacts are required in addition to tests.
- Formal/Production authority remains separate from Research outputs.
- no_auto_trade=true.
