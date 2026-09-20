# Current Mission

## Goal
Converge the existing stock system into one trustworthy daily decision surface before adding new models. Preserve Candidate Lifecycle, valuation/decision thresholds, Formal authority separation, UNKNOWN != PASS, and no_auto_trade=true.

## Current Phase
Close a production Deep liveness defect discovered after #222: successful periodic workflow_run triggers must not cancel an active official-evidence closure.

## Last Verified Main
- #222 merged as `0626380c5b68104cd66f86cc1387a0049fdc0735`.
- Branch #223 was created from live main `eb3565a14468028d53e82b2d0fccea3ce1e6e9af`; later main movement observed before PR creation was persisted-data activity.
- Live GitHub refs / PRs / Actions / artifacts / persisted data always override this checkpoint.

## Active Branch
`fix/deep-workflow-run-liveness-20260920`

## Active PR
- #223 — `fix: preserve deep closure across periodic workflow triggers`.
- Head before this checkpoint: `e2b21dbc079faad9322b7b8594a38ea1dd26bdc3`.
- Scope: Deep concurrency liveness + workflow-contract regressions + this checkpoint only.

## CI
- #222 PR CI passed before merge.
- #223 fresh CI is required before merge.
- No tests, governance, evidence gates, or fail-closed rules may be weakened to obtain green.

## Production / Artifact
- #222 post-merge authoritative Deep candidate was `35507967197`.
- It processed the full initial workset: requested=852, processed=852, profiles=853, unresolved gates before closure=4044.
- It reached official evidence closure but was cancelled before terminal persistence.
- Terminal artifact upload exists for the cancelled run, but terminal persistence / Provenance / Terminal dispatch were skipped.
- Current persisted latest Deep remains older lambda `35500463361` until a valid post-fix terminal run completes.

## Completed
- Candidate Lifecycle continuity/materialization is production-proven.
- #219/#220/#221 were replayed via #222 and #222 merged.
- Superseded #219/#220/#221 were closed.
- #222 production showed dated EOD market-structure wording on Investor surface.
- #222 bounded predictability retry code is live.
- #222 epoch fence captures actual checked-out Deep SHA and preserves immutable history.
- Post-#222 Deep `35507967197` completed initial pass on all 852 requested codes.
- Production cancellation was reproduced and timestamp-correlated with successful Era Radar workflow_run.
- Era Radar `35508146541` completed at 11:36:05Z.
- It triggered Deep `35508293335` at 11:36:07Z.
- Active Deep `35507967197` was cancelled during official evidence closure and reported `closure outcome: cancelled`.
- PR #223 changes workflow_run cancellation semantics so periodic successful workflow_run cannot preempt active closure.

## Current Findings
- #220 fixed failed/non-main skipped-trigger cancellation but did not solve successful periodic trigger preemption.
- Global `cancel-in-progress: true` creates a liveness loop when closure duration exceeds recurring upstream cadence.
- Correct behavior is:
  - push/manual evidence-code changes may supersede an older active Deep;
  - workflow_run triggers share the evidence epoch but do not cancel the active Deep;
  - GitHub concurrency coalesces pending same-group workflow_run work instead of allowing unbounded parallelism.
- The post-merge Investor run observed before Deep completion was not valid Deep convergence; it still referenced old state and showed Terminal unavailable.

## Blockers
- #223 fresh blocking CI must pass.
- Post-merge production must demonstrate an active Deep survives at least one successful periodic workflow_run trigger through terminal persistence.
- Provenance + Terminal + Investor/decision surface must converge on the completed new Deep lineage.
- Only then can the predictability retry effect be measured against the pre-fix 377 transport-failure baseline.

## Next Action
1. Observe #223 CI and review output.
2. Fix only real failures without weakening governance or evidence semantics.
3. Merge #223 only when blocking checks are green.
4. Track the fresh post-merge Deep to terminal persistence.
5. Verify periodic successful workflow_run does not cancel active closure.
6. Verify latest/history epoch fencing and downstream Provenance/Terminal convergence.
7. Compare new predictability transport-failure count with old baseline=377.
8. Then continue measured evidence acquisition; do not loosen hard gates.

## Do Not Repeat
- Do not reopen solved Candidate Lifecycle continuity defects.
- Do not treat cancelled Deep `35507967197` as terminal production evidence.
- Do not treat pre-completion Investor runs as current Deep convergence.
- Do not loosen valuation, BUY/WAIT_PRICE/REJECT, Candidate Lifecycle, Formal authority, UNKNOWN != PASS, or no_auto_trade.
- Do not merge stale superseded #219/#220/#221.

## Guardrails
- GitHub live state is the source of truth.
- Preserve exact run/profile/source/code-epoch lineage.
- Production artifacts are required in addition to tests.
- Formal/Production authority remains separate from Research outputs.
- no_auto_trade=true.
