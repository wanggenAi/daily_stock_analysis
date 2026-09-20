# Current Mission

## Goal
Converge the existing stock system into one trustworthy daily decision surface for a user-confirmed CNY 50,000 stock-account planning cash balance. The final report must connect social/macro structure, capital-flow evidence, A-share market/industry state, Candidate Lifecycle, Deep research, valuation, holdings and a concrete cash/action table. Preserve Candidate Lifecycle, valuation/decision thresholds, Formal authority separation, UNKNOWN != PASS, and no_auto_trade=true.

## Current Phase
Close report-chain gaps and production-verify the merged CNINFO predictability transport fix before merging any new Deep-workflow change.

## Last Verified Main
- PR #223 is merged and production-verified.
- PR #225 is merged at Deep/evidence code epoch `9a681db9f52520d0d37e95c082c596c5735a0c1f`.
- Live main observed during this task reached `c6f1a3b0313ddd527e74e836bca575ef840bdc2b` via data-only investor overlay persistence.
- Live GitHub refs / PRs / Actions / artifacts / persisted data always override this checkpoint.

## Active Branch
`feat/complete-investor-report-20260920`

## Active PR
- New report-convergence PR is to be opened from this branch after the current checkpoint.
- It supersedes the implementation intent of stale/open #224 and the stale docs checkpoint #226 once verified and merged.

## CI
- Branch changes require fresh PR CI before merge.
- #224's original implementation had green CI, but it is being replayed on current main inside this branch rather than merging the stale divergent branch.
- Do not merge this branch while Deep `35518154713` is still active because the Deep-workflow path change would create a push Deep that may supersede the production verification run.

## Production / Artifact
- Authoritative pre-#225 baseline: Deep `35513686165`, source Every-Industry `35513006839`.
- Baseline: requested=852; unknown_gate_count=4021; new_evidence_count=1501; predictability_verified=0; final_failed=999; final_missing=327.
- Baseline predictability unresolved: 470 `ANNUAL_REPORT_QUERY_FAILED:PRIMARY:HTTPError:403,CNINFO:HTTPError:403`; 375 `INSUFFICIENT_CONSECUTIVE_COMPLETE_FISCAL_YEARS`.
- Post-#225 Deep `35518154713` is the authoritative production verification run for code epoch `9a681db9f52520d0d37e95c082c596c5735a0c1f`.
- Its contracts, initial calculation and initial artifact succeeded; it is currently in official-evidence closure.
- No newer Deep had superseded it at the last live check.
- Do not start or merge a change that intentionally supersedes it until its terminal result is captured.

## Completed
- User-confirmed stock planning cash changed from the old CNY 57,000 floor to CNY 50,000; the old exact broker snapshot is retained only as historical reference.
- Final Decision Center now exposes a `today_account_plan` with available cash, deployment budget, planned immediate cash, cash after plan, quote coverage and plain-language cash action.
- Current Terminal RESEARCH_GAP rows are translated for the investor as `暂不买；等待补齐...` instead of ending at engineering terminology.
- Decision Center now reads the exact Era Radar evidence bundle for the active snapshot and reports POLICY_CAPITAL / INDUSTRIAL_CAPITAL / FINANCIAL_CAPITAL / REAL_DEMAND / TECHNOLOGY / GLOBAL_STRUCTURE counts.
- Missing FINANCIAL_CAPITAL is explicit and market/industry-strength proxies cannot be promoted into direct fund-flow evidence.
- Live Execution Quote Refresh now dispatches Three-Pillar Decision Center after quote persistence so the final report cannot silently lag the refreshed execution prices.
- #224 logical-workset Deep concurrency fix has been replayed on current main in this branch: default Deep work is grouped by logical workset instead of runtime SHA.
- Changelog and Era Radar capital-coverage semantics are updated.
- No BUY/WAIT_PRICE/REJECT thresholds, valuation formulas, Formal authority, Candidate Lifecycle or no-auto-trade rules were changed.

## Current Findings
- Era Radar architecture supports six evidence families, but current live production collectors are World Bank structural + MIIT policy + MIIT statistics only.
- Current latest Era Radar evidence bundle has 12 records and no FINANCIAL_CAPITAL evidence; current trends remain EMERGING and validated Era→A-share handoff count is 0.
- Therefore the system may describe structural/social direction and market-behavior proxies, but it must not claim real financial-capital flow is fully known yet.
- The source registry already defines PBC as an OFFICIAL FINANCIAL_CAPITAL source, but no production-authoritative PBC live collector is enabled yet.
- Existing TickFlow support provides indices, A-share breadth and total market amount when configured; it does not prove industry-to-industry capital migration and must not be relabeled as direct fund flow.
- CURRENT_FUNDS.md intentionally has no confirmed rows because no sufficiently current user-confirmed fund snapshot exists; LATEST_HOLDINGS_NOT_PERSISTED is a safety state, not a broken pipeline.
- Off-session live quote coverage 0/4 is expected fail-closed behavior. During an active A-share session, the direct quote workflow should attempt current holding/BUY/WAIT_PRICE coverage and then refresh the final Decision Center.

## Blockers
- Deep `35518154713` has not yet produced its terminal post-#225 production result.
- This branch has not yet passed fresh PR CI.
- Financial-capital live evidence remains incomplete; do not add an unverified PBOC scraper merely to make the report look complete.

## Next Action
1. Open the current report-convergence PR and run fresh CI.
2. Fix any real CI failures without weakening evidence, Formal authority, Candidate Lifecycle or no-auto-trade.
3. Continue following Deep `35518154713` without starting a competing Deep.
4. When Deep finishes, compare CNINFO 403 470→?, predictability_verified 0→?, unknown_gate_count 4021→?, new_evidence_count 1501→?, final_failed 999→?, final_missing 327→?.
5. Inspect any newly verified predictability rows for official source_urls and complete metrics_by_year under the unchanged three-complete-fiscal-year rule.
6. Verify Deep → Provenance → Terminal Research → Investor → Decision Center convergence.
7. Only after that production evidence is captured, merge this report-convergence PR and verify the new 50k/account/capital-coverage/quote-convergence report on main.
8. Close obsolete #224 and #226 after their required intent is safely represented in merged current-main work.
9. Treat a production PBC/financial-capital collector as the next evidence-layer implementation only after official endpoint/parser/PIT/failure semantics are validated.

## Do Not Repeat
- Do not reopen #223 liveness work without contradictory production evidence.
- Do not use Deep `35510170838` or 375 query failures as the authoritative pre-#225 benchmark; use `35513686165` and 470.
- Do not redo merged CNINFO/SSE/SZSE routing work from #175/#179/#187/#189/#198/#207/#225.
- Do not label market/industry behavior, turnover or price strength as direct financial-capital flow.
- Do not infer missing fund holdings from old conversations or stale screenshots.
- Do not expose thousands of RESEARCH_GAP rows as if “gap” itself were an investor action; user-facing action is wait/do-not-buy unless evidence and authority permit more.
- Do not loosen predictability, valuation, BUY/WAIT_PRICE/REJECT, Candidate Lifecycle, Formal authority, UNKNOWN != PASS, or no_auto_trade.

## Guardrails
- GitHub live state is the source of truth.
- Preserve exact run/profile/source/code-epoch lineage.
- Production artifacts are required in addition to tests.
- Formal/Production authority remains separate from Research outputs.
- Transport success alone is not evidence PASS.
- UNKNOWN != PASS.
- no_auto_trade=true.
