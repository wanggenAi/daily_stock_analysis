# Current Mission

## Goal
Converge the existing stock system into one trustworthy daily decision surface before adding new models. Preserve Candidate Lifecycle, valuation/decision thresholds, Formal authority separation, UNKNOWN != PASS, and no_auto_trade=true.

## Current Phase
Repair the production fail-closed regression discovered while verifying #229: a later official-source fetch failure must not erase previously VERIFIED/ACTIVE/HIGH exchange material-event FAILs. Do not weaken evidence semantics.

## Active Branch
`fix/preserve-verified-material-event-fails-20260921`

## Active PR
- #232 — `fix: preserve verified material-event failures across deep runs`.
- Safety scope only: reuse immutable historical evidence only when it independently satisfies the existing VERIFIED + ACTIVE + HIGH + official-exchange material-event FAIL rule.
- #230 (SSE annual-report discovery) and #231 (MIIT industry evidence depth) remain separate and must not be merged ahead of this fail-closed repair.

## CI
- #232 initial CI run `35554179025` failed only in `ai-governance` because this checkpoint lacked required headings; backend/web/docker jobs were skipped before code tests.
- Required checkpoint headings are now restored; the next #232 head must run the actual blocking code/test gates.

## Last Verified Main
- PR #229 merged into main as `c8693a1d89794fb351bde5cf563f5cf2ef9c4cc9`.
- Latest observed main at checkpoint: `7744b46b8e8b188f3bc209bad6a9efe6bf59440f`; later `[skip ci]` investor persistence commits do not modify Deep calculation code.
- Live GitHub refs / PRs / Actions / artifacts / persisted data always override this checkpoint.

## PR / CI State
- #232 — `fix: preserve verified material-event failures across deep runs` — open; blocking CI/review required before merge.
- #230 — `fix: restore SSE multi-year annual-report discovery` — open; its latest observed CI is green, but merge is held behind #232.
- #231 — `fix: deepen MIIT industry evidence discovery` — open and independent; merge is held behind #232.
- #229 — `fix: front-load strict predictability evidence collection` — is merged.
- Final PR head: `3493029639c2ec64a20eca4231c574d222ce18c4`.
- Required CI/review checks were green before merge.
- Scope remained scheduling-only; no evidence gate, provider authority, MIN_COMPLETE_YEARS, valuation, BUY/WAIT_PRICE/REJECT, Candidate Lifecycle, Formal authority, UNKNOWN != PASS, or no_auto_trade semantics changed.

## Production / Artifact
- Post-#229 Deep run `35551673513` completed successfully at code baseline `c8693a1d89794fb351bde5cf563f5cf2ef9c4cc9`.
- Terminal artifact: `genge-v31-deep-calculation-35551673513`.
- requested=852; processed=852; complete=0; evidence_exhausted=852.
- predictability verified=0; predictability_resolved_gate_count=0.
- All 852 predictability rows ended `INSUFFICIENT_CONSECUTIVE_COMPLETE_FISCAL_YEARS`: 273 0-prefix, 109 3-prefix, 470 6-prefix.
- #229 materially changed Shenzhen/ChiNext transport behavior: the old 0/3-prefix query-failure shape disappeared and 23 0-prefix rows obtained report metrics/source URLs, but none reached the strict multi-year resolution threshold.
- Exact same-workset comparison to terminal run `35549602593` exposed a separate safety regression: 18 previously verified material-event FAIL gates disappeared; 16 became UNKNOWN and 2 became PASS.
- The two unsafe FAIL -> PASS regressions are `000557 financial_safety` and `000603 financial_safety`.

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
- #225 browser-form CNINFO headers alone were insufficient in production.
- Previous production showed first-party SZSE transport degrading later in long Deep runs, followed by CNINFO 403 fallback.
- #229 tests the scheduling/transport-liveness hypothesis by running the unchanged strict predictability collector before high-volume general evidence collection.
- The optimized runtime patch was re-read after merge and confirmed not to bypass this order.
- Transport/query recovery is never evidence PASS; verified annual-report bodies and complete strict metrics remain mandatory.
- Shanghai strict incomplete-consecutive-year cases stay UNKNOWN unless verified official evidence resolves them.
- The prior terminal artifact contains 13 VERIFIED/ACTIVE/HIGH official exchange material-event disclosures across 12 companies that generated 18 hard-gate FAILs.
- In `35551673513`, SZSE announcement metadata still surfaced those risks, but `disc.static.szse.cn` PDF downloads returned HTTP 403 and later retries sometimes hit SZSE transport failure; the fresh run therefore failed to recreate the verified rows.
- Current closure logic uses only same-run material-event evidence, so transient refetch failure can erase an earlier verified negative gate. This is the demonstrated root cause addressed by #232.
- Immutable `data/deep_calculation/history/*.evidence.json` already persists prior evidence packets; #232 reuses only rows that pass the existing strict negative-event validator and never reuses historical PASS evidence.

## Completed
- #223 Deep liveness fix remains production-proven.
- #225 was merged, production-tested, and correctly classified as unsuccessful for its intended transport recovery.
- #229 passed required CI/review and merged.
- Main production code path was verified after merge.
- Volatile web-session checkpoint is stored on `state/chatgpt-recovery` at `recovery/tasks/stock-system-convergence.json`; live GitHub remains authoritative.

## Blockers
#232 must pass blocking CI/review, merge, and receive fresh production Deep verification before #230/#231 transport/evidence expansion is allowed to merge.

## Next Action
1. Let #232 blocking CI/review complete; fix only demonstrated failures.
2. Merge #232 when green.
3. Run a fresh production Deep on main.
4. Verify the known 18 historical material-event FAIL gates remain FAIL unless stricter fresh verified evidence applies.
5. Specifically verify `000557 financial_safety` and `000603 financial_safety` cannot remain PASS while their prior VERIFIED/ACTIVE/HIGH risks remain in immutable history.
6. Verify historical evidence counters, Deep -> Provenance -> Terminal -> Investor convergence, UNKNOWN != PASS, and no_auto_trade=true.
7. Only after #232 is production-proven, resume #230 Shanghai SSE annual-report discovery verification and then #231 long-term-demand evidence depth.

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
