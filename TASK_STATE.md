# Current Mission

## Goal
Turn the stock research system into a convergent autonomous opportunity engine that surfaces reference-worthy stock codes without fabricating certainty, forcing BUY, or presenting contradictory investor actions.

## Current Phase
TERMINAL_RESEARCH_DISPLAY_CONVERGENCE_PR

## Source of Truth
- Live GitHub refs, Actions, artifacts, and persisted data override this checkpoint.
- Production bot persistence may advance main after any recorded SHA.

## Last Verified Main
- Live main re-read at `81b3b6674ae9cca9017d56017d99ae8ca503fd8b` after the 19:00 production persistence cycle.
- Main advances since this PR's merge base are runtime/report/evidence persistence only; they do not touch the #293 implementation, regression test, or documentation files.
- PR #292 is merged; its research-priority wake handoff is production-verified.
- Fresh TypeSafe/Jev production run: `35849969346`.
- Exact deterministic Orchestrator run: `35850186518`.

## Active Branch
- `fix/terminal-research-supersedes-qualified-20260923`
- Merge base: `da1b8212b209ff17b823721b4a93dd12eee98f64`.
- Scope: prevent a current terminal research decision from being duplicated by the preliminary Deep-qualified `DO_NOT_BUY_YET` display layer.

## Active PR
- #293 `fix: converge terminal research display precedence` is open from the active branch.

## CI
- Regression covers the exact overlap case: current 5/5 Deep-qualified 603596 plus current terminal `RESEARCH:BUY` / risk-budget `BUILD`.
- PR-head Three-Pillar, Opportunity Discovery, and Legacy Risk-Capped workflows succeeded.
- CI run `35851756202` on head `94bc1377568c204ae54a8cb0d4f0d227442d5cac`: change detection, AI governance, Docker and deterministic checks passed; Web correctly skipped.
- Its offline pytest step remained `in_progress` for more than 39 minutes, materially beyond the last five successful PR baselines (~9-21.5 minutes), with no failure conclusion and no downloadable job log. Treat that run as an abnormal stalled validation, not as a pass or a test failure.
- This checkpoint intentionally advances the PR head so the PR concurrency contract can replace the stalled run with a clean newest-head CI. Merge still requires that fresh blocking CI to pass.
- No threshold, Jev confidence gate, Formal authority, or capital model change.

## Production / Artifact
- Jev run `35849969346`: SUCCESS, 25 entities, requested model `jev-latest`, served model `jev-1.13.0`.
- 603596 伯特利: HIGH attention, evidence `ADEQUATE_FOR_CURRENT_RESEARCH_STATE`, route `DEEP_RESEARCH`, route confidence `0.46`, Deep lineage `35849124866`, 5/5 hard gates PASS, research decision `BUY`.
- Orchestrator `35850186518` consumed exact Jev lineage `35849969346` and converged to `HUMAN_REVIEW / NOOP` because route confidence `0.46 < 0.50`; no new Deep dispatch occurred.
- Latest verified pre-fix Three-Pillar state preserves `formal_action_source=FINALIZED_CANONICAL_ONLY` and `no_auto_trade=true`.
- Production display conflict is proven: 603596 simultaneously appears as terminal `MANUAL_BUILD_ADVISORY` and preliminary `DO_NOT_BUY_YET`, while both correctly retain `formal_buy_authorized=false`.

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
- Live-main drift was rechecked and is confined to production persistence data/report artifacts, so no code replay/rebase is required before a conflict-free merge.
- The first #293 full-CI attempt was classified as stalled only after exceeding recent successful offline-suite runtimes; no failing assertion has been observed.

## Current Findings
- 603596 has a legitimate current terminal research decision and risk-budget advisory, but still no Canonical Formal BUY authority.
- The preliminary Deep-qualified layer is only for names that have passed 5/5 gates but have not yet reached a current terminal research decision.
- Once exact-current terminal research exists, continuing to show the same code as `DO_NOT_BUY_YET` is stale stage duplication.
- Correct convergence is to let the terminal research layer supersede the preliminary display while preserving every authority guardrail.

## Blockers
- No user/login/approval blocker.
- Merge is blocked only by fresh newest-head required CI.

## Next Action
1. Require the clean newest-head #293 blocking CI to pass.
2. Merge only after green CI.
3. Verify live main and the post-merge Three-Pillar production refresh no longer expose the same current-runtime code under both terminal and preliminary contradictory account-action layers.
4. Confirm terminal research remains `RESEARCH_ONLY`, risk budget remains `ADVISORY_ONLY`, `formal_buy_authorized=false`, and `no_auto_trade=true`.
5. Persist the final production checkpoint.

## Do Not Repeat
- Do not reopen or reuse #292 / `fix/jev-wake-on-research-priority-20260923`.
- Do not rerun old Jev lineage and call it fresh production verification.
- Do not lower the Jev 0.50 confidence gate or any stock-selection threshold.
- Do not promote research BUY into Formal BUY.
- Do not remove the risk-budget advisory layer merely to hide the display conflict.
- Do not treat stalled CI as green; only a completed newest-head blocking run authorizes merge.

## Guardrails
- Jev is advisory research routing only; deterministic guards own dispatch.
- Formal actions remain Canonical-only; automatic Formal BUY=false.
- Research capital allocation remains advisory-only and cannot create holding-add or order authority.
- UNKNOWN != PASS; no_auto_trade=true.
- Current terminal research decisions supersede preliminary research-qualified display for the same code and exact Deep runtime.
