# Current Mission

## Goal
Make the existing stock system usable as one durable closed research loop. Jev must route research automatically into the already-built Deep -> Terminal -> Investor -> Three-Pillar chain without changing Formal trading authority.

## Source of Truth
Live GitHub main / PRs / Actions / artifacts / persisted data always override this file and chat history.

## Current Phase
JEV_AUTO_ORCHESTRATION_PR_242

## Active Branch
`feat/jev-auto-orchestrator-20260921`

## Active PR
- #242 — `feat: auto-chain Jev into bounded research execution`
- #241 is closed and superseded by #242.

## Jev Status
- Phase 1 merged in #237.
- Phase 2 merged in #240 as `a14b3b0c4b7efcdfd0e85d2b7e402105327d3cb3`.
- First production Jev run `35569181282` succeeded 25/25 on `jev-1.13.0` and persisted:
  - `data/jev_shadow/latest.json`
  - `data/jev_shadow/latest_routing.json`
  - `JEV_RESEARCH_ROUTING.md`
- First sample returned 25/25 `EVIDENCE_REFRESH`, exposing overly homogeneous candidate selection.
- Phase 3 triage was proven by PR smoke: current holdings changed to `needs_deep_research=true`, while route uncertainty remained visible.
- #242 replays Phase 3 onto current main and adds deterministic bounded research dispatch.

## Target Automatic Chain
`Jev Shadow Evaluation -> Jev Research Orchestrator -> V3.1 Deep Calculation Lambda -> V3.1 Terminal Research Decision -> Investor Terminal Research Overlay -> Three-Pillar Decision Center`

## Orchestration Contract
- Jev direct dispatch: false.
- Deterministic bounded research dispatch: allowed only when Jev route and existing deterministic triage agree.
- Default max dispatch: 12 codes.
- Human-review routes are not auto-dispatched.
- Formal trading authority: false.
- Automatic Formal BUY: false.
- UNKNOWN != PASS.
- no_auto_trade=true.

## Durable Runtime State
- Jev routing: `data/jev_shadow/latest_routing.json`
- Orchestration cursor: `data/jev_shadow/orchestration/latest.json`
- Exact lineage key: `source_workflow_run_id`
- Deep idempotency key: `JEV_ORCHESTRATOR_<source_workflow_run_id>`

## Lifecycle
`JEV_READY -> ORCHESTRATION_PENDING -> DEEP_DISPATCH_ACCEPTED -> DEEP_COMPLETE -> TERMINAL_COMPLETE -> INVESTOR_OVERLAY_COMPLETE -> DECISION_CENTER_REFRESHED`

## Resume Rule When User Says "继续"
1. Read live main, open PRs, Actions, and this file.
2. Read `data/jev_shadow/latest_routing.json`.
3. Read `data/jev_shadow/orchestration/latest.json` if present.
4. If `ORCHESTRATION_PENDING`, reconcile Actions for the exact `JEV_ORCHESTRATOR_<source_run_id>` before retrying.
5. If `DEEP_DISPATCH_ACCEPTED`, follow its exact `deep_run_id`; do not dispatch another Deep for the same Jev source run.
6. After Deep success, verify the automatically chained Terminal run.
7. After Terminal success, verify Investor Terminal Overlay and Three-Pillar refresh.
8. Inspect the newest persisted terminal/investor result and continue from the first unfinished stage.
9. Never ask the user to restate project background and never repeat completed stages.

## Current PR #242 Acceptance
Before merge:
- Jev contracts must pass.
- Jev live PR smoke must pass.
- Jev Orchestrator contracts must pass.
- Main CI / ai-governance / backend / Docker checks must pass.

After merge:
1. main push must run a 25-entity Jev production evaluation;
2. Jev output must persist exact workflow lineage;
3. Orchestrator must consume only that exact Jev run;
4. at most one bounded Deep dispatch may be created;
5. cursor must persist `DEEP_DISPATCH_ACCEPTED` with exact Deep run id;
6. Deep must auto-chain to Terminal;
7. Terminal must auto-refresh Investor Overlay;
8. Investor Overlay must auto-refresh Three-Pillar;
9. final investor-facing result must preserve all authority guardrails.

## Other Important Open PRs
- #238 — material-event historical false-positive semantics; safety-sensitive.
- #235 — SSE annual-report discovery.
- #236 — MIIT evidence-depth repair.
- #234 — recovered historical candidate continuity.
- #233 — investor report readiness.
These remain separate scopes; do not fold them into Jev orchestration without fresh live-state review.

## Immediate Next Action
Fix PR #242 CI until green, merge it, then follow the automatically triggered main Jev -> Orchestrator -> Deep -> Terminal -> Investor -> Three-Pillar production chain to completion and record the exact run ids/results.

## Do Not Repeat
- Do not reopen #241.
- Do not run a second Deep for the same Jev source run.
- Do not let Jev mutate Formal BUY/WAIT_PRICE/REJECT.
- Do not loosen evidence gates, valuation thresholds, Candidate Lifecycle, UNKNOWN != PASS, or no_auto_trade.
- Do not trust stale chat state over GitHub.
