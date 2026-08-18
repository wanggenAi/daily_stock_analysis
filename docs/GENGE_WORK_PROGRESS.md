# GenGe / daily_stock_analysis — Production Work Handoff

Last updated: 2026-08-18 (Asia/Shanghai)
Repository: `wanggenAi/daily_stock_analysis`
Branch: `main`

> This is the current durable source of truth for continuation. Older detailed milestone text remains available in Git history.

## Product invariants

1. Research Pool stays wide; Formal BUY stays strict.
2. Every represented industry retains research visibility, target Top3–5 where available. A weak industry may have zero investable names, but must not silently disappear.
3. Never manufacture BUYs. Hard blockers, financial integrity, PIT freshness, valuation/MOS, real R/R and major-event risk remain binding.
4. Medium-horizon / exit-profile sample shortage is not a long-term investment veto. Names passing non-exit-profile hard logic must still reach valuation/fundamental review.
5. Reverse valuation is a parallel discovery channel so scarce-resource/cyclical/growth names are not lost merely because technical quant rank is lower.
6. Model selection is not model execution. Missing model execution/inputs are research gaps, not evidence of no opportunity.
7. Master Opportunity Ranking is research priority, never a new BUY score.
8. Research sidecars remain locked: `formal_signal_eligible=false`, `automatic_promotion_allowed=false`, `no_auto_trade=true`.
9. No broker/order integration and no automatic trading.
10. Production must remain observable, PIT-safe and auditable.

## Validated upstream All-A snapshot — DO NOT RERUN FOR DOWNSTREAM VALIDATION

Workflow: `GenGe Opportunity Discovery`
Run: **`32099563360`**
Conclusion: **SUCCESS**
Artifact: `genge-all-a-production-report`
Artifact ID: **`9311716238`**
SHA256: **`26813b6cee3a001287683f7dffe430c6597f12f90db09cff2389832ff7a55716`**
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
- `no_auto_trade=true`.

Do not rerun this All-A snapshot merely to validate downstream routing/model changes. Reuse the artifact.

## Core correctness already locked

### Financial/PIT correctness
- per-share OCF is never treated as total OCF;
- total OCF, per-share OCF and provider cash-conversion ratio remain separate;
- Sina OCF/net-profit ratio such as `1.5263` is dimensionless and is not divided by 100;
- undated report periods use conservative statutory latest-disclosure deadlines;
- future financial rows must not leak into an earlier as-of date.

Relevant historical commits include `6213c9f8`, `1d40b1bc`, `20397a84`, `754e14a7`.

### Industry recall provenance
A previous false missing-industry result was caused by overlap rows losing industry metadata. Fixes `3a358065` + `e569a498` preserve global valuation/ranking semantics while backfilling only missing provenance. Current clean-industry representation is **81/81**.

### Artifact resolver / production observability
Historical resolver fixes include `feba9b27`, `4fbd214d`, `2966619a`. Normal All-A production uses the permanent progress runner (`c9dee76e`).

## Long-term final-decision proof

### `603369 今世缘`
Current classification: **`LONG_TERM_BUY_READY`**
- report: `2026-03-31`;
- cash conversion: **1.5263**;
- earnings quality: **65 HIGH**;
- normalized core operating profit about **1.381bn CNY**;
- current PE: **15.76**;
- required profit growth vs reference: **-25.31%**;
- real R/R: **7.05**;
- price: **29.63**;
- entry: **29.53–29.63**;
- invalidation: **29.01**;
- targets: **34.00 / 34.54**;
- blockers: none;
- `long_term_formal_buy_eligible=True`;
- `no_auto_trade=True`.

### `688687 凯因科技`
Current classification: **`LONG_TERM_REVIEW_BLOCKED`**
- report: `2026-03-31`;
- cash conversion: **-0.4952**;
- earnings quality: **30 HIGH**;
- current PE: **283.36**;
- required profit growth vs reference: **+626.19%**;
- real R/R: **3.25**;
- blockers: `earnings_quality_below_minimum;valuation_expectation_too_high`;
- `long_term_formal_buy_eligible=False`;
- `no_auto_trade=True`.

Pipeline improvements may restore a valid candidate, but substantive valuation/quality blockers remain binding.

## Master Opportunity Ranking — COMPLETE

Permanent module: `src/strategies/genge_opportunity_discovery/master_opportunity_ranking.py`
Permanent test: `tests/test_genge_master_opportunity_ranking.py`
Canonical workflow: `.github/workflows/genge-postscan-research.yml`

Semantics:
- `ranking_semantics=research_priority_not_trade_score`;
- existing `valuation_research_rank` is preserved for valuation-researched names;
- remaining industry Top5 names are appended for visibility;
- long-term final decision is a separate overlay, not a new numeric buy score;
- high research rank never grants trade permission.

Stable 2026-08-17 counts:
- Master names: **400**;
- industry Top5 rows: **381**;
- represented industries: **82**;
- clean industries: **81**;
- valuation-researched: **257**;
- actionable long-term: **1**;
- BUY_READY: **1**;
- TRY_POSITION: **0**;
- REVIEW_BLOCKED: **1**.

`603369` is actionable. `688687` remains high research priority but is blocked and absent from actionable output.

## Specialized valuation execution

### Broker / capital-markets family — COMPLETE

Permanent module: `src/strategies/genge_opportunity_discovery/specialized_valuation_execution.py`
Permanent test: `tests/test_genge_specialized_valuation_execution.py`

Key implementation commits:
- `612d5e803d28dd45abb08084dda21bc0ac87243f` — PIT-safe broker research execution;
- `d1dbfbdf140dc58b84989d076e659951ebb065ce` — execution tests;
- `961268e64f3eed28957b984c4a9426af283cc386` — isolate/refresh specialized cache;
- `b3c132b1c6c6616bda6949829c86a79998cfa0bb` — cache regression test.

Execution contract:
- current PIT P/B + PIT-safe annual ROE;
- no quarterly ROE annualization;
- annual `12-31` rows only;
- disclosure date must be <= as-of, or conservative statutory deadline must have passed;
- ROE percentage points converted `/100`;
- minimum **3**, maximum **5** annual samples;
- median mid-cycle ROE;
- research assumptions: cost of equity **11%**, long-term growth **3%**;
- normalized book-value units avoid inventing BVPS/share count;
- dedicated cache namespace `specialized_execution_v1`.

Current broker execution is **3/3**. Sidecar remains research-only and is not consumed by Formal BUY.

## Company-level gas routing — COMPLETE

Broad `燃气 -> yield_asset` remains only an industry prior. Company-specific PIT evidence now controls exceptions.

### `603393 新天然气`
Profile `603393-resource-cycle-v1` disables `yield_asset` and routes through `capacity_cycle_normalizer;general_reverse_earnings` because the company combines city gas with upstream coalbed-methane/unconventional gas, conventional oil/gas and coal-resource development.

Permanent profile commit: **`c028b023c527174d4ae941bad266bc364e4a3f09`**.
Regression commits include **`429afcf8ed71b4b22ee898473e25d6cca8b5bf1`** and **`ffb2f4ab8c17c395c4ce97b467f9ab6aae19fda7`**.

### `600903 贵州燃气` and `600681 百川能源`
Both received explicit company-level city-gas profiles and remain **`YIELD_ASSET`**. This prevents the 603393 resource-cycle correction from contaminating ordinary city-gas operators.

Focused city-gas profile/routing validation run: **`32147146982`** — SUCCESS.

Important: both city-gas yield-asset names correctly remain **`SPECIALIZED_MODEL_SELECTED_INPUTS_REQUIRED`**. The yield-asset model requires auditable normalized FCFE plus a defensible maintenance-capex / growth-capex split. Never substitute `CFO - total capex` just to make the model execute.

## Insurance embedded-value reverse appraisal — COMPLETE

### Permanent implementation

- `config/insurance_embedded_value_inputs.yaml` — commit **`8d7a159a1f59f0a98e70d1f9e673375612ac3206`**;
- `src/strategies/genge_opportunity_discovery/insurance_embedded_value_inputs.py` — **`94b7c156005a52ffeda060fe45b2211d86962edc`**;
- `src/strategies/genge_opportunity_discovery/insurance_valuation_execution.py` — **`3003da91dcdfa292d38a700b0a85c487d5bafb6b`**;
- `tests/test_genge_insurance_embedded_value_inputs.py` — **`de23e334501a6a2b5133a4f84b5de7da2f84925e`**;
- `tests/test_genge_insurance_valuation_execution.py` — **`147bf1331e8de4a2361a1fef6e16f62e5a443590`**.

PIT registry deliberately includes only scope-compatible HIGH-confidence annual inputs:
- `601628 中国人寿`: 2025 EV **1,467,876 CNY million**, annual NBV **45,752 CNY million**, known at **2026-03-26**;
- `601601 中国太保`: 2025 EV **613,365 CNY million**, annual NBV **18,609 CNY million**, known at **2026-03-27**;
- `601319 中国人保`: intentionally absent because life/health segment EV/NBV cannot safely be treated as listed-group EV/NBV without a scope-consistent group/SOTP bridge.

Historical market-cap probe established the Baidu `总市值` series used by this execution path is in **CNY 100m**. The executor records the explicit conversion basis:
`AKSHARE_BAIDU_TOTAL_MARKET_CAP_CNY_100M_X100_TO_CNY_MILLION`.

The insurance sidecar computes only observable reverse appraisal:
- current P/EV;
- market-implied NBV franchise multiple.

It does **not** invent a subjective franchise multiple and does **not** publish synthetic fair value. Negative implied multiples remain visible rather than being clipped.

Focused insurance CI:
- run **`32148721002`** — SUCCESS.

Independent production-artifact replay:
- run **`32149017516`** — SUCCESS;
- selected **3**, executed **2**, input/scope required **1**;
- `601628` implied NBV franchise multiple **-8.854760447630705x**;
- `601601` **-17.373958837121823x**;
- `601319` -> `INSURANCE_GROUP_EV_NBV_SCOPE_REQUIRED`;
- `ranking_changed=false`;
- `formal_buy_consumes_insurance_sidecar=false`;
- `no_auto_trade=true`.

## CURRENT BEST FULL CANONICAL POSTSCAN SNAPSHOT

Canonical insurance integration commit:
**`d223f417a07894b7f0e6cb0a613741bc1d472c4e`**

Workflow: `GenGe Postscan Research Pipeline`
Run: **`32151478376`**
Upstream: **`32099563360`**
Conclusion: **SUCCESS**
Artifact: `genge-postscan-research`
Artifact ID: **`9329983021`**
Artifact SHA256: **`e560711044929f9fd3845cf0cdc42f58c123c86f9e5b028e1b7fa8f00f372423`**
As-of date: **2026-08-17**

This canonical validation reused the validated All-A artifact. **All-A was not rerun.**

Every canonical stage passed:
- dependency/install;
- **122 focused tests passed**;
- industry coverage;
- long-term second pass;
- industry-aware valuation source;
- recall contract;
- reverse valuation / PIT financial review;
- company/model routing;
- broker specialized execution;
- insurance reverse appraisal execution;
- long-term Formal BUY;
- zero-BUY audit;
- Master Ranking;
- final production contract;
- cache save;
- artifact upload.

Exact final counts:
- valuation rows: **257**;
- profile-routed: **3**;
- specialized selected: **14**;
- specialized composition: brokers **3**, insurance **3**, transport **6**, yield assets **2**;
- broker selected/executed: **3/3**;
- insurance selected/executed/input-required: **3 / 2 / 1**;
- industry Top5 rows: **381**;
- represented industries: **82**;
- clean industries: **81**;
- Master names: **400**;
- actionable long-term: **1**;
- BUY_READY: **1**;
- TRY_POSITION: **0**;
- REVIEW_BLOCKED: **1**.

Long-term decisions remain:
- `603369 今世缘` -> **`LONG_TERM_BUY_READY`**, sole actionable long-term name;
- `688687 凯因科技` -> **`LONG_TERM_REVIEW_BLOCKED`**, blocked for substantive earnings-quality / valuation-expectation reasons.

The legacy zero-BUY audit still reports legacy Formal BUY = 0 in a GREEN regime and therefore requires the second pass. This is expected: the long-term overlay separately produces the valid 603369 BUY-ready candidate without weakening legacy hard gates.

All research locks remain intact:
- `ranking_semantics=research_priority_not_trade_score`;
- `formal_signal_eligible=false`;
- `automatic_promotion_allowed=false`;
- `no_auto_trade=true`.

## Automatic Postscan trigger note

Canonical Postscan supports `workflow_run` after successful `GenGe Opportunity Discovery` runs whose event is `schedule` or `workflow_dispatch`, plus explicit `workflow_dispatch` with `upstream_run_id`.

Synthetic proof runs started from repository `GITHUB_TOKEN` are not a reliable test of native scheduled `workflow_run` behavior because GitHub suppresses some recursive workflow events. Keep the current architecture until a **native scheduled** All-A run proves/disproves it. Do not add a duplicate permanent dispatcher.

A temporary dispatcher run **`32151376321`** successfully launched final canonical run `32151478376`; the dispatcher itself failed only because its final locator JSON push lost a non-fast-forward race. The target canonical run was fully successful.

Two temporary patcher runs **`32149375210`** and **`32151072493`** had zero jobs due temporary workflow parsing and never touched the canonical workflow. Canonical integration was made directly through GitHub Contents API.

Temporary validation/replay/patcher/dispatcher/locator files were removed after proof. They are not part of production architecture.

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
       -> company-level PIT profiles may override unsafe broad industry priors
  -> specialized valuation sidecars where auditable inputs exist
       -> brokers: executed 3/3
       -> insurance: executed 2/3, one scope-blocked
       -> transport: inputs required
       -> yield assets: inputs required
  -> long-term final decision
  -> Master Opportunity Ranking
  -> actionable long-term list separated from research-watch names
  -> zero-BUY audit / production contract

Valuation research capacity remains up to 500 names with financial deep review up to 100.

## Next work — exact order

1. **Do not rerun the validated 2026-08-17 All-A, rebuild Master Ranking, or rebuild insurance execution.** Current best downstream proof is canonical Postscan **`32151478376`**, artifact **`9329983021`**.
2. On the next **native scheduled** `GenGe Opportunity Discovery` success, verify exactly one automatic `GenGe Postscan Research Pipeline` run consumes that upstream artifact. Change trigger architecture only if the native test fails.
3. Continue specialized-model execution family by family only when inputs are genuinely PIT-safe and auditable. The likely next family is **`transport_cycle`**, subject to a defensible through-cycle EBITDA + lease-consistent net-debt contract.
4. Keep **`yield_asset`** at `INPUTS_REQUIRED` until normalized FCFE and maintenance/growth capex can be sourced without fabrication.
5. Consider bank/other specialized families only after their model-specific evidence contracts are explicit and testable.
6. Specialized sidecars remain research-only and are not consumed by Formal BUY unless a separately tested design explicitly changes that contract.
7. Use `master_opportunity_ranking.csv` for broad research priority, `every_industry_top5_enriched.csv` for industry visibility, and `actionable_long_term_candidates.csv` only for genuinely eligible long-term BUY/TRY review.
8. Preserve PIT correctness, industry recall, reverse-valuation discovery, strict hard blockers, cache versioning and `no_auto_trade=true`.

## Resume instruction for a new ChatGPT session

Tell ChatGPT:

`继续 daily_stock_analysis，先读取仓库 docs/GENGE_WORK_PROGRESS.md，再核对 main 最新 commits 和 GitHub Actions；不要重跑已完成的 2026-08-17 All-A/Postscan，直接从 Next work 继续。`

This file is the durable source of truth. Update it after every meaningful implementation milestone or production finding.
