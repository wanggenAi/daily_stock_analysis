# Current Mission

## Goal
Converge the existing stock system into one trustworthy daily decision surface before adding new models. Preserve Candidate Lifecycle, valuation/decision thresholds, Formal authority separation, UNKNOWN != PASS, and no_auto_trade=true.

## Current Phase
Repair the production-discovered historical material-event title false positives exposed by post-#232 Deep run `35556365712`. Do not merge #230/#231 until #238 is merged and a fresh Deep run proves the corrected cumulative risk ledger.

## Active Branch
`fix/material-event-historical-semantic-v2`

## Active PR
- #238 — `fix: exclude non-assertive historical risk titles` — open; production-follow-up repair for #232.
- #232 — `fix: preserve verified material-event failures across deep runs` — merged as `07dd4ca72e94c7576e3f2672a5df38266c1deddb`; persistence works, but production exposed incomplete title-semantic filtering.
- #230 (SSE annual-report discovery) and #231 (MIIT industry evidence depth) remain open and held until #238 production verification passes.

## CI
- #232 final PR head `dabfb27a1e74b3ce21641d1bf54993505e4e266f` completed PR CI successfully before merge.
- Main merge commit `07dd4ca72e94c7576e3f2672a5df38266c1deddb` triggered push CI run `35556361160` and production evidence workflows.

## Last Verified Main
- PR #229 merged into main as `c8693a1d89794fb351bde5cf563f5cf2ef9c4cc9`.
- Current business-code main baseline for this verification: `07dd4ca72e94c7576e3f2672a5df38266c1deddb` (#232 squash merge).
- Live GitHub refs / PRs / Actions / artifacts / persisted data always override this checkpoint.

## PR / CI State
- #232 — `fix: preserve verified material-event failures across deep runs` — merged; production verification in progress.
- #230 — `fix: restore SSE multi-year annual-report discovery` — open; its latest observed CI is green, but merge is held behind #232.
- #231 — `fix: deepen MIIT industry evidence discovery` — open and independent; merge is held behind #232.
- #229 — `fix: front-load strict predictability evidence collection` — is merged.
- Final PR head: `3493029639c2ec64a20eca4231c574d222ce18c4`.
- Required CI/review checks were green before merge.
- Scope remained scheduling-only; no evidence gate, provider authority, MIN_COMPLETE_YEARS, valuation, BUY/WAIT_PRICE/REJECT, Candidate Lifecycle, Formal authority, UNKNOWN != PASS, or no_auto_trade semantics changed.

## Production / Artifact
- Post-#232 Deep run `35556365712` completed successfully; terminal artifact `genge-v31-deep-calculation-35556365712` was inspected.
- Run `35556365712`: requested=852; processed=852; material-event ledger=13 historical rows; historical material-event FAIL gates=19; current material-event evidence rows=0.
- `000557` correctly remained fail-closed; `000603` and `301251` were not resurrected.
- Five historical titles were still false-positive ACTIVE risks: `000722`, `000420`, `002418`, `002427`, `002117`. These explain the 13/19 result versus the expected strict 8/12 set.
- Post-#229 Deep run `35551673513` completed successfully at code baseline `c8693a1d89794fb351bde5cf563f5cf2ef9c4cc9`.
- Terminal artifact: `genge-v31-deep-calculation-35551673513`.
- requested=852; processed=852; complete=0; evidence_exhausted=852.
- predictability verified=0; predictability_resolved_gate_count=0.
- All 852 predictability rows ended `INSUFFICIENT_CONSECUTIVE_COMPLETE_FISCAL_YEARS`: 273 0-prefix, 109 3-prefix, 470 6-prefix.
- #229 materially changed Shenzhen/ChiNext transport behavior: the old 0/3-prefix query-failure shape disappeared and 23 0-prefix rows obtained report metrics/source URLs, but none reached the strict multi-year resolution threshold.
- Raw same-workset comparison to terminal run `35549602593` exposed 18 disappeared historical material-event FAIL gates: 16 became UNKNOWN and 2 became PASS.
- Revalidating the 13 underlying historical rows with corrected current title semantics removes 5 stale/non-assertive rows: 3 explicit resolution rows and 2 "是否存在..." due-diligence classifications.
- The strict carry-forward set is therefore 8 still-active official rows mapping to 12 hard-gate FAILs.
- After semantic correction, the demonstrated true FAIL -> PASS regression is `000557 financial_safety`; `000603` must not be restored because its disclosure says the funds occupation was already resolved.

## Locked Comparison Baseline
- Prior terminal run: `35549602593`.
- requested=852; processed=852.
- predictability verified=0; predictability_resolved_gate_count=0.
- Terminal predictability unresolved:
  - 377 = `ANNUAL_REPORT_QUERY_FAILED:PRIMARY:ConnectionError,CNINFO:HTTPError:403`
    - 269 codes with 0-prefix
    - 108 codes with 3-prefix
  - 470 = `INSUFFICIENT_CONSECUTIVE_COMPLETE_FISCAL_YEARS`
- Earlier pre-#225 exact query-failure baseline: 375.
- #225 therefore did not improve the production transport bucket.

## Current Findings
- #232 persistence itself is working: the fresh run reused verified historical negative evidence when current refetch produced zero material-event rows.
- Production verification failed semantic acceptance because five governance/due-diligence/routine assurance titles were still classified ACTIVE solely by keywords.
- #238 narrows only title semantics: reversed `占用资金` preventive policy wording, acquisition due-diligence explanations, routine funds-occupation audit/clearance reports, and illegal-guarantee release reports are not live incidents without an explicit incident assertion.
- #225 browser-form CNINFO headers alone were insufficient in production.
- Previous production showed first-party SZSE transport degrading later in long Deep runs, followed by CNINFO 403 fallback.
- #229 tests the scheduling/transport-liveness hypothesis by running the unchanged strict predictability collector before high-volume general evidence collection.
- The optimized runtime patch was re-read after merge and confirmed not to bypass this order.
- Transport/query recovery is never evidence PASS; verified annual-report bodies and complete strict metrics remain mandatory.
- Shanghai strict incomplete-consecutive-year cases stay UNKNOWN unless verified official evidence resolves them.
- The prior terminal artifact stored 13 rows as VERIFIED/ACTIVE/HIGH and generated 18 hard-gate FAILs; artifact review showed 5 of those labels were semantically stale/non-assertive under the corrected rules.
- In `35551673513`, SZSE announcement metadata still surfaced those risks, but `disc.static.szse.cn` PDF downloads returned HTTP 403 and later retries sometimes hit SZSE transport failure; the fresh run therefore failed to recreate the verified rows.
- Current closure logic uses only same-run material-event evidence, so transient refetch failure can erase an earlier verified negative gate. This is the demonstrated root cause addressed by #232.
- #232 revalidates persisted rows with the current material-event title classifier before reuse, including expiry at the run as-of date.
- #232 fixes title semantics for explicit "已解决/影响已消除" resolutions and "是否存在..." due-diligence questions so keyword presence alone cannot create a hard FAIL.
- #232 uses compact status files as the bootstrap index instead of scanning every multi-megabyte evidence payload, then writes a cumulative complete risk ledger for future runs.
- Historical PASS evidence, ordinary evidence, resolved/expired events, non-assertive titles, unofficial domains, and lower-severity events are never reused.

## Completed
- #223 Deep liveness fix remains production-proven.
- #225 was merged, production-tested, and correctly classified as unsuccessful for its intended transport recovery.
- #229 passed required CI/review and merged.
- #232 passed PR CI and merged as `07dd4ca72e94c7576e3f2672a5df38266c1deddb`.
- Evidence Change Trigger run `35556361159` succeeded and launched Deep production run `35556365712`.
- Main production code path was verified after merge.
- Volatile web-session checkpoint is stored on `state/chatgpt-recovery` at `recovery/tasks/stock-system-convergence.json`; live GitHub remains authoritative.

## Blockers
#238 must pass CI, merge, and then pass fresh Deep production verification before #230/#231 may merge.

## Next Action
1. Run PR #238 CI and inspect any failure at the exact test/job level.
2. Merge #238 only after required checks are green.
3. Trigger/observe a fresh Deep production run on the merged main.
4. Inspect terminal artifact and persisted ledger; with no genuinely new verified active events, require historical ledger=8 rows and historical material-event FAIL gates=12.
5. Verify `000557 financial_safety` remains FAIL, while `000603`, `301251`, `000722`, `000420`, `002418`, `002427`, and `002117` are not falsely resurrected.
6. Verify Deep -> Provenance -> Terminal -> Investor convergence, all PASS gates verified, UNKNOWN != PASS, and no_auto_trade=true.
7. Only then resume #230 and #231.

## Do Not Repeat
- Do not reopen solved Candidate Lifecycle continuity work.
- Do not treat #225 as a successful transport fix.
- Do not recreate or reopen #229; it is merged.
- Do not restart from generic CNINFO-header speculation.
- Do not use stale `latest_status.json` as the result of run `35551673513`.
- Do not merge #230 or #231 ahead of the #232 fail-closed safety repair.
- Do not treat current-source unavailability as evidence that a previously VERIFIED/ACTIVE/HIGH material risk disappeared.
- Do not change multiple transport variables while a production experiment is being isolated.
- Do not promote metadata/query success itself to evidence PASS.
- Do not loosen predictability, valuation, BUY/WAIT_PRICE/REJECT, Candidate Lifecycle, Formal authority, UNKNOWN != PASS, or no_auto_trade.

## Guardrails
- GitHub live state is the source of truth.
- Preserve exact run/profile/source/code-epoch lineage.
- Production artifacts are required in addition to tests.
- Formal/Production authority remains separate from Research outputs.
- UNKNOWN != PASS.
- no_auto_trade=true.
