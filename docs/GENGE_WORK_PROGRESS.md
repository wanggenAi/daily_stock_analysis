# GenGe / daily_stock_analysis — Production Work Handoff

Last updated: 2026-08-18 (Asia/Shanghai)
Repository: wanggenAi/daily_stock_analysis
Branch: main

## Product invariants

1. Research Pool must be wide; Formal BUY must remain strict.
2. Every represented industry must retain research visibility, target 3–5 names where available. A bad industry may have zero investable names, but it must not silently disappear.
3. Formal BUY must not collapse to zero because of soft/mechanical gates. Zero is acceptable only for a genuinely defensive market or when no candidate survives true hard investment logic + valuation/fundamental review.
4. Never fabricate BUYs to meet a quota. Hard blockers, financial integrity, data freshness, valuation/MOS, real R/R and major risk events remain binding.
5. 60-day/medium-horizon exit-profile sample shortage is not a long-term investment veto. Surface candidates passing all non-exit-profile hard gates separately and force them through valuation/fundamental review.
6. Reverse valuation is a parallel discovery channel so scarce-resource/cyclical/growth opportunities are not lost merely because technical quant ranking is lower.
7. No auto-trading. Recall/routing sidecars do not silently grant Formal BUY eligibility.
8. Production observability is required: processed/total, %, throughput, ETA, current code, cache/failure counts.

## Latest real production evidence

Workflow: `GenGe Opportunity Discovery`
Run: `32036451355`
Attempt 2: SUCCESS.
Artifact: `genge-all-a-production-report`, id `9307071666`, created 2026-08-18 01:08:08 UTC.

Resolved market date: `2026-08-17`.

- official universe: 5209
- effective scan: 4510
- market regime: GREEN
- market score: 82.21
- external risk: LOW
- strict_review_ready_count: 0
- buy_signal_count: 0
- condition_watch_count: 2
- research_watch_count: 10
- evidence queue: 80
- deep review: 80

This proves the old funnel could collapse to zero even in a strong market.

Critical real examples:

- `603369 今世缘`: actionability 76.9699, R/R 7.05; failed strict gates only exit-profile family.
- `688687 凯因科技`: actionability 74.6814, R/R 3.25; failed strict gates only exit-profile family.
- `688606 奥泰生物`: actionability 73.1885, R/R 3.53; exit-profile failures plus `event_risk_not_high`, therefore not exit-profile-only.

## Current production validation run

The successful All-A job from run `32036451355` has now been re-run again to create a new upstream completion event after the unified postscan workflow was added.

- original All-A job id: `95555128057`
- re-run request: accepted successfully
- treat this as the current validation attempt (attempt 3 / next attempt of run 32036451355)
- purpose: prove `GenGe Postscan Research Pipeline` triggers and generates routed valuation outputs using the latest default-branch code.

## Implemented commits

- `d285887523982f5a439a0d8e5e19b4fcfd5231cc` — robust valuation workflow_run trigger.
- `e963a352` / `c08fecc` / `168b42dc` — every-industry Top5 coverage core, tests and workflow.
- `234691f7` / `418ad256` / `26ee2320` — Zero Formal BUY audit core, tests and workflow.
- `5c3dcc67` / `4c93d056` / `a0b7e35e` — real additive industry valuation bridge + production wiring; Global Top80 + up to Top3 clean names/industry.
- `569bade0` / `a3fac60f` — low-overhead All-A progress runner + tests. Not yet live in production command.
- `971a8bbd` / `ef631217` / `f4e9f0a9` — long-term second pass for exit-profile-only blocked names + tests/workflow.
- `28871c93ef18cb0c4f3167ac4745746cfbb584e6` — merge long-term second-pass names into valuation source so they cannot remain a sidecar only.
- `332e53459c5c0a0fce39a91b1d022c4f3740d335` — long-term valuation merge tests.
- `0e23a87faff56b36b51be700ae83cb6ee2ccead8` — unified `GenGe Postscan Research Pipeline`.
- `c9a39510` — clean durable handoff path `docs/GENGE_WORK_PROGRESS.md`.

## Unified architecture now intended

All-A universe
  -> hard data/risk/liquidity/history filters
  -> quant screen
  -> recall A: global opportunity leaders
  -> recall B: every-industry Top3–5 champions
  -> recall C: exit-profile-only long-term second-pass names
  -> merge/de-duplicate
  -> reverse valuation
  -> valuation model routing
  -> evidence/fundamental/financial checks
  -> Zero-BUY audit
  -> final long-term decision/reporting

`GenGe Postscan Research Pipeline` now executes the downstream chain in one workflow instead of relying on four independent workflow_run listeners. Its production contract requires:

- clean industries represented in valuation source;
- all long-term second-pass names present in final valuation source;
- all long-term second-pass names survive into valuation research queue;
- `valuation_research_routed.csv` exists and row counts match routing summary;
- non-defensive zero BUY cannot silently terminate as an ordinary conclusion.

Valuation research capacity in the unified workflow is currently up to 500 names with deep financial review up to 100, to avoid industry/long-term names being squeezed out by a global Top80 cap.

## Progress instrumentation

`all_a_progress_runner.py` and tests exist, but `GenGe Opportunity Discovery` still invokes `all_a_full_scan` directly. Do not claim percentage/ETA logging is live yet. Switch only after validating wrapper safety.

## Next work — exact order

1. Watch the current All-A re-run until completion. Then verify `GenGe Postscan Research Pipeline` actually triggers from the new completion event.
2. Inspect unified postscan artifact and especially `valuation_research_routed.csv`. Confirm 603369 and 688687, if still qualifying in that All-A snapshot, are not dropped before valuation.
3. If unified postscan fails, fix the exact failed step immediately; do not fall back to separate manual sidecars.
4. Build the final long-term Formal BUY decision layer using true hard gates + valuation/fundamental confirmation, while treating exit-profile-only shortage as medium-horizon validation rather than a long-term veto.
5. Only after that layer is validated, enforce: non-defensive market + zero long-term Formal BUY must have explicit proof that no candidate survives true hard logic + valuation/fundamental review.
6. Switch All-A production command to the tested progress runner and prove real `% / speed / ETA` logs on a fresh run.
7. Produce final every-industry Top3–5 map + Master Opportunity Ranking + actionable long-term candidates with entry zone, invalidation, valuation/fundamental target range and long-term review/exit logic.

## Resume instruction for a new ChatGPT session

Tell ChatGPT:

`继续 daily_stock_analysis，先读取仓库 docs/GENGE_WORK_PROGRESS.md，然后核对 main 最新 commits 和 GitHub Actions 状态，从 Next work 第一项继续，不要重新设计已经完成的部分。`

This file is the durable source of truth. Update it after every meaningful implementation milestone or production finding.
