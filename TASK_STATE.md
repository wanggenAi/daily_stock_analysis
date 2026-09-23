# Current Mission

## Goal
Turn the stock research system into a convergent autonomous opportunity engine that surfaces reference-worthy stock codes without fabricating certainty or forcing BUY.

## Current Phase
DEEP_QUALIFIED_RESEARCH_VISIBILITY_AND_ROUTING

## Source of Truth
- Live GitHub refs, Actions, artifacts, and persisted data override this checkpoint.
- Production bot persistence may advance main after any recorded SHA.

## Last Verified Main
- PR #289 merged and production-verified research-exhaustion dormancy.
- PR #290 merged and production-verified lifecycle visibility in the final decision center.
- Main was re-read at `84c68d3937ca9f1cfb5e632a7bbe2c274dd9efdb` before this branch was created; re-read live main before merge/write verification.

## Active Branch
- `fix/deep-qualified-research-visibility-20260923`
- Scope: route current-runtime five-hard-gate PASS research leads into priority ordering and expose them in the final decision center without creating BUY/WAIT_PRICE authority.

## Active PR
- Not opened yet at this checkpoint; open after branch tests/contracts are committed.

## CI
- Previous main CI run `35837313841` was still in progress when this branch started; governance and Docker were green, backend-gate was still running.
- Branch CI has not yet run. Required focused suites: research-priority routing and three-pillar runtime, then repository blocking CI.
- Governance heading is intentionally present in this checkpoint.

## Production / Artifact
- Candidate lifecycle is converged: ACTIVE=123, DORMANT=3, ARCHIVED/INVALIDATED=0.
- DORMANT: 600816 建元信托, 601020 华钰矿业, 000504 南华生物; current holdings remain ACTIVE.
- Canonical snapshot `538269c3908f97c328d1`: discovery=533, deep_review=382, production=0, holdings=4.
- Every-Industry run `35829289957`: 843 valuation-research rows -> 500 Deep rows; 500/500 processed.
- 603596 伯特利 is the only nonholding in that 500-row workset with all five Deep hard gates PASS. It still has no Formal BUY/WAIT_PRICE because valuation/price/authority closure is not complete.

## Actual TypeSafe/Jev Use
- Current persisted Jev path uses TypeSafe and served model `jev-1.13.0`.
- 001316 润贝航科 is P0/HIGH-attention but evidence remains insufficient; deterministic strategy ledger currently reports no novel supported strategy in its evidence epoch.
- Jev remains advisory-only; deterministic guards own dispatch; Formal trading authority remains false.
- Current fix makes exact-current-runtime five-gate PASS candidates visible to the research-priority queue so future bounded Jev runs do not lose them behind generic P3 ordering.

## Completed
- #289 dormancy implementation merged and production-verified.
- #290 lifecycle display implementation merged and production-verified.
- Full-A funnel audit traced 4514 valid -> 843 valuation research -> 500 Deep -> 1 five-gate-complete nonholding research lead.
- Root cause identified: research-priority router did not consume current Deep qualification, and final decision center had no research-only display layer for fully resolved hard gates without Formal authority.

## Current Findings
- Dominant issue is not broad discovery recall and should not be fixed by lowering thresholds.
- 603596 伯特利: all five Deep hard gates PASS in current persisted profiles; generic valuation remains non-authoritative/incomplete, so BUY/WAIT_PRICE must remain absent.
- 001316 润贝航科 remains visible and high priority; its remaining problem is evidence closure, not discovery loss.
- A trustworthy report needs a distinct research-qualified layer between hard-gate completion and Formal trading action.

## In Progress
- Research priority: exact current successful Deep profile with 5/5 PASS receives research-order-only boost; stale lineage or UNKNOWN receives none.
- Decision center: expose nonholding 5/5 PASS profiles as RESEARCH_ONLY / DO_NOT_BUY_YET leads while keeping Canonical BUY/WAIT_PRICE unchanged.
- Add regression tests for current lineage, stale lineage, UNKNOWN != PASS, and authority separation.

## Blockers
- No user/login/approval blocker.
- Merge remains blocked until PR CI is green.

## Next Action
1. Open PR and run focused/blocking CI.
2. Fix any regression without weakening authority or evidence rules.
3. Merge only after blocking CI is green.
4. Dispatch/rebuild Research Learning on production main and verify 603596 enters the research-priority/Jev candidate window.
5. Verify a fresh TypeSafe/Jev -> deterministic Orchestrator cycle and record whether 603596 receives a useful route or truthful NOOP.
6. Rebuild/verify Three-Pillar Decision Center and confirm 603596 is visible only as a research-qualified lead, never as Formal BUY/WAIT_PRICE.
7. Persist the final production checkpoint and continue valuation-closure work only if a supported evidence/model path exists.

## Do Not Repeat
- Do not reopen consumed old branches or PRs without a newly proven regression.
- Do not lower thresholds to force BUY/WAIT_PRICE.
- Do not label missing evidence as FAIL.
- Do not treat a research-qualified lead as a trading recommendation or Formal action.

## Guardrails
- Jev is advisory research routing only; deterministic guards own dispatch.
- Formal actions remain Canonical-only; automatic Formal BUY=false.
- UNKNOWN != PASS; no_auto_trade=true.
- Missing evidence is not business-quality FAIL.
- Exact Deep PASS/FAIL cannot be reopened by stale routing text.
- Deep-qualified priority is research-order only and requires exact current successful runtime lineage.
- Exhausted non-holdings may dorm only with exact current-epoch ledger proof; holdings must never silently leave ACTIVE.
