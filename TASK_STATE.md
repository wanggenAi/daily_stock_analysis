# Current Mission

## Goal
Keep Jev Structured Entry Judgment current with the latest successful Deep/Terminal lineage, then verify 603596 end to end without granting Formal or automatic trading authority.

## Current Phase
JEV_POST_TERMINAL_LINEAGE_REFRESH_MAIN_REPLAY

## Source of Truth
- Live GitHub main/PR/Actions/artifacts and persisted production data override this checkpoint.
- Production persistence may advance main at any time; re-read live main before merge and production acceptance.

## Last Verified Main
- Latest-main replay base: `b9795670bb9b6a76326c3cd94b0435cb330fea98`.
- #297 is merged as `ce4cbbca4ca3afc1390d654da48246832660d1fa`.
- #298 passed all newest-head CI on `31d576a45b8d84d0cb29d650ecb94e5b7eaf9d05`, but production persistence advanced main by 23 commits during the long offline suite, so #298 is superseded for merge purposes.

## Active Branch
- `fix/jev-refresh-after-terminal-main-replay-20260924`.
- Replays only the already-green #298 workflow/test fix onto current live main, plus this checkpoint update.
- No stale production runtime data is copied.

## Active PR
- Latest-main replay PR not yet opened at this checkpoint.
- #298 is CI evidence only after main advanced; do not merge it directly.

## CI
- #298 initial governance failure was TASK_STATE-only and was repaired.
- #298 newest-head CI run `35891380780`: SUCCESS.
- #298 Opportunity Discovery `35891380730`: SUCCESS.
- #298 Legacy Risk-Capped Research `35891380650`: SUCCESS.
- #298 PR Review `35891377502`: SUCCESS.
- Fresh newest-head CI is still required on this latest-main replay branch.

## Production / Artifact
- Post-#297 Jev V4 source `35880305447` succeeded and persisted 25 routing rows: 24 WAIT_EVIDENCE, 1 ENTRY_NOW.
- 603596 伯特利 was ENTRY_NOW on Deep `35872063645`, using 2026-09-22 reference price 29.15 and research buy ceiling 43.7169.
- That row is now correctly stale because current Deep/Terminal advanced to `35887467588`.
- Current Terminal `35887467588` still reports 603596 research BUY, 5/5 hard gates PASS, 2026-09-23 reference price 28.72, research buy ceiling 43.072, BUILD, max advisory research size 3%.
- Current Decision Center reports Jev EMPTY_CURRENT because all 25 persisted Jev rows have stale Deep lineage.
- Formal BUY remains false; automatic execution remains false; no_auto_trade=true.

## Actual TypeSafe/Jev Use
- Production uses pinned TypeSafe SDK and requested model `jev-latest`; post-#297 run served `jev-1.13.0`.
- Jev remains ADVISORY_ONLY. Deterministic code owns lineage, verified price thresholds, sizing validation, dispatch, and authority boundaries.

## Completed
- #297 structured entry judgment merged and production V4 proved the judgment/validation/persistence path works.
- Current stale-lineage hiding was verified: stale Jev rows are excluded rather than promoted.
- Root cause was isolated to missing post-Terminal wake wiring for independently newer Deep lineage.
- #298 implemented the minimal lineage-keyed wake and passed all CI, but was not merged because main advanced during CI.
- The same workflow/test diff has now been replayed onto live main `b9795670`.

## Current Findings
- The entry-judgment implementation itself is not the blocker.
- Existing Jev Orchestration Reconciler only continues exact Deep work Jev itself dispatched; it cannot claim an independently newer Deep lineage when its marker has no accepted Jev Deep run.
- Research-priority wake already exists and is consumed by main; it solves a different trigger source.
- Correct durable fix: after Terminal persists, wake exactly one Jev V4 run keyed by that exact Deep lambda run id and deduplicate repeated Terminal convergence.
- Existing Jev routing persistence already triggers Three-Pillar refresh.

## Blockers
- No user/login/approval blocker.
- Fresh replay PR + newest-head CI + merge + production acceptance are pending.

## Next Action
1. Open the latest-main replay PR.
2. Require fresh newest-head blocking CI and workflow-contract tests.
3. Re-read live main immediately before merge; replay again only if production persistence creates another real latest-main divergence.
4. Merge only when green.
5. Observe merge-triggered Terminal -> lineage-keyed Jev V4 -> persisted routing -> Three-Pillar chain.
6. Verify 603596 against the then-current successful Deep/Terminal lineage, never an old price snapshot.
7. Record exact Jev run/artifact, validated judgment, verified price ceiling, initial/max research size, add/do-not-chase/invalidation conditions, and authority flags.
8. Persist final TASK_STATE with live main SHA and the next unfinished stage.

## Do Not Repeat
- Do not reopen #292/#293/#294 or merge stale #296.
- Do not merge superseded #298 after latest-main replay exists.
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
