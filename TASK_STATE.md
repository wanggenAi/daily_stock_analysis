# Current Mission

## Goal
Continue deep calculation for historical/current candidates and close only engineering-repairable evidence gaps without changing valuation, Candidate Lifecycle, BUY/WAIT_PRICE/REJECT, or Formal authority.

## Current Phase
Clean integration of SSE bulletin transport recovery (#189) onto live main after production-state commits diverged the original branch.

## Last Verified Main
`2229793793b5ac6ed10c7ccb17b40717a6e64a28` at clean-integration base; live `main` remains authoritative.

## Last Verified Code Checkpoint
Original #189 head `067a6beef38210677ab157fbebd9936aab40adda` contains the intended SSE transport code/tests. Its targeted Opportunity run `35410799477` and risk-capped run `35410799605` are green; blocking CI `35410799511` had ai-governance and Docker green with backend offline tests still running when the clean integration was created.

## Active Branch
`fix/sse-bulletin-403-transport`; original lineage preserved at `checkpoint/sse-pre-reconcile-067a6be`.

## Active PR
#189 — `fix: recover current SSE bulletin transport`.

## CI
- #187 is merged after fresh green CI.
- Original #189 targeted Opportunity and risk-capped checks are green.
- Fresh blocking + targeted CI is required on the clean integration head before merge.

## Production / Artifact
- Research mapping durability remains 118/118 mapped, 0 unmapped.
- Deep run `35408711645` exposed legacy SSE metadata HTTP 403 and the structural 850-requested / 500-profile continuity gap.
- Deep run `35407967652` reached official SSE PDFs for sampled Shanghai issuers but exposed later PDF parse failures; sampled Shenzhen still reflected pre-#187 CNINFO routing.
- Latest decision-center refresh references Deep run `35407972654` from EVIDENCE_LAYER_CHANGE with requested=0 and a mismatched prior terminal snapshot; it is not evidence that #189 provider recovery works.
- No post-#189 merged Deep evidence exists yet.

## Completed
- #185 repaired SSE PDF URL-aware extraction and strict annual-report filtering.
- #186 preserved industry mapping; production remains 118/118.
- #187 moved Shenzhen primary evidence to SZSE and is merged.
- #189 code replaces legacy SSE `queryCompanyBulletin.do` with `queryCompanyBulletinNew.do`, exact disclosure Referer + productId, client-side SSEDATE filtering, bounded fail-closed pagination, JSON/JSONP decoding, official static URL normalization, 2200-day predictability history, and cache invalidation.
- Original #189 lineage is preserved before reconciliation.
- UNKNOWN remains fail-closed; no decision threshold or authority changed.

## Current Findings
- #189's pre-reconcile merge failure was branch topology / TASK_STATE divergence after production-state commits, not a newly observed business-code conflict.
- Provider transport and Deep workset continuity are separate defects. #189 should close transport first; #188 remains the workset-continuity follow-up.
- PDF parser changes remain deferred until post-#189 production evidence proves the next bottleneck is parsing.

## Blockers
- Fresh CI must pass on the clean #189 integration head.
- Production recovery requires a non-empty post-merge Deep run and persisted evidence.

## Next Action
1. Run/observe fresh targeted and blocking CI on the clean #189 head; fix only real failures.
2. Merge #189 only when green and mergeable.
3. Inspect the first non-empty post-merge Deep persisted evidence, separating Shanghai/SZSE outcomes.
4. Then reconcile #188 onto live main and verify the 850-requested / 500-profile structural gap is removed.
5. Continue only from the next measured evidence bottleneck.

## Do Not Repeat
- Do not change valuation, BUY/WAIT_PRICE/REJECT, Candidate Lifecycle, Capital Flow Routing, or Formal authority.
- Do not route Shanghai or Shenzhen primary-exchange evidence back through CNINFO.
- Do not treat HTTP/parser/coverage UNKNOWN as PASS.
- Do not redo the resolved 118/118 mapping investigation.
- Do not modify the PDF parser without new production evidence.

## Guardrails
- Live GitHub main / PR / Actions / artifacts / persisted data are the source of truth.
- Keep provider changes fail-closed with exact issuer/date/document provenance.
- Tests are necessary but not production proof.
