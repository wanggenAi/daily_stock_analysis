# Current Mission

## Goal
Continue deep calculation for historical/current candidates and close only evidence gaps that can be repaired by engineering, without changing investment thresholds, valuation, Candidate Lifecycle, or Formal authority.

## Current Phase
Primary-exchange evidence recovery and production verification.

## Last Verified Main
`5d8bf71e02d784ebac9d5a89274e725a6354da4d` (live `main` remains authoritative).

## Last Verified Code Checkpoint
`574edc2b145cca3c2ec56b0ed154360032039a4b` on `fix/szse-primary-disclosures` before this TASK_STATE checkpoint commit.

## Active Branch
`fix/szse-primary-disclosures`

## Active PR
- #185 `Recover SSE PDF extraction when MIME is generic`: targeted GenGe Opportunity Discovery passed on head `e472528a17560aa398ead8e868eb9079fbd1c9eb`; full CI run `35406705085` is still in progress.
- #187 `Use SZSE primary disclosures for Shenzhen evidence`: latest targeted GenGe Opportunity Discovery passed before this checkpoint; latest code checkpoint is `574edc2b145cca3c2ec56b0ed154360032039a4b`. Re-run CI after this state commit.

## CI
- #186 full CI run `35336553336` passed and PR merged.
- #185 targeted workflow `35406705021` passed; full CI pending completion.
- #187 targeted workflow `35407091433` passed through opportunity tests on the pre-checkpoint code head; final CI must be read from live GitHub after this checkpoint.

## Production / Artifact
- PR #186 merged as `d2f82edeb42a085021a5389fc51906f30f6b7479`.
- Research mapping production verification at 2026-09-18T23:06:58Z: 118/118 mapped, 0 unmapped; mapping survived later hourly cycles.
- Pre-#185 Deep baseline: run `35403919220`, generated 2026-09-18T23:42:57Z, 0 predictability VERIFIED; company extraction status = 280 SOURCE_DATA_ABSENT + 219 SOURCE_FETCH_FAILED; predictability reasons = 280 INSUFFICIENT_CONSECUTIVE_COMPLETE_FISCAL_YEARS + 219 ANNUAL_REPORT_QUERY_FAILED:HTTPError.

## Completed
- #179 moved Shanghai annual-report and material-event queries off CNINFO onto SSE.
- #186 fixed Hourly Overlay mapping replay and production mapping is stable at 118/118.
- #185 repaired PDF detection by source URL, typed extraction URL propagation, cache contract versioning, and strict full-annual SSE title filtering; targeted tests are green.
- #187 routes Shenzhen 0/2/3 securities to SZSE first-party disclosures, uses fixed_disc + 010301 for annual reports, normalizes attachments through disc.static.szse.cn/download, preserves pagination completeness, validates exact secCode/date/schema, avoids CNINFO orgId calls on primary-exchange routes, and preserves exchange-specific UNKNOWN provenance.
- UNKNOWN remains fail-closed; no investment decision threshold or authority change was made.

## Current Findings
- Latest production before #185 still has the same provider split: Shanghai query succeeds but annual PDF extraction remains unresolved on main; Shenzhen still fails at CNINFO transport.
- The remaining evidence work is provider/extraction recovery, not a reason to loosen evidence requirements.

## Blockers
- #185 cannot merge until current blocking CI is green.
- #187 must be reconciled against main after #185 merges and must pass fresh blocking CI before merge.
- Production proof for SSE PDF recovery and SZSE first-party transport is still pending merge.

## Next Action
1. Read #185 current CI; if green, merge with expected head SHA and verify main.
2. Observe the Deep production run triggered after #185 and compare against baseline, especially Shanghai SOURCE_DATA_ABSENT / predictability coverage.
3. Reconcile #187 against the new main, run targeted + full CI, merge only if green.
4. Verify production SZSE company/material-event transport and Deep artifact; continue only from the next real evidence bottleneck.

## Do Not Repeat
- Do not rebuild Candidate Lifecycle, valuation, BUY/WAIT_PRICE/REJECT, Capital Flow Routing, or a new scoring system.
- Do not route Shanghai back through CNINFO.
- Do not treat transport/parser/coverage UNKNOWN as PASS.
- Do not redo the resolved 118/118 research-mapping durability investigation.

## Guardrails
- Live GitHub main / PR / Actions / artifacts / persisted data are the source of truth.
- Keep provider changes fail-closed and preserve exact issuer/date/document provenance.
- Do not claim production recovery from unit tests alone; require post-merge persisted/artifact evidence.
