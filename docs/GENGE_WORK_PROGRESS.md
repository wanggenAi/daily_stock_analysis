# GenGe / daily_stock_analysis — Production Work Handoff

Last updated: 2026-08-18 (Asia/Shanghai)
Repository: `wanggenAi/daily_stock_analysis`
Branch: `main`

## Product invariants

1. Research Pool must be wide; Formal BUY must remain strict.
2. Every represented industry must retain research visibility, target 3–5 names where available. A bad industry may have zero investable names, but it must not silently disappear.
3. Formal BUY must not collapse to zero because of soft/mechanical gates. Zero is acceptable only for a genuinely defensive market or when no candidate survives true hard investment logic + completed valuation/fundamental review.
4. Never fabricate BUYs to meet a quota. Hard blockers, financial integrity, PIT data freshness, valuation/MOS, real R/R and major risk events remain binding.
5. 60-day/medium-horizon exit-profile sample shortage is not a long-term investment veto. Candidates passing all non-exit-profile hard gates must be forced through valuation/fundamental review.
6. Reverse valuation is a parallel discovery channel so scarce-resource/cyclical/growth opportunities are not lost merely because technical quant ranking is lower.
7. Model selection is not model execution. Missing specialized-model execution, missing financial review or missing valuation inputs are production/research gaps, not proof that no opportunity exists.
8. No auto-trading. Research/routing/final-decision reports remain auditable and manual-review only.
9. Production observability is required: processed/total, %, throughput, ETA, current code, cache/failure counts.

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

This is the normal production workflow, not the temporary Fresh workflow.

Validated facts:

- `all_a_progress_runner` is now used by normal production.
- production strategy tests: **247 passed**.
- structured live progress was present in the real production log, including processed/total, percentage, throughput, ETA and current code.
- raw/official universe: **5209**
- effective scan: **4510**
- price coverage: **100%**
- fatal data failures: **0**
- market regime: **GREEN**
- market score: **82.21**
- priority research: **389**
- secondary research: **1081**
- evidence queue: **80**
- deep review: **80**
- strict review ready: **0**
- condition watch: **2**
- research watch: **10**
- financial coverage: **1.0**
- valuation coverage: **1.0**
- runtime: about **1804.71 s**
- `acceptance_enum=PASS_ALL_A_PRODUCTION_RESEARCH_READY`
- `no_auto_trade=true`
- `no_broker_integration=true`

### Canonical Postscan production proof

Workflow: `GenGe Postscan Research Pipeline`
Successful canonical run: **`32102437218`**
Upstream normal production run: **`32099563360`**
Head SHA: **`e569a498cf8ae41a6255aa97001589252dd9e61d`**
Conclusion: **SUCCESS**
Artifact: `genge-postscan-research`
Artifact ID: **`9312056410`**
Artifact SHA256: `f2e5314819ea96236eadd0b7df37d27f1a359029db3a76c3c05424ef4026b22c`

All canonical stages passed:

- upstream resolution + All-A artifact download
- focused Postscan tests
- every-industry Top5 research map
- long-term second pass
- industry-aware valuation source
- long-term merge into valuation source
- recall coverage contract
- reverse valuation + long-term-priority financial review
- valuation model routing
- long-term Formal BUY review
- legacy zero-BUY audit
- final production contract
- cache save + unified artifact upload

Industry coverage result after the final provenance fix: **81/81 clean industries represented before valuation**.

## Final long-term examples from canonical production artifact

### `603369 今世缘`

Final classification: **`LONG_TERM_BUY_READY`**

- financial report date: `2026-03-31`
- PIT handling: uses the latest report safely available as of the All-A date; 2026H1 is not pulled forward into the 2026-08-17 snapshot without verified disclosure.
- cash conversion ratio: **1.5263**
- earnings quality score: **65**
- earnings quality confidence: **HIGH**
- normalized core operating profit: about **1.3810 billion CNY**
- current PE: **15.76**
- required profit growth vs reference: **-25.31%**
- real R/R: **7.05**
- current price: **29.63**
- research entry zone: **29.53–29.63**
- risk invalidation price: **29.01**
- target 1 / target 2: **34.00 / 34.54**
- blockers: **none**
- `long_term_formal_buy_eligible=True`
- `formal_signal_eligible=False`
- `automatic_promotion_allowed=False`
- `no_auto_trade=True`

### `688687 凯因科技`

Final classification: **`LONG_TERM_REVIEW_BLOCKED`**

- financial report date: `2026-03-31`
- cash conversion ratio: **-0.4952**
- earnings quality score: **30**
- earnings quality confidence: **HIGH**
- current PE: **283.36**
- required profit growth vs reference: **+626.19%**
- real R/R: **3.25**
- blockers: **`earnings_quality_below_minimum;valuation_expectation_too_high`**
- financial review status: **OK**
- valuation diagnostic: completed
- `long_term_formal_buy_eligible=False`
- `no_auto_trade=True`

This is the intended behavior: fixing data/research bugs restored 今世缘, while 凯因科技 remains blocked by substantive valuation/earnings-quality logic rather than missing research inputs.

## Major production fixes completed on 2026-08-18

### 1. All-A artifact/report-root resolver

Production artifacts can download as `upstream/YYYYMMDD/...` rather than preserving `reports/all_a_full_scan/`.
The resolver now prefers the canonical top-level `all_a_quant_screen.csv + run_summary.json` and does not allow nested `_deep_review/quant_screen_all.csv` decoys to become the production root.

Key commits include:

- `feba9b27` — tolerate flattened All-A artifact layout.
- `4fbd214d` — prefer canonical All-A report root.
- `2966619a` — regression test with nested deep-review decoy.

### 2. Cash-flow unit correctness

A provider field for per-share operating cash flow was previously treated as total operating cash flow, creating dimensionally invalid earnings-quality ratios.

The financial loader now keeps total OCF, per-share OCF and provider cash-conversion ratio as separate concepts. Sina `stock_financial_analysis_indicator` values such as `1.5263` are preserved as unitless ratios; they are not divided by 100 a second time.

Relevant final fixes/tests include:

- `6213c9f8` — preserve Sina cash-conversion ratio semantics / cache schema update.
- `1d40b1bc` — ratio regression coverage.

### 3. PIT financial-report safety

Without a verified disclosure date, a report-period row is not assumed public merely because its report period has ended. Legal latest-disclosure deadlines are used as fail-closed fallback boundaries.

For the `2026-08-17` All-A snapshot, 今世缘 therefore uses 2026Q1 rather than pulling the 2026H1 row forward.

Relevant fixes/tests include:

- `20397a84` — PIT statutory-deadline fallback.
- `754e14a7` — PIT regression coverage.

### 4. Industry recall provenance

Canonical Postscan run `32102091118` exposed a real recall-contract failure for seven industries. Investigation showed the names were not actually dropped: their global rows were already present and marked `BOTH`, but the global rows had blank `industry`, and overlap merging changed only the channel without backfilling industry provenance.

The bridge now fills only missing industry-recall provenance on overlap while preserving global ranking/valuation/hard-blocker fields.

- `3a358065` — backfill missing industry provenance for `BOTH` rows.
- `e569a498` — regression test for blank global industry + populated industry-champion row.

Replay of the failed artifact changed coverage from seven falsely missing industries to **missing=[] / 81 of 81 represented**, and canonical run `32102437218` passed the production recall contract.

### 5. Normal production progress runner

Normal `GenGe Opportunity Discovery` has been permanently switched to `all_a_progress_runner`; the old background heartbeat loop is gone. The change does not alter screening formulas or hard thresholds.

Key production migration commit:

- `c9dee76e` — use progress runner for normal All-A production.

## Automatic Postscan trigger note

`GenGe Postscan Research Pipeline` still supports:

- automatic `workflow_run` after successful production `GenGe Opportunity Discovery` runs whose upstream event is `schedule` or `workflow_dispatch`;
- explicit `workflow_dispatch` with `upstream_run_id`.

The normal production proof run `32099563360` was itself started by another GitHub Actions job using the repository `GITHUB_TOKEN`. GitHub suppresses most recursively generated workflow events from `GITHUB_TOKEN`; in this proof path no automatic `workflow_run` Postscan appeared after production completion. The canonical Postscan was therefore explicitly dispatched with the validated upstream run id.

This does **not** prove the native scheduled cron path is broken. A native `schedule` event is not created by a repository `GITHUB_TOKEN`, so the current `workflow_run` design should remain in place until the next real scheduled production run proves or disproves it.

Do not add a duplicate permanent dispatcher solely because this synthetic proof path was recursion-suppressed. If a native scheduled production run succeeds and still fails to create Postscan, then replace the trigger with one deterministic handoff (for example an explicit `workflow_dispatch` after successful production artifact upload) and remove the duplicate `workflow_run` path so only one Postscan can run per upstream.

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
  -> legacy Zero-BUY audit / production contract

Valuation research capacity remains up to 500 names with financial deep review up to 100.

## Long-term final-decision semantics

- `LONG_TERM_BUY_READY`: true hard logic passes, real R/R is acceptable, market/event risk is acceptable, valuation diagnostic is ready, financial review is complete, normalized core profit is positive, earnings quality is strong enough and implied required profit growth is acceptable.
- `LONG_TERM_TRY_POSITION`: hard logic and review are acceptable but valuation/earnings-quality comfort is weaker; research-only smaller trial-position classification.
- `LONG_TERM_REVIEW_BLOCKED`: one or more substantive blockers remain.

`valuation_model_execution_state=SPECIALIZED_MODEL_SELECTED_INPUTS_REQUIRED` is not treated as completed valuation. Missing specialized-model execution, missing financial review, missing valuation diagnostics or missing required-growth inputs cannot justify a silent non-defensive zero-BUY result.

## Next work — exact order

1. **No need to rerun All-A or canonical Postscan for the 2026-08-17 snapshot. They are production-validated.**
2. On the next native scheduled `GenGe Opportunity Discovery` success, verify that exactly one `GenGe Postscan Research Pipeline` run appears automatically and consumes that scheduled upstream artifact. Only change trigger architecture if this native schedule test fails.
3. Build the final every-industry Top3–5 research map and Master Opportunity Ranking from the validated production outputs, keeping Formal BUY strict and surfacing actionable long-term candidates separately from research-watch names.
4. Keep 603369 as the current validated `LONG_TERM_BUY_READY` example and 688687 as a validated substantive-blocker example; do not hard-code either outcome because each future market snapshot must recompute them.
5. Continue improving specialized valuation execution only when routing selects a specialized model whose required inputs can be sourced reliably; never convert `model selected` into `model executed` by label alone.
6. Preserve `no_auto_trade`, PIT correctness, hard blockers and audit artifacts.

## Resume instruction for a new ChatGPT session

Tell ChatGPT:

`继续 daily_stock_analysis，先读取仓库 docs/GENGE_WORK_PROGRESS.md，再核对 main 最新 commits 和 GitHub Actions；不要重跑已完成的 2026-08-17 All-A/Postscan，直接从 Next work 继续。`

This file is the durable source of truth. Update it after every meaningful implementation milestone or production finding.
