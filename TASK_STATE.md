# Current Mission

## Goal
Converge the existing stock system into one trustworthy daily decision surface for a user-confirmed CNY 50,000 stock-account planning cash balance. The final report must connect social/macro structure, capital-flow evidence, A-share market/industry state, Candidate Lifecycle, Deep research, valuation, holdings and a concrete cash/action table. Preserve Candidate Lifecycle, valuation/decision thresholds, Formal authority separation, UNKNOWN != PASS, and no_auto_trade=true.

This is a repository-wide report-readiness closure mission, not a single-PR feature task. Before the mission can be declared complete, scan the current real repository and production chain for every material capability that should affect the final daily report, classify what is ACTIVE / PARTIAL / BROKEN / DESIGNED_ONLY / STALE / DISCONNECTED, and fix every material unfinished, low-quality, disconnected, invisible, duplicated, stale, or evidence-insufficient path that prevents the report from being trustworthy and useful.

## Mission Acceptance Criteria
- Do not stop because one PR merged or CI is green. Continue until the report-facing production chain is audited end-to-end from current GitHub truth.
- Inventory existing capabilities and verify whether each one is actually wired into production and visible in the final investor report. A prompt, design document, isolated module, test fixture, stale artifact, or unused workflow is not implementation.
- At minimum audit: holdings reconciliation; Candidate Lifecycle/history continuity; all-market/every-industry scanning; market/industry trend analysis; Era/social/macro evidence; policy/industrial/financial-capital/real-demand evidence; news/event/evidence freshness; PIT/provenance; Deep research; specialized and generic valuation; reverse valuation/price anchors; Formal/Canonical authority; opportunity routing; BUY/WAIT_PRICE/REJECT and RESEARCH_GAP translation; account cash/deployment; live execution quotes; report/dashboard wiring; persistence; concurrency/idempotency; stale-state protection; workflow lineage; production observability.
- Explicitly find and fix the failure patterns the user has repeatedly observed: trend/large-context analysis exists but is absent from the daily report; reports repeatedly surface only old holdings; evidence gaps end in engineering wording or no actionable result; features execute but are not consumed downstream; stale state or duplicate workflows overwrite newer truth; data fallbacks/mock/partial sources masquerade as complete; candidate/research results disappear between days; valuation results exist but do not reach Canonical/reporting.
- Missing evidence must remain UNKNOWN / INPUTS_REQUIRED / RESEARCH_GAP as appropriate. Never convert missing evidence into PASS merely to make the report complete.
- Fixes must be structural/general, not ticker-specific patches.
- Every material fix requires code/test/PR/CI plus main/production/artifact/persisted-state/downstream-lineage verification where applicable.
- If a material report-readiness gap cannot be fixed because of a real external blocker, record the blocker, exact affected capability, current fail-closed behavior, and next executable action here. Do not silently defer it.
- Mission completion requires a final capability matrix showing the major report-facing functions and their verified production status, plus a final production daily report proving the chain is connected.

## Current Phase
Finish PR #227 report-convergence work and then continue the repository-wide report-readiness audit from current main. #227 is a major closure step, not the end of the mission.

## Last Verified Main
- PR #223 is merged and production-verified.
- PR #225 is merged at Deep/evidence code epoch `9a681db9f52520d0d37e95c082c596c5735a0c1f`.
- Live main observed after post-#225 production convergence reached at least `800c139d27fe46b121791f98cdc8a922f3d3739e` via data/runtime persistence commits.
- Live GitHub refs / PRs / Actions / artifacts / persisted data always override this checkpoint.

## Active Branch
`feat/complete-investor-report-20260920`

## Active PR
- #227 — `feat: complete investor decision reporting pipeline`.
- #227 is mergeable and contains report convergence, CNY 50,000 account planning, investor-facing research actions, Era evidence-family coverage, official NBS INDUSTRIAL_CAPITAL and PBC FINANCIAL_CAPITAL live collectors, quote-to-final-report convergence, and the replayed #224 logical-workset Deep concurrency fix.
- #227 supersedes the implementation intent of stale/open #224 and stale docs checkpoint #226 once verified and merged.

## CI
- PR #227 CI run `35520607143` is active at this checkpoint.
- Change Detection: success.
- ai-governance: success.
- docker-build: success.
- web-gate: skipped as expected for the changed paths.
- backend-gate deterministic checks passed; the offline test suite is still running.
- Do not merge until fresh blocking CI for the current PR head is green.

## Production / Artifact
- Authoritative pre-#225 baseline: Deep `35513686165`, source Every-Industry `35513006839`.
- Baseline: requested=852; unknown_gate_count=4021; new_evidence_count=1501; predictability_verified=0; final_failed=999; final_missing=327.
- Baseline predictability HTTP-403 bucket: 470 `ANNUAL_REPORT_QUERY_FAILED:PRIMARY:HTTPError:403,CNINFO:HTTPError:403`.
- Post-#225 Deep `35518154713` completed successfully at code epoch `9a681db9f52520d0d37e95c082c596c5735a0c1f`.
- Post-#225 result: CNINFO predictability HTTP-403 bucket=375, an improvement of 95 from the 470 baseline; unresolved_requested_gate_count=4021; new_evidence_count=1501; hard_gate_passed_count=1; final_failed_count=79; final_missing_count=209; complete_requested_count=0; partial_requested_count=852.
- Deep `35518154713` persisted terminal state, uploaded its artifact, and dispatched downstream convergence successfully.
- Transport recovery is not evidence PASS; unresolved evidence remains fail-closed.
- PR-head Era Radar deterministic contracts pass, but live-production is skipped on PR. Real NBS/PBC retrieval and persisted production evidence must be verified after merge.

## Completed
- User-confirmed stock planning cash changed from the old CNY 57,000 floor to CNY 50,000; the old exact broker snapshot is retained only as historical reference.
- Final Decision Center now exposes a `today_account_plan` with available cash, deployment budget, planned immediate cash, cash after plan, quote coverage and plain-language cash action.
- Current Terminal RESEARCH_GAP rows are translated for the investor as `暂不买；等待补齐...` instead of ending at engineering terminology.
- Decision Center reads the exact Era Radar evidence bundle for the active snapshot and reports POLICY_CAPITAL / INDUSTRIAL_CAPITAL / FINANCIAL_CAPITAL / REAL_DEMAND / TECHNOLOGY / GLOBAL_STRUCTURE counts.
- Missing evidence is explicit and market/industry-strength proxies cannot be promoted into direct stock fund-flow evidence.
- #227 adds official NBS fixed-asset-investment evidence as INDUSTRIAL_CAPITAL and official PBC financial-statistics evidence as FINANCIAL_CAPITAL, with parser/freshness/schema failures fail-closed.
- Live Execution Quote Refresh dispatches Three-Pillar Decision Center after quote persistence so the final report cannot silently lag refreshed execution prices.
- #224 logical-workset Deep concurrency fix is replayed on current main in #227: default Deep work is grouped by logical workset instead of runtime SHA.
- PR #227 description has been corrected to match its actual NBS/PBC/report-convergence scope and post-#225 production evidence.
- No BUY/WAIT_PRICE/REJECT thresholds, valuation formulas, Formal authority, Candidate Lifecycle or no-auto-trade rules were changed.

## Current Findings
- The original mission is broader than #227: the repository still requires a systematic post-merge capability audit before declaring report readiness complete.
- Post-#225 CNINFO transport improved the HTTP-403 bucket from 470 to 375, but 375 transport failures remain and must not be hidden.
- Current unresolved requested gate count remains 4021; evidence completeness is therefore still materially limited even though the user-facing report can be action-complete by translating uncertainty into wait/do-not-buy/keep-cash actions.
- Current pre-#227 production Era Radar evidence lacked direct FINANCIAL_CAPITAL coverage. #227 implements PBC live evidence and NBS industrial-capital evidence, but production network retrieval/persistence is not yet proven.
- Existing TickFlow support provides indices, A-share breadth and total market amount when configured; it does not prove industry-to-industry capital migration and must not be relabeled as direct fund flow.
- CURRENT_FUNDS.md intentionally has no confirmed rows because no sufficiently current user-confirmed fund snapshot exists; LATEST_HOLDINGS_NOT_PERSISTED is a safety state, not automatically a broken pipeline.
- Off-session live quote coverage 0/4 can be expected fail-closed behavior. During an active A-share session, the direct quote workflow should attempt current holding/BUY/WAIT_PRICE coverage and refresh the final Decision Center.
- A green CI result alone does not prove the original repository-wide report-readiness mission is complete.

## Blockers
- PR #227 current-head blocking CI is not yet complete.
- PBC/NBS live network collection and persisted evidence have not yet been production-verified on main.
- The repository-wide post-#227 report-readiness capability matrix has not yet been completed.
- Remaining CNINFO/predictability and other Deep evidence gaps remain real evidence limitations and must stay explicit.

## Next Action
1. Finish fresh #227 CI; fix only real failures without weakening evidence, Formal authority, Candidate Lifecycle or no-auto-trade.
2. Merge #227 only when the current head is green.
3. Verify main production: NBS/PBC source retrieval, source URLs/publication timestamps/freshness, Era evidence persistence, Era → Investor → Decision Center convergence, CNY 50,000 account plan, and quote-to-final-report refresh.
4. Close obsolete #224 and #226 only after their required intent is represented in merged main.
5. Resume the repository-wide report-readiness audit from live main rather than declaring the mission complete.
6. Build/refresh a capability matrix for all major report-facing subsystems and classify each as ACTIVE / PARTIAL / BROKEN / DESIGNED_ONLY / STALE / DISCONNECTED, backed by code + workflow + production evidence.
7. For every PARTIAL/BROKEN/DISCONNECTED material capability, trace the full path from source/input → evidence/PIT → model/research/valuation → Canonical/Formal authority → persisted state → final report, fix the root cause structurally, and production-verify it.
8. Re-check the known high-risk classes: trend/context missing from report; reports dominated by old holdings; candidate lifecycle/history loss; evidence-insufficient/no-result loops; specialized valuation not reaching generic merge/Canonical; sidecars/features not consumed downstream; stale/duplicate workflow writers; fallback/mock/partial data presented as real; missing report observability.
9. Produce the final capability matrix and a fresh production daily report only after all material gaps are either fixed or explicitly blocked with fail-closed behavior.

## Do Not Repeat
- Do not treat #227 merge as mission completion.
- Do not reopen #223 liveness work without contradictory production evidence.
- Do not use Deep `35510170838` or 375 query failures as the authoritative pre-#225 benchmark; use `35513686165` and 470.
- Do not redo merged CNINFO/SSE/SZSE routing work from #175/#179/#187/#189/#198/#207/#225 unless fresh production evidence contradicts it.
- Do not label market/industry behavior, turnover or price strength as direct financial-capital or stock fund-flow evidence.
- Do not infer missing fund holdings from old conversations or stale screenshots.
- Do not expose thousands of RESEARCH_GAP rows as if “gap” itself were an investor action; user-facing action is wait/do-not-buy unless evidence and authority permit more.
- Do not count prompts, docs, isolated modules, stale artifacts or tests as production implementation without runtime/workflow/report evidence.
- Do not patch individual tickers when the defect is structural.
- Do not loosen predictability, valuation, BUY/WAIT_PRICE/REJECT, Candidate Lifecycle, Formal authority, UNKNOWN != PASS, or no_auto_trade.

## Guardrails
- GitHub live state is the source of truth.
- Preserve exact run/profile/source/code-epoch lineage.
- Production artifacts are required in addition to tests.
- Formal/Production authority remains separate from Research outputs.
- Transport success alone is not evidence PASS.
- UNKNOWN != PASS.
- no_auto_trade=true.
