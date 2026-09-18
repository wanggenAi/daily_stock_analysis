# Current Mission

## Goal
Make this repository resumable for long ChatGPT web development sessions by storing verified execution state in GitHub, without changing stock-analysis business logic.

## Current Phase
Modification — establish the recovery contract and CI guard.

## Last Verified Main
`a6b86098b6ab5a30aa90e33fcb0f744914d247d2`

Current commit SHA: `a6b86098b6ab5a30aa90e33fcb0f744914d247d2` (verified branch HEAD immediately before this checkpoint write; the live GitHub branch ref is authoritative).

## Active Branch
`fix/candidate-terminal-runtime-main` — reused only after PR #178 was merged/closed; fast-forwarded to current `main`.

## Active PR
none

## CI
This mission has not opened a PR yet. Existing `ci.yml` runs `python scripts/check_ai_assets.py` in blocking `ai-governance`.

## Production / Artifact
No production change is intended. Latest observed Candidate Terminal Review on `main`: run `35320870736` in progress for `a6b8609`; previous run `35320723321` succeeded and exposed no workflow artifacts. Persisted `data/opportunity_snapshots/candidate_lifecycle_state.json` blob: `b8207c0db854a9aef0c9e7aef00326c1bab82654`.

## Completed
- Verified current `main`, recent history, open PRs, Actions, AI instructions, and persisted lifecycle state.
- Confirmed `AGENTS.md` exists and `TASK_STATE.md` did not exist.
- Confirmed existing `ai-governance` CI is the minimal integration point.
- Isolated this work from current business PRs.

## Current Findings
- `AGENTS.md` and Copilot instructions need an explicit exception for tasks where the user already authorized commit/push/PR/merge.
- No new workflow, database, or service is needed.

## Blockers
none

## Next Action
Update `AGENTS.md`, the minimal Copilot mirror, and `scripts/check_ai_assets.py` so resumable checkpoints are mandatory and structurally validated.

## Do Not Repeat
- Do not redesign or re-audit stock selection, valuation, BUY/WAIT_PRICE/REJECT logic, or evidence thresholds.
- Do not add a new state service, database, or workflow for this mechanism.

## Guardrails
- GitHub live state is the source of truth; chat context is not.
- Keep `TASK_STATE.md` concise, factual, and checkpoint-oriented.
- Do not change stock business logic, valuation logic, signal thresholds, or data-decision standards.
