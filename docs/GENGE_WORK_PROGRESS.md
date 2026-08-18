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

Critical real examples:

- `603369 今世缘`: actionability 76.9699, R/R 7.05; failed strict gates only exit-profile family.
- `688687 凯因科技`: actionability 74.6814, R/R 3.25; failed strict gates only exit-profile family.
- `688606 奥泰生物`: actionability 73.1885, R/R 3.53; exit-profile failures plus `event_risk_not_high`, therefore not exit-profile-only.

This proves the old funnel could collapse to zero even in a GREEN market and that medium-horizon exit-profile history can erase otherwise strict-qualified long-term candidates.

## Validation incident and correction

Re-running job `95555128057` created run attempt 3 for old run `32036451355`, but GitHub completed attempt 3 as `cancelled`. More importantly, that run remains permanently tied to old `head_sha=0dc6c8f8...`, so rerunning it cannot validate current-main architecture. Do not rerun that old run again for current-code validation.

Current validation now uses a fresh push-triggered workflow on current `main`:

- `d50bf65355b3555fcb4caf794901d0ef3973b6f2` — add temporary `.github/workflows/genge-opportunity-discovery-fresh-validation.yml`.
- The temporary workflow deliberately uses `name: GenGe Opportunity Discovery`, so existing `workflow_run` listeners can consume its successful completion exactly like the production upstream.
- It runs `all_a_progress_runner` with the production All-A parameters, validates core All-A outputs, saves cache and uploads artifact `genge-all-a-production-report`.
- `272c13d23b1ba7a8dd31cdd83fab49f68a346e51` — second marker push with commit message `[run-all-a] trigger fresh validation on current main`; this was created after the validation workflow already existed, eliminating ambiguity about whether a newly-added workflow can react to its own creation push.
- Marker file: `docs/GENGE_FRESH_VALIDATION_TRIGGER.md`; remove after successful end-to-end validation.

Expected validation chain:

Fresh current-main All-A with progress runner
  -> `genge-all-a-production-report`
  -> workflow_run completion under name `GenGe Opportunity Discovery`
  -> `GenGe Postscan Research Pipeline`
  -> industry coverage
  -> long-term second pass
  -> industry-aware + long-term valuation source merge
  -> reverse valuation
  -> valuation model routing
  -> zero-BUY audit
  -> unified artifact with `valuation_research_routed.csv`.

## Implemented commits

- `d2858875` — robust valuation workflow_run trigger.
- `e963a352` / `c08fecc` / `168b42dc` — every-industry Top5 coverage core, tests and workflow.
- `234691f7` / `418ad256` / `26ee2320` — Zero Formal BUY audit core, tests and workflow.
- `5c3dcc67` / `4c93d056` / `a0b7e35e` — real additive industry valuation bridge + production wiring; Global Top80 + up to Top3 clean names/industry.
- `569bade0` / `a3fac60f` — low-overhead All-A progress runner + tests.
- `971a8bbd` / `ef631217` / `f4e9f0a9` — long-term second pass for exit-profile-only blocked names + tests/workflow.
- `28871c93` — merge long-term second-pass names into valuation source so they cannot remain a sidecar only.
- `332e5345` — long-term valuation merge tests.
- `0e23a87f` — unified `GenGe Postscan Research Pipeline`.
- `c9a39510` — clean durable handoff path `docs/GENGE_WORK_PROGRESS.md`.
- `d50bf653` — current-main Fresh Validation workflow using progress runner.
- `272c13d2` — guaranteed fresh validation trigger push.

## Unified architecture

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

`GenGe Postscan Research Pipeline` runs the downstream chain in one workflow. Its contract requires:

- clean industries represented in valuation source;
- all long-term second-pass names present in final valuation source;
- all long-term second-pass names survive into valuation research queue;
- `valuation_research_routed.csv` exists and routing row counts match;
- non-defensive zero BUY cannot silently terminate as an ordinary conclusion.

Valuation research capacity in the unified workflow is up to 500 names with deep financial review up to 100 so industry/long-term recall cannot be squeezed out by the old global Top80 budget.

## Progress instrumentation

`all_a_progress_runner.py` logs processed/total, percentage, throughput, ETA and current code without changing screening formulas. The temporary Fresh Validation workflow is the first live end-to-end validation of this runner. Do not claim the normal scheduled production workflow has switched to it until Fresh Validation succeeds and the main workflow command is subsequently updated.

## Next work — exact order

1. Verify the fresh validation triggered from commit `272c13d2`; obtain its new run id and inspect progress-runner steps/logs.
2. If fresh All-A fails, fix the exact failure on current main and re-trigger with another `[run-all-a]` marker commit.
3. On fresh All-A success, verify `GenGe Postscan Research Pipeline` triggers automatically and inspect its exact failed/success steps.
4. Inspect unified postscan artifact, especially `valuation_research_routed.csv`; confirm long-term candidates such as 603369/688687, if still qualifying in the fresh snapshot, are not dropped before valuation.
5. Build the final long-term Formal BUY decision layer using true hard gates + valuation/fundamental confirmation while treating exit-profile-only shortage as medium-horizon validation rather than a long-term veto.
6. Enforce final invariant: non-defensive market + zero long-term Formal BUY requires explicit proof that no candidate survives true hard logic + valuation/fundamental review.
7. After Fresh Validation passes, switch the normal scheduled All-A production command to `all_a_progress_runner`, remove the temporary validation workflow/marker, and prove scheduled production remains green.
8. Produce final every-industry Top3–5 map + Master Opportunity Ranking + actionable long-term candidates with entry zone, invalidation, valuation/fundamental target range and long-term review/exit logic.

## Resume instruction for a new ChatGPT session

Tell ChatGPT:

`继续 daily_stock_analysis，先读取仓库 docs/GENGE_WORK_PROGRESS.md，然后核对 main 最新 commits 和 GitHub Actions 状态，从 Next work 第一项继续，不要重新设计已经完成的部分。`

This file is the durable source of truth. Update it after every meaningful implementation milestone or production finding.
