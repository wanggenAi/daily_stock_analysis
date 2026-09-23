# Current Mission

## Goal
Close the post-Deep valuation/price loop so a non-holding that has all five hard gates PASS cannot stall at a preliminary research lead or disappear when a later Deep workset omits it.

The required chain is:
1. exact-current 5/5 hard-gate PASS;
2. valuation / price closure;
3. durable research BUY or WAIT_PRICE with explicit price threshold;
4. investor output persistence across later unrelated Deep runtimes;
5. Formal trading authority remains separate and no-auto-trade remains true.

## Current Phase
VALUATION_PRICE_CLOSURE_IMPLEMENTATION

## Source of Truth
- Live GitHub refs, Actions, artifacts, and persisted data override this checkpoint.
- Production persistence may advance main; re-read live main before merge/production verification.

## Last Verified Main
- Branch started from live main `06497599a91fb6e4d8513d24fe7c7086c0c1f0ac`.
- Previous #293 display-precedence mission is complete; do not reopen it.

## Active Branch
- `fix/valuation-price-closure-20260923`

## Active PR
- #294 `fix: close five-gate leads through valuation and price`.
- PR branch is intentionally based on the last code baseline; observed live-main drift before PR creation was production/data persistence only, with no overlapping code files.

## CI
- PR #294 newest-head CI is authoritative.
- First CI run `35870528630` failed only `ai-governance` because this checkpoint omitted the required `## CI` heading; backend/docker/web were skipped downstream.
- This checkpoint restores the required heading; re-read the next newest-head run before merge.
- No business/test failure has been observed yet.

## Production / Artifact
- Regression lineage: Jev `35849969346` -> Orchestrator `35850186518`; 603596 was 5/5 PASS + `RESEARCH:BUY` but stopped at NOOP.
- Historical 603596 Terminal result: research BUY + BUILD, conviction 0.945, advisory max 3%; Formal BUY=false.
- #294 production verification is pending merge and must prove durable closure plus `research_buy_price_ceiling`.

## Proven Production Defect
- `603596 伯特利` is the concrete regression case.
- Jev run `35849969346` saw it as HIGH attention, evidence `ADEQUATE_FOR_CURRENT_RESEARCH_STATE`, exact Deep 5/5 PASS, existing engine action `RESEARCH:BUY`, quant score 80.0059, PE 17.95 vs historical median reference 33.65.
- Jev had no valuation/price-closure route. It selected `DEEP_RESEARCH` with route confidence 0.46 while `needs_deep_research=false`.
- Orchestrator `35850186518` therefore converged to HUMAN_REVIEW / NOOP because 0.46 < 0.50.
- Historical terminal lineage had already produced research BUY + BUILD for 603596 (capital conviction 0.945, advisory max portfolio 3%), but later Deep runtime `35854781919` omitted 603596 from its requested workset.
- Current Three-Pillar output therefore regressed to preliminary 5/5-PASS / DO_NOT_BUY_YET visibility instead of preserving the prior valuation-closed research state.

## Root Cause
1. Jev routing schema only supports NO_ESCALATION / EVIDENCE_REFRESH / DEEP_RESEARCH / HUMAN_REVIEW.
2. There is no explicit `VALUATION_CLOSURE` route for 5/5-PASS names whose remaining work is price/valuation rather than evidence/deep research.
3. The deterministic orchestrator only dispatches Deep research and has no valuation-closure handoff.
4. Terminal research iterates the latest Deep `requested_codes`; a fully qualified candidate can lose its terminal BUY/WAIT_PRICE visibility when a later unrelated Deep workset does not request it.
5. Terminal valuation exposes PE discount logic but does not reverse-solve the existing BUY threshold into an explicit research buy-price ceiling.

## Required Fix
- Add `VALUATION_CLOSURE` to Jev typed routing with instructions that distinguish post-5/5 valuation work from more Deep/evidence work.
- Add deterministic override: exact 5/5 PASS + no failures/unknowns + research BUY/WAIT_PRICE may enter valuation closure even if Jev route confidence is below 0.50 or Jev mislabels it as DEEP_RESEARCH.
- Keep Deep dispatch and valuation-closure dispatch separate; valuation closure must not consume a hard-gate research strategy attempt.
- Reuse the existing Terminal research workflow rather than create a parallel valuation engine.
- Extend Terminal convergence so current 5/5-PASS priority follow-up candidates remain in valuation closure even when absent from the newest Deep requested workset.
- Reverse-solve the existing `PE_BUY_RATIO=0.80` into an explicit research buy-price ceiling when price/PE reference data are available.
- Persist enough lineage/reason fields to prove why a candidate was carried into closure.
- Preserve Formal Authority, UNKNOWN != PASS, and `no_auto_trade=true`.

## Acceptance Case
For a 603596-shaped state:
- all five hard gates PASS;
- research decision BUY;
- evidence adequate;
- P1 / urgent follow-up;
- Jev route confidence may be 0.46;
the deterministic plan must not send it to HUMAN_REVIEW merely due low route confidence and must not rerun Deep for already-resolved hard gates. It must request valuation/price closure.
A later Deep workset that excludes 603596 must not erase its valuation-closed research BUY/WAIT_PRICE state if its current profile remains 5/5 PASS and the priority follow-up is current.

## Completed
- Reconciled the user-reported behavior against live main and production Jev/Deep/Terminal artifacts.
- Confirmed this is a routing + terminal persistence defect, not a missing business-quality analysis problem.
- Created the fresh implementation branch from current live main.
- Recorded the defect and required acceptance behavior here before code changes.
- Added Jev `VALUATION_CLOSURE` typed route and price-reference context.
- Added deterministic 5/5-PASS valuation-closure override without lowering the global 0.50 Jev confidence gate.
- Added Terminal carry-forward for current 5/5-PASS priority follow-ups omitted by a later bounded Deep workset.
- Added explicit research buy-price ceiling derived from the existing `PE_BUY_RATIO=0.80` policy.
- Added 603596-shaped regression coverage across Jev schema, routing, orchestrator, workflow handoff, and Terminal persistence.
- Opened PR #294; CI/merge/production verification remain pending.

## Current Findings
- This is a post-Deep routing/persistence defect, not a hard-gate evidence deficiency.
- The fix preserves thresholds and reuses existing Terminal valuation rather than creating parallel authority.

## Blockers
- None requiring user action.

## Next Action
1. Read #294 newest-head CI and fix any real failures without weakening the contract.
2. Merge #294 only when blocking CI is green and the PR is mergeable.
3. Verify post-merge main checks.
4. Run/observe fresh production Jev -> deterministic Orchestrator -> Terminal -> Three-Pillar lineage.
5. Confirm 603596 reaches durable valuation closure rather than low-confidence HUMAN_REVIEW/NOOP or preliminary-only fallback.
6. Confirm Terminal exposes research BUY/WAIT_PRICE plus `research_buy_price_ceiling` while Formal BUY remains false.
7. Persist final production checkpoint in this file.

## Do Not Repeat
- Do not lower Jev 0.50 confidence threshold globally.
- Do not lower stock-selection or hard-gate thresholds to force BUY.
- Do not rerun already-PASS hard gates merely to obtain a newer Deep lineage.
- Do not promote Research BUY/WAIT_PRICE or advisory BUILD into Canonical Formal BUY.
- Do not create a second valuation engine if existing Terminal valuation can close the state.

## Guardrails
- Jev remains advisory.
- Deterministic guards own dispatch and closure eligibility.
- Formal actions remain Canonical-only; automatic Formal BUY=false.
- Research capital allocation remains advisory-only.
- UNKNOWN != PASS.
- no_auto_trade=true.
