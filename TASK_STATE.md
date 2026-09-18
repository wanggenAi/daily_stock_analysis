# Current Mission

## Goal
Keep long ChatGPT web development resumable from live GitHub state without changing stock-analysis business logic.

## Current Phase
Checkpoint repair — resumable execution mechanism is already on `main`; repair stale `TASK_STATE.md`, then verify through PR/CI/merge.

## Last Verified Main
`90b340af0735b1d11d2adaba003d3910974ad4d9`

Current verified implementation commit on main: `feb104def09967cda74db6be7a156fe5ba2a17a7`.

## Active Branch
`chore/finalize-resumable-task-state`

## Active PR
none

## CI
Current branch CI not run yet. Existing `ci.yml` contains blocking `ai-governance`; `scripts/check_ai_assets.py` validates required `TASK_STATE.md` headings and the 120-line limit.

## Production / Artifact
No production change is intended. Verified persisted `data/opportunity_snapshots/candidate_lifecycle_state.json` blob: `b8207c0db854a9aef0c9e7aef00326c1bab82654`.

## Completed
- Verified current main/history, open PR search, CI workflow, AI instructions, and persisted lifecycle state.
- Verified `AGENTS.md` contains the GitHub-first long-task recovery protocol.
- Verified Copilot instructions require live GitHub recovery and stable-phase checkpoints.
- Verified existing CI validates `TASK_STATE.md`; no new workflow/database/service is needed.
- Confirmed the resumable-execution implementation commit is already present on current `main`.

## Current Findings
- Previous `TASK_STATE.md` was stale: it still said PR #181 needed merging although its implementation commit is already on `main`.
- Only checkpoint-state repair is required; stock business logic must remain untouched.

## Blockers
none

## Next Action
Open a PR containing only the checkpoint-state repair, run CI, merge when green, then verify live `main` and production/artifact state.

## Do Not Repeat
- Do not rebuild the resumable-task mechanism already present on `main`.
- Do not redesign or re-audit stock selection, valuation, BUY/WAIT_PRICE/REJECT logic, evidence thresholds, or candidate lifecycle.
- Do not add a database, service, or new workflow for checkpointing.

## Guardrails
- Live GitHub state is the source of truth; chat context is not.
- Keep `TASK_STATE.md` concise, factual, and checkpoint-oriented.
- Do not change stock business logic, valuation logic, signal thresholds, production workflows, or data-decision standards.
