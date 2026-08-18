# GenGe / daily_stock_analysis — Production Work Handoff

Last updated: 2026-08-18 (Asia/Shanghai)
Repository: `wanggenAi/daily_stock_analysis`
Branch: `main`

## Product invariants

1. Research Pool must be wide; Formal BUY must remain strict.
2. Every represented industry must retain research visibility, target 3–5 names where available. A bad industry may have zero investable names, but it must not silently disappear.
3. Formal BUY must not collapse to zero because of soft/mechanical gates. Zero is acceptable only for a genuinely defensive market or when no candidate survives true hard investment logic plus completed valuation/fundamental review.
4. Never fabricate BUYs to meet a quota. Hard blockers, financial integrity, PIT data freshness, valuation/MOS, real R/R and major risk events remain binding.
5. 60-day/medium-horizon exit-profile sample shortage is not a long-term investment veto. Candidates passing all non-exit-profile hard gates must be forced through valuation/fundamental review.
6. Reverse valuation is a parallel discovery channel so scarce-resource/cyclical/growth opportunities are not lost merely because technical quant ranking is lower.
7. Model selection is not model execution. Missing specialized-model execution, missing financial review or missing valuation inputs are production/research gaps, not proof that no opportunity exists.
8. No auto-trading. Research/routing/final-decision reports remain auditable and manual-review only.
9. Production observability is required: processed/total, %, throughput, ETA, current code, cache/failure counts.
10. Master Opportunity Ranking is a research-priority view, not a new BUY score. High Master rank never grants trade permission.

## Current production state — VALIDATED

### Normal All-A production

Workflow: `GenGe Opportunity Discovery`
Run: **`32099563360`**
Event: `workflow_dispatch`
Conclusion: **SUCCESS**
Production artifact: `genge-all-a-production-report`
Artifact ID: **`9311716238`**
Artifact SHA256: `26813b6cee3a001287683f7dffe430c6597f12f90db09cff2389832ff7a55716`
Resolved market date: **`2026-08-17`**

Validated facts:

- normal production uses `all_a_progress_runner`;
- production strategy tests: **247 passed**;
- structured live progress reached 5005/5005 and 5209/5209 with processed/total, %, throughput, ETA and current code;
- raw/official universe: **5209**;
- effective scan: **4510**;
- price coverage: **100%**;
- fatal data failures: **0**;
- market regime: **GREEN**, score **82.21**;
- priority research: **389**;
- secondary research: **1081**;
- evidence queue: **80**;
- deep review: **80**;
- runtime about **1804.71 s**;
- `acceptance_enum=PASS_ALL_A_PRODUCTION_RESEARCH_READY`;
- `no_auto_trade=true`;
- `no_broker_integration=true`.

**Do not rerun this All-A snapshot merely to validate downstream changes.**

### Canonical Postscan baseline before Master integration

Workflow: `GenGe Postscan Research Pipeline`
Run: **`32102437218`**
Upstream: **`32099563360`**
Head SHA: `e569a498cf8ae41a6255aa97001589252dd9e61d`
Conclusion: **SUCCESS**
Artifact: `genge-postscan-research`
Artifact ID: **`9312056410`**
Artifact SHA256: `f2e5314819ea96236eadd0b7df37d27f1a359029db3a76c3c05424ef4026b22c`

All stages passed: upstream artifact resolution/download, focused tests, every-industry map, long-term second pass, industry-aware valuation source, long-term merge, recall contract, reverse valuation, long-term-priority financial review, model routing, Formal BUY, zero-BUY audit, final production contract, cache and artifact upload.

Industry recall after provenance repair: **81/81 clean industries represented before valuation**.

## Key production correctness fixes already completed

### All-A artifact/report-root resolver

Production artifacts can flatten to `upstream/YYYYMMDD/...`. The resolver now prefers the canonical top-level `all_a_quant_screen.csv + run_summary.json` and rejects nested deep-review decoys as the production root.

Relevant commits include:

- `feba9b27` — tolerate flattened All-A artifact layout;
- `4fbd214d` — prefer canonical All-A report root;
- `2966619a` — nested deep-review decoy regression test.

### Cash-flow unit correctness

The financial loader no longer treats per-share operating cash flow as total operating cash flow. Total OCF, per-share OCF and provider cash-conversion ratio remain separate concepts. Sina `stock_financial_analysis_indicator` ratios such as `1.5263` are preserved as already-dimensionless ratios and are not divided by 100 again.

Relevant commits include `6213c9f8` and `1d40b1bc`.

### PIT financial-report safety

Without a verified disclosure date, a report-period row is not assumed public just because its period ended. Statutory latest-disclosure deadlines are used as fail-closed fallback boundaries. For the `2026-08-17` snapshot, 今世缘 therefore uses 2026Q1 rather than pulling 2026H1 forward without verified disclosure.

Relevant commits include `20397a84` and `754e14a7`.

### Industry recall provenance

Canonical Postscan run `32102091118` falsely reported seven missing industries. The names were present, usually as `BOTH`, but global rows had blank `industry` and overlap merging did not backfill provenance.

Fixes:

- `3a358065` — backfill only missing industry provenance for overlaps while preserving global valuation/ranking/hard-blocker semantics;
- `e569a498` — regression test for blank global industry plus populated industry-champion row.

Replay changed the recall result to **missing=[] / 81 of 81 clean industries represented**.

### Normal production progress runner

Normal `GenGe Opportunity Discovery` permanently uses `all_a_progress_runner`; the old background heartbeat loop is gone. Screening formulas and hard thresholds were not changed.

Key migration commit: `c9dee76e`.

## Long-term final-decision proof

### `603369 今世缘`

Current validated classification: **`LONG_TERM_BUY_READY`**

- financial report date: `2026-03-31`;
- cash conversion ratio: **1.5263**;
- earnings quality score: **65**, confidence **HIGH**;
- normalized core operating profit about **1.3810 billion CNY**;
- current PE: **15.76**;
- required profit growth vs reference: **-25.31%**;
- real R/R: **7.05**;
- current price: **29.63**;
- research entry zone: **29.53–29.63**;
- invalidation: **29.01**;
- targets: **34.00 / 34.54**;
- blockers: none;
- `long_term_formal_buy_eligible=True`;
- `formal_signal_eligible=False`;
- `automatic_promotion_allowed=False`;
- `no_auto_trade=True`.

### `688687 凯因科技`

Current validated classification: **`LONG_TERM_REVIEW_BLOCKED`**

- financial report date: `2026-03-31`;
- cash conversion ratio: **-0.4952**;
- earnings quality score: **30**, confidence **HIGH**;
- current PE: **283.36**;
- required profit growth vs reference: **+626.19%**;
- real R/R: **3.25**;
- blockers: `earnings_quality_below_minimum;valuation_expectation_too_high`;
- financial review: **OK**;
- valuation diagnostic: completed;
- `long_term_formal_buy_eligible=False`;
- `no_auto_trade=True`.

This distinction is intentional: pipeline/data bugs may restore a valid candidate, but substantive valuation/earnings-quality blockers remain binding.

## Master Opportunity Ranking — COMPLETE

Master Opportunity Ranking is implemented, production-replayed, integrated into canonical Postscan, and validated against the same upstream All-A snapshot `32099563360`.

### Implementation

Module: `src/strategies/genge_opportunity_discovery/master_opportunity_ranking.py`

- implementation commit: **`84d03bf056af53a2292a0574b88bdd652d33fc77`** — `feat: add master opportunity research ranking`;
- test file: `tests/test_genge_master_opportunity_ranking.py`;
- test commit: **`92ace140b838c05c118f8b79a7a29bd691fc51e3`** — `test: lock master opportunity ranking semantics`;
- canonical workflow integration commit: **`2de14872987b7a736543b3be2adbf9e1c54ccd73`** — `ci: integrate master opportunity ranking into postscan`.

Master semantics:

- `ranking_semantics=research_priority_not_trade_score`;
- names that reached valuation preserve their existing `valuation_research_rank`;
- remaining every-industry Top5 names are appended by quant/industry research order for visibility;
- long-term `BUY_READY` / `TRY_POSITION` / `REVIEW_BLOCKED` is a separate overlay;
- no new numeric BUY score was invented;
- high research rank never authorizes a trade;
- `formal_signal_eligible=false`;
- `automatic_promotion_allowed=false`;
- `no_auto_trade=true`.

Outputs:

1. `master_opportunity_ranking.csv`
2. `every_industry_top5_enriched.csv`
3. `actionable_long_term_candidates.csv`
4. `master_opportunity_summary.json`
5. `master_opportunity_ranking.md`

### Independent real-production replay

Run: **`32104411189`**
Conclusion: **SUCCESS**
Artifact: `genge-master-ranking-production-replay`
Artifact ID: **`9312666959`**
Artifact SHA256: `680f30a3412ac067e33248be333c1338a06b4daa47bfe3fa5d13b78e41ebfd98`

This replay used the already validated production Postscan artifact and passed Master-focused tests, generation, production replay contract and artifact upload.

### Temporary PR #37 CI note

PR **#37** was a validation-marker PR only; the marker was never intended to merge. Docker build, Python syntax, flake8-critical and deterministic checks passed. The repository-wide offline pytest gate failed, but the available connector logs did not establish that failure as a Master regression. The independent production replay and the fully integrated canonical Postscan both passed Master-specific execution and production contracts.

PR #37 is now **closed without merge**.

### Canonical integrated Postscan proof

Workflow: `GenGe Postscan Research Pipeline`
Run: **`32107277842`**
Upstream: **`32099563360`**
Conclusion: **SUCCESS**
Artifact: `genge-postscan-research`
Artifact ID: **`9313621616`**
Artifact SHA256: `9796034093b407995dae63ee6e28d620531565ffc99afcbe78218b5c0aae041b`

The integrated run passed every stage, including:

- focused Postscan + Master tests;
- every-industry Top5 map;
- long-term second pass;
- valuation-source merge and recall contract;
- reverse valuation and financial review;
- valuation routing;
- long-term Formal BUY;
- zero-BUY audit;
- **Build Master Opportunity Ranking**;
- final production contract;
- cache save;
- unified artifact upload.

Final Master artifact counts:

- master names: **400**;
- industry Top5 rows: **381**;
- represented industries: **82**;
- clean industries: **81**;
- valuation-researched names: **257**;
- actionable long-term names: **1**;
- `LONG_TERM_BUY_READY`: **1**;
- `LONG_TERM_TRY_POSITION`: **0**;
- `LONG_TERM_REVIEW_BLOCKED`: **1**.

Overlay proof:

- `603369 今世缘`: Master research rank **#1**, `LONG_TERM_BUY_READY`, present in `actionable_long_term_candidates.csv`, `long_term_formal_buy_eligible=True`, `no_auto_trade=True`;
- `688687 凯因科技`: Master research rank **#2**, `LONG_TERM_REVIEW_BLOCKED`, blockers remain `earnings_quality_below_minimum;valuation_expectation_too_high`, and it is **absent** from `actionable_long_term_candidates.csv`.

The temporary dispatcher, run locator and locator record used to obtain the canonical proof were removed afterward.

## Automatic Postscan trigger note

`GenGe Postscan Research Pipeline` supports automatic `workflow_run` after successful production `GenGe Opportunity Discovery` runs whose upstream event is `schedule` or `workflow_dispatch`, plus explicit `workflow_dispatch` with `upstream_run_id`.

The validated production run `32099563360` was itself started by another GitHub Actions job using repository `GITHUB_TOKEN`. In that synthetic proof path, an automatic downstream `workflow_run` did not appear, so Postscan was explicitly dispatched with the already validated upstream ID.

This does **not** prove the native scheduled path is broken. Keep the current `workflow_run` design until a true native scheduled production success proves or disproves it. Do not add a duplicate permanent dispatcher solely because of the synthetic proof path. If a native scheduled success does not spawn exactly one Postscan, then replace the handoff with one deterministic mechanism and avoid duplicate downstream runs.

## Current architecture

All-A universe
  -> hard data/risk/liquidity/history filters
  -> quant screen
  -> recall A: global opportunity leaders
  -> recall B: every-industry Top3–5 champions
  -> recall C: exit-profile-only long-term second-pass names
  -> merge/de-duplicate with provenance preservation
  -> reverse valuation
  -> prioritized financial review for long-term second-pass names
  -> valuation model routing
  -> long-term final decision
  -> Master Opportunity Ranking (research priority + long-term decision overlay)
  -> actionable long-term review list separated from research-watch names
  -> legacy Zero-BUY audit / production contract

Valuation research capacity remains up to 500 names with financial deep review up to 100.

## Long-term final-decision semantics

- `LONG_TERM_BUY_READY`: true hard logic passes, real R/R is acceptable, market/event risk is acceptable, valuation diagnostic is ready, financial review is complete, normalized core profit is positive, earnings quality is strong enough and implied required profit growth is acceptable.
- `LONG_TERM_TRY_POSITION`: hard logic and review are acceptable but valuation/earnings-quality comfort is weaker; research-only smaller trial-position classification.
- `LONG_TERM_REVIEW_BLOCKED`: one or more substantive blockers remain.

`valuation_model_execution_state=SPECIALIZED_MODEL_SELECTED_INPUTS_REQUIRED` is not completed valuation. Missing specialized-model execution, missing financial review, missing valuation diagnostics or missing required-growth inputs cannot justify a silent non-defensive zero-BUY result.

## Next work — exact order

1. **Do not rerun the validated 2026-08-17 All-A/Postscan merely to rebuild Master Ranking. Master is complete and canonical production-validated.**
2. On the next **native scheduled** `GenGe Opportunity Discovery` success, verify that exactly one `GenGe Postscan Research Pipeline` run appears automatically and consumes that scheduled upstream artifact. Only change trigger architecture if this native schedule test fails.
3. Use `reports/master_opportunity_ranking/master_opportunity_ranking.csv` as the broad cross-industry research-priority view, `every_industry_top5_enriched.csv` for industry visibility, and `actionable_long_term_candidates.csv` only for genuinely eligible long-term BUY/TRY review. Never turn Master rank into trade permission.
4. Keep 603369 as the current validated `LONG_TERM_BUY_READY` example and 688687 as a validated substantive-blocker example; do not hard-code either future outcome because every new market snapshot must recompute them.
5. Continue specialized valuation execution only when routing selects a specialized model whose required inputs can be sourced reliably. `model selected` must never masquerade as `model executed`.
6. Preserve PIT correctness, every-industry recall, reverse-valuation discovery, strict hard blockers, `no_auto_trade` and all audit artifacts.

## Resume instruction for a new ChatGPT session

Tell ChatGPT:

`继续 daily_stock_analysis，先读取仓库 docs/GENGE_WORK_PROGRESS.md，再核对 main 最新 commits 和 GitHub Actions；不要重跑已完成的 2026-08-17 All-A/Postscan，直接从 Next work 继续。`

This file is the durable source of truth. Update it after every meaningful implementation milestone or production finding.
