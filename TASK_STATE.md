# Current Mission

## Goal
Converge the existing stock system into one trustworthy daily decision surface before adding new models. Preserve Candidate Lifecycle, valuation/decision thresholds, Formal authority separation, UNKNOWN != PASS, and no_auto_trade=true.

## Current Phase
Recover the remaining Shenzhen/ChiNext strict multi-year predictability metadata transport without weakening the evidence gate.

## Last Verified Main
- PR #223 is merged and production-verified.
- #223 merge/code epoch: `d06b040a6373054aa50b5ccda835a1a354f113a5`.
- Live main observed before this branch: `a73828ccfd37862bbbdce5848424cf0c7179f3fb`.
- Live GitHub refs / PRs / Actions / artifacts / persisted data always override this checkpoint.

## Active Branch
`fix/cninfo-query-contract-20260920`

## Active PR
- #225 — `fix: restore CNINFO predictability query contract`.
- Head before this checkpoint: `b1fcbaf826d347df44c5253e327fe32852f42001`.
- Scope: CNINFO browser-form request transport + regressions + this checkpoint only.

## CI
- PR #225 initial CI run `35513415635` failed only in `ai-governance` because this checkpoint omitted the repository-required `## CI` heading.
- Change Detection passed.
- Opportunity Discovery, risk-capped, and PR Review were still running when the documentation-only CI defect was found.
- Fix the checkpoint structure only; do not weaken tests, governance, evidence gates, or fail-closed rules.

## Production Proof Completed
- Deep `35509192911` survived a successful periodic workflow_run trigger while its official-evidence closure was active.
- Deep `35509192911` closure ran 11:58:13Z–12:49:11Z and completed successfully.
- Hourly Deep Overlay `35510103689` completed at 12:16:55Z and triggered Deep `35510170838` while `35509192911` was still running.
- `35509192911` was not cancelled; it persisted terminal state and dispatched downstream convergence.
- Deep `35510170838` also completed and persisted terminal state.
- Provenance converged to audit `35512219496`.
- Terminal Research and Investor dashboard converged to Deep `35510170838`.
- Investor research counts from that lineage: requested=852, RESEARCH_GAP=833, REJECT=19, WAIT_PRICE=0, BUY=0.
- Research authority remains RESEARCH_ONLY; formal_trading_authority=false; automatic_formal_buy_allowed=false; unknown_is_pass=false; no_auto_trade=true.

## Current Production Findings
- #223 liveness defect is closed in production.
- Latest measured Deep `35510170838` has unknown_gate_count=4021 and new_evidence_count=1501.
- Predictability remains unresolved for 845 names:
  - 375 metadata query failures: `ANNUAL_REPORT_QUERY_FAILED:PRIMARY:ConnectionError,CNINFO:HTTPError:403`.
  - 470 strict evidence insufficiency: `INSUFFICIENT_CONSECUTIVE_COMPLETE_FISCAL_YEARS`.
- The 375 transport failures are entirely Shenzhen/ChiNext:
  - 267 codes beginning with 0.
  - 108 codes beginning with 3.
  - no 6-prefix Shanghai codes in this failure bucket.
- The current CNINFO fallback POST had only generic User-Agent + homepage Referer while the browser/API form contract uses form Content-Type, X-Requested-With, Origin and disclosure-search Referer.
- HTTP 403 remains non-transient and must not be blindly retried.

## Current Patch
- Introduce shared `CNINFO_QUERY_URL`, `CNINFO_QUERY_REFERER`, and `CNINFO_QUERY_HEADERS`.
- Use that request contract for shared CNINFO announcement POSTs.
- Reuse the same contract in strict multi-year predictability fallback.
- Add regression coverage asserting form Content-Type, X-Requested-With, Origin, Referer, stock/orgId and annual-report category.
- Do not change provider authority, MIN_COMPLETE_YEARS, gate logic, valuation logic, BUY/WAIT_PRICE/REJECT thresholds, Candidate Lifecycle, or Formal authority.

## Next Action
1. Rerun fresh blocking CI / targeted Opportunity checks after the checkpoint-format fix.
2. Fix only real failures without weakening evidence semantics.
3. Merge #225 only after green checks.
5. Observe fresh post-merge Deep triggered by the evidence collector change.
6. Compare CNINFO 403 count against current baseline=375.
7. Require actual official report source URLs / metrics_by_year before any predictability PASS.
8. Verify Deep → Provenance → Terminal → Investor lineage converges.
9. If 403 remains, inspect transport response and provider contract again; do not convert 403 to a retry/pass condition.
10. Treat the remaining 470 insufficient-complete-year cases as UNKNOWN unless new verified official evidence exists.

## Do Not Repeat
- Do not reopen #223 liveness work unless fresh production evidence contradicts the completed proof.
- Do not redo merged CNINFO/SSE/SZSE routing work from #175/#179/#187/#189/#198/#207.
- Do not treat stale branch names `feature/deep-evidence-recovery-cninfo` or `fix/cninfo-announcement-403-recovery` as unfinished work; their intended PRs were merged.
- Do not loosen predictability, valuation, BUY/WAIT_PRICE/REJECT, Candidate Lifecycle, Formal authority, UNKNOWN != PASS, or no_auto_trade.
- Do not promote transport success itself to evidence PASS.

## Guardrails
- GitHub live state is the source of truth.
- Preserve exact run/profile/source/code-epoch lineage.
- Production artifacts are required in addition to tests.
- Formal/Production authority remains separate from Research outputs.
- UNKNOWN != PASS.
- no_auto_trade=true.
