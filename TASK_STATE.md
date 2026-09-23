# Current Mission

## Goal
Complete the Jev Structured Entry Judgment loop on current production main, then verify a fresh TypeSafe/Jev production run and 603596 end to end without granting Formal or automatic trading authority.

## Current Phase
JEV_ENTRY_JUDGMENT_MAIN_REPLAY

## Source of Truth
- Live GitHub main/PR/Actions/artifacts override this checkpoint.
- Production persistence may advance main at any time; re-read live refs before merge and production verification.

## Last Verified Main
- Replay base: `cb29b5fa93cf939d6e0b00122b29e68ca64af37d`.
- #295 is merged; #294 is superseded/closed.
- #295 production closure is already visible on main.

## Active Branch
- `feat/jev-entry-judgment-main-replay-20260923`
- Replay commit before this checkpoint: `34fdac5b5e13f514ec8fc6b72d5a4b744f165862`.
- Replays only #296 net business/test/docs changes onto live main.

## Active PR
- New latest-main replay PR not yet opened at this checkpoint.
- #296 `feat: add validated Jev entry judgments` is implementation/CI evidence only; its branch is stale/diverged and must not be merged.

## CI
- Original #296 head `766d5a1d` passed Jev Shadow `35875174705`, Jev Orchestrator `35875174599`, and Three-Pillar `35875174632`.
- Fresh CI is still required on the latest-main replay head.

## Production / Artifact
- #295 valuation/price closure is production-visible.
- Current Jev routing includes exactly one `VALUATION_CLOSURE`: 603596 伯特利.
- Current Terminal source: `35872063645`; requested=16, research BUY=1, WAIT_PRICE=0, RESEARCH_GAP=15.
- 603596 is current research BUY and risk-budget BUILD, conviction=0.945, advisory max=3.0%.
- Current Decision Center reports the Terminal snapshot as current for runtime.
- Formal BUY remains false; no_auto_trade=true.

## Actual TypeSafe/Jev Use
- Current persisted Jev routing completed SUCCESS for 25 entities and routed 603596 to VALUATION_CLOSURE.
- Existing production TypeSafe/Jev path remains advisory only.
- Fresh post-merge V4 TypeSafe/Jev run is required before final acceptance.

## Completed
- #295 valuation closure merged.
- Durable 603596 research BUY/BUILD closure is production-visible.
- #296 typed entry-judgment implementation was completed and workflow-validated on its original head.
- Verified all #296 changed static files on live main still matched #296 base blobs before replay.
- Replayed schema/context/deterministic validator/persistence/report/tests/workflow changes onto current production main without copying stale runtime data.

## Current Findings
- The prerequisite valuation/price closure is no longer the blocker.
- Remaining work is latest-main CI/merge plus fresh production V4 Jev and 603596 entry-jJudgment acceptance.
- Jev categorical judgment may only be downgraded by deterministic guards; deterministic verified price/risk-budget data owns numeric entry thresholds and sizing.

## Blockers
- No user/login/approval blocker.
- Fresh replay PR + CI + merge + production V4 execution still pending.

## Next Action
1. Open replay PR against current main.
2. Require fresh newest-head blocking CI; fix any real failure.
3. Merge replay PR after re-reading live main and resolving any production-only divergence safely.
4. Trigger/observe fresh TypeSafe/Jev V4 production evaluation.
5. Verify deterministic routing persistence and current-lineage Three-Pillar rendering.
6. Verify 603596 answers buy-now-or-not, verified threshold, initial/max manual research size, do-not-chase, and invalidation.
7. Persist final TASK_STATE with live main SHA, Jev run IDs/artifacts, 603596 result, and remaining next action.

## Do Not Repeat
- Do not reopen #292/#293/#294.
- Do not merge stale #296 directly.
- Do not lower Jev 0.50 or hard-gate/selection thresholds to force a result.
- Do not rerun already-PASS hard gates only to manufacture newer lineage.
- Do not copy historical 603596 price/valuation into production as current truth.
- Do not promote Research BUY/BUILD/Jev entry judgment into Canonical Formal BUY.

## Guardrails
- Jev authority: ADVISORY_ONLY research routing + structured entry judgment.
- Deterministic code owns eligibility, lineage, price/sizing validation, dispatch, and authority boundaries.
- Formal actions remain Canonical-only; formal_buy_authorized=false.
- automatic_execution_allowed=false; no_auto_trade=true.
- UNKNOWN != PASS.
- Risk-budget sizing caps Jev suggestions.

## User-Facing Decision Reporting Contract
- For each leading candidate answer: buy now or not; exact verified price/evidence trigger; initial size; add condition; max size; do-not-chase; invalidation.
- If verified inputs cannot support a defensible trigger, report the missing evidence/unlock condition instead of inventing a number.

## Jev Structured Entry Judgment
- Typed judgment: `ENTRY_NOW | WAIT_PRICE | WAIT_EVIDENCE | DO_NOT_CHASE | INVALIDATED | NO_JUDGMENT`.
- Jev judges categorical attractiveness/state only.
- Deterministic code supplies/validates price zones and manual research sizing from current verified valuation/risk-budget inputs.
- Persist exact Jev/Deep/Terminal/valuation lineage and authority flags.

## 603596 Acceptance Case
- Fresh V4 Jev must evaluate current 603596 state.
- Prior BUY/BUILD and old 29.15 reference are regression evidence, not permission to fabricate current price truth.
- Completion requires current lineage, deterministic validation, persisted entry advisory, and actionable Three-Pillar output while Formal BUY remains false.

## Completion Criteria
- Latest-main replay merged with green CI.
- Fresh production TypeSafe/Jev V4 run exercises the new schema.
- 603596 end-to-end output is current, deterministic, persisted, and user-facing actionable.
- Final checkpoint records live main SHA, run IDs, artifact result, and next unfinished stage.
