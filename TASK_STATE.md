# Current Mission

## Goal
Operate the stock system as one durable closed research loop. Jev may accelerate bounded research through the existing Deep -> Terminal -> Investor -> Three-Pillar chain, but it must not change Formal trading authority.

## Current Phase
OFFICIAL_EVIDENCE_LOCAL_CONTEXT_PRODUCTION_VERIFIED_COMPLETE

## Last Verified Main
- Live main before this final checkpoint: `117485e05c9345fdbbe7de30f0c1af1deefc2836`.
- Final production code epoch for this verification: `0156e68bb73121adbfdd29a011cc9f49352c3eba` (#267 merge).
- #266 and #267 are merged; stale #265 is closed without merge.
- Live GitHub refs / Actions / persisted data always override this checkpoint.

## Active Branch
- None for this mission.

## Active PR
- None for this mission.
- #266 `fix: replay official metric local-context extraction on latest main`: merged.
- #267 `fix: stop split-layout NBS excerpts at the target metric`: merged.
- #265: closed, not merged.

## CI
- #266 PR head checks passed: CI `35675319708`, Opportunity Discovery `35675319725`, Legacy Risk-Capped Research `35675319698`.
- #267 merged as main code epoch `0156e68...` after its production-shaped split-layout regression.
- Post-merge push CI `35679077724`: completed success. ai-governance, backend-gate and docker-build passed; web-gate was correctly skipped for this backend-only change.
- No CI blocker remains.

## Production / Artifact
- Baseline Deep: `35618926319` (success), requested=16, unresolved_requested_gate_count=69, unique_industry_evidence_count=20.
- Verified Deep: `35679085547` (success), requested=22, unresolved_requested_gate_count=93, unique_industry_evidence_count=22, new_evidence_count=55, progressed_gate_count=3, predictability_resolved_gate_count=1.
- The aggregate 69 -> 93 unresolved change is caused by six additional requested codes; those six contribute exactly 26 UNKNOWN gates.
- On the same original 16-code cohort, UNKNOWN gates improved 69 -> 67.
- `000576` 甘化科工 long_term_demand: UNKNOWN -> PASS from independent NBS + MIIT official families. MIIT extraction now correctly captures 14.6% / 15.4% operating growth rather than title/year noise.
- `603160` 汇顶科技 long_term_demand: UNKNOWN -> PASS from the same independently verified official families.
- `603209` 兴通股份 G55 NBS evidence is now correctly POSITIVE at 14.7%; MOT evidence remains NEUTRAL, so long_term_demand correctly remains UNKNOWN because the two-independent-official-source same-direction rule is not met.
- Provenance Audit `35679518840`: success; verified_pass_gate_count=224, unverified_pass_gate_count=0, all_pass_gates_have_verified_evidence=true.
- Terminal Research Decision `35679520250`: success and current for Deep `35679085547`; requested=22, RESEARCH_GAP=22, BUY=0, WAIT_PRICE=0, REJECT=0.
- Investor Terminal Research Overlay `35679622373`: success.
- Three-Pillar Decision Center `35679743365`: success; terminal snapshot current_for_deep_runtime=true.

## Completed
- #266 fixed local numeric binding, calendar/date/month-range rejection, MIIT report extraction, and evidence cache v6.
- #267 fixed the remaining NBS split-layout clause-boundary contamination.
- Fresh production Deep -> Provenance -> Terminal -> Investor -> Three-Pillar chain completed successfully.
- The target extraction defects are production-proven fixed without relaxing evidence thresholds.
- Post-merge repository CI completed successfully.
- Formal/Production authority remains unchanged; no automatic trading authority was introduced.

## Current Findings
- The official-evidence extraction defect is closed.
- Same-cohort unresolved gates decreased from 69 to 67 because two C39 names legitimately gained long_term_demand PASS.
- G55 direction extraction is corrected but remains fail-closed because corroboration is insufficient.
- Terminal synchronization is healthy: the terminal snapshot is current for the active Deep run and all 22 requested names have a research terminal state.
- Jev was NOT actually invoked in this final #267 production replay. The Deep job log contains no Jev/TypeSafe dispatch; Jev Orchestration Reconciler workflow_run instances around the merge were skipped. The Deep -> Provenance -> Terminal -> Investor -> Three-Pillar continuation here was deterministic GitHub workflow chaining.
- Earlier Jev -> Orchestrator automatic continuation remains production-proven from prior completed work; do not conflate that historical proof with an actual Jev call in this replay.

## Blockers
- None for this mission.

## Next Action
- This mission is complete.
- On the next stock-project request, continue from the persisted 22-name Terminal/Three-Pillar state and the live repository state.
- Only rerun this production evidence closure if evidence-layer code or relevant upstream evidence changes.

## Do Not Repeat
- Do not redo Jev Phase 1/2/3 or recreate #242.
- Do not reopen or merge stale #265.
- Do not rerun #266/#267 production verification unless evidence-layer code changes.
- Do not loosen long_term_demand's two-independent-official-source same-direction rule.
- Do not alter valuation formulas, BUY / WAIT_PRICE / REJECT thresholds, Candidate Lifecycle, Formal authority, UNKNOWN != PASS, or no_auto_trade.
- Do not infer completion from chat; use live GitHub.

## Guardrails
- GitHub live state is the source of truth.
- Jev direct dispatch=false.
- Deterministic bounded research dispatch is research-only.
- Formal trading authority=false.
- Automatic Formal BUY=false.
- UNKNOWN != PASS.
- no_auto_trade=true.
- On future user message “继续”, resume from the first unfinished live GitHub stage without asking for background.
