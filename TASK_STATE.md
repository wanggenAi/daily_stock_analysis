# Current Mission

## Goal
Converge the existing stock system into one trustworthy daily decision surface before adding new models. Preserve Candidate Lifecycle, valuation/decision thresholds, Formal authority separation, UNKNOWN != PASS, and no_auto_trade=true.

## Current Phase
Recover three reviewed production guards that passed CI on stale branches but were not absorbed by current main. Replay them exactly onto latest main, rerun CI, merge only when green, then verify production lineage/evidence behavior.

## Last Verified Main
- Live main before replay: `2b3aa594f88d3deaa5d55876f95323cfaf3e8fab`.
- Commit message: `Store locked V3.1 PIT backtest results`.
- Live GitHub refs / PRs / Actions / artifacts / persisted data always override this checkpoint.

## Active Branch
`fix/replay-production-guards-main-20260920`

## Active PR
- #222 — `fix: replay reviewed production guards on current main`.
- Base at creation: `2b3aa594f88d3deaa5d55876f95323cfaf3e8fab`.
- Head before this checkpoint: `36603e01d4ac6624293bb5e0af227d99e6478603`.
- Replays #219, #220, #221 with exact context/hunk matching; no whole-file replacement.

## CI
- Source PR #219 CI run `35500534030`: SUCCESS.
- Source PR #220 CI run `35500821218`: SUCCESS.
- Source PR #221 CI run `35501076821`: SUCCESS.
- #222 fresh current-main CI is required before merge; observe live Actions after this checkpoint commit.

## Production / Artifact
- Candidate continuity is production-proven and is not the blocker.
- Latest main also contains locked V3.1 PIT backtest results.
- Production verification for #222 remains pending until CI merge and post-merge Deep / Investor / evidence runs are observed.

## Completed
- Candidate Lifecycle continuity/materialization defect was fixed and production-proven.
- Deep → Provenance → Terminal → Three-Pillar convergence work progressed beyond the old #196 checkpoint; old TASK_STATE was stale.
- Formal main-board new-exposure guard merged (#211).
- Investor execution quote freshness fix merged (#212).
- Confirmed holding numeric parsing fix merged (#213).
- Sticky staged-add consumption fix merged (#214).
- Specialized industry evidence routing fix merged (#215).
- Deep evidence run deduplication fix merged (#216).
- Reviewed stale fixes #219/#220/#221 all passed their original CI.
- Dry-run against current main proved every replay hunk matched uniquely.
- #222 now contains all six replayed files from #219/#220/#221.

## Current Findings
- #219 was still missing from current main: Investor market context lacked explicit dated `EOD_DAILY_STRUCTURE` semantics.
- #220 was still missing: Deep runs lacked latest-pointer epoch fencing and skipped-trigger concurrency isolation.
- #221 was still missing: transient official predictability metadata failures lacked bounded retry/status diagnostics.
- All three old branches had diverged substantially from main, so direct stale merge was unsafe.
- Exact patch replay onto current main succeeded without conflict.

## Blockers
- #222 fresh CI must pass.
- Mergeability must be re-read after GitHub computes current PR state.
- Post-merge production evidence must confirm no regression in lineage, evidence fail-closed semantics, or Investor surface.

## Next Action
1. Read #222 CI/checks and review output.
2. Fix only real failures; do not weaken tests, governance, gates, thresholds, or fail-closed semantics.
3. Merge #222 when blocking checks are green.
4. Close stale superseded PRs #219/#220/#221.
5. Re-read live main.
6. Verify relevant production workflows/artifacts and persisted state.
7. Continue measured evidence-acquisition improvement only after production guard closure.

## Do Not Repeat
- Do not reopen solved Candidate Lifecycle continuity defects using old evidence.
- Do not merge stale #219/#220/#221 directly.
- Do not change valuation formulas or BUY/WAIT_PRICE/REJECT thresholds to force output.
- Do not change Candidate Lifecycle or Formal authority.
- Do not manufacture evidence or treat UNKNOWN as PASS.
- Do not bypass CI by deleting/skipping tests or weakening governance.

## Guardrails
- GitHub live state is the source of truth.
- Preserve exact run/profile/source/code-epoch lineage.
- Production artifacts are required in addition to tests.
- Formal/Production authority remains separate from Research outputs.
- no_auto_trade=true.
