# Current Mission

## Goal
Continue deep calculation for historical/current candidates and close only engineering-repairable evidence gaps without changing valuation, Candidate Lifecycle, BUY/WAIT_PRICE/REJECT, or Formal authority.

## Current Phase
Deep workset continuity recovery: preserve retained historical/current research codes through the bounded valuation/V3.1 handoff so requested Deep work cannot silently collapse from 850 codes to 500 profiles.

## Last Verified Main
`aaac167ce81102fc8397822f840c7c9f6088f5a0` (#189 merged); live `main` remains authoritative.

## Last Verified Code Checkpoint
#188 code checkpoint `3ae4578ff46867a24fceee1990bb27d9027a8a06` passed full CI `35410349544`, targeted Opportunity `35410349351`, risk-capped `35410349397`, and Candidate Terminal `35410349437`. Old lineage is preserved at `checkpoint/deep-continuity-pre-reconcile-b51963e`.

## Active Branch
`fix/deep-continuity-materialization`.

## Active PR
#188 — `fix: preserve deep workset through bounded review handoff`.

## CI
- #189 clean integration head passed CI `35411251999`, Opportunity `35411252058`, and risk-capped `35411252021`; merged as `aaac167ce81102fc8397822f840c7c9f6088f5a0`.
- #188 pre-reconcile code checkpoint is fully green.
- Fresh CI is required on this clean #188 integration head before merge.

## Production / Artifact
- Mapping durability remains 118/118 mapped, 0 unmapped.
- Production Deep run `35408711645` requested 850 codes but produced only 500 profiles; 351 requested codes were absent from the Deep profile set.
- Reconciliation proved 349/351 missing profiles were present in the same-run 4,505-row All-A quant source; the remaining 2 (601995, 605050) were present in the same-run universe. Missing-nowhere = 0.
- Therefore the 850→500 loss is an upstream bounded handoff/materialization defect, not absence from the current market universe.
- #189 post-merge production Deep runs `35412424204` (push) and `35412428540` (EVIDENCE_LAYER_CHANGE) are running; provider recovery is not yet claimed until persisted evidence is inspected.

## Completed
- #185 repaired SSE PDF URL-aware extraction and annual-report filtering.
- #186 preserved industry mapping; production remains 118/118.
- #187 moved Shenzhen primary evidence to SZSE.
- #189 repaired current SSE bulletin transport and is merged after clean full CI.
- #188 implementation makes ACTIVE lifecycle recall additive in valuation research, preserves recall provenance, and re-materializes retained Deep continuity codes beyond the ordinary V3.1 review limit from the exact same-run All-A quant source with universe fallback.
- Re-materialized continuity rows are research-only: formal_signal_eligible=false, automatic_promotion_allowed=false, no_auto_trade=true; no PASS/valuation fact is synthesized.
- UNKNOWN remains fail-closed.

## Current Findings
- Deep continuity is a memory/materialization contract, not a ranking bonus.
- Ordinary bounded review limits may still govern new daily discovery, but already-retained unresolved Deep codes must remain additive until explicitly resolved/retired.
- #188 and #189 are independent: #189 repairs provider transport; #188 repairs the structural workset drop.

## Blockers
- Fresh CI must pass on the clean #188 integration head.
- Production verification must show the requested/profile gap materially closes; unit tests alone are not proof.
- #189 provider production evidence is concurrently running and should be inspected before attributing remaining UNKNOWN reasons.

## Next Action
1. Run/observe fresh targeted + blocking CI for #188; fix only real failures.
2. Merge only when green and mergeable.
3. Inspect post-merge Deep persisted evidence and compare requested_count, profile_count, REQUESTED_CODE_NOT_PRESENT_IN_DEEP_PROFILE, and continuity coverage against the 850/500/351 baseline.
4. Separately inspect #189 Shanghai/SZSE provider outcomes from the first non-empty post-merge Deep evidence.
5. Continue from the next measured bottleneck without loosening gates.

## Do Not Repeat
- Do not change valuation, BUY/WAIT_PRICE/REJECT, Candidate Lifecycle, Capital Flow Routing, or Formal authority.
- Do not turn retained continuity into automatic promotion or trading authority.
- Do not manufacture valuation evidence for re-materialized rows.
- Do not treat HTTP/parser/coverage UNKNOWN as PASS.
- Do not redo the resolved 118/118 mapping investigation.

## Guardrails
- Live GitHub main / PR / Actions / artifacts / persisted data are the source of truth.
- Preserve same-run provenance for continuity materialization.
- Tests are necessary but production artifact evidence is required.
