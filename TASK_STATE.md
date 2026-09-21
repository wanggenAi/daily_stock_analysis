# Current Mission

## Goal
Converge the existing stock system into one trustworthy daily decision surface before adding new models. Preserve Candidate Lifecycle, valuation/decision thresholds, Formal authority separation, UNKNOWN != PASS, and no_auto_trade=true.

## Current Phase
Recover Shenzhen/ChiNext strict multi-year predictability transport by fixing production request scheduling, not by weakening the evidence gate.

## Last Verified Main
- Live main before this branch: `9d20baa3156d95738084a4e638859cf598799a92`.
- PR #225 is merged as `9a681db9f52520d0d37e95c082c596c5735a0c1f`, but its intended CNINFO transport recovery is disproved by post-merge production.
- Live GitHub refs / PRs / Actions / artifacts / persisted data always override this checkpoint.

## Active Branch
`fix/frontload-predictability-20260921`

## Active PR
- #229 — `fix: front-load strict predictability evidence collection`.
- Scope: scheduling only — run the unchanged strict multi-year predictability collector before the high-volume general evidence collection.

## CI
- PR #229 first CI run `35549629306`: governance, change detection and Docker passed; backend offline suite had exactly one failure in the newly-added scheduling regression fixture.
- Offline suite result: 5370 passed, 1 failed, 2 deselected; the failure was test setup producing an empty selected workset, not a production-code assertion.
- Regression fixture was corrected by mocking parsed profile/candidate inputs directly; fresh CI is running on the corrected head.
- Do not weaken tests, governance, evidence gates, retry semantics, or fail-closed rules.

## Production / Artifact
- Post-#225 authoritative Deep run: `35541596198`; execution SUCCESS / COMPLETED.
- Requested=852 and processed=852.
- Provenance audit completed as `35543165132`; all PASS gates have verified evidence.
- Production safety remained intact: formal_trading_authority=false; automatic_formal_buy_allowed=false; unknown_is_pass=false; no_auto_trade=true.
- Predictability collector ran at 22:53:26Z–22:56:30Z, after the high-volume general evidence collection/retry.
- Predictability evidence rows: 852; verified predictability rows: 0.
- Raw predictability reasons in the artifact: 382 Shenzhen/ChiNext query failures + 470 strict insufficient-complete-year cases.
- Terminal unresolved predictability count is 847 because five query-failure names were already resolved negatively by independent verified material-event evidence.
- Terminal exact query-failure bucket: 377 = 269 0-prefix + 108 3-prefix.
- Previous baseline was 375, so #225 did not improve the production failure bucket.

## Current Findings
- #225 browser-form CNINFO headers were insufficient in production.
- During the same Deep run, first-party SZSE collection degraded from earlier successful requests to widespread `ConnectionError ... [Errno 101] Network is unreachable` in the later phase.
- Example 001316: an earlier material-event scan succeeded, while later SZSE annual-report retrieval failed; the later CNINFO fallback then returned HTTP 403.
- By the time strict multi-year predictability started, every requested Shenzhen/ChiNext name ended in the combined PRIMARY ConnectionError + CNINFO 403 reason.
- This is a scheduling/transport-liveness hypothesis. It is not evidence that any stock passes predictability.
- Shanghai's 470 cases remain strict `INSUFFICIENT_CONSECUTIVE_COMPLETE_FISCAL_YEARS` and stay UNKNOWN absent verified report metrics.

## Completed
- #223 Deep liveness fix remains production-proven.
- #225 merged and was production-tested; its intended effect is now correctly classified as unsuccessful.
- Production artifact `genge-v31-deep-calculation-35541596198` was inspected directly.
- Root-cause evidence narrowed from generic CNINFO headers to late-stage official-source network degradation.
- Current branch front-loads the unchanged strict predictability collector before general evidence collection.
- No provider authority, MIN_COMPLETE_YEARS, gate logic, valuation logic, BUY/WAIT_PRICE/REJECT threshold, Candidate Lifecycle, or Formal authority change.

## Blockers
- Fresh CI must validate the scheduling-only patch.
- Post-merge production must prove whether the exact 377 query-failure bucket materially falls.
- Transport recovery alone is never evidence PASS; verified official report bodies and complete multi-year metrics remain mandatory.

## Next Action
1. Open PR for the scheduling-only patch and run all required CI/review checks.
2. Fix only real CI failures without changing evidence semantics.
3. Merge only after green checks.
4. Observe a fresh post-merge Deep run.
5. Compare exact query failures against post-#225 baseline=377 and pre-#225 baseline=375.
6. Verify predictability source URLs / metrics_by_year for any newly resolved gate.
7. Verify Deep → Provenance → Terminal → Investor lineage converges.
8. If Shenzhen failures remain systemic, inspect official-source transport again; do not convert 403/ConnectionError into PASS.
9. Keep the remaining Shanghai insufficient-complete-year cases UNKNOWN unless new verified official evidence exists.

## Do Not Repeat
- Do not reopen #223 liveness work unless fresh production evidence contradicts it.
- Do not treat #225 as a successful transport fix merely because it merged.
- Do not redo Candidate Lifecycle continuity.
- Do not loosen predictability, valuation, BUY/WAIT_PRICE/REJECT, Candidate Lifecycle, Formal authority, UNKNOWN != PASS, or no_auto_trade.
- Do not promote metadata/query success itself to evidence PASS.

## Guardrails
- GitHub live state is the source of truth.
- Preserve exact run/profile/source/code-epoch lineage.
- Production artifacts are required in addition to tests.
- Formal/Production authority remains separate from Research outputs.
- UNKNOWN != PASS.
- no_auto_trade=true.
