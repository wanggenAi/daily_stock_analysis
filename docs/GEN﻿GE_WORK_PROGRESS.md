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
8. Production observability is required: All-A should eventually log processed/total, %, speed, current code, cache/failure counts and ETA without materially slowing the scan.

## Production incident being followed

Upstream workflow: GenGe Opportunity Discovery
Run: 32036451355
Re-run attempt: 2
Last observed state in this work session: All-A production research report still `in_progress` at step `Run unified all-A production scan`; fixture smoke succeeded. This attempt checked out older code, so changes below apply to subsequent runs, not the already-running attempt.

Original downstream failure: GenGe Valuation Research Queue was skipped/not successfully triggered after a successful All-A run.

## Implemented commits in this session

- `d285887523982f5a439a0d8e5e19b4fcfd5231cc` — fix valuation routing trigger: workflow_run only requires successful upstream conclusion; remove brittle coupling to upstream trigger type.
- `e963a352` — industry coverage core: every-industry research map, up to Top5 per industry.
- `c08fecc` — tests for industry coverage.
- `168b42dc0ade152aadd6679ed6b392aab32981a1` — `GenGe Industry Coverage` production workflow.
- `234691f7de57897c325dc20cf18602408308793b` — Zero Formal BUY audit core logic.
- `418ad25680f6ba67c5336344d64a10b2ea99db70` — Zero-BUY audit tests.
- `26ee2320d06eb38d4f92eff8197d80d31336070d` — Zero-BUY audit workflow.
- `b6e9b39d513b1dc6030125d8fe38503781f21af7` — initial industry-to-valuation bridge.
- `5c3dcc677615b56abae1e9338e47d43e421a92ea` — fix bridge semantics so industry slots are truly additional rather than being swallowed by full All-A de-duplication.
- `4c93d056936e55b65dd56f1e54e93b9da1d3d278` — bridge tests including cold-industry supplementation, BOTH channel and hard-blocker behavior.
- `a0b7e35e21000b41d57f93981c7df66b233001a2` — wire industry coverage into the formal valuation workflow. Intended production semantics: Global Top80 + up to Top3 clean candidates per industry, de-duplicated; valuation capacity expanded to roughly 320 and deep financial review to 80.

## Current intended architecture

All-A universe
  -> hard data/risk/liquidity/history filters
  -> quant screen
  -> two parallel recall paths:
       A. global opportunity recall
       B. every-industry Top3–5 research champions
  -> merge/de-duplicate (`GLOBAL_RECALL`, `INDUSTRY_CHAMPION`, `BOTH`)
  -> reverse valuation + valuation model routing
  -> evidence/fundamental/financial checks
  -> market/industry regime + entry/MOS/R:R
  -> Formal BUY decision
  -> if Formal BUY == 0 and market is not truly defensive: Zero-BUY second-pass audit

Industry representation is research recall only. It never deletes hard blockers or auto-promotes a stock to BUY.

## Important current code behavior / known issue

`valuation_research_report.py` historically selected a bounded broad-recall pool with `research_limit=80`, `relaxed_reserve=20`, then ranked reverse-PE diagnostics and performed limited financial review. The new workflow/bridge is intended to remove the structural problem where those 80 global seats could exclude entire industries.

The initial bridge version mistakenly used the complete All-A quant screen as the global side, which meant every industry name already existed and got de-duplicated; commit `5c3dcc67` corrected this so industry slots are actually additive.

## Next work — do these in order

1. Verify the new industry-aware valuation workflow end-to-end on a fresh run. Contract must prove clean represented industries reach valuation source; inspect `valuation_research_routed.csv`.
2. Add production progress logging to the real All-A expensive loops (history fetch/as_completed and quant_screen): processed/total, percentage, throughput, ETA, current code, cache/failure counts; throttle output (e.g. every 50–100 names or 10–15 seconds).
3. Connect Zero-BUY second-pass candidates back into the final Formal BUY decision/reporting path. It must distinguish hard blockers from soft/exit-profile-only blockers and never synthesize BUY eligibility.
4. Add a production contract: non-defensive market + zero Formal BUY cannot silently publish as normal; require an audit explanation and second-pass result.
5. Ensure 60-day exit-profile insufficiency is separately reported as a medium-term validation limitation, not a long-term hard veto when all non-exit-profile hard gates pass.
6. Produce final per-industry output (target 3–5 names where available) plus Master Opportunity Ranking across industry champions.
7. After a fresh successful run, report actionable candidates with entry zone, invalidation/risk level, valuation/fundamental target range, and long-term review/exit logic. Do not publish these from incomplete intermediate artifacts.

## Resume instruction for a new ChatGPT session

Tell ChatGPT: `继续 daily_stock_analysis，先读取仓库 docs/GENGE_WORK_PROGRESS.md，然后核对 main 最新 commits 和 GitHub Actions 状态，从 Next work 第一项继续，不要重新设计已经完成的部分。`

The repository file is the durable source of truth for handoff; update it after each meaningful implementation milestone or production finding.
