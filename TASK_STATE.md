# Current Mission

## Goal
Converge the existing stock system into one trustworthy daily decision surface before adding new models. Preserve Candidate Lifecycle, valuation/decision thresholds, Formal authority separation, UNKNOWN != PASS, and no_auto_trade=true.

## Current Phase
Production-verify the merged scheduling fix for Shenzhen/ChiNext strict multi-year predictability. Do not weaken evidence semantics.

## Last Verified Main
- PR #229 merged into main as `c8693a1d89794fb351bde5cf563f5cf2ef9c4cc9`.
- Latest observed main at checkpoint: `7744b46b8e8b188f3bc209bad6a9efe6bf59440f`; later `[skip ci]` investor persistence commits do not modify Deep calculation code.
- Live GitHub refs / PRs / Actions / artifacts / persisted data always override this checkpoint.

## PR / CI State
- #229 — `fix: front-load strict predictability evidence collection` — is merged.
- Final PR head: `3493029639c2ec64a20eca4231c574d222ce18c4`.
- Required CI/review checks were green before merge.
- Scope remained scheduling-only; no evidence gate, provider authority, MIN_COMPLETE_YEARS, valuation, BUY/WAIT_PRICE/REJECT, Candidate Lifecycle, Formal authority, UNKNOWN != PASS, or no_auto_trade semantics changed.

## Production / Artifact
- Fresh post-merge Deep run: `35551673513`.
- Run code baseline: `c8693a1d89794fb351bde5cf563f5cf2ef9c4cc9`.
- Contracts job succeeded.
- Deep steps 1-12 succeeded, including exact input/workset resolution, initial calculation, checkpoint, and initial artifact upload.
- Current step at checkpoint: step 13 `Close unresolved gates with optimized quality-preserving official evidence` = IN_PROGRESS.
- Initial artifact exists: `genge-v31-deep-initial-35551673513`.
- No terminal Deep artifact exists yet at this checkpoint.
- Do not attribute current `data/deep_calculation/latest_status.json` to run `35551673513` until its lineage/run_id updates.

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

## Completed
- #223 Deep liveness fix remains production-proven.
- #225 was merged, production-tested, and correctly classified as unsuccessful for its intended transport recovery.
- #229 passed required CI/review and merged.
- Main production code path was verified after merge.
- Volatile web-session checkpoint is stored on `state/chatgpt-recovery` at `recovery/tasks/stock-system-convergence.json`; live GitHub remains authoritative.

## Blocker
Fresh terminal production evidence from Deep run `35551673513` is still required before #229 can be classified as production-proven.

## Next Action
1. Resume from live Deep run `35551673513`.
2. If step 13 fails, inspect the exact failure and repair only the demonstrated cause.
3. If it succeeds, inspect the fresh terminal artifact and persisted lineage.
4. Recount exact predictability failures against post-#225 baseline=377 and pre-#225 baseline=375, split by 0/3/6 prefix.
5. Check predictability verified/resolved counts, source URLs, and `metrics_by_year` for every newly resolved gate.
6. Verify Deep -> Provenance -> Terminal -> Investor lineage convergence.
7. Re-verify all PASS evidence provenance and the safety invariants.
8. If Shenzhen/ChiNext failures remain systemic, continue at provider/session/pacing/runner-network transport level without weakening gates.

## Do Not Repeat
- Do not reopen solved Candidate Lifecycle continuity work.
- Do not treat #225 as a successful transport fix.
- Do not recreate or reopen #229; it is merged.
- Do not restart from generic CNINFO-header speculation.
- Do not use stale `latest_status.json` as the result of run `35551673513`.
- Do not change multiple transport variables while the #229 production experiment is still running.
- Do not promote metadata/query success itself to evidence PASS.
- Do not loosen predictability, valuation, BUY/WAIT_PRICE/REJECT, Candidate Lifecycle, Formal authority, UNKNOWN != PASS, or no_auto_trade.

## Guardrails
- GitHub live state is the source of truth.
- Preserve exact run/profile/source/code-epoch lineage.
- Production artifacts are required in addition to tests.
- Formal/Production authority remains separate from Research outputs.
- UNKNOWN != PASS.
- no_auto_trade=true.
