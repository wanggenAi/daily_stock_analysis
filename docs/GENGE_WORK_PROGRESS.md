# GenGe / daily_stock_analysis — Production Work Handoff

Last updated: 2026-08-18 (Asia/Shanghai)
Repository: wanggenAi/daily_stock_analysis
Branch: main

## Product invariants agreed with the user

1. Research Pool must be wide; Formal BUY must remain strict.
2. Every represented industry/sector must retain research results. Target: 3–5 research names per industry where available. A bad industry may have zero investable names, but it must not silently disappear.
3. Formal BUY must not collapse to zero because of mechanical/soft gates. Zero Formal BUY is acceptable only when the market is genuinely defensive/RED or no candidate passes true hard investment logic. Otherwise it must trigger a second-pass audit.
4. Do not fabricate BUYs to meet a quota. Hard blockers, financial integrity, data freshness, valuation/MOS, real risk/reward, and major risk events remain binding.
5. A medium-term/60-day exit-profile sample shortage must not masquerade as a long-term investment veto. Surface candidates that pass all non-exit-profile hard gates separately.
6. Reverse valuation is a parallel opportunity-discovery channel so scarce-resource/cyclical/growth opportunities are not lost merely because technical quant ranking is lower.
7. No auto-trading. Research/routing sidecars must not silently grant Formal BUY eligibility.
8. Production observability is required: All-A should log processed/total, %, speed, current code, cache/failure counts and ETA without materially slowing the scan.

## Latest production state

Upstream workflow: `GenGe Opportunity Discovery`
Run: `32036451355`
Re-run attempt: `2`

**Result: SUCCESS.**

The `All-A production research report` job completed successfully, including the unified scan, report contract validation, summary publication, cache save and artifact upload. New artifact: `genge-all-a-production-report`, artifact id `9307071666`, created 2026-08-18 01:08:08 UTC.

This attempt checked out older code (`0dc6c8f8...`), so newer architecture changes below were not used by this successful scan. They require a fresh production run for end-to-end validation.

## Key findings from the real 2026-08-18 artifact

Resolved market data date: `2026-08-17`.

- official universe: 5209
- effective scan: 4510
- market regime: `GREEN`
- market regime score: `82.21`
- external risk: `LOW`
- strict_review_ready_count: `0`
- buy_signal_count: `0`
- condition_watch_count: `2`
- research_watch_count: `10`
- evidence queue: `80`
- deep review: `80`

This is exactly the failure mode the new design must prevent from being silently accepted: the market is GREEN, yet Formal BUY collapsed to zero.

Most important real examples:

- `603369 今世缘`: actionability 76.9699, R/R 7.05. Failed strict gates are only `exit_profile_passed; exit_profile_sample_count; exit_profile_recent_2y_samples; exit_profile_confidence`.
- `688687 凯因科技`: actionability 74.6814, R/R 3.25. Failed strict gates are only the same exit-profile family.
- `688606 奥泰生物`: actionability 73.1885, R/R 3.53. Exit-profile failures plus `event_risk_not_high`, so it is **not** an exit-profile-only long-term second-pass candidate yet.

Therefore the old 60-day/medium-horizon exit-profile gate demonstrably erased candidates that passed every other strict gate. This validates the user's requirement that exit-profile sample shortage must not be treated as a long-term investment veto.

## Implemented commits in this workstream

- `d285887523982f5a439a0d8e5e19b4fcfd5231cc` — fix valuation routing trigger.
- `e963a352` — every-industry coverage core, up to Top5 research names per industry.
- `c08fecc` — industry coverage tests.
- `168b42dc0ade152aadd6679ed6b392aab32981a1` — `GenGe Industry Coverage` workflow.
- `234691f7de57897c325dc20cf18602408308793b` — Zero Formal BUY audit core.
- `418ad25680f6ba67c5336344d64a10b2ea99db70` — Zero-BUY audit tests.
- `26ee2320d06eb38d4f92eff8197d80d31336070d` — Zero-BUY audit workflow.
- `b6e9b39d513b1dc6030125d8fe38503781f21af7` — initial industry-to-valuation bridge.
- `5c3dcc677615b56abae1e9338e47d43e421a92ea` — fix bridge semantics so industry slots are truly additive.
- `4c93d056936e55b65dd56f1e54e93b9da1d3d278` — bridge tests.
- `a0b7e35e21000b41d57f93981c7df66b233001a2` — wire industry coverage into valuation workflow; intended semantics Global Top80 + up to Top3 clean candidates per industry, valuation capacity ~320, deep financial review 80.
- `569bade04f244bc75041203a8632e979a13981f4` — low-overhead All-A progress runner with processed/total, %, throughput, ETA and current code.
- `a3fac60f90c08432048924c42a434fa59f1771e8` — progress instrumentation tests.
- `971a8bbdfdb4b6d8038a7f13a2c545b089516133` — long-term second-pass selector for candidates blocked only by exit-profile validation.
- `ef631217e4efe237b21a8930a660a89a773d482e` — long-term second-pass tests.
- `f4e9f0a9185a11eaac6125c527bf03b781c8b003` — `GenGe Long Term Second Pass` workflow.
- `c9a39510287dcc6f7e76733bbb509d29e1c141f7` — create clean durable handoff path `docs/GENGE_WORK_PROGRESS.md` after detecting an invisible character in the original filename.

## Current intended architecture

All-A universe
  -> hard data/risk/liquidity/history filters
  -> quant screen
  -> parallel recall paths:
       A. global opportunity recall
       B. every-industry Top3–5 research champions
       C. long-term second pass for exit-profile-only blocked names
  -> merge/de-duplicate (`GLOBAL_RECALL`, `INDUSTRY_CHAMPION`, `BOTH`, long-term second pass)
  -> reverse valuation + valuation model routing
  -> evidence/fundamental/financial checks
  -> market/industry regime + entry/MOS/R:R
  -> Formal BUY decision
  -> if Formal BUY == 0 and market is not defensive: mandatory Zero-BUY audit and second pass

Industry representation and long-term second pass are recall layers only. Neither may erase hard blockers or auto-promote a stock to Formal BUY.

## Progress instrumentation status

`all_a_progress_runner.py` is implemented with tests, but the production `GenGe Opportunity Discovery` workflow has **not yet** been switched from `all_a_full_scan` to this wrapper. Do not claim live progress instrumentation until that command is changed and a fresh run proves the logs.

## Next work — do these in order

1. Switch the production All-A command to `src.strategies.genge_opportunity_discovery.all_a_progress_runner`, then prove real progress logs on a fresh run.
2. Verify the newly fixed `GenGe Valuation Research Queue` automatically triggered after run 32036451355 and inspect `valuation_research_routed.csv`. If it did not trigger, continue fixing the workflow_run chain.
3. Feed `long_term_second_pass_candidates.csv` into valuation/fundamental review so names such as 603369/688687 cannot disappear solely because of exit-profile history coverage.
4. Add a final production contract: `market != defensive AND Formal BUY == 0` must not publish as an ordinary success unless the Zero-BUY audit proves no candidate survives all true hard gates + valuation/fundamental review.
5. Produce final every-industry Top3–5 results plus Master Opportunity Ranking across industry champions.
6. After valuation routing is complete, produce actionable long-term candidates with entry zone, invalidation/risk level, valuation/fundamental target range and long-term review/exit logic. Do not publish these from incomplete intermediate artifacts.

## Resume instruction for a new ChatGPT session

Tell ChatGPT:

`继续 daily_stock_analysis，先读取仓库 docs/GENGE_WORK_PROGRESS.md，然后核对 main 最新 commits 和 GitHub Actions 状态，从 Next work 第一项继续，不要重新设计已经完成的部分。`

This file is the durable source of truth for handoff. Update it after each meaningful implementation milestone or production finding.
