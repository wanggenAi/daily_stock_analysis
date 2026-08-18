# GenGe / daily_stock_analysis — Production Work Handoff

Last updated: 2026-08-18 (Asia/Shanghai)
Repository: wanggenAi/daily_stock_analysis
Branch: main

## Product invariants

1. Research Pool must be wide; Formal BUY must remain strict.
2. Every represented industry must retain research visibility, target 3–5 names where available. A bad industry may have zero investable names, but it must not silently disappear.
3. Formal BUY must not collapse to zero because of soft/mechanical gates. Zero is acceptable only for a genuinely defensive market or when no candidate survives true hard investment logic + completed valuation/fundamental review.
4. Never fabricate BUYs to meet a quota. Hard blockers, financial integrity, data freshness, valuation/MOS, real R/R and major risk events remain binding.
5. 60-day/medium-horizon exit-profile sample shortage is not a long-term investment veto. Candidates passing all non-exit-profile hard gates must be forced through valuation/fundamental review.
6. Reverse valuation is a parallel discovery channel so scarce-resource/cyclical/growth opportunities are not lost merely because technical quant ranking is lower.
7. Model selection is not model execution. Missing specialized-model execution, missing financial review or missing valuation inputs are production/research gaps, not proof that no opportunity exists.
8. No auto-trading. Research/routing/final-decision reports remain auditable and manual-review only.
9. Production observability is required: processed/total, %, throughput, ETA, current code, cache/failure counts.

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

## Validation incident and current validation method

Old run `32036451355` attempt 3 was `cancelled` and remains tied to old `head_sha=0dc6c8f8...`. Do not rerun that old run again to validate current code.

Fresh validation uses temporary workflow `.github/workflows/genge-opportunity-discovery-fresh-validation.yml` with workflow name `GenGe Opportunity Discovery`, so existing `workflow_run` downstream logic can consume a successful fresh run.

The temporary validation workflow is now restricted to changes of `docs/GENGE_FRESH_VALIDATION_TRIGGER.md` only. This prevents normal repository pushes from creating skipped same-name upstream runs and accidentally triggering Postscan without an artifact.

Latest validation trigger:

- `5f492bc21c07beebf133c91546cd4d67396cb90a` — `[run-all-a] validate long-term Formal BUY pipeline`
- This trigger is based on the latest main after long-term valuation priority and long-term Formal BUY integration.

Expected chain:

Fresh All-A using `all_a_progress_runner`
  -> `genge-all-a-production-report`
  -> `GenGe Postscan Research Pipeline`
  -> every-industry Top5
  -> long-term second pass
  -> industry-aware valuation source
  -> long-term candidates merged into valuation source
  -> long-term-priority reverse valuation / financial review
  -> valuation model routing
  -> long-term Formal BUY review
  -> legacy Zero-BUY audit
  -> unified artifact including `valuation_research_routed.csv` and final long-term decision report.

## Implemented commits

- `d2858875` — robust valuation workflow_run trigger.
- `e963a352` / `c08fecc` / `168b42dc` — every-industry Top5 coverage core, tests and workflow.
- `234691f7` / `418ad256` / `26ee2320` — Zero Formal BUY audit core, tests and workflow.
- `5c3dcc67` / `4c93d056` / `a0b7e35e` — additive industry valuation bridge + production wiring; Global Top80 + up to Top3 clean names/industry.
- `569bade0` / `a3fac60f` — low-overhead All-A progress runner + tests.
- `971a8bbd` / `ef631217` / `f4e9f0a9` — long-term second pass for exit-profile-only blocked names + tests/workflow.
- `28871c93` / `332e5345` — merge long-term second-pass names into valuation source + tests.
- `0e23a87f` — unified `GenGe Postscan Research Pipeline`.
- `d50bf653` — current-main Fresh Validation workflow.
- `7ab0a4d8` — scope Fresh Validation trigger to marker file only and include latest focused tests.
- `d949ec85` — add auditable `long_term_formal_buy.py` final decision layer.
- `b2765670` — tests for long-term BUY_READY / TRY_POSITION / blocked semantics.
- `134ff33e` — `valuation_research_long_term_runner.py`: preserve long-term source tags and prioritize long-term candidates for bounded financial deep review without changing valuation formulas.
- `d851885b` — tests for long-term valuation priority/source preservation.
- `65800b22` — integrate long-term-priority valuation and long-term Formal BUY review into unified Postscan workflow; final contract rejects non-defensive zero when caused by unresolved model/valuation/financial-review gaps.
- `5f492bc2` — latest fresh current-main validation trigger.
- `c9a39510` — clean durable handoff path `docs/GENGE_WORK_PROGRESS.md`.

## Unified architecture

All-A universe
  -> hard data/risk/liquidity/history filters
  -> quant screen
  -> recall A: global opportunity leaders
  -> recall B: every-industry Top3–5 champions
  -> recall C: exit-profile-only long-term second-pass names
  -> merge/de-duplicate
  -> reverse valuation
  -> prioritized financial review for long-term second-pass names
  -> valuation model routing
  -> long-term final decision
  -> legacy Zero-BUY audit / production contract

### Long-term final decision semantics

`long_term_formal_buy.py` only evaluates candidates already proven to have passed all non-exit-profile hard gates. It joins their All-A price/risk plan with routed valuation/fundamental data.

Possible outcomes:

- `LONG_TERM_BUY_READY`: true hard logic passes, real R/R >= 1.8, market/event risk acceptable, generic reverse valuation is actually ready, financial review is OK, normalized core profit is positive, earnings quality is strong, routing confidence acceptable, and market-implied required profit growth is low enough.
- `LONG_TERM_TRY_POSITION`: hard logic and valuation/fundamental review are acceptable, but valuation/earnings-quality comfort is weaker than BUY_READY; suitable only as smaller trial-position research candidate.
- `LONG_TERM_REVIEW_BLOCKED`: one or more real blockers remain.

Important: `valuation_model_execution_state=SPECIALIZED_MODEL_SELECTED_INPUTS_REQUIRED` is **not** treated as completed valuation. If non-defensive zero is caused by missing specialized-model execution, missing financial review, missing valuation diagnostics or missing required-growth inputs, the Postscan contract must fail rather than publish “no opportunity.”

The module emits entry zone, current action, invalidation price, target 1/2, R/R, required profit growth, earnings quality and blockers. It remains `no_auto_trade=True` and never grants automatic trade permission.

## Industry and valuation guarantees

`GenGe Postscan Research Pipeline` contract requires:

- every clean industry represented in valuation source;
- every long-term second-pass name present in final valuation source;
- every long-term second-pass name survives into valuation queue;
- long-term source tag survives into valuation output;
- if long-term candidate count <= financial review budget (currently 100), all long-term names must receive financial review before normal valuation names consume the remaining budget;
- `valuation_research_routed.csv` exists and routing row counts match;
- non-defensive zero cannot be explained by unresolved research/model execution gaps.

Valuation research capacity remains up to 500 names with financial deep review up to 100.

## Progress instrumentation

`all_a_progress_runner.py` logs processed/total, percentage, throughput, ETA and current code without changing screening formulas. Fresh Validation is the live proof step. The normal scheduled `GenGe Opportunity Discovery` workflow has not yet been switched permanently; only do that after Fresh Validation is green.

## Next work — exact order

1. Verify the Fresh Validation started from commit `5f492bc2`; obtain its run id and inspect progress-runner logs for real `% / speed / ETA`.
2. If fresh All-A fails, fix the exact failure and re-trigger by editing only `docs/GENGE_FRESH_VALIDATION_TRIGGER.md` with another `[run-all-a]` commit.
3. On fresh All-A success, verify `GenGe Postscan Research Pipeline` auto-triggers and inspect every step.
4. Inspect unified artifact: `valuation_research_routed.csv`, `long_term_formal_buy_candidates.csv`, industry coverage, second-pass and zero-buy audit. Confirm 603369/688687, if still qualifying in the fresh snapshot, receive valuation + financial review and are not lost.
5. If Postscan fails because of `valuation_model_not_executed`, implement/execute the selected specialized valuation model rather than weakening the contract.
6. If long-term Formal BUY remains zero in a non-defensive market only because of true substantive blockers (valuation too expensive, earnings quality weak, R/R inadequate, event/hard risk), record the proof. Missing research data is not accepted as proof.
7. After Fresh Validation passes, switch the normal scheduled All-A command to `all_a_progress_runner`, remove temporary Fresh Validation workflow + marker, and prove normal production remains green.
8. Produce final every-industry Top3–5 map + Master Opportunity Ranking + actionable long-term candidates with entry zone, invalidation, valuation/fundamental target range and long-term review/exit logic.

## Resume instruction for a new ChatGPT session

Tell ChatGPT:

`继续 daily_stock_analysis，先读取仓库 docs/GENGE_WORK_PROGRESS.md，然后核对 main 最新 commits 和 GitHub Actions 状态，从 Next work 第一项继续，不要重新设计已经完成的部分。`

This file is the durable source of truth. Update it after every meaningful implementation milestone or production finding.
