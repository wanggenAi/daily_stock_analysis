# Current Mission

## Goal
Keep long ChatGPT web development resumable from live GitHub state.

## Current Phase
Completed — repository recovery rules, checkpointing, CI validation, merge verification, and persisted-state verification are complete.

## Last Verified Main
`f9dbee445b1e43e494030bcf72b990c33aedee2e` (verified before this final state-only checkpoint; live `main` remains authoritative).

## Active Branch
none

## Active PR
none

## CI
PR #183 validation completed successfully in CI run `35324057764`: `ai-governance`, `backend-gate`, and `docker-build` passed; `web-gate` was skipped as expected.

## Production / Artifact
No application behavior change was introduced by this mission. The persisted lifecycle-state blob remains `b8207c0db854a9aef0c9e7aef00326c1bab82654`.

## Completed
- Verified live main, recent history, open PRs, Actions, agent instructions, and relevant persisted state.
- Confirmed `AGENTS.md` contains the GitHub-first long-task recovery protocol.
- Confirmed Copilot instructions mirror the recovery/checkpoint rule.
- Confirmed existing `ai-governance` validates `TASK_STATE.md`; no new database, service, or workflow was required.
- Repaired stale task state through PR #183 with a `TASK_STATE.md`-only diff.
- Passed CI, merged PR #183, and re-read live `main`.
- Preserved concurrent production-state commits while preparing this final checkpoint.

## Current Findings
- Repository state is sufficient to recover the next task without relying on chat context.
- Live `main` may continue to advance through persisted-data commits; always re-read it before resuming work.

## Blockers
none

## Next Action
For the next task, first read live `main`, recent history, open PRs, Actions/checks, task-relevant persisted data/artifacts, and this file; then replace this completed mission with the new verified mission.

## Do Not Repeat
- Do not rebuild the resumable-task mechanism already present on `main`.
- Do not re-run this completed checkpoint-repair mission.
- Do not change application decision logic merely to support checkpointing.

## Guardrails
- Live GitHub state is the source of truth; chat context is not.
- Keep `TASK_STATE.md` concise, factual, and checkpoint-oriented.
- Keep checkpointing isolated from application behavior.
