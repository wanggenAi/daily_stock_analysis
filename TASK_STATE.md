# Current Mission

## Goal
Continue deep calculation for historical/current candidates and close only evidence gaps that can be repaired by engineering, without changing investment thresholds, valuation, Candidate Lifecycle, BUY/WAIT_PRICE/REJECT, or Formal authority.

## Current Phase
SSE bulletin transport recovery after production proved query-layer HTTP 403.

## Last Verified Main
`6a819f731fcee5c92d3c857bab91f80138aedfd6` at branch creation; live `main` remains authoritative.

## Last Verified Code Checkpoint
Current branch contains the SSE transport implementation and regression tests; CI has not yet run on this checkpoint.

## Active Branch
`fix/sse-bulletin-403-transport`

## Active PR
#189 — `fix: recover current SSE bulletin transport`

## CI
- #185 full CI `35406705085`: green; merged as `1710ff74203cf79cbeb306f9153783b6de490ac3`.
- #187 fresh reconciled full CI `35409178824`: green; targeted Opportunity `35409178972`: green; risk-capped `35409178944`: green.
- #187 merged as `afe052a2cf4f4dc48c8ceb8b34c52cb9a5806b35`.
- Current SSE transport branch still requires fresh targeted and blocking CI.

## Production / Artifact
- Research mapping durability remains verified at 118/118 mapped, 0 unmapped.
- Pre-#185 Deep baseline `35403919220`: predictability VERIFIED 0; company status 280 SOURCE_DATA_ABSENT + 219 SOURCE_FETCH_FAILED.
- Bound Deep history run `35408711645`, generated `2026-09-19T00:30:04Z`: 497 SOURCE_FETCH_FAILED + 2 SOURCE_DATA_ABSENT; its run-specific evidence records HTTP 403 from the legacy SSE `queryCompanyBulletin.do` metadata query for Shanghai issuers and CNINFO 403 for Shenzhen issuers.
- Bound Deep history run `35407967652`, generated `2026-09-19T00:47:32Z`: 277 PARSE_FAILED + 3 SOURCE_DATA_ABSENT + 219 SOURCE_FETCH_FAILED. Its run-specific evidence shows Shanghai metadata/material-event queries succeeded and reached official static SSE PDFs (then failed at `PdfStreamError` for sampled annual reports), while sampled Shenzhen issuer 001316 still used CNINFO and failed 403.
- These concurrent histories prove the legacy SSE query transport is unstable across runs rather than deterministically unavailable. They do not yet prove #187 production routing because the Shenzhen samples in both bound histories still use CNINFO.
- No run-specific persisted Deep evidence has yet been verified as originating from the post-#187 merge code path.

## Completed
- #179 moved Shanghai metadata routing from CNINFO to SSE.
- #185 fixed URL-aware PDF parsing and strict full-annual filtering; production proved the next bottleneck is earlier at SSE query transport.
- #186 fixed hourly research-mapping replay; production remains stable at 118/118.
- #187 moved Shenzhen 0/2/3 evidence to SZSE first-party disclosure APIs and merged after clean-main reconciliation plus fresh full CI.
- Current branch replaces the obsolete SSE bulletin endpoint with `queryCompanyBulletinNew.do`, uses the exact disclosure-page Referer, keeps `productId`, removes unreliable server-side date parameters, filters dates locally on `SSEDATE`, and shares bounded pagination across annual/material-event collection.
- SSE multi-year predictability now uses the full 2200-day research horizon instead of reusing a 560-day single-report query.
- Annual/material-event cache contracts are bumped so old 403 results cannot masquerade as current evidence.
- UNKNOWN remains fail-closed; no investment decision threshold or authority changed.

## Current Findings
- Production history exposes two sequential Shanghai bottlenecks depending on run: the legacy metadata query can 403, and when it succeeds the sampled annual-report fetch reaches the static PDF but pypdf can raise `PdfStreamError`. The transport instability is the current engineering target; parser work must wait for post-transport production evidence.
- Current public endpoint research indicates the active SSE bulletin path requires `queryCompanyBulletinNew.do`, `productId`, and the exact listed-announcement Referer; server-side begin/end date filters are not relied upon.
- A transport recovery is successful only when a post-merge Deep run moves SSE/SZSE failures to verified evidence or to a later honest UNKNOWN reason.

## Blockers
- Fresh CI has not yet validated the current branch.
- Production verification requires a new persisted Deep run after merge.

## Next Action
1. Open a PR from this branch.
2. Read targeted Opportunity / risk-capped / blocking CI; fix only real failures.
3. Merge only when fresh CI is fully green and PR is mergeable.
4. Inspect the automatic post-merge Deep persisted evidence; quantify Shanghai and Shenzhen separately.
5. Continue from the next real evidence bottleneck without loosening any gate.

## Do Not Repeat
- Do not change valuation, BUY/WAIT_PRICE/REJECT, Candidate Lifecycle, Capital Flow Routing, or Formal authority.
- Do not route Shanghai or Shenzhen back through CNINFO.
- Do not treat HTTP/parser/coverage UNKNOWN as PASS.
- Do not redo the resolved 118/118 mapping durability investigation.
- Do not rework the PDF parser unless new production evidence reaches PDF fetch/parsing and proves a parser defect.

## Guardrails
- Live GitHub main / PR / Actions / artifacts / persisted data are the source of truth.
- Keep provider changes fail-closed and preserve exact issuer/date/document provenance.
- Do not claim production recovery from unit tests alone; require persisted/artifact evidence.
