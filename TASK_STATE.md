# Current Mission

## Goal
Make this repository resumable for long ChatGPT web development sessions by storing verified execution state in GitHub, without changing stock-analysis business logic.

## Current Phase
Merge — blocking CI is green; merge PR #181, then verify live main and production/artifact state.

## Last Verified Main
`466944c7f2887c1babcc6c714390bfd81e8850ba`

Current commit SHA: `12eeee1e3d24f33693293ebd760f7765478ff053` (CI-verified PR head immediately before this state-only checkpoint write; the live GitHub branch ref is authoritative).

## Active Branch
`fix/candidate-terminal-runtime-main` — reused only after PR #178 was merged/closed; fast-forwarded and then merged with the latest `main`.

## Active PR
#181 — open

## CI
PR #181 CI run `35321792911` passed on `12eeee1e3d24f33693293ebd760f7765478ff053`: `ai-governance` success, `backend-gate` success, `docker-build` success, `web-gate` skipped as expected.

## Production / Artifact
No production change is intended. Latest verified persisted `data/opportunity_snapshots/candidate_lifecycle_state.json` blob: `b8207c0db854a9aef0c9e7aef00326c1bab82654`. Production files changed on concurrent `main` were preserved during synchronization; this branch diff contains only governance/state files.

## Completed
- Verified live `main`, history, open PRs, Actions, AI instructions, and persisted lifecycle state.
- Created `TASK_STATE.md` and checkpointed each stable implementation phase.
- Added GitHub-first recovery and interruption-resume rules to `AGENTS.md`.
- Synchronized the minimal Copilot mirror.
- Extended existing `ai-governance` validation to require the state file and compact schema.
- Re-read a concurrently advanced `main`, verified its two changed files were unrelated, and merged it without conflict.
- Verified branch is ahead of current `main` with `behind_by=0` and only four intended files changed.

## Current Findings
- Existing `ci.yml` is sufficient; no new workflow, database, or service is needed.
- No stock-analysis business or production workflow file is in this diff.

## Blockers
none

## Next Action
Merge PR #181, then re-read live `main`, merge result, Actions, and persisted production/artifact state.

## Do Not Repeat
- Do not redesign or re-audit stock selection, valuation, BUY/WAIT_PRICE/REJECT logic, or evidence thresholds.
- Do not add a new state service, database, or workflow for this mechanism.
- Do not re-handle the concurrent `main` commits already merged into this branch.

## Guardrails
- GitHub live state is the source of truth; chat context is not.
- Keep `TASK_STATE.md` concise, factual, and checkpoint-oriented.
- Do not change stock business logic, valuation logic, signal thresholds, or data-decision standards.
