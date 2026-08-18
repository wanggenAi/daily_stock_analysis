# GenGe / daily_stock_analysis — Production Work Handoff

Last updated: 2026-08-18 (Asia/Shanghai)
Repository: `wanggenAi/daily_stock_analysis`
Branch: `main`

## Product invariants

1. Research Pool stays wide; Formal BUY stays strict.
2. Every represented industry retains research visibility, target Top3–5 where available. Bad industries may have zero investable names, but must not silently disappear.
3. Do not manufacture BUYs. Hard blockers, financial integrity, PIT freshness, valuation/MOS, real R/R and major event risk remain binding.
4. Medium-horizon / exit-profile sample shortage is not a long-term investment veto. Names passing non-exit-profile hard logic must still reach valuation/fundamental review.
5. Reverse valuation is a parallel discovery channel so scarce-resource/cyclical/growth names are not lost merely because technical quant rank is lower.
6. Model selection is not model execution. Missing model execution or inputs are research gaps, not evidence of no opportunity.
7. Master Opportunity Ranking is research priority, never a new BUY score.
8. No auto-trading. `formal_signal_eligible=false`, `automatic_promotion_allowed=false`, `no_auto_trade=true` remain locked for research sidecars.
9. Production must remain observable and auditable.

## Current validated production snapshot

### All-A production — DO NOT RERUN FOR DOWNSTREAM VALIDATION

Workflow: `GenGe Opportunity Discovery`
Run: **`32099563360`**
Conclusion: **SUCCESS**
Artifact: `genge-all-a-production-report`
Artifact ID: **`9311716238`**
SHA256: `26813b6cee3a001287683f7dffe430c6597f12f90db09cff2389832ff7a55716`
Market date: **2026-08-17**

Validated facts:
- raw/official universe: **5209**;
- effective scan: **4510**;
- price coverage: **100%**;
- fatal data failures: **0**;
- market regime: **GREEN**, score **82.21**;
- priority research: **389**;
- secondary research: **1081**;
- evidence queue: **80**;
- deep review: **80**;
- runtime about **1804.71s**;
- production tests: **247 passed**;
- normal production uses `all_a_progress_runner` with processed/total, %, throughput, ETA and current code;
- `acceptance_enum=PASS_ALL_A_PRODUCTION_RESEARCH_READY`;
- `no_auto_trade=true`, no broker integration.

## Core correctness fixes already complete

### Artifact/report-root resolver
- `feba9b27` — tolerate flattened All-A artifact layout.
- `4fbd214d` — prefer canonical All-A report root.
- `2966619a` — nested deep-review decoy regression test.

### Financial cash-flow units / ratio semantics
The loader no longer maps per-share OCF as total OCF. Total OCF, per-share OCF and provider cash-conversion ratio are separate. Sina OCF/net-profit ratio such as `1.5263` remains dimensionless and is not divided by 100.
- relevant commits include `6213c9f8`, `1d40b1bc`.

### PIT financial-report safety
Undated report periods use conservative statutory latest-disclosure deadlines. A period-end row is not assumed public immediately.
- relevant commits include `20397a84`, `754e14a7`.

### Industry recall provenance
Run `32102091118` falsely reported seven missing industries because global+industry overlap rows kept blank global `industry` provenance.
- `3a358065` — backfill only missing industry provenance without altering ranking/valuation/hard blockers.
- `e569a498` — regression test.
- fixed result: **81/81 clean industries represented**.

### Normal production progress runner
Normal `GenGe Opportunity Discovery` permanently uses `all_a_progress_runner`; old background heartbeat logic is gone.
- migration commit: `c9dee76e`.

## Long-term final-decision proof

### `603369 今世缘`
Current validated classification: **`LONG_TERM_BUY_READY`**
- financial report: `2026-03-31`;
- cash conversion: **1.5263**;
- earnings quality: **65 HIGH**;
- normalized core operating profit about **1.381bn CNY**;
- current PE: **15.76**;
- required profit growth vs historical reference: **-25.31%**;
- real R/R: **7.05**;
- price: **29.63**;
- entry: **29.53–29.63**;
- invalidation: **29.01**;
- targets: **34.00 / 34.54**;
- blockers: none;
- `long_term_formal_buy_eligible=True`;
- `no_auto_trade=True`.

### `688687 凯因科技`
Current validated classification: **`LONG_TERM_REVIEW_BLOCKED`**
- financial report: `2026-03-31`;
- cash conversion: **-0.4952**;
- earnings quality: **30 HIGH**;
- current PE: **283.36**;
- required profit growth vs historical reference: **+626.19%**;
- real R/R: **3.25**;
- blockers: `earnings_quality_below_minimum;valuation_expectation_too_high`;
- `long_term_formal_buy_eligible=False`;
- `no_auto_trade=True`.

Pipeline fixes may restore a valid candidate, but substantive valuation/quality blockers remain binding.

## Master Opportunity Ranking — COMPLETE

Module: `src/strategies/genge_opportunity_discovery/master_opportunity_ranking.py`
Test: `tests/test_genge_master_opportunity_ranking.py`
Canonical integration: `.github/workflows/genge-postscan-research.yml`

Relevant commits:
- implementation: `84d03bf056af53a2292a0574b88bdd652d33fc77`;
- tests: `92ace140b838c05c118f8b79a7a29bd691fc51e3`;
- workflow integration: `2de14872987b7a736543b3be2adbf9e1c54ccd73`.

Semantics:
- `ranking_semantics=research_priority_not_trade_score`;
- existing `valuation_research_rank` is preserved for researched names;
- remaining industry Top5 names are appended for visibility;
- long-term classification is an overlay, not a new buy score;
- high rank never grants trade permission.

Validated integrated run before specialized execution:
- run: `32107277842`, SUCCESS;
- artifact ID: `9313621616`;
- SHA256: `9796034093b407995dae63ee6e28d620531565ffc99afcbe78218b5c0aae041b`.

Stable Master counts on the 2026-08-17 snapshot:
- master names: **400**;
- industry Top5 rows: **381**;
- represented industries: **82**;
- clean industries: **81**;
- valuation-researched: **257**;
- actionable long-term: **1**;
- BUY_READY: **1**;
- TRY_POSITION: **0**;
- REVIEW_BLOCKED: **1**.

`603369` is Master #1 and actionable. `688687` is Master #2 but blocked and absent from actionable output.

## Specialized valuation execution — BROKER FAMILY COMPLETE

Goal: close the gap between `SPECIALIZED_MODEL_SELECTED_INPUTS_REQUIRED` and an actually executed specialized valuation, without loosening Formal BUY and without fabricating model inputs.

### Permanent implementation

Module: `src/strategies/genge_opportunity_discovery/specialized_valuation_execution.py`
Test: `tests/test_genge_specialized_valuation_execution.py`

Relevant permanent commits:
- **`612d5e803d28dd45abb08084dda21bc0ac87243f`** — `feat: execute PIT-safe broker valuation research`;
- **`d1dbfbdf140dc58b84989d076e659951ebb065ce`** — `test: lock PIT-safe broker specialized execution`;
- **`8f9fa8c3f95d6427382e6869d95302a355d5d76d`** — `ci: execute specialized broker valuation in postscan`;
- **`961268e64f3eed28957b984c4a9426af283cc386`** — `fix: isolate and refresh specialized valuation cache`;
- **`b3c132b1c6c6616bda6949829c86a79998cfa0bb`** — `test: lock specialized cache isolation`.

The first executable specialized family is `capital_markets_cycle` for traditional securities brokers.

Execution design:
- use current PIT P/B plus PIT-safe historical annual ROE;
- no quarterly ROE annualization;
- only fiscal-year `12-31` ROE rows are eligible;
- actual disclosure date must be <= as-of, or conservative statutory annual-report deadline must have passed;
- provider ROE is percentage points and is converted `/100`;
- require at least **3** annual ROE samples, use up to **5**;
- normalize mid-cycle ROE by median;
- default research assumptions: cost of equity **11%**, long-term growth **3%**;
- execute the residual-income model in normalized book units (`BVPS=1`, current price=current PB), which is algebraically equivalent for fair PB / implied ROE / MOS and avoids inventing actual BVPS/share count;
- results are a research sidecar only.

Other specialized families remain explicit `INPUTS_REQUIRED` until their real inputs can be sourced:
- insurance: disclosed EV/NBV;
- transport: through-cycle EBITDA + lease-consistent net debt;
- yield assets: normalized FCFE with maintenance/growth capex separation;
- bank residual income, real-estate NAV, biotech rNPV, consumer compounder DCF likewise fail closed until model-specific evidence exists.

### Specialized cache correctness

The first integrated canonical run (`32108818113`) exposed a real cache bug: restoring the older general financial cache could leave annual ROE absent, causing broker execution to depend on cache history (1/3 instead of the independent replay's 3/3).

Fix:
- specialized executor now uses a dedicated versioned cache namespace: **`specialized_execution_v1`** under the existing valuation cache root;
- if that specialized financial cache is hit but still lacks sufficient annual ROE, only the specialized financial cache file is removed and refetched once;
- the general valuation/fundamental cache is never deleted by this repair;
- the canonical Actions cache already persists the parent cache directory, so the specialized namespace is persisted with it.

Focused validation after cache isolation:
- run **`32109348122`** — SUCCESS;
- syntax + specialized cache tests + broker valuation + routing + long-term runner all passed.

Independent real-production replay before integration:
- run **`32108514951`** — SUCCESS;
- artifact `genge-specialized-production-replay`;
- artifact ID **`9314032964`**;
- SHA256 `9b13585e05ba3313e9c7dcf393bcd285ea14b15cc7869cf09361b7f3569e5d06`;
- capital-markets specialized execution: **3/3**.

### Final canonical Postscan proof — CURRENT BEST SNAPSHOT

Workflow: `GenGe Postscan Research Pipeline`
Run: **`32109532494`**
Upstream: **`32099563360`**
Conclusion: **SUCCESS**
Artifact: `genge-postscan-research`
Artifact ID: **`9314388591`**
Artifact SHA256: **`be199bcf99397242b18d49ab8a07ec057bf224384419f227e0e6d5fd704f48af`**
Head SHA at dispatch: `25f4923c0b4de580399dd4d47a0892cfd7779738`

Every canonical stage passed, including:
- focused tests;
- industry Top5 / recall;
- long-term second pass;
- reverse valuation and financial review;
- model routing;
- **Execute specialized valuation models**;
- long-term Formal BUY;
- zero-BUY audit;
- Master Ranking;
- final contract;
- cache save;
- artifact upload.

Final specialized summary:
- total valuation rows: **257**;
- specialized selected: **15**;
- selected by strategy:
  - `capital_markets_cycle`: **3**;
  - `insurance_embedded_value`: **3**;
  - `transport_cycle`: **6**;
  - `yield_asset`: **3**;
- execution states:
  - `SPECIALIZED_MODEL_EXECUTED_RESEARCH_ONLY`: **1**;
  - `SPECIALIZED_MODEL_EXECUTED_FAIL_CLOSED`: **2**;
  - `SPECIALIZED_MODEL_SELECTED_INPUTS_REQUIRED`: **12**;
- capital-markets selected: **3**;
- capital-markets executed: **3**;
- capital-markets input-required: **0**;
- `ranking_changed=false`;
- `formal_buy_consumes_specialized_sidecar=false`;
- `formal_signal_eligible=false`;
- `automatic_promotion_allowed=false`;
- `no_auto_trade=true`.

Broker proof:

1. `600109 国金证券`, valuation research rank **#28**
   - execution: `SPECIALIZED_MODEL_EXECUTED_RESEARCH_ONLY` / `OK`;
   - annual ROE years: `2021;2022;2023;2024;2025`;
   - current PB: **0.89**;
   - normalized mid-cycle ROE: **5.28%**;
   - fair PB: **0.285**;
   - market-implied mid-cycle ROE: **10.12%**;
   - normalized-minus-implied ROE gap: **-4.84pp**;
   - P/B-space MOS: about **-67.98%**.
   - Interpretation: model executes successfully, but current PB requires a materially stronger sustainable ROE than the PIT historical normalization supports.

2. `600155 华创云信`, valuation research rank **#102**
   - execution: `SPECIALIZED_MODEL_EXECUTED_FAIL_CLOSED`;
   - status: `NON_POSITIVE_RESIDUAL_INCOME_VALUE`;
   - current PB: **0.65**;
   - normalized mid-cycle ROE: **1.94%**;
   - market-implied mid-cycle ROE: **8.20%**.

3. `000712 锦龙股份`, valuation research rank **#150**
   - execution: `SPECIALIZED_MODEL_EXECUTED_FAIL_CLOSED`;
   - status: `NON_POSITIVE_RESIDUAL_INCOME_VALUE`;
   - current PB: **3.04**;
   - normalized mid-cycle ROE: **-3.99%**;
   - market-implied mid-cycle ROE: **27.32%**.

This is desired behavior: completing a model does not create a BUY. It converts unknown model state into an auditable valuation conclusion.

The same final canonical artifact proves the existing long-term decisions were unchanged by the new sidecar:
- `603369 今世缘`: still `LONG_TERM_BUY_READY`, eligible, R/R **7.05**, entry **29.53–29.63**, invalidation **29.01**, targets **34.00 / 34.54**;
- `688687 凯因科技`: still `LONG_TERM_REVIEW_BLOCKED`, blockers `earnings_quality_below_minimum;valuation_expectation_too_high`, not eligible.

Master counts also remain **400 / 381 / 82 / 81 / 257 / actionable 1**, exactly preserving Master semantics.

All temporary specialized validation/replay/dispatcher/locator workflows and locator JSON records were removed after proof. Permanent canonical workflow remains `.github/workflows/genge-postscan-research.yml`.

## Automatic Postscan trigger note

Canonical Postscan supports `workflow_run` after successful `GenGe Opportunity Discovery` production runs whose upstream event is `schedule` or `workflow_dispatch`, plus explicit `workflow_dispatch` with `upstream_run_id`.

The validated All-A run `32099563360` was itself started by another Actions job using repository `GITHUB_TOKEN`. That synthetic path did not create the downstream `workflow_run`, so downstream validation used explicit dispatch. This does **not** prove native scheduled production is broken.

Keep the current `workflow_run` architecture until a true native scheduled All-A success proves or disproves it. Do not add a duplicate permanent dispatcher. If a native scheduled success fails to spawn exactly one Postscan, replace the handoff with one deterministic mechanism and avoid duplicate downstream runs.

## Current architecture

All-A universe
  -> hard data/risk/liquidity/history filters
  -> quant screen
  -> recall A: global leaders
  -> recall B: every-industry Top3–5 champions
  -> recall C: exit-profile-only long-term second pass
  -> provenance-preserving merge/de-dup
  -> reverse valuation
  -> prioritized PIT financial review
  -> valuation model routing
  -> specialized valuation execution sidecar where auditable inputs exist
       (currently capital-markets/broker family; audit-only, not consumed by Formal BUY)
  -> long-term final decision
  -> Master Opportunity Ranking
  -> actionable long-term list separated from research-watch names
  -> zero-BUY audit / production contract

Valuation research capacity remains up to 500 names with financial deep review up to 100.

## Next work — exact order

1. **Do not rerun the validated 2026-08-17 All-A/Postscan again.** Current best canonical downstream proof is run `32109532494` / artifact `9314388591`.
2. On the next **native scheduled** `GenGe Opportunity Discovery` success, verify exactly one automatic `GenGe Postscan Research Pipeline` run consumes that scheduled upstream artifact. Change trigger architecture only if this native test fails.
3. Continue specialized-model execution **family by family**, only where required inputs can be sourced reliably and PIT-safely. The current unfinished selected pool is: transport **6**, insurance **3**, yield assets **3**. Do not mark any as executed until the actual model-specific inputs are present.
4. Prefer the next family based on input feasibility and production coverage, not on a desire to create more BUYs. Transport has the largest current selected count but requires lease-consistent net debt and through-cycle EBITDA; insurance requires disclosed EV/NBV; yield assets require defensible normalized FCFE and maintenance/growth capex separation.
5. Keep specialized execution sidecars research-only until a separately tested design explicitly integrates their completed outputs into long-term final-decision semantics. Do not silently switch Formal BUY to consume them.
6. Use `master_opportunity_ranking.csv` for broad research priority, `every_industry_top5_enriched.csv` for industry visibility, and `actionable_long_term_candidates.csv` only for genuinely eligible long-term BUY/TRY review.
7. Preserve PIT correctness, industry recall, reverse-valuation discovery, strict hard blockers, cache versioning, `no_auto_trade` and audit artifacts.

## Resume instruction for a new ChatGPT session

Tell ChatGPT:

`继续 daily_stock_analysis，先读取仓库 docs/GENGE_WORK_PROGRESS.md，再核对 main 最新 commits 和 GitHub Actions；不要重跑已完成的 2026-08-17 All-A/Postscan，直接从 Next work 继续。`

This file is the durable source of truth. Update it after every meaningful implementation milestone or production finding.
