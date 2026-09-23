# Current Mission

## Goal
Build a convergent autonomous stock opportunity engine that returns actionable research entry judgments without fabricating certainty or granting Jev/Formal/automatic trading authority.

## Current Phase
JEV_ENTRY_JUDGMENT_IMPLEMENTATION

## Source of Truth
- Live GitHub main/PR/Actions/artifacts override this checkpoint.
- Production persistence may advance main; re-read live refs before merge and production verification.

## Last Verified Main
- Replay base: `f97730bcd11bc46de4e17ef30b39ddc0a0e3bcfd`.
- Live main has since advanced by production/report persistence; re-read before merge.
- #293 display-precedence mission is complete.

## Active Branch
- `feat/jev-entry-judgment-20260923`, stacked on the current #295 head while prerequisite CI/merge completes.
- #295 branch is the valuation/price-closure prerequisite; #294 remains superseded.

## Active PR
- #295 `fix: replay valuation and price closure on current main` is the prerequisite PR.
- #296 `feat: add validated Jev entry judgments` is open from `feat/jev-entry-judgment-20260923`, currently stacked on #295 to isolate the feature diff; retarget to main after #295 merges.

## CI
- #295 first CI `35873089047` failed only ai-governance because TASK_STATE exceeded the 120-line limit.
- No business/test failure was observed in that run; downstream jobs were skipped by the governance gate.
- #294 companion evidence was green: Jev Shadow `35870891406`, Jev Orchestrator `35870891764`, Opportunity Discovery `35870891162`, Legacy Risk-Capped `35870891108`.
- Require fresh newest-head #295 blocking CI before merge.

## Production / Artifact
- Latest known Deep terminal source before #295 merge: `35869903181`; 15 requested, BUY 0, WAIT_PRICE 0, RESEARCH_GAP 15.
- 603596 伯特利 remains current 5/5-PASS Deep-qualified research lead but preliminary `DO_NOT_BUY_YET`.
- Historical validated 603596 lineage `35849124866`: research BUY + BUILD, conviction 0.945, advisory cap 3%, reference price 29.15, PE 17.95 vs historical median PE 33.65.
- Formal BUY=false; no_auto_trade=true.

## Actual TypeSafe/Jev Use
- Last relevant production Jev: `35849969346`, SUCCESS, 25 entities, requested `jev-latest`, served `jev-1.13.0`.
- Orchestrator `35850186518` consumed that lineage but returned HUMAN_REVIEW/NOOP because route confidence 0.46 < 0.50.
- #295 adds a typed `VALUATION_CLOSURE` route plus deterministic 5/5-PASS closure override; it does not lower the global 0.50 gate.

## Completed
- #289 dormancy, #290 lifecycle visibility, #291 Deep-qualified visibility, #292 Jev wake handoff, #293 display precedence are merged/verified.
- #294 root cause isolated: post-Deep 5/5-PASS candidates could stall because Jev lacked valuation closure and later Deep worksets could erase terminal visibility.
- #294 net implementation replayed onto current-main branch without stale production data or stale TASK_STATE.
- Replay includes Jev VALUATION_CLOSURE, price-reference context, deterministic closure handoff, Terminal carry-forward, research buy-price ceiling, and 603596 regressions.
- Entry implementation in progress: Jev V4 typed `entry_judgment`, valuation/risk-budget/source-lineage context, deterministic validator, persisted routing fields, Three-Pillar current-lineage display, workflow guard assertions, regression tests, docs and changelog are on the feature branch.

## Current Findings
- Valuation/price closure is a prerequisite for the larger Jev Entry Judgment mission, not the endpoint.
- TypeSafe System One is used for typed judgments; deterministic code must derive/validate price and sizing fields from verified inputs rather than allow unsupported numeric invention.

## Blockers
- No user/login/approval blocker.
- #295 must merge before the entry-judgment PR can become a clean main-targeting PR.

## Next Action
1. Require newest-head #295 CI green, merge it, and production-verify valuation closure.
2. Run stacked entry-judgment PR CI and fix all failures.
3. Retarget/replay entry PR onto live main after #295 merge.
4. Merge only with green blocking CI.
5. Verify fresh production Jev V4 -> persisted routing -> deterministic entry validation -> Three-Pillar.
6. Verify 603596 end-to-end actionable result and authority guards.
7. Persist final checkpoint.

## Do Not Repeat
- Do not reopen #292/#293/#294 branches.
- Do not lower Jev 0.50 or stock/hard-gate thresholds to force a result.
- Do not rerun already-PASS hard gates merely for newer lineage.
- Do not promote research BUY/PROBE/Jev judgment into Canonical Formal BUY.
- Do not copy historical 603596 price/valuation into production as if current.

## Guardrails
- Jev authority: advisory research routing + structured entry judgment only.
- Deterministic code owns eligibility, price/sizing validation, dispatch, and authority boundaries.
- Formal actions remain Canonical-only; automatic_formal_buy_allowed=false.
- UNKNOWN != PASS; no_auto_trade=true.
- Risk-budget sizing is advisory-only and caps Jev suggestions.

## User-Facing Decision Reporting Contract
- Never stop at “most worth watching / focus on / continue tracking”.
- For each leading candidate answer: buy now or not; exact price/evidence trigger; initial size; add condition; max size; do-not-chase condition; invalidation condition.
- If inputs cannot support a defensible trigger, state the missing evidence and unlock condition instead of inventing a number.

## Jev Structured Entry Judgment
- Required typed judgment: `ENTRY_NOW | WAIT_PRICE | WAIT_EVIDENCE | DO_NOT_CHASE | INVALIDATED | NO_JUDGMENT`.
- Jev judges attractiveness/state; deterministic code supplies or validates numeric price zones and position sizes from current verified valuation/risk-budget inputs.
- Persist exact Jev/Deep/Terminal/valuation lineage and explicit `authority=ADVISORY_ONLY`, `formal_buy_authorized=false`, `automatic_execution_allowed=false`, `no_auto_trade=true`.
- Required actionable fields when supported: entry reason/trigger, price zone, initial manual position %, add condition, max manual %, do-not-chase condition, invalidation condition, judgment confidence.
- Stale/contradictory/unsupported inputs must become WAIT_EVIDENCE or NO_JUDGMENT; UNKNOWN never becomes PASS.
- Jev may suggest less than the deterministic risk-budget cap, never more.

## 603596 Acceptance Case
- Fresh/current evidence must determine whether 603596 is ENTRY_NOW, WAIT_PRICE, WAIT_EVIDENCE, DO_NOT_CHASE, or INVALIDATED.
- Prior 5/5 PASS + BUY/BUILD + 29.15 reference is regression evidence only, not current truth.
- Completion requires fresh production Jev using the new schema, deterministic validation, persisted lineage, and user-facing actionable entry conditions while Formal BUY remains false.

## Completion Criteria
- #295 valuation closure merged and production-verified.
- Entry-judgment typed schema/context/validator/persistence/report/tests merged with green CI.
- Fresh production TypeSafe/Jev run exercises it.
- 603596 end-to-end output answers “when to buy” or exactly why no defensible trigger exists.
- Final TASK_STATE records live main SHA, Jev run, downstream artifact, result, and no remaining blocker.
