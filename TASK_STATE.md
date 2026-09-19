# Current Mission

## Goal
Continue deep calculation for historical/current candidates and close only engineering-repairable evidence gaps without changing valuation, Candidate Lifecycle, BUY/WAIT_PRICE/REJECT, or Formal authority.

## Current Phase
Post-merge production verification for #188 Deep workset continuity, while separately validating #189 SSE/SZSE provider recovery from fresh persisted Deep evidence.

## Last Verified Main
`170cfef1b56cce1e0c22179b625355f46377dba8`; live `main` remains authoritative. #188 merged as `4457ca8234b43f9ba55ad989fe2737382f999a56`.

## Last Verified Code Checkpoint
#188 clean head `4aebfad8f0acb96416d599f6c8b61a486d73ae98` passed blocking CI `35412511593`, Opportunity `35412511591`, Candidate Terminal `35412511581`, and risk-capped `35412511637`, then merged.

## Active Branch
None for business-code repair. This checkpoint is state-only.

## Active PR
None for the current #188 repair; #188 is merged. #180 remains open because it covers the distinct boundary where an explicitly recovered historical candidate is absent from current All-A/universe sources. #182 was closed as superseded by merged #186.

## CI
- #189 clean integration passed full/targeted CI and merged as `aaac167ce81102fc8397822f840c7c9f6088f5a0`.
- #188 clean integration passed all blocking and targeted checks before merge.
- No gate, valuation, lifecycle transition, Formal authority, or auto-trade rule was loosened.

## Production / Artifact
- Durable research mapping remains 118/118 mapped, 0 unmapped.
- Pre-#188 persisted baseline remains Deep run `35407972654`: requested=850, profile workset=500, 351 requested codes absent from Deep profiles.
- Reconciliation proved 349/351 missing profiles were present in the same-run 4,505-row All-A quant source; 601995 and 605050 were present in the same-run universe; missing-nowhere=0.
- #188 now re-materializes retained Deep continuity codes additively from same-run All-A quant with universe fallback, research-only and no-auto-trade.
- #189 post-merge Deep runs `35412424204` and `35412428540` completed initial pass with the old 850/500/351 baseline and are still in official-evidence closure; no terminal persisted provider verdict yet.
- Current `data/deep_calculation/latest_status.json` still points to `35407972654`; therefore #188 production recovery is not yet claimed.

## Completed
- #185 repaired SSE PDF URL-aware extraction and annual-report filtering.
- #186 preserved recovered industry mapping through hourly replay.
- #187 moved Shenzhen primary evidence to SZSE.
- #189 repaired current SSE bulletin transport and merged after clean CI.
- #188 repaired bounded-handoff Deep continuity and merged after clean CI.
- #182 stale duplicate was closed as superseded by #186.
- UNKNOWN remains fail-closed; retained continuity grants no Formal/BUY/trading authority.

## Current Findings
- The 850→500/351 gap is a handoff/materialization defect, not absence from the current market universe.
- Deep continuity is a memory/materialization obligation, not a ranking bonus.
- Provider transport (#189) and workset continuity (#188) are independent; remaining evidence failures must be attributed only after fresh terminal artifacts.
- The old persisted run still shows provider/parser/evidence UNKNOWNs, so it cannot prove the post-#189 provider state.

## Blockers
- Need the first terminal post-#188 Deep persisted artifact/state to measure requested_count, profile_count, REQUESTED_CODE_NOT_PRESENT_IN_DEEP_PROFILE and continuity coverage.
- Need terminal post-#189 evidence to separate Shanghai SSE, Shenzhen SZSE, PDF parsing, source-fetch, and evidence-quality outcomes.

## Next Action
1. Observe the first post-#188 production Deep run and persisted state.
2. Compare requested/profile/missing-profile counts against the 850/500/351 baseline; fix only if a measured continuity defect remains.
3. Inspect #189 terminal evidence by exchange/provider and identify the next real bottleneck.
4. Continue from that measured bottleneck without changing thresholds, valuation, Candidate Lifecycle, or Formal authority.
5. Revisit #180 only after the current production continuity/provider evidence is closed.

## Do Not Repeat
- Do not redesign selection, valuation, BUY/WAIT_PRICE/REJECT, Candidate Lifecycle, Capital Flow Routing, or Formal authority.
- Do not turn continuity recall into promotion, PASS, BUY, or trading authority.
- Do not synthesize valuation facts for re-materialized rows.
- Do not route SSE/SZSE primary evidence back through CNINFO.
- Do not treat HTTP/parser/coverage UNKNOWN as PASS.
- Do not redo the resolved 118/118 mapping investigation.
- Do not close #180 as superseded unless its source-absent historical-lineage boundary is independently resolved.

## Guardrails
- Live GitHub main / PR / Actions / artifacts / persisted data are the source of truth.
- Preserve exact same-run provenance for continuity materialization.
- Tests are necessary but production artifact evidence is required.
