# Current Mission

## Goal
Keep Jev Structured Entry Judgment current with the latest successful Deep/Terminal lineage, then verify 603596 end to end without granting Formal or automatic trading authority.

## Current Phase
JEV_POST_TERMINAL_LINEAGE_REFRESH

## Source of Truth
- Live GitHub main/PR/Actions/artifacts and persisted production data override this checkpoint.
- Production persistence may advance main at any time; re-read live main before merge and production acceptance.

## Last Verified Main
- Branch base: `0ce39b0f6e787e1554487d4ab90f17cb0369d055`.
- #297 is merged as `ce4cbbca4ca3afc1390d654da48246832660d1fa`.
- Post-merge CI `35880305679`, Jev V4 `35880305447`, and Three-Pillar `35880305965` succeeded.

## Active Branch
- `fix/jev-refresh-after-terminal-20260924`.
- Scope: wake one lineage-keyed Jev V4 evaluation after each successfully persisted Terminal Research Decision, deduped by exact Deep run id.

## Active PR
- Not opened yet at this checkpoint.

## Production / Artifact
- Fresh post-#297 Jev V4 source `35880305447` succeeded and persisted 25 routing rows.
- That run produced 24 WAIT_EVIDENCE and one ENTRY_NOW.
- 603596 伯特利 was the ENTRY_NOW row on Deep `35872063645`, with 2026-09-22 reference price 29.15, research buy ceiling 43.7169, initial manual research size 1%, max 3%.
- That row is now correctly stale because current Deep/Terminal advanced to `35887467588`.
- Current Terminal `35887467588` still reports 603596 research BUY, 5/5 hard gates PASS, 2026-09-23 reference price 28.72, research buy ceiling 43.072, BUILD, max advisory research size 3%.
- Current Decision Center reports Jev status EMPTY_CURRENT, current entry count 0, stale Jev rows 25, Jev source `35880305447`.
- Formal BUY remains false; automatic execution remains false; no_auto_trade=true.

## Actual TypeSafe/Jev Use
- Production uses pinned TypeSafe SDK and requested model `jev-latest`; post-#297 run served `jev-1.13.0`.
- Jev remains ADVISORY_ONLY. Deterministic code owns lineage, price thresholds, sizing validation, dispatch, and authority boundaries.

## Root Cause
- The entry-judgment implementation and stale-lineage hiding are working.
- The missing handoff is after an independent successful Deep/Terminal cycle: Terminal state can advance beyond the latest persisted Jev routing without guaranteeing a new Jev V4 evaluation.
- Existing Jev Orchestration Reconciler only continues exact Deep work that Jev itself dispatched; current marker has no accepted Jev Deep run, so it cannot repair an independently newer Deep lineage.
- The old `fix/jev-wake-on-research-priority-20260923` branch is fully consumed by main and solves a different wake source.

## Fix In Progress
- After Terminal Research Decision persists successfully, dispatch `GenGe Jev Shadow Evaluation / <deep_run_id>`.
- Use `continuation_deep_run_id=<deep_run_id>`, scope=combined, max_entities=25.
- Deduplicate by exact run title so repeated Terminal convergence for the same Deep cannot create a loop.
- If the exact lineage-keyed Jev run exists and failed, rerun it; if it is active/successful, do not duplicate it.
- Existing Jev persistence then triggers current-lineage Three-Pillar refresh through `data/jev_shadow/latest_routing.json`.

## Blockers
- No user/login/approval blocker.
- PR creation, newest-head CI, merge, and production acceptance are pending.

## Next Action
1. Open the latest-main PR for this minimal wake fix.
2. Require newest-head blocking CI and workflow-contract tests.
3. Re-read live main before merge and safely replay if production persistence causes a real conflict.
4. Merge only when green.
5. Observe the merge-triggered Terminal -> lineage-keyed Jev V4 -> persisted routing -> Three-Pillar chain.
6. Verify current-lineage 603596 entry judgment against Deep/Terminal `35887467588` or any legitimately newer production lineage.
7. Record exact Jev run/artifact, validated judgment, current verified price ceiling, initial/max research size, add/do-not-chase/invalidation conditions, and authority flags.
8. Persist final TASK_STATE with the live main SHA and next unfinished stage.

## Do Not Repeat
- Do not reopen #292/#293/#294 or merge stale #296.
- Do not reuse the consumed `fix/jev-wake-on-research-priority-20260923` branch.
- Do not lower Jev 0.50, hard gates, research selection thresholds, or valuation thresholds to force a result.
- Do not rerun passed hard gates only to manufacture a newer lineage.
- Do not copy the 2026-09-22 29.15 price into current production truth.
- Do not promote Research BUY/BUILD/Jev entry judgment into Canonical Formal BUY.

## Guardrails
- Jev authority: ADVISORY_ONLY research routing + structured entry judgment.
- Deterministic code owns eligibility, lineage, verified price/sizing, dispatch, and authority boundaries.
- Formal actions remain Canonical-only; formal_buy_authorized=false.
- automatic_execution_allowed=false; no_auto_trade=true.
- UNKNOWN != PASS.
- Risk-budget sizing caps Jev suggestions.

## User-Facing Decision Reporting Contract
- For each leading candidate answer: buy now or not; exact verified price/evidence trigger; initial size; add condition; max size; do-not-chase; invalidation.
- If verified inputs cannot support a defensible trigger, report the missing evidence/unlock condition instead of inventing a number.

## Completion Criteria
- Latest-main wake fix merged with green CI.
- A fresh production TypeSafe/Jev V4 run is keyed to the current successful Deep/Terminal lineage.
- 603596 end-to-end output is current, deterministic, persisted, and visible in Three-Pillar when lineage matches.
- Formal BUY remains false and automatic execution remains disabled.
