# Current Mission

## Goal
Eliminate the production false-positive path where generic management-system certifications can satisfy the strict multi-year moat entry-barrier rule, then re-verify the exact Deep -> Provenance -> Terminal -> Investor -> Three-Pillar chain without weakening any authority guardrail.

## Current Phase
GENERIC_CERTIFICATION_MOAT_FIX_MERGED_AWAITING_PRODUCTION_DEEP

## Last Verified Main
- PR #269 merged to main as `8ddc6efb46526d44d2313dd20cd1fa764d13461a`.
- PR #269 final blocking CI `35684679501`: ai-governance=success, docker-build=success, backend-gate=success, web-gate=skipped.
- Live GitHub refs / Actions / persisted data always override this checkpoint.

## Active Branch
- None required for the merged fix.

## Active PR
- None for the current mission. #269 is merged.

## CI
- PR #269 blocking CI passed before merge.
- Merge changed `src/strategies/genge_opportunity_discovery/evidence_collectors/multi_year_predictability.py` and its regression tests, which match the Deep workflow push path.
- Post-merge production Deep evidence has not yet persisted; do not claim production verification until a new Deep commit/status proves code epoch `8ddc6efb...`.

## Production / Artifact
- Pre-fix Deep `35683878901`: SUCCESS, requested=22, processed=22, missing=0, unresolved_requested_gate_count=89, progressed_gate_count=7, predictability_resolved_gate_count=1, moat_resolved_gate_count=4.
- Pre-fix new automatic moat PASS codes: `000576`, `002375`, `603160`, `603396`.
- `603396` is the false-positive case: generic ISO9001/ISO14001/ISO45001 management-system certification plus patent support incorrectly satisfied the broad entry-barrier rule.
- Required post-fix invariant: `603396` must not obtain moat PASS from generic ISO certification evidence.

## Completed
- Recovered from live GitHub rather than chat state.
- Verified #268 had already merged and did not repeat it.
- Audited the first strict-moat production pass set and found the `603396` false positive.
- Removed only the generic `国家级|国际 ... 认证|资质` strong-barrier pattern.
- Preserved high-specificity ASIL-D, exclusive/unique rights, market leadership, customer embedding and resource barriers.
- Added regressions proving generic ISO certifications remain insufficient while ASIL-D remains recognized.
- PR #269 passed blocking CI and was squash-merged to main.

## Current Findings
- The fix remains PASS-only and fail-closed. It can reduce automatic moat PASS count; it cannot manufacture FAIL or Formal action.
- `000576`, `002375`, and `603160` did not depend on the removed generic-certification rule in the audited pre-fix production evidence.
- Jev/TypeSafe did not determine any moat gate in this mission; the moat closure is deterministic official-evidence logic.

## TypeSafe / Jev
- Live Jev shadow uses pinned `typesafe-sdk==0.7.0`, `JEV_MODEL=jev-latest`, and `TYPESAFE_API_KEY`.
- Jev produces typed attention/evidence/routing judgments only.
- Current orchestration is: Jev typed routing -> deterministic research orchestrator -> bounded eligible-code dispatch -> Deep.
- `jev_direct_dispatch_allowed=false`; Jev cannot create Formal BUY or mutate trading authority.
- No new Jev call has been proven in this mission yet. Report Jev usage only if a TypeSafe/Jev workflow log proves it.

## Blockers
- Awaiting the post-merge production Deep persistence/verification for code epoch `8ddc6efb...`.

## Next Action
1. Observe the new post-merge Deep triggered by the #269 main push.
2. Verify its persisted `data/deep_calculation/latest_status.json` uses code epoch `8ddc6efb...`.
3. Audit the resulting moat PASS set; `603396` must remain unresolved for moat unless independent high-specificity evidence exists.
4. Verify exact Deep -> Provenance -> Terminal -> Investor -> Three-Pillar lineage.
5. Record whether Jev actually ran; do not report Jev usage without workflow-log evidence.
6. Update this checkpoint to completion.

## Do Not Repeat
- Do not redo #268 or #269.
- Do not rerun old Deep `35679085547` or pre-fix Deep `35683878901` as if they were post-fix verification.
- Do not broaden moat rules to recover pass count.
- Do not loosen long_term_demand, predictability, financial-safety, earnings-authenticity, valuation, BUY/WAIT_PRICE/REJECT, Candidate Lifecycle, or Formal authority rules.

## Guardrails
- GitHub live state is the source of truth.
- Jev direct dispatch=false.
- Deterministic bounded research dispatch is research-only.
- Formal trading authority=false.
- Automatic Formal BUY=false.
- UNKNOWN != PASS.
- no_auto_trade=true.
