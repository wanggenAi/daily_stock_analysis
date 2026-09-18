# Current Mission

## Goal
Keep long ChatGPT web development resumable from live GitHub state without changing stock-analysis business logic.

## Current Phase
CI — PR #183 is open with a state-only diff; wait for/check blocking CI before merge.

## Last Verified Main
`90b340af0735b1d11d2adaba003d3910974ad4d9`

Verified resumable-execution implementation commit on main: `feb104def09967cda74db6be7a156fe5ba2a17a7`.

## Active Branch
`chore/finalize-resumable-task-state`

## Active PR
#183 — open

## CI
PR #183 CI not yet observed after PR creation. Existing `ci.yml` has blocking `ai-governance`; `scripts/check_ai_assets.py` validates required `TASK_STATE.md` headings and the 120-line limit.

## Production / Artifact
No production change is intended. Verified persisted `data/opportunity_snapshots/candidate_lifecycle_state.json` blob: `b8207c0db854a9aef0c9e7aef00326c1bab82654`.

## Completed
- Verified current main/history, open PR search, CI workflow, AI instructions, and persisted lifecycle state.
- Verified `AGENTS.md` contains the GitHub-first long-task recovery protocol.
- Verified Copilot instructions require live GitHub recovery and stable-phase checkpoints.
- Verified existing CI validates `TASK_STATE.md`; no new workflow/database/service is needed.
- Confirmed the resumable-execution implementation commit is already present on current `main`.
- Repaired the stale checkpoint on a branch whose diff is only `TASK_STATE.md`.
- Opened PR #183.

## Current Findings
- Previous `TASK_STATE.md` was stale: it still said PR #181 needed merging although its implementation commit is already on `main`.
- Only checkpoint-state repair is required; stock business logic remains untouched.

## Blockers
none

## Next Action
Check PR #183 CI; if green, merge it, then re-read live `main` and production/artifact state.

## Do Not Repeat
- Do not rebuild the resumable-task mechanism already present on `main`.
- Do not redesign or re-audit stock selection, valuation, BUY/WAIT_PRICE/REJECT logic, evidence thresholds, or candidate lifecycle.
- Do not add a database, service, or new workflow for checkpointing.

## Guardrails
- Live GitHub state is the source of truth; chat context is not.
- Keep `TASK_STATE.md` concise, factual, and checkpoint-oriented.
- Do not change stock business logic, valuation logic, signal thresholds, production workflows, or data-decision standards.
