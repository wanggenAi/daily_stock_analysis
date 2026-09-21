# Current Mission

## Goal
Make the stock system operate as one durable closed research loop. Jev should automatically route bounded research into the existing Deep -> Terminal -> Investor -> Three-Pillar chain without changing Formal trading authority.

## Current Phase
JEV_AUTO_ORCHESTRATION_PR_242

## Last Verified Main
- Live main when this checkpoint was written: `380a57063cf89b4a78ba8afd749b844753c5fb02`.
- Live GitHub refs / PRs / Actions / artifacts / persisted data always override this checkpoint.

## Active Branch
`feat/jev-auto-orchestrator-20260921`

## Active PR
- #242 — `feat: auto-chain Jev into bounded research execution`
- #241 is closed and superseded by #242.

## CI
- PR #242 must pass:
  - repository `CI`
  - `ai-governance`
  - backend gate
  - Docker gate
  - `GenGe Jev Shadow Evaluation` contracts + live PR smoke
  - `GenGe Jev Research Orchestrator` contracts
- Current known governance requirement: this file must remain <=120 lines and preserve every required heading.

## Production / Artifact
- Jev Phase 1 merged in #237.
- Jev Phase 2 merged in #240 as `a14b3b0c4b7efcdfd0e85d2b7e402105327d3cb3`.
- First production Jev run `35569181282` succeeded 25/25 on `jev-1.13.0`.
- Persisted advisory files:
  - `data/jev_shadow/latest.json`
  - `data/jev_shadow/latest_routing.json`
  - `JEV_RESEARCH_ROUTING.md`
- Automatic-loop cursor after #242 merges:
  - `data/jev_shadow/orchestration/latest.json`

## Completed
- First live Jev production integration is proven.
- First persisted 25-entity Jev advisory is proven.
- Phase 3 triage concept is proven by live PR smoke.
- #241 was closed to avoid parallel stale implementation.
- #242 now combines Phase 3 + exact Jev run lineage + bounded deterministic research orchestration + durable resume rules.

## Current Findings
- First production sample returned 25/25 `EVIDENCE_REFRESH`; candidate selection was too homogeneous.
- Phase 3 changes selection to holdings first, then urgent / P0-P2 / strong deterministic research candidates.
- Jev remains advisory-only.
- The deterministic orchestrator may auto-dispatch research only when Jev route and existing deterministic triage agree.
- Target chain:
  `Jev Shadow Evaluation -> Jev Research Orchestrator -> V3.1 Deep Calculation Lambda -> V3.1 Terminal Research Decision -> Investor Terminal Research Overlay -> Three-Pillar Decision Center`
- Default maximum dispatch is 12 codes per Jev cycle.
- Human-review routes are never auto-dispatched.

## Blockers
- PR #242 is not mergeable until all required CI passes.
- After merge, production proof is still required for the full automatic chain.
- Separate stock-system PRs remain open and are not part of this Jev scope:
  - #238 material-event semantics
  - #235 SSE annual-report discovery
  - #236 MIIT evidence-depth repair
  - #234 recovered historical candidate continuity
  - #233 investor-report readiness

## Next Action
1. Fix PR #242 CI until green.
2. Merge #242 only after required checks succeed.
3. Verify merge-triggered main Jev run evaluates 25 prioritized entities and persists exact `source_workflow_run_id`.
4. Verify Jev Research Orchestrator consumes only that exact run.
5. Verify at most one bounded Deep dispatch is created and cursor becomes `DEEP_DISPATCH_ACCEPTED`.
6. Follow exact Deep run to success.
7. Verify automatic Terminal Research Decision.
8. Verify Investor Terminal Overlay.
9. Verify Three-Pillar refresh.
10. Inspect newest persisted terminal/investor result and record exact run ids/results.

## Do Not Repeat
- Do not reopen or merge #241.
- Do not dispatch a second Deep run for the same Jev `source_workflow_run_id`.
- Do not let Jev mutate Formal BUY / WAIT_PRICE / REJECT.
- Do not loosen evidence gates, valuation thresholds, Candidate Lifecycle, UNKNOWN != PASS, or no_auto_trade.
- Do not trust stale chat state over live GitHub.

## Guardrails
- GitHub live state is the source of truth.
- Jev direct dispatch=false.
- Deterministic bounded research dispatch is research-only.
- Formal trading authority=false.
- Automatic Formal BUY=false.
- UNKNOWN != PASS.
- no_auto_trade=true.
- Exact Jev lineage key: `source_workflow_run_id`.
- Deep idempotency key: `JEV_ORCHESTRATOR_<source_workflow_run_id>`.
- Orchestration cursor lifecycle:
  `JEV_READY -> ORCHESTRATION_PENDING -> DEEP_DISPATCH_ACCEPTED -> DEEP_COMPLETE -> TERMINAL_COMPLETE -> INVESTOR_OVERLAY_COMPLETE -> DECISION_CENTER_REFRESHED`.
- On future user message "继续": read live main / PRs / Actions, this file, Jev routing, and orchestration cursor; resume from the first unfinished stage without asking for background.
