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
- `completed`
- `next_action`
- `do_not_repeat`

Allowed status values are `IDLE`, `IN_PROGRESS`, `WAITING_CI`, `WAITING_PRODUCTION`, `BLOCKED`, and `DONE`.

## Atomic checkpoint procedure

For every checkpoint write:

1. re-read live GitHub state needed for the current stage;
2. fetch the latest `RECOVERY_STATE.json` from `state/chatgpt-recovery`;
3. reconcile any drift before writing;
4. increment `generation`;
5. update only facts that were actually observed;
6. write with the current blob SHA; on SHA conflict, re-read and reconcile instead of force-overwriting.

A checkpoint is evidence of the last observed state, not a lock on reality.

## Mandatory checkpoint boundaries

Write a recovery checkpoint:

- immediately after choosing the unique task and work branch;
- after a meaningful code/data/document stage becomes remotely durable;
- after commit/push;
- immediately after PR creation or material PR-head change;
- before starting or waiting on a long CI, production workflow, external probe, or artifact-producing run;
- after CI/run completion is observed;
- after merge;
- after post-merge main/production/artifact verification;
- before any operation whose interruption would otherwise make the next worker guess what happened.

Do not wait until the end of a long task to checkpoint.

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
