# Current Mission

## Goal
Make this repository resumable for long ChatGPT web development sessions by storing verified execution state in GitHub, without changing stock-analysis business logic.

## Current Phase
Validation — recovery contract is committed; verify structure before opening the PR.

## Last Verified Main
`a6b86098b6ab5a30aa90e33fcb0f744914d247d2`

Current commit SHA: `28f181bc08d3dbc0cc8cbe9ad0ae48dd2cbf4196` (verified branch HEAD immediately before this checkpoint write; the live GitHub branch ref is authoritative).

## Active Branch
`fix/candidate-terminal-runtime-main` — reused only after PR #178 was merged/closed; fast-forwarded to current `main`.

## Active PR
none

## CI
This mission has not opened a PR yet. Existing `ci.yml` blocking `ai-governance` already runs `python scripts/check_ai_assets.py`; that script now validates `TASK_STATE.md`.

## Production / Artifact
No production change is intended. Latest observed Candidate Terminal Review on `main`: run `35320870736` in progress for `a6b8609`; previous run `35320723321` succeeded and exposed no workflow artifacts. Persisted `data/opportunity_snapshots/candidate_lifecycle_state.json` blob: `b8207c0db854a9aef0c9e7aef00326c1bab82654`.

## Completed
- Verified current `main`, recent history, open PRs, Actions, AI instructions, and persisted lifecycle state.
- Created the first resumable `TASK_STATE.md` checkpoint.
- Added GitHub-first recovery rules and stable-phase checkpoint rules to `AGENTS.md`.
- Synchronized the minimal Copilot mirror.
- Extended existing `ai-governance` validation to require the state file and its compact schema.
- Kept stock-analysis business logic and production workflows untouched.

## Current Findings
- Existing `ci.yml` is sufficient; no new workflow, database, or service is needed.
- The work is isolated from current business PRs.

## Blockers
none

## Next Action
Run deterministic structural verification on the committed branch, then open the PR and follow CI to completion.

## Do Not Repeat
- Do not redesign or re-audit stock selection, valuation, BUY/WAIT_PRICE/REJECT logic, or evidence thresholds.
- Do not add a new state service, database, or workflow for this mechanism.

## Guardrails
- GitHub live state is the source of truth; chat context is not.
- Keep `TASK_STATE.md` concise, factual, and checkpoint-oriented.
- Do not change stock business logic, valuation logic, signal thresholds, or data-decision standards.
