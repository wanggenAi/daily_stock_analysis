# Current Mission

## Goal
Close the dominant V3.1 moat evidence gap with a strict, auditable multi-year official-report rule while preserving the existing Deep -> Terminal -> Investor -> Three-Pillar authority boundaries.

## Current Phase
STRICT_MULTI_YEAR_MOAT_CODE_WRITTEN_AWAITING_PR_CI

## Last Verified Main
- Live main at mission start: `25468263d23ed5aa40a1d830c67e8b5d9ebd8c62`.
- Previous official-evidence mission is complete and production verified through Deep `35679085547` -> Provenance `35679518840` -> Terminal `35679520250` -> Investor `35679622373` -> Three-Pillar `35679743365`.
- Live GitHub refs / Actions / persisted data always override this checkpoint.

## Active Branch
- `feat/strict-multiyear-moat-evidence-20260922`.
- Last code/docs commit before this checkpoint: `6313b521eab244e6a1e0e05497fcc3c9d2c266fe`.

## Active PR
- None yet. Next stage is PR creation from the active branch to `main`.

## CI
- Not started for this branch yet.
- Required after PR creation: blocking CI plus deep-calculation contract tests.
- No production claim is allowed until post-merge Deep artifacts verify the new rule on live official reports.

## Production / Artifact Baseline
- Deep `35679085547`: requested=22, unresolved_requested_gate_count=93, progressed_gate_count=3, predictability_resolved_gate_count=1.
- Terminal `35679520250`: requested=22, RESEARCH_GAP=22, BUY=0, WAIT_PRICE=0, REJECT=0.
- Dominant unresolved distribution: moat=21, predictability=21, long_term_demand=19, earnings_authenticity=16, financial_safety=16.
- Moat dominant reason: `NO_STRICT_MACHINE_RULE_PROVES_DURABLE_COMPETITIVE_ADVANTAGE` x21.
- `603993` already has explicit verified moat PASS and is blocked only by predictability; do not use it as proof that the new automatic moat rule works.

## Completed
- Reconfirmed live main, AGENTS.md, TASK_STATE.md, open historical PRs, recent commits and the persisted 22-name Terminal/Three-Pillar state.
- Rejected repeating #266/#267 and rejected a narrow 603993 parser patch that would not change its terminal state.
- Identified moat as the largest unresolved hard-gate class and verified that current automatic Deep has no moat inference function.
- Added strict multi-year moat extraction to the existing official annual-report collector without a second network-download fanout.
- Added automatic moat closure in `v31_deep_gap_closure.py`.
- Added unit/closure regression tests plus `docs/V31_DEEP_EVIDENCE_CLOSURE.md` and changelog entry.

## Current Findings
- The new rule is PASS-only and fail-closed: absence/ambiguity remains UNKNOWN; it does not manufacture moat FAIL.
- PASS requires the same strong moat category in two consecutive fiscal-year official reports plus at least one second corroborating category across the pair.
- Generic phrases such as “加大研发投入 / 保持行业领先 / 积极拓展客户”, one-year evidence, and patent-count-only evidence remain UNKNOWN.
- The rule reuses annual-report bodies already fetched for strict predictability, so it does not add another provider fanout.
- Jev/TypeSafe has not been invoked in this mission yet. All work so far is deterministic repository inspection and code/test construction. Historical Jev -> Orchestrator continuation remains separately production-proven.

## Blockers
- None currently. CI has not run yet.

## Next Action
1. Open PR from the active branch.
2. Read blocking CI/review; fix any failures on the same branch.
3. Merge only when blocking checks are green and head is current.
4. Verify live main.
5. Verify a fresh production Deep -> Provenance -> Terminal -> Investor -> Three-Pillar chain and measure `moat_resolved_gate_count` plus unresolved moat count.
6. Record whether Jev actually ran; do not report Jev usage unless a TypeSafe/Jev workflow log proves it.

## Do Not Repeat
- Do not redo Jev Phase 1/2/3 or recreate #242.
- Do not reopen stale #265 or replay #266/#267.
- Do not loosen long_term_demand's two-independent-official-source same-direction rule.
- Do not convert promotional moat language, a single report, or patent counts alone into PASS.
- Do not alter valuation formulas, BUY / WAIT_PRICE / REJECT thresholds, Candidate Lifecycle, Formal authority, UNKNOWN != PASS, or no_auto_trade.
- Do not infer completion from chat; use live GitHub.

## Guardrails
- GitHub live state is the source of truth.
- Jev direct dispatch=false.
- Deterministic bounded research dispatch is research-only.
- Formal trading authority=false.
- Automatic Formal BUY=false.
- UNKNOWN != PASS.
- no_auto_trade=true.
