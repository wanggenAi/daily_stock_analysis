# Current Mission

## Goal
Converge the existing stock system into one trustworthy daily decision surface before adding new models. Preserve Candidate Lifecycle, valuation/decision thresholds, Formal authority separation, UNKNOWN != PASS, and no_auto_trade=true.

## Current Phase
Production-verify the merged CNINFO strict multi-year predictability transport fix without weakening evidence requirements.

## Last Verified Main
- PR #223 is merged and production-verified; periodic workflow_run triggers no longer cancel an active official-evidence closure.
- PR #225 `fix: restore CNINFO predictability query contract` is merged at code epoch `9a681db9f52520d0d37e95c082c596c5735a0c1f`.
- Main observed after #225 advanced through data-only investor persistence to `5c5da3ab705a440d5cb0ce1d466af07e39ab9bd4`.
- The files changed after #225 were only `INVESTOR_DECISION_DASHBOARD.md`, `data/decision_center/latest.json`, and `data/investor_decision_dashboard/latest.json`; no Deep/evidence code changed.
- Live GitHub refs / PRs / Actions / artifacts / persisted data always override this checkpoint.

## Active Branch
`chore/checkpoint-cninfo-production-20260920`

## Active PR
- Documentation-only checkpoint PR pending/open from this branch.
- No business, evidence, valuation, threshold, Candidate Lifecycle, or Formal authority code change belongs in this PR.

## CI
- PR #225 final CI and blocking workflows passed before merge: CI `35513533475`, Legacy Risk-Capped `35513533478`, Opportunity Discovery `35513533417`, PR Review `35513532725`.
- The active production verification is not to be replaced by a synthetic test or a fresh competing Deep run.

## Production / Artifact
- Authoritative pre-fix production baseline is Deep `35513686165`, generated 2026-09-20T14:33:31Z from Every-Industry `35513006839`.
- Baseline: requested=852, unknown_gate_count=4021, new_evidence_count=1501, predictability_evidence=852, predictability_verified=0.
- Baseline predictability unresolved reasons: 470 `ANNUAL_REPORT_QUERY_FAILED:PRIMARY:HTTPError:403,CNINFO:HTTPError:403`; 375 `INSUFFICIENT_CONSECUTIVE_COMPLETE_FISCAL_YEARS`.
- Baseline final evidence collection: final_failed_count=999, final_missing_count=327, research_terminal_state=EVIDENCE_EXHAUSTED.
- Post-#225 authoritative Deep is `35518154713`, event `workflow_dispatch`, trigger `EVIDENCE_LAYER_CHANGE`, head/code epoch `9a681db9f52520d0d37e95c082c596c5735a0c1f`.
- Its contracts and initial pass succeeded; initial artifact `genge-v31-deep-initial-35518154713` exists.
- Initial checkpoint source_run_id is `35513006839`, requested_count=852, so the production comparison is like-for-like with the baseline workset.
- Initial profile gate snapshot: UNKNOWN=4044, PASS=217, FAIL=4; no transport result has been promoted to evidence PASS.
- Deep `35518154713` is currently in `Close unresolved gates with optimized quality-preserving official evidence`.
- No newer Deep run has superseded `35518154713`; the cancelled push run `35518145612` was replaced by the intended explicit EVIDENCE_LAYER_CHANGE run.
- Research authority remains RESEARCH_ONLY; formal_trading_authority=false; automatic_formal_buy_allowed=false; unknown_is_pass=false; no_auto_trade=true.

## Completed
- #223 liveness fix is production-proven.
- #225 browser-form CNINFO query contract is merged.
- Shared CNINFO metadata POST now supplies form Content-Type, X-Requested-With, Origin and disclosure-search Referer while keeping HTTP 403 non-transient.
- Regression coverage locks the CNINFO request contract and stock/category payload.
- The true latest pre-fix benchmark was corrected from older 375-query-failure data to Deep `35513686165`: 470 CNINFO/primary HTTP 403 failures.
- Current main drift since the #225 code epoch is data-only and does not supersede the active Deep code epoch.

## Current Findings
- Production validation is still in progress; do not claim #225 is production-proven yet.
- The first success criterion is CNINFO/primary HTTP 403 count falling below baseline=470.
- The second success criterion is strict predictability_verified increasing above 0 only where official report source_urls and complete `metrics_by_year` satisfy the unchanged three-complete-fiscal-year rule.
- Transport success alone is not PASS.
- If 403 drops but predictability_verified remains 0, the next bottleneck is report-body extraction / complete-year metric parsing, not the transport layer.

## Blockers
- Deep `35518154713` must finish its official-evidence closure and persist/upload the terminal result.
- GitHub job logs for the running job are not downloadable until the job finishes; use steps/artifacts/persisted state meanwhile.
- Do not trigger another Deep while this closure is active.

## Next Action
1. Follow Deep `35518154713` to completion without starting a competing run.
2. Read `data/deep_calculation/history/35518154713.json` and `.evidence.json` or the final artifact.
3. Compare exact post-fix metrics against baseline Deep `35513686165`: CNINFO 403 470→?, predictability_verified 0→?, unknown_gate_count 4021→?, new_evidence_count 1501→?, final_failed 999→?, final_missing 327→?.
4. Inspect every newly verified predictability row for official `source_urls` and complete `metrics_by_year`; transport recovery alone must never count as PASS.
5. Verify Deep → Provenance → Terminal Research → Investor lineage converges on this Deep run/code epoch.
6. If 403 remains near 470, inspect the live CNINFO/provider transport contract again without retrying 403 or weakening source authority.
7. If 403 falls but verified remains 0, investigate annual-report extraction/parser completeness under the existing strict rules.
8. After production evidence is complete, checkpoint the final result and only then choose the next engineering bottleneck.

## Do Not Repeat
- Do not reopen #223 liveness work unless fresh production evidence contradicts its completed proof.
- Do not redo merged CNINFO/SSE/SZSE routing work from #175/#179/#187/#189/#198/#207/#225.
- Do not use older Deep `35510170838` and baseline=375 as the authoritative pre-#225 benchmark; use `35513686165` and baseline=470.
- Do not treat stale branch names as unfinished work.
- Do not loosen predictability, valuation, BUY/WAIT_PRICE/REJECT, Candidate Lifecycle, Formal authority, UNKNOWN != PASS, or no_auto_trade.
- Do not promote transport success itself to evidence PASS.

## Guardrails
- GitHub live state is the source of truth.
- Preserve exact run/profile/source/code-epoch lineage.
- Production artifacts are required in addition to tests.
- Formal/Production authority remains separate from Research outputs.
- UNKNOWN != PASS.
- no_auto_trade=true.
