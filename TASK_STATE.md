# Current Mission

## Goal
Turn the stock research system into a convergent autonomous opportunity engine that surfaces reference-worthy stock codes without fabricating certainty, forcing BUY, or presenting contradictory investor actions.

## Current Phase
TERMINAL_RESEARCH_DISPLAY_CONVERGENCE_COMPLETE

## Source of Truth
- Live GitHub refs, Actions, artifacts, and persisted data override this checkpoint.
- Production bot persistence may advance main after any recorded SHA.

## Last Verified Main
- Pre-checkpoint live main: `83b05e6ef28754d6c010f155c3eb2e16deca8edd`.
- PR #293 `fix: converge terminal research display precedence` is closed and its fix is present on main as `734c7ca2a2bf7b37830f25b930a4436c2266fda4`.
- Later main commits are production/report persistence; the latest verified Three-Pillar artifact is generated at `2026-09-23T12:02:50+00:00`.
- This checkpoint commit itself will advance main; live GitHub ref remains authoritative after the write.

## Active Branch
- None for this completed mission.
- Consumed branch: `fix/terminal-research-supersedes-qualified-20260923`; do not resume work on it.

## Active PR
- None for this completed mission.
- #293 is closed/merged into main.

## CI
- Final #293 branch head: `1e3f9506921996d1642784d297db9f0c9b7878d1`.
- Required CI run `35855835509`: SUCCESS.
- Jobs: Change Detection SUCCESS; ai-governance SUCCESS; backend-gate SUCCESS; docker-build SUCCESS; web-gate correctly SKIPPED.
- Same-head companion workflows all succeeded:
  - Three-Pillar Decision Center `35855835498`
  - Opportunity Discovery `35855835511`
  - Legacy Risk-Capped Research `35855835506`
- Earlier stalled CI `35851756202` finished CANCELLED and was not used as merge authorization.

## Production / Artifact
- Current Three-Pillar artifact: `data/decision_center/latest.json`, generated `2026-09-23T12:02:50+00:00`.
- `formal_action_source=FINALIZED_CANONICAL_ONLY`; `no_auto_trade=true`.
- Current terminal research source is Deep `35854781919`: 15 requested, BUY 0, WAIT_PRICE 0, RESEARCH_GAP 15, REJECT 0.
- Current preliminary Deep-qualified leads: exactly one, `603596 伯特利`, account action `DO_NOT_BUY_YET`, `formal_buy_authorized=false`, `no_auto_trade=true`.
- Current terminal-research codes and preliminary Deep-qualified codes have intersection size 0. No current-runtime code is displayed under both terminal and preliminary contradictory action layers.
- `603105 芯能科技` is the current risk-budget `PROBE` advisory: conviction 0.596, suggested portfolio cap 0.72%, while its research decision remains `RESEARCH_GAP`, authority remains `RESEARCH_ONLY / ADVISORY_ONLY`, and Formal BUY remains false.
- The exact historical overlap case (603596 terminal research BUY + BUILD plus preliminary qualification) is covered by the green #293 regression because the newer Deep terminal source no longer contains 603596.

## Actual TypeSafe/Jev Use
- Last relevant production TypeSafe/Jev execution remains run `35849969346`: SUCCESS, 25 entities, requested model `jev-latest`, served model `jev-1.13.0`.
- Exact deterministic Orchestrator run `35850186518` consumed that Jev lineage and returned `HUMAN_REVIEW / NOOP` because route confidence 0.46 was below the deterministic 0.50 dispatch gate.
- No new Jev evaluation was required for #293 because the remaining change was display precedence only; Jev selection, confidence, routing authority, thresholds, and research truth were unchanged.

## Completed
- #289 research-exhaustion dormancy merged and production-verified.
- #290 lifecycle visibility merged and production-verified.
- #291 Deep-qualified research visibility merged and production-verified.
- #292 Research Learning -> Jev wake handoff merged and production-verified.
- Fresh Jev + exact Orchestrator lineage `35849969346 -> 35850186518` verified.
- #293 display-precedence fix merged after fresh newest-head required CI passed.
- Post-merge production Three-Pillar refresh verified with zero terminal/preliminary code overlap.
- Formal authority, research/advisory authority separation, UNKNOWN != PASS, and no-auto-trade invariants remain intact.

## Current Findings
- The contradictory-display bug is closed.
- `603596 伯特利` remains a reference-worthy research lead in the preliminary Deep-qualified layer, not a Formal BUY.
- `603105 芯能科技` currently has a bounded manual PROBE advisory, not a Formal BUY.
- There is currently no Canonical Formal new-stock BUY or WAIT_PRICE in the verified Three-Pillar artifact.
- The system now exposes research-worthy names without duplicating a current terminal decision with the stale preliminary `DO_NOT_BUY_YET` stage.

## Blockers
- None for this mission.

## Next Action
- None for the #293 display-convergence mission; it is at terminal state.
- Any new research/selection iteration must start from live main, latest production artifacts, and latest Jev/Deep lineage rather than reopening the consumed #293 branch.

## Do Not Repeat
- Do not reopen or reuse #292 or #293 implementation branches.
- Do not rerun old Jev lineage and call it fresh production verification.
- Do not lower the Jev 0.50 confidence gate or any stock-selection threshold.
- Do not promote research BUY, PROBE, or Deep-qualified visibility into Formal BUY.
- Do not remove the risk-budget advisory layer to simplify display semantics.
- Do not treat cancelled/stalled CI as green.

## Guardrails
- Jev is advisory research routing only; deterministic guards own dispatch.
- Formal actions remain Canonical-only; automatic Formal BUY=false.
- Research capital allocation remains advisory-only and cannot create holding-add or order authority.
- UNKNOWN != PASS; no_auto_trade=true.
- Current terminal research decisions supersede preliminary research-qualified display for the same code and exact Deep runtime.


## User-Facing Decision Reporting Contract
- Stock-result reporting must not stop at vague labels such as "most worth watching", "focus on", or "continue tracking".
- For every leading candidate, the report must answer the execution question explicitly: **when to buy, at what verified trigger/price condition, initial size, add condition, do-not-chase condition, and invalidation/stop condition**.
- If current evidence is insufficient to calculate a defensible buy trigger, say exactly which missing evidence prevents the trigger and what future event would unlock it. Do not substitute "worth watching" for an executable decision rule.
- Research/advisory triggers must remain clearly separated from Canonical Formal BUY authority and automatic execution authority.

## 603596 伯特利 Execution Checkpoint
- Current state: Deep-qualified research lead, 5/5 hard gates PASS, but current account action remains `DO_NOT_BUY_YET`; current Formal BUY authorization=false.
- Last validated terminal BUY/BUILD lineage: Deep `35849124866`.
- In that lineage:
  - research_decision=`BUY`
  - capital action=`BUILD`
  - capital conviction=0.945
  - suggested maximum portfolio weight=3%
  - reference price=29.15 CNY
  - current PE at that snapshot=17.95
  - historical median PE reference=33.65
  - PE/history ratio=0.5334
  - all five hard gates PASS
- User-facing execution rule to preserve across future sessions:
  1. **Do not buy solely because 603596 is "the best research lead".**
  2. First-buy trigger requires a fresh/current Terminal Research result that again confirms `BUY + BUILD` with all 5/5 hard gates still PASS.
  3. If that confirmation occurs while price is at or below the prior validated 29.15 CNY reference zone, first manual tranche may be sized around 1% of account equity.
  4. Around 27.3 CNY, if the same 5/5 PASS research thesis remains current and no invalidating evidence appears, a second manual tranche around 1% may be considered.
  5. Total manual exposure under this checkpoint should not exceed the prior advisory cap of 3% unless a newer validated risk-budget result changes the cap.
  6. If confirmation has not occurred and price has already risen above roughly 32.8 CNY, do not chase; rerun valuation/research before any entry.
  7. If any critical or hard gate degrades from PASS to UNKNOWN/FAIL, stop new buying and invalidate the above entry plan until revalidated.
- The 27.3 / 32.8 CNY levels are execution guardrail zones derived from the prior validated valuation reference, not Canonical Formal orders and not automatic-trading authority.
