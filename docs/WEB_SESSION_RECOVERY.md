# ChatGPT Web Session Recovery Protocol

This repository is designed to survive ChatGPT Plus web-session stalls, connection loss, browser death, context replacement, and handoff to a new chat.

## Recovery model

The repository does not try to resurrect an interrupted model invocation. Instead, execution state is externalized to GitHub so a new worker can reconstruct the first unfinished stage.

The precedence order is:

1. live GitHub facts: default-branch HEAD/history, open PRs, branch heads, Actions/checks, artifacts, persisted production data;
2. `state/chatgpt-recovery:RECOVERY_STATE.json`, the volatile machine-readable checkpoint;
3. `TASK_STATE.md`, the compact stable mission/handoff summary on the default branch;
4. prior chat text, only as a locator.

If any lower layer disagrees with a higher layer, reconcile toward live GitHub.

## Permanent recovery branch

A permanent branch named `state/chatgpt-recovery` carries `RECOVERY_STATE.json`.

This branch is intentionally separate from normal feature branches and from `main`:

- checkpoint writes do not compete with business PRs;
- high-frequency production commits on `main` do not invalidate the checkpoint transport;
- every update is itself a Git commit and therefore has an auditable history;
- GitHub Contents API updates use the current blob SHA, providing compare-and-swap semantics against accidental concurrent overwrite.

The state branch must never be merged as application code merely to "apply" a checkpoint.

## Required checkpoint fields

`RECOVERY_STATE.json` must remain valid JSON and retain at least:

- `schema_version`
- `generation`
- `repository`
- `status`
- `task_key`
- `stage`
- `last_observed_main_sha`
- `work_branch`
- `work_head_sha`
- `active_pr`
- `ci`
- `production_or_artifact`
- `pending_operation`
- `health`
- `completed`
- `next_action`
- `do_not_repeat`

The current schema is version 2. Allowed status values are `IDLE`, `IN_PROGRESS`, `WAITING_CI`, `WAITING_PRODUCTION`, `BLOCKED`, and `DONE`. The machine-checkable example is `.github/recovery/RECOVERY_STATE.example.json`; `scripts/validate_recovery_state.py` validates shape, bounds and obvious secret leakage without third-party dependencies.

## Adaptive checkpoint sizing

Checkpoint frequency is driven by **loss cost**, not by tool-call count or a fixed timer.

A hard checkpoint is required when any of the following is true:

- the next step is a long wait: CI, production workflow, artifact generation, external probe or another operation likely to outlive the current response;
- an external side effect is non-idempotent or its outcome could be ambiguous;
- a merge or production/artifact verification materially changes the durable project state;
- the unique task, active branch, active PR or recovery stage changes;
- estimated redo cost since the last durable checkpoint exceeds roughly 8 minutes;
- three or more independently useful conclusions have accumulated and would otherwise need to be rediscovered.

Do **not** checkpoint merely because a file was read, a status was polled, a tool was called, or an intermediate thought changed.

Safe, discoverable GitHub actions may be coalesced. For example, a focused commit, push, PR creation and CI start can normally be represented by one checkpoint immediately before waiting for CI, because live GitHub can reconstruct the preceding steps. This keeps a typical long task in the range of a handful of checkpoints rather than dozens.

The invariant is: a crash may lose transient reasoning, but it should not force more than one bounded stage of expensive rediscovery.

## Non-interference invariant — zero business-runtime tax

Recovery is a **control-plane concern only**.

- Application/runtime code must not import, parse, poll or write `RECOVERY_STATE.json`.
- Production jobs, scanners, APIs, market analysis, commercial discovery and user-facing request paths must not wait on recovery writes.
- Recovery files must not become a database, cache, queue, lock service or dependency of business logic.
- A checkpoint write failure may degrade agent recoverability, but it must not slow or fail an already-running business workload.
- Recovery validation must use local deterministic checks only; no network request, external model call or production data scan is allowed just to validate the recovery contract.
- The target business-runtime latency cost is therefore zero: the runtime does not know the recovery system exists.

Checkpoint commits use messages beginning with `[skip ci] recovery:` and remain on `state/chatgpt-recovery`. The branch is not a feature branch, must not be opened as a PR, and must not be merged into `main`. Installation and future workflow changes must verify that checkpoint commits do not trigger business workflows.

For a recovery-only PR, run the required PR checks on the head commit, then use a merge/squash commit whose message includes `[skip ci]`. This prevents the documentation/control-plane merge itself from launching duplicate main-push CI, scans, tagging or production workflows. Never use this optimization for a PR that changes business/runtime behavior.

## Fenced single-writer and compare-and-swap

The state-file blob SHA plus monotonically increasing `generation` form the writer fence.

For a checkpoint update:

1. read live GitHub facts needed for the current stage;
2. fetch the latest state file and its blob SHA;
3. reconcile drift;
4. increment `generation`;
5. write with the exact blob SHA;
6. if GitHub rejects the SHA because another worker won the race, the losing worker must stop mutating, re-read live state and reacquire a fresh generation. It must never force-overwrite.

For GitHub mutations that support an expected head/base SHA, use it. A stale worker must not merge, overwrite or delete based on an earlier generation.

## Write-ahead intent and ambiguous outcomes

`pending_operation` is a small write-ahead-intent slot for operations where duplicate execution would be harmful.

Before a non-idempotent external side effect, persist:

- `operation_id`: deterministic for this logical action;
- `kind`;
- `target`;
- `phase = PREPARED`;
- `idempotency`: how duplicate execution is prevented or detected;
- `prepared_generation`.

After success is independently observed, mark it `OBSERVED_COMMITTED` and then clear it at the next compact checkpoint.

If delivery times out and the outcome is unknown, do **not** blindly retry. Treat it as `UNKNOWN_OUTCOME` and reconcile against provider-side evidence first. If provider-side evidence cannot answer whether the action occurred, stop at `BLOCKED` and require explicit human resolution.

This strict rule applies especially to email/outreach, payments, submissions, external web actions and any operation that cannot be safely repeated. Ordinary GitHub reads are read-only; GitHub commits/PRs/runs are generally discoverable and must be queried before any retry.

## Idempotent recovery rules

- **Commit/push timeout:** query the branch/ref and commit history before creating another commit.
- **PR creation timeout:** search open/closed PRs for the intended head/base before creating another PR.
- **CI trigger timeout:** find runs for the exact head SHA before rerunning.
- **Merge timeout:** read the PR and default-branch history before attempting another merge; use expected head SHA when supported.
- **Issue/comment timeout:** read the target thread before posting a duplicate.
- **External non-idempotent action:** require durable write-ahead intent and provider-side reconciliation; never auto-repeat an unknown outcome.

## Atomic checkpoint procedure

For every checkpoint write:

1. re-read live GitHub state needed for the current stage;
2. fetch the latest `RECOVERY_STATE.json` from `state/chatgpt-recovery`;
3. reconcile any drift before writing;
4. increment `generation`;
5. update only facts that were actually observed;
6. validate the candidate state against schema/version/size rules;
7. write with the current blob SHA using a `[skip ci] recovery:` commit message;
8. on SHA conflict, re-read and reconcile instead of force-overwriting.

A checkpoint is evidence of the last observed state, not a lock on reality.

## State bounds, integrity and secret hygiene

The recovery state is deliberately small:

- maximum serialized size: 16 KiB;
- bounded summary lists: at most 20 entries each;
- no raw logs, chat transcripts, large diffs, model traces or copied artifacts;
- no tokens, passwords, cookies, credentials, authorization headers, private keys or other secrets;
- store references/IDs/SHAs instead of bulky evidence whenever possible.

Git already provides content-addressed integrity and history; a separate database is unnecessary for this use case.

If the current JSON is corrupt, inspect prior commits on `state/chatgpt-recovery` and recover the newest valid version, then reconcile with live GitHub. If the branch/file is missing, recreate it from current live repository truth. Never reconstruct missing durable state from chat memory alone.

## Degraded recovery mode

If GitHub state storage is temporarily unavailable:

- existing application/business execution continues normally;
- read-only investigation may continue;
- safe, fully discoverable GitHub work may continue only with live preflight and later reconciliation;
- non-idempotent external side effects that require write-ahead intent must pause rather than risk duplication;
- set recovery health to degraded when a durable checkpoint can next be written.

## Resume algorithm

A new chat or worker must:

1. read `AGENTS.md` and this protocol;
2. inspect live default-branch HEAD/history;
3. inspect relevant open PRs and their current head SHAs;
4. inspect relevant Actions/checks and artifacts/persisted data;
5. read `state/chatgpt-recovery:RECOVERY_STATE.json`;
6. read `TASK_STATE.md`;
7. classify the checkpoint as `FRESH`, `STALE`, or `CONFLICTED`;
8. reconcile toward live GitHub;
9. continue from the first incomplete stage without repeating already-verified work.

### FRESH

The referenced task/branch/PR still exists and recorded SHAs/statuses match the current relevant refs.

### STALE

Live GitHub moved after the checkpoint, but the movement is explainable: automation advanced `main`, CI finished, the PR head moved, or the PR was merged/closed. Read the delta and advance the checkpoint.

### CONFLICTED

The checkpoint claims a task/PR/branch relation that cannot be reconciled with live refs. Do not guess. Preserve verified completed work, identify the first uncertain transition, and resume from that boundary.

For repositories with automated commits to `main`, a changed main SHA alone does not invalidate a checkpoint. Inspect whether the delta touches the active task or is only runtime/persisted-data activity.

## Stable vs volatile state

`RECOVERY_STATE.json` is the volatile execution cursor. `TASK_STATE.md` is the stable mission summary.

Do not rewrite `TASK_STATE.md` for every tiny transition. Fold durable milestone facts into it when a stage materially changes the mission, blocker, active PR, verified artifact, or next action.

## Crash-window rule

There is always a possible gap between a remote side effect and the following checkpoint write. Therefore recovery never assumes the checkpoint is complete. It checks GitHub first.

Examples:

- commit exists but checkpoint still says "editing" -> keep the commit and advance;
- PR exists but `active_pr` is null -> adopt the real PR after verifying it belongs to the task;
- CI finished while checkpoint says `WAITING_CI` -> consume the result instead of rerunning;
- PR merged while checkpoint says "ready to merge" -> verify merged main and continue post-merge validation.

## Completion

When the task is fully verified:

- set `status` to `DONE` or `IDLE`;
- record the merged/default-branch SHA actually verified;
- clear obsolete active branch/PR fields where appropriate;
- record the next real action, if any;
- update `TASK_STATE.md` when the stable project handoff changed.

The objective is not to keep a web request alive forever. The objective is that killing the current chat at any checkpoint loses no verified work and requires no project re-analysis.
