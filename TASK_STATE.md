# Current Mission

## Goal
Turn the stock research system into a convergent autonomous opportunity engine that surfaces reference-worthy stock codes without fabricating certainty, forcing BUY, or presenting contradictory investor actions.

## Current Phase
TERMINAL_RESEARCH_DISPLAY_CONVERGENCE_PR

## Source of Truth
- Live GitHub refs, Actions, artifacts, and persisted data override this checkpoint.
- Production bot persistence may advance main after any recorded SHA.

## Last Verified Main
- Live main checkpoint before this fix: `da1b8212b209ff17b823721b4a93dd12eee98f64`.
- PR #292 is merged; its research-priority wake handoff is production-verified.
- Fresh TypeSafe/Jev production run: `35849969346`.
- Exact deterministic Orchestrator run: `35850186518`.

## Active Branch
- `fix/terminal-research-supersedes-qualified-20260923`
- Base: `da1b8212b209ff17b823721b4a93dd12eee98f64`.
- Scope: prevent a current terminal research decision from being duplicated by the preliminary Deep-qualified `DO_NOT_BUY_YET` display layer.

## Active PR
- Pending creation from the active branch.

## CI
- Regression added for the exact overlap case: current 5/5 Deep-qualified 603596 plus current terminal `RESEARCH:BUY` / risk-budget `BUILD`.
- Full blocking PR CI still pending.
- No threshold, Jev confidence gate, Formal authority, or capital model change.

## Production / Artifact
- Jev run `35849969346`: SUCCESS, 25 entities, requested model `jev-latest`, served model `jev-1.13.0`.
- 603596 伯特利: HIGH attention, evidence `ADEQUATE_FOR_CURRENT_RESEARCH_STATE`, route `DEEP_RESEARCH`, route confidence `0.46`, Deep lineage `35849124866`, 5/5 hard gates PASS, research decision `BUY`.
- Orchestrator `35850186518` consumed exact Jev lineage `35849969346` and converged to `HUMAN_REVIEW / NOOP` because route confidence `0.46 < 0.50`; no new Deep dispatch occurred.
- Latest Three-Pillar state preserves `formal_action_source=FINALIZED_CANONICAL_ONLY` and `no_auto_trade=true`.
- Production display conflict found: 603596 simultaneously appears as terminal `MANUAL_BUILD_ADVISORY` and preliminary `DO_NOT_BUY_YET`, while both correctly retain `formal_buy_authorized=false`.

## Actual TypeSafe/Jev Use
- Pinned TypeSafe/Jev workflow executed successfully in run `35849969346`.
- Jev remained advisory-only; deterministic Orchestrator owned dispatch.
- The deterministic confidence guard prevented automatic Deep re-dispatch and routed the low-confidence terminal state to human review.
- This fix does not alter Jev selection, model, confidence threshold, routing authority, or no-auto-trade semantics.

## Completed
- #289 research-exhaustion dormancy merged and production-verified.
- #290 lifecycle visibility merged and production-verified.
- #291 Deep-qualified research visibility merged and production-verified.
- #292 Research Learning -> Jev wake handoff merged and production-verified.
- Fresh Jev + exact Orchestrator lineage verified through `35849969346 -> 35850186518`.
- Root cause of the remaining user-visible contradiction isolated to display precedence, not research or trading authority.
- Minimal display-precedence code, regression test, documentation, and changelog change are on the active branch.

## Current Findings
- 603596 has a legitimate current terminal research decision and risk-budget advisory, but still no Canonical Formal BUY authority.
- The preliminary Deep-qualified layer is only for names that have passed 5/5 gates but have not yet reached a current terminal research decision.
- Once exact-current terminal research exists, continuing to show the same code as `DO_NOT_BUY_YET` is stale stage duplication.
- Correct convergence is to let the terminal research layer supersede the preliminary display while preserving every authority guardrail.

## Blockers
- No user/login/approval blocker.
- Merge is blocked only by the new PR's required CI.

## Next Action
1. Open the display-convergence PR.
2. Require newest-head blocking CI to pass.
3. Merge only after green CI.
4. Verify main and the post-merge Three-Pillar production refresh no longer expose 603596 under both contradictory account-action layers.
5. Confirm terminal research remains `RESEARCH_ONLY`, risk budget remains `ADVISORY_ONLY`, `formal_buy_authorized=false`, and `no_auto_trade=true`.
6. Persist the final production checkpoint.

## Do Not Repeat
- Do not reopen or reuse #292 / `fix/jev-wake-on-research-priority-20260923`.
- Do not rerun old Jev lineage and call it fresh production verification.
- Do not lower the Jev 0.50 confidence gate or any stock-selection threshold.
- Do not promote research BUY into Formal BUY.
- Do not remove the risk-budget advisory layer merely to hide the display conflict.

## Guardrails
- Jev is advisory research routing only; deterministic guards own dispatch.
- Formal actions remain Canonical-only; automatic Formal BUY=false.
- Research capital allocation remains advisory-only and cannot create holding-add or order authority.
- UNKNOWN != PASS; no_auto_trade=true.
- Current terminal research decisions supersede preliminary research-qualified display for the same code and exact Deep runtime.
