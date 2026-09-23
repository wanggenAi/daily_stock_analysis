# Current Mission

## Goal
Turn the stock research system into a convergent autonomous opportunity engine that surfaces reference-worthy stock codes without fabricating certainty or forcing BUY.

Solve together:
1. Autonomous research closure for active non-holding RESEARCH_GAP candidates until progression, hard-gate FAIL, or deterministic exhaustion.
2. Candidate-funnel health: explain real stage attrition before changing thresholds.

## Current Phase
JEV_DEEP_CLOSURE_PRODUCTION_VALIDATION_AND_FUNNEL_AUDIT

## Source of Truth
- Live GitHub refs, Actions, artifacts, and persisted data override this checkpoint.
- Production bots can advance main after any recorded SHA; always re-read live main before writes, merge, or verification.

## Last Verified Main
- #283 hand persisted Jev routing to deterministic orchestrator merged as 95be7f92d91fc0e03ac895f7c02c9abe75ba4a2e.
- #286 keep UNKNOWN gate retries inside research ledger merged as 81a638bb61a8410af9e64898beb6b1cdb2e4f1ea.
- #287 persist accepted Jev continuation cursor passed blocking CI and merged as f6e4cc465d1019c214479ab7bc2b49d8ff922000.
- Live main may already be newer due runtime persistence.

## Active Branch
- Branch: fix/deep-profile-gate-authority-20260923.

## Active PR
- PR #288: fix: trust exact Deep gate status over stale retry hints.
- Branch started from main 9513dfd09d8731e998145694d92cb131f7c5002e; do not treat that as current main.
- #288 changes research scheduling only: exact Deep PASS/FAIL removes stale upstream unresolved retry scope; UNKNOWN remains researchable.

## CI
- #283 blocking PR CI: PASS.
- #286 blocking PR CI: PASS.
- #287 blocking PR CI: PASS (ai-governance/backend/docker; web-gate skipped by path).
- #288 latest-head CI must be read live before merge; never infer green from this checkpoint.

## Production / Artifact
- Confirmed full Every-Industry source: run `35776816635`.
- Funnel artifact: 4514 valid stocks -> 843 merged valuation-research rows -> 500 V3.1 Deep rows; Deep processed 500/500 with missing=0, complete=1, partial=499 and 2291 unresolved requested hard gates.
- Current production Deep: `35823336693`, SUCCESS; requested=6, processed=6, missing=0, BUY=0 / WAIT_PRICE=0 / RESEARCH_GAP=6 / REJECT=0.
- Current deterministic orchestration: `35823998354`, NOOP / WAIT_FOR_NEW_RESEARCH_STATE because no novel strategy remains in the current evidence epoch for the high-priority rows.
- Research mapping now has explicit industry mapping for 126/126 active candidates; old mapping-gap counts are no longer the dominant bottleneck.
- Candidate lifecycle remains active=126, archived/invalidated=0; durable exhaustion-to-dormancy semantics remain unfinished.

## Actual TypeSafe/Jev Use
- Jev run 35817253869 actually executed and persisted data/jev_shadow/latest_routing.json with continuation_from_deep_run_id=35816583696.
- #283 makes successful persisted Jev routing explicitly dispatch the deterministic Research Orchestrator by source run id.
- #287 persists the exact accepted continuation Jev run id into the orchestration cursor.
- Jev remains advisory only; deterministic code owns dispatch eligibility and no trading authority is granted.

## Current Findings
- Broad recall is no longer the largest observed loss: 500/500 Every-Industry Deep candidates were processed without missing workset rows.
- The dominant broad-funnel loss is evidence closure: 499/500 remained partial with 2291 unresolved requested hard gates.
- The Jev/ledger autonomous continuation is live and converges: current orchestration is NOOP when no novel strategy remains in the same evidence epoch.
- A remaining retry-scope defect is isolated in #288: stale routing missing-evidence text can still name a gate already PASS/FAIL in the exact Deep profile.
- Live example 603105 has exact PASS on earnings_authenticity, financial_safety and predictability; only long_term_demand and moat remain UNKNOWN.
- Lifecycle still has 126 ACTIVE and zero archived/invalidated, so exhausted non-holding dormancy/reactivation remains a real unfinished success criterion.
- These are research-control diagnostics, not investment recommendations.

## Completed
- Reconciled stale TASK_STATE against live main, open PRs, Actions, persisted Jev routing, orchestration ledger, Deep status, Terminal state, and production observability.
- Did not return to old consumed branches.
- Merged #283, #286, #287 only after their blocking CI was green.
- Opened #288 from a fresh live-main checkpoint with source fix, live-shaped regression tests, changelog, and Jev routing contract documentation.

## Blockers
- No user-only blocker. #288 must pass latest-head blocking CI before merge; production continuation must remain lineage-consistent.

## Next Action
1. Finish #288 latest-head blocking CI; merge only if green and mergeable.
2. Verify post-merge main push checks and the next real Jev -> deterministic orchestrator handoff.
3. Confirm fresh orchestration no longer spends Deep capacity on profile-missing codes and does not retry exact PASS/FAIL gates.
4. Compare new requested_profile_count / processed_requested_count / missing_requested_codes against Deep 35816583696.
5. Continue stage-by-stage funnel audit from confirmed All-A / Every-Industry artifacts and quantify the next largest attrition point.
6. Trace Runbei plus multiple current priority/near-buy candidates end-to-end after the corrected orchestration epoch.
7. Implement durable dormant/excluded semantics and deterministic reactivation for exhausted non-holdings if still absent after corrected research closure.
8. Surface final strategy-attempt/progression/exclusion evidence in investor outputs where not already present.

## Do Not Repeat
- Do not reopen #268/#269/#270/#271/#283/#286/#287 without a newly proven regression.
- Do not dispatch duplicate Deep/Jev work when persisted lineage proves it already happened.
- Do not lower thresholds just to force BUY/WAIT_PRICE.
- Do not label missing evidence as business-quality FAIL.

## Guardrails
- Jev is advisory research routing only; deterministic guards own dispatch.
- Formal actions remain Canonical-only; automatic Formal BUY=false.
- UNKNOWN != PASS; no_auto_trade=true.
- Missing evidence is not FAIL.
- Exact Deep profile PASS/FAIL must not be reopened by stale routing missing-evidence text.
- Exhausted non-holdings must eventually leave ACTIVE; holdings must never be silently dropped.
