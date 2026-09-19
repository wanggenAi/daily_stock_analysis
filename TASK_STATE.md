# Current Mission

## Goal
Continue deep calculation for historical/current candidates and close only evidence gaps that can be repaired by engineering, without changing investment thresholds, valuation, Candidate Lifecycle, BUY/WAIT_PRICE/REJECT, or Formal authority.

## Current Phase
Primary-exchange production verification plus Deep workset continuity repair. #187 is merged; post-merge Deep is running. #188 fixes the structural 850-requested / 500-profile handoff loss.

## Last Verified Main
`afe052a2cf4f4dc48c8ceb8b34c52cb9a5806b35` merged #187. Live `main` remains authoritative and may advance through persisted-state bots.

## Last Verified Code Checkpoint
#187 head `48e1d59b99d87462ca1f617b4b29d81128562171` passed blocking CI `35409178824` and was merged as `afe052a2cf4f4dc48c8ceb8b34c52cb9a5806b35`.
#188 current code head before this checkpoint: `3ae4578ff46867a24fceee1990bb27d9027a8a06`.

## Active Branch
`fix/deep-continuity-materialization`.

## Active PR
#188 — `fix: preserve deep workset through bounded review handoff`.

## CI
- #187 blocking CI `35409178824`: green; merged.
- #188 targeted Opportunity Discovery `35410349351`: green.
- #188 Candidate Terminal `35410349437`: green.
- #188 Legacy Risk-Capped `35410349397`: green.
- #188 blocking CI `35410349544`: in progress at checkpoint; syntax, flake8 and deterministic checks passed; Docker gate reached successful build/smoke; offline pytest still running when last checked.

## Production / Artifact
- Latest fully inspected persisted Deep run before #187 merge: `35408711645`.
- Baseline run `35408711645`: requested=850, profiles=500, hard gates=2500, PASS=213, UNKNOWN=2285, FAIL=2, unverified PASS=0.
- Baseline unresolved structural gap: 351 codes reported `REQUESTED_CODE_NOT_PRESENT_IN_DEEP_PROFILE`.
- Exact upstream reconciliation against Opportunity Discovery run `35357155903` and Every-Industry run `35403243897`: 349/351 missing Deep codes are present in the same-run 4,505-row All-A quant source; the remaining 2 (601995, 605050) are present in the same-run listed-company universe metadata. Missing-nowhere count=0.
- #187 post-merge Deep runs `35410335991` (push) and `35410340825` (EVIDENCE_LAYER_CHANGE dispatch) are in progress. They validate SSE/SZSE provider recovery but still consume the pre-#188 bounded Every-Industry candidate artifact.

## Completed
- #185 fixed SSE PDF source-URL detection, typed extraction propagation/cache contract, and strict full-annual title filtering.
- #186 preserved recovered industry mapping through hourly replay; production mapping remained 118/118.
- #187 routes Shenzhen 0/2/3 issuers to SZSE first-party disclosure APIs and is merged after full green CI.
- Root cause of the 351 profile-missing Deep gap is confirmed as a bounded handoff mismatch, not stale chat state and not evidence-threshold semantics.
- #188 implementation now:
  - treats ACTIVE lifecycle recall as additive research continuation through valuation recall;
  - preserves lifecycle recall provenance through valuation serialization;
  - materializes retained Deep codes beyond the ordinary V3.1 review limit from the exact same-run All-A quant source, falling back to same-run universe metadata when no quant row exists;
  - keeps additive rows research-only, UNKNOWN fail-closed, Formal/trading authority disabled.

## Current Findings
- Deep continuity must not be implemented by deleting historical unresolved codes: 349/351 currently missing profiles still have same-run All-A quant rows.
- The Deep Lambda itself has no 500-profile hard cap; it builds profiles for every candidate row it receives. The 500 cap is upstream in the frozen V3.1 review handoff.
- ACTIVE lifecycle metadata was also being lost by the valuation research serialization path, weakening the existing additive recall contract.
- Provider recovery and workset materialization are separate concerns: #187 repairs evidence transport; #188 repairs which requested codes actually reach Deep.

## Blockers
- #188 blocking CI must finish green before merge.
- #187 post-merge Deep artifacts/persisted state must be inspected before claiming SSE/SZSE production recovery.
- #188 production closure must ultimately show the structural profile-missing gap removed from a fresh Every-Industry -> Deep chain; tests alone are insufficient.

## Next Action
1. Finish #188 blocking CI; fix only real failures.
2. Merge #188 with expected head SHA when green and mergeable.
3. Inspect #187 post-merge Deep persisted/artifact results and compare provider outcomes against run 35408711645.
4. Run/observe the next fresh Every-Industry -> Deep chain on merged #188 and verify requested codes are materially represented rather than reported as missing profiles.
5. Continue only from remaining real evidence gaps; do not loosen gates.

## Do Not Repeat
- Do not delete retained Deep lineage merely to reduce requested_count.
- Do not rebuild Candidate Lifecycle, valuation, BUY/WAIT_PRICE/REJECT, Capital Flow Routing, or a new scoring system.
- Do not route Shanghai or Shenzhen primary-exchange evidence back through CNINFO.
- Do not treat transport/parser/coverage UNKNOWN as PASS.
- Do not redo the resolved 118/118 mapping durability investigation.
- Do not re-investigate whether the 351 missing profiles are caused by the Deep profile builder; that layer was verified to accept every candidate row it receives.

## Guardrails
- Live GitHub main / PR / Actions / artifacts / persisted data are the source of truth.
- Historical/current research continuity is additive to bounded daily discovery budgets and remains research-only.
- Keep provider changes fail-closed and preserve exact issuer/date/document provenance.
- Do not claim production recovery from tests alone; require persisted/artifact evidence.
