# Current Mission

## Goal
Operate the stock system as one durable closed research loop. Jev may accelerate bounded research through the existing Deep -> Terminal -> Investor -> Three-Pillar chain, but it must not change Formal trading authority.

## Current Phase
POST_JEV_PRODUCTION_COMPLETE_EVIDENCE_CLOSURE

## Last Verified Main
- Live main HEAD observed at `16b0b617cd10fd0b0730d7a40b54f053ee72cb31`.
- #242 merged earlier as `10e095d613162f9b65217207f806fffe019eaae1`.
- Live GitHub refs / Actions / persisted data always override this checkpoint.

## Active Branch
- `chore/checkpoint-jev-production-complete-20260921` for this checkpoint only.

## Active PR
- Checkpoint PR to be created from the branch above.
- #242 is merged and complete.
- #241 remains superseded/closed and must not be revived.

## CI
- #242 PR validation passed before merge.
- Merge-triggered Jev production evaluation succeeded.
- Deterministic Jev orchestrator succeeded.
- Deep run `35574223501` completed successfully.
- Deep contracts and `deep-calculate` both concluded `success`.
- Deep artifact `genge-v31-deep-calculation-35574223501` exists and is unexpired.
- Exact live Actions state must still be re-read before retry or repair.

## Production / Artifact
- Jev source run: `35573887821`.
- Jev orchestrator run: `35574096933`.
- Deep run: `35574223501`.
- Exact requested Deep workset: `000576,603209,688162,603160`.
- Deep artifact digest: `sha256:953505a69b237de289b2c705f7be622028486e71b9966e7c4b177dd8733a8438`.
- Terminal / Investor / Three-Pillar downstream state persisted successfully on main.
- Investor overlay persisted with `source_deep_lambda_run_id=35574223501`.
- Three-Pillar Decision Center refreshed after the Deep lineage.
- Jev orchestration cursor: `DECISION_CENTER_REFRESHED`.
- `next_expected_stage=COMPLETE`.
- `production_verification_complete=true`.
- Cursor file: `data/jev_shadow/orchestration/latest.json`.

## Completed
- Jev Phase 1 live API/shadow integration is production-proven.
- Jev Phase 2 persistent advisory routing is production-proven.
- Jev Phase 3 priority triage is production-proven.
- #242 merged the bounded deterministic research orchestrator.
- Jev -> Orchestrator -> Deep executed automatically on main without a user saying “继续”.
- Deep completed successfully for the exact bounded four-code workset.
- Deep dispatched provenance / terminal convergence successfully.
- Terminal research output propagated into Investor Terminal Overlay.
- Three-Pillar Decision Center refreshed from the same Deep lineage.
- Orchestration state reconciled to `DECISION_CENTER_REFRESHED` and marked production complete.
- Fail-closed routing remained active throughout.
- No duplicate Deep dispatch was required.

## Current Findings
- The automatic chain is real and production-verified end to end: Jev -> Orchestrator -> Deep -> Terminal -> Investor -> Three-Pillar.
- Auto-dispatch required Jev route + route confidence >= 0.50 + deterministic triage agreement.
- The bounded workset contained 4 rows: 甘化科工 000576, 兴通股份 603209, 巨一科技 688162, 汇顶科技 603160.
- All 4 finished as `RESEARCH_GAP`, not Formal BUY / WAIT_PRICE / REJECT.
- The common unresolved hard-gate evidence set is: `predictability`, `long_term_demand`, `moat`, `financial_safety`, `earnings_authenticity`.
- Jev direct dispatch=false.
- Formal trading authority=false.
- Automatic Formal BUY=false.
- UNKNOWN != PASS.
- no_auto_trade=true.

## Blockers
- Jev automatic continuation itself is no longer the blocker.
- The active blocker is official-evidence closure quality for the four research-gap names.
- Existing evidence-discovery PRs must be reconciled against current main before reuse; stale branches must not be merged blindly.

## Next Action
1. Re-read current open evidence-related PRs and current main before changing evidence collection.
2. Reconcile #230 (SSE multi-year annual-report discovery) and #231 (MIIT industry evidence discovery) against current main.
3. Preserve only still-valid fixes; replay onto current main if the old branches are stale/non-mergeable.
4. Prioritize closure of the five hard-gate evidence families for the four Jev-selected names.
5. Run CI, merge only verified changes, then trigger fresh production Deep evidence closure.
6. Verify whether the four names remain RESEARCH_GAP or advance based on actual official evidence.
7. Do not alter valuation formulas, BUY / WAIT_PRICE / REJECT thresholds, Candidate Lifecycle, Formal authority, UNKNOWN != PASS, or no_auto_trade.

## Do Not Repeat
- Do not redo Jev Phase 1/2/3.
- Do not reopen #241.
- Do not recreate or remerge #242.
- Do not manually dispatch another Deep run for Jev source `35573887821`.
- Do not treat current RESEARCH_GAP rows as Formal BUY.
- Do not merge stale evidence branches without replaying/revalidating against current main.
- Do not loosen evidence gates, valuation thresholds, Candidate Lifecycle, UNKNOWN != PASS, or no_auto_trade.
- Do not infer completion from chat; use live GitHub.

## Guardrails
- GitHub live state is the source of truth.
- Jev direct dispatch=false.
- Deterministic bounded research dispatch is research-only.
- Formal trading authority=false.
- Automatic Formal BUY=false.
- UNKNOWN != PASS.
- no_auto_trade=true.
- Exact Jev lineage key: `source_workflow_run_id`.
- Deep idempotency key: `JEV_ORCHESTRATOR_<source_workflow_run_id>`.
- Orchestration cursor lifecycle:
  `JEV_READY -> ORCHESTRATION_PENDING -> DEEP_DISPATCH_ACCEPTED -> DEEP_COMPLETE -> TERMINAL_COMPLETE -> INVESTOR_OVERLAY_COMPLETE -> DECISION_CENTER_REFRESHED`.
- On future user message “继续”, resume from the first unfinished live GitHub stage without asking for background.
