# Current Mission

## Goal
Operate the stock system as one durable closed research loop. Jev may accelerate bounded research through the existing Deep -> Terminal -> Investor -> Three-Pillar chain, but it must not change Formal trading authority.

## Current Phase
POST_MERGE_JEV_AUTO_ORCHESTRATION_PRODUCTION_VERIFICATION

## Last Verified Main
- #242 merged to `main` as `10e095d613162f9b65217207f806fffe019eaae1`.
- Live GitHub refs / Actions / persisted data always override this checkpoint.

## Active Branch
None for the merged Jev auto-orchestration work.

## Active PR
- #242 — `feat: auto-chain Jev into bounded research execution` — merged.
- #241 remains superseded/closed and must not be revived.

## CI
- #242 PR validation passed before merge.
- Merge-triggered Jev production evaluation and deterministic orchestrator both progressed successfully to Deep dispatch.
- Exact live Actions state must be re-read before any retry or repair.

## Production / Artifact
- Merge-triggered Jev source run: `35573887821`.
- Persisted Jev routing source_workflow_run_id: `35573887821`.
- Routing result: 25 entities; 23 EVIDENCE_REFRESH; 2 HUMAN_REVIEW.
- Jev orchestrator run: `35574096933`.
- Orchestration cursor: `DEEP_DISPATCH_ACCEPTED`.
- Exact Deep run: `35574223501`.
- Deep requested workset: `000576,603209,688162,603160`.
- Latest observed Deep state: contracts passed; `deep-calculate` was in progress.
- Cursor file: `data/jev_shadow/orchestration/latest.json`.

## Completed
- Jev Phase 1 live API/shadow integration is production-proven.
- Jev Phase 2 persistent advisory routing is production-proven.
- Phase 3 priority triage is merged through #242.
- #242 merged the bounded deterministic research orchestrator.
- Main production run proved Jev can trigger the orchestrator without a user saying “继续”.
- Orchestrator proved idempotent exact lineage and automatically dispatched one bounded Deep workset.
- Fail-closed routing worked: uncertain/low-confidence rows were held for HUMAN_REVIEW instead of auto-dispatch.

## Current Findings
- The automatic chain is real, not only architectural: Jev -> Orchestrator -> Deep has executed on main.
- Auto-dispatch required Jev route + route confidence >= 0.50 + deterministic triage agreement.
- 4 rows met the bounded dispatch contract.
- 21 rows were not auto-dispatched; HUMAN_REVIEW/fail-closed handling remained active.
- Jev direct dispatch=false.
- Formal trading authority=false.
- Automatic Formal BUY=false.
- UNKNOWN != PASS.
- no_auto_trade=true.

## Blockers
- Full production proof is not complete until Deep `35574223501` reaches terminal completion and the downstream automatic chain is verified.
- Do not dispatch another Deep run for Jev source `35573887821`.

## Next Action
1. Re-read Deep run `35574223501` jobs and artifacts.
2. If Deep fails, inspect the exact failed job/step and repair only the demonstrated cause.
3. If Deep succeeds, verify its persisted status/artifact and exact requested four-code workset.
4. Verify automatic Terminal Research Decision starts/completes.
5. Verify Investor Terminal Overlay refreshes.
6. Verify Three-Pillar Decision Center refreshes.
7. Confirm persisted lineage reaches the newest terminal/investor outputs without duplicate dispatch.
8. Update this checkpoint with final production run ids and result.

## Do Not Repeat
- Do not redo Phase 3.
- Do not reopen #241.
- Do not recreate or remerge #242.
- Do not manually dispatch a second Deep run for source `35573887821`.
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
