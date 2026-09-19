# Current Mission

## Goal
Continue deep calculation for historical/current candidates and close only evidence gaps that can be repaired by engineering, without changing investment thresholds, valuation, Candidate Lifecycle, BUY/WAIT_PRICE/REJECT, or Formal authority.

## Current Phase
Primary-exchange evidence recovery — #185 merged; #187 reconciled onto latest verified main and awaiting fresh integration CI / production verification.

## Last Verified Main
`11e9923ac46da28b34e93fc05aec82cef28d820f` (live `main` remains authoritative).

## Last Verified Code Checkpoint
#187 pre-reconcile code head `574edc2b145cca3c2ec56b0ed154360032039a4b` passed targeted and full CI. The clean integration lineage is based on current main and will receive fresh CI after this checkpoint.

## Active Branch
`fix/szse-primary-disclosures` (integration source branch: `fix/szse-primary-disclosures-integration`; old lineage preserved at `checkpoint/szse-pre-reconcile-c51d57b`).

## Active PR
#187 — `fix: use SZSE primary disclosures for Shenzhen evidence`.

## CI
- #185 full CI run `35406705085`: green; targeted Opportunity run `35406705021`: green; merged.
- #187 pre-reconcile full CI run `35407091156`: green; targeted Opportunity run `35407091433`: green.
- Fresh CI is required on the reconciled #187 head before merge.

## Production / Artifact
- #186 mapping durability fix is merged; production research mapping remains 118/118 mapped, 0 unmapped.
- #185 merged as `1710ff74203cf79cbeb306f9153783b6de490ac3`.
- Latest persisted Deep status is still baseline run `35403919220`, generated `2026-09-18T23:42:57Z`; no post-#185 Deep persistence has appeared yet.
- Baseline: predictability VERIFIED 0; company extraction = 280 SOURCE_DATA_ABSENT + 219 SOURCE_FETCH_FAILED; predictability reasons = 280 INSUFFICIENT_CONSECUTIVE_COMPLETE_FISCAL_YEARS + 219 ANNUAL_REPORT_QUERY_FAILED:HTTPError.

## Completed
- #179 moved Shanghai annual-report/material-event metadata queries from CNINFO to SSE.
- #185 fixed SSE PDF source-URL detection, typed extraction propagation/cache contract, and strict full-annual title filtering; merged after full CI.
- #186 fixed Hourly Overlay mapping replay; production mapping verified stable at 118/118.
- #187 implementation routes Shenzhen 0/2/3 securities to SZSE first-party disclosure APIs, uses fixed_disc + 010301 for annual reports, normalizes official attachments through disc.static.szse.cn/download, enforces exact secCode/date/schema checks, preserves pagination completeness, avoids CNINFO orgId calls on primary-exchange routes, and keeps exchange-specific UNKNOWN provenance.
- #187 old stacked lineage was preserved at `checkpoint/szse-pre-reconcile-c51d57b`; a clean integration lineage was rebuilt from current main using only the intended SZSE code/tests.
- UNKNOWN remains fail-closed; no investment decision thresholds or authority were changed.

## Current Findings
- #185 is code-complete and merged, but production Deep has not yet persisted a post-merge result, so SSE recovery is not yet claimed as production-proven.
- #187's previous merge conflict was historical branch topology after #185 landed, not a new functional failure.
- Remaining work is provider/extraction recovery and production evidence, not threshold relaxation.

## Blockers
- Fresh CI must pass on the reconciled #187 head before merge.
- Post-merge Deep persisted evidence is still required to prove SSE/SZSE production behavior.

## Next Action
1. Move `fix/szse-primary-disclosures` to the clean integration lineage and read the live PR state.
2. Run/observe fresh targeted + blocking CI; fix only real failures.
3. Merge #187 with expected head SHA when green and mergeable.
4. Compare the next persisted Deep result against baseline, separating Shanghai and Shenzhen outcomes.
5. Continue only from the next real evidence bottleneck; do not loosen gates.

## Do Not Repeat
- Do not rebuild Candidate Lifecycle, valuation, BUY/WAIT_PRICE/REJECT, Capital Flow Routing, or a new scoring system.
- Do not route Shanghai back through CNINFO.
- Do not restore Shenzhen CNINFO transport after #187.
- Do not treat transport/parser/coverage UNKNOWN as PASS.
- Do not redo the resolved 118/118 mapping durability investigation.

## Guardrails
- Live GitHub main / PR / Actions / artifacts / persisted data are the source of truth.
- Keep provider changes fail-closed and preserve exact issuer/date/document provenance.
- Do not claim production recovery from tests alone; require persisted/artifact evidence.
