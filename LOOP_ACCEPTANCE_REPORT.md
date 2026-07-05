# Current Snapshot Scanner Acceptance Report

## Current Push Summary

- Scope: current snapshot scanner only, separated from historical walk-forward backtest.
- Base context: current snapshot work after `f686c4cba31146d518551de841f14e416016f7ff`; previous Industry Evidence Layer acceptance notes are preserved below for audit continuity.
- No broker integration, no Citic Securities client access, no account/position/password/captcha reading, no automatic buy/sell/cancel behavior.
- Pork, panel, Muyuan, and TCL remain evidence-chain sample objects only. They are not hardcoded as candidates and are not forced into output.
- New current snapshot outputs are designed as `current_snapshot_summary.md/json`, `current_snapshot_all.csv`, `current_cycle_turning_point_candidates.csv`, `current_watch_only_candidates.csv`, `industry_alias_resolution.csv`, `evidence_match_audit.csv`, `data_failure_audit.csv`, and `industry_evidence_cards.md/json`.

## Current Snapshot Tests

- Compile check passed for `data_provider/tencent_fetcher.py` and `src/strategies/genge_cycle_bottom/cli.py`.
- Targeted data-chain tests: `/Users/seker./.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest tests/test_tencent_fetcher.py tests/test_genge_cycle_bottom_current_snapshot.py -q` -> 16 passed, 1 warning, 0.41 seconds.
- Full current snapshot related pytest: `/Users/seker./.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest tests/test_genge_cycle_bottom_*.py tests/test_tencent_fetcher.py` -> 93 passed, 1 warning, 272.09 seconds.
- Full pytest was completed; no requested test group was skipped.

## Current Snapshot Real Run

- Required command naturally exited with `--stock-pool-file stock_pools/genge_broad_pool.txt`, `--max-codes 100`, `--years 5`, `--benchmark 000905`, `--output-dir reports/genge_current_snapshot`, both `data/user_supplied` evidence files, `config/industry_evidence_schema.yaml`, `config/industry_alias_map.yaml`, `--current-snapshot`, `--output-current-snapshot`, `--fixture-smoke-passed`, and `--ci-passed`.
- Latest report path: `reports/genge_current_snapshot/20260705_103627`.
- Runtime: runner `elapsed_seconds=551.98`; wall time `real 552.20`.
- `current_snapshot_summary.json -> industry_evidence_file`: `data/user_supplied/industry_cycle_evidence.csv`.
- `current_snapshot_summary.json -> company_evidence_file`: `data/user_supplied/company_cycle_evidence.csv`.
- `snapshot_total_stocks=100`, `snapshot_valid_stocks=100`, `fatal_data_failures=0`, `skipped_data_unavailable=0`, `skipped_invalid_or_delisted=0`.
- Daily price source distribution from diagnostics: `TencentFetcher=100`; Eastmoney/efinance failures were safely bypassed by multi-source fallback instead of stopping the current snapshot pool.
- `industry_alias_resolution.csv` has 100 rows: 33 matched stocks and 67 unresolved industry stocks.
- Evidence rows loaded: industry 16, company 20. Current evidence coverage: industry 3.0%, company 2.0%.
- `hard_logic_level_distribution={'NONE': 98, 'WEAK': 2}`, `snapshot_decision_distribution={'NOT_QUALIFIED': 98, 'WATCH_ONLY': 2}`.
- `current_cycle_turning_point_candidate_count=0`; `current_cycle_turning_point_candidates.csv` was generated with a disclaimer placeholder row and no candidate was fabricated.
- Zero-candidate blockers: `cycle_phase_not_turning=100`, `hard_logic_below_medium=100`, `industry_evidence_missing_or_unresolved=97`, `trend_below_medium=87`, `price_not_low=62`, `severe_financial_risk=10`, `valuation_risk=25`.

## Current Snapshot Acceptance

Final enum: `PASS_CURRENT_SNAPSHOT_RESEARCH_READY`.

Not upgraded to `PASS_CURRENT_SNAPSHOT_CANDIDATE_GENERATED` because:

- No stock reached `hard_logic_level >= MEDIUM`.
- Most stocks lacked matched current industry/company evidence, and trend confirmation remained below medium for 87 stocks.
- No cycle turning point candidate was fabricated or force-added.

# Industry Evidence Layer Prior Acceptance Report

## A Scope

- Base commit: `1beed4b72b7b36d68a24efb41251262bd7431ea6`.
- This loop stopped feature expansion and only fixed blockers for clean evidence-path validation, summary diagnostics, cycle turning point CSV audit fields, and tests.
- No new industry, no exit-policy tuning, no architecture refactor, no broker integration, no account/position/password/captcha access, no auto order placement.

## B Evidence Inputs

- Industry evidence file: `data/user_supplied/industry_cycle_evidence.csv`.
- Company evidence file: `data/user_supplied/company_cycle_evidence.csv`.
- `summary.json -> diagnostics.industry_evidence_file`: `data/user_supplied/industry_cycle_evidence.csv`.
- `summary.json -> diagnostics.company_evidence_file`: `data/user_supplied/company_cycle_evidence.csv`.
- Industry evidence rows: 16 accepted, 0 rejected.
- Company evidence rows: 20 accepted, 0 rejected.
- Rejected evidence file: `data/user_supplied/rejected_evidence.csv`, 0 data rows.
- Industry source type distribution: `research_report_summary=3`, `company_announcement=6`, `exchange_disclosure=2`, `official_report=3`, `news_summary=2`.
- Industry confidence distribution: `LOW=5`, `MEDIUM=7`, `HIGH=4`.
- Company source type distribution: `company_announcement=12`, `exchange_disclosure=8`.
- Company confidence distribution: `HIGH=16`, `MEDIUM=4`.
- Future-dated input evidence rows: 0.
- Missing fallback: no. The final run recorded `data/user_supplied`, not `data/examples`, `tests/fixtures`, template, placeholder, null, or missing paths.

## C Tests

- Full pytest command: `/Users/seker./.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m pytest tests/test_genge_cycle_bottom_*.py`.
- Result: 77 passed, 0 failed, 1 warning, 276.31 seconds wall time.
- Fixture smoke test was included in the full pytest set and passed.
- No requested test was skipped.

## D Final Broad Run

- Command used the required real broad pool arguments, `--max-codes 100`, `--years 5`, `--benchmark 000905`, `--fixture-smoke-passed`, `--ci-passed`, and both `data/user_supplied` evidence files.
- Latest report path: `reports/genge_industry_evidence_final/20260704_114820`.
- Run exit: natural exit, not manually stopped.
- Wall time: 2400.47 seconds. Runner printed `elapsed_seconds=500.28`.
- `total_signals=1720`.
- `data_failures=90`.
- `provider_error_count=0`.
- `pe_missing_count=0`.
- `pb_missing_count=0`.
- `financial_missing_count=0`.
- Main candidate count: `balanced_research_observation_candidate_count=915`.
- Risk review count: 5 from the runner terminal stats.
- `paper_observation_candidate_count=0`.
- `research_observation_candidate_count=1044`.
- `watch_only_candidate_count=1720`.

## E Evidence Coverage

- Industry evidence coverage rate: 0.0%.
- Company evidence coverage rate: 0.0%.
- Industry evidence missing count: 1720.
- Company evidence missing count: 1720.
- Output industry evidence source distribution: `MISSING=1720`.
- Output company evidence source distribution: `MISSING=1720`.
- Covered industries in final signal rows: none from the supplied pork/panel evidence. Final signal rows were in `白酒` and `食品饮料`.
- Covered sample stocks from supplied company evidence: none.
- Stale evidence count: 0.
- Conflict evidence count: 0.

## F Hard Logic And Candidates

- `hard_logic_level` distribution: `NONE=1720`, `WEAK=0`, `MEDIUM=0`, `STRONG=0`.
- Safe downgrade path worked: missing industry/company evidence blocked hard logic instead of upgrading signals.
- `cycle_turning_point_candidates.csv` was generated.
- `cycle_turning_point_candidate_count=0`.
- Zero-candidate blocker summary in the CSV: `hard_logic_insufficient=1720`, `cycle_phase_mismatch=1720`, `price_percentile_not_low=657`, `trend_insufficient=458`, `balanced_exit_profile_not_passed=361`, `valuation_or_financial_not_passed=3`, `execution_or_value_trap_risk=1`.
- The candidate CSV includes the required disclaimer and did not contain buy/sell promises.

## G Sample Object And Safety Check

- Pork, panel, Muyuan, and TCL were only used as evidence-chain sample objects in user-supplied data and research notes.
- Production code did not hardcode those stocks as candidates and did not force them into output.
- No broker client was opened.
- No Citic Securities account integration was added.
- No automatic buy, sell, cancel, or account-reading behavior exists in this validation path.

## H Acceptance Decision

Final enum: `FAIL_CLEAN_EVIDENCE_RUN`.

Blocking reasons, capped at three:

- Latest final-code broad run had `data_failures=90`, so it fails the required clean-run criterion even though it exited naturally and recorded real `data/user_supplied` evidence paths.
- Evidence coverage was 0.0% for both industry and company evidence, so all 1720 signals safely downgraded to `hard_logic_level=NONE`.
- `cycle_turning_point_candidate_count=0`; candidates were not fabricated because hard logic, cycle phase, trend, valuation/financial, execution risk, and balanced-exit gates did not pass.

Audit note: an earlier same-command run at `reports/genge_industry_evidence_final/20260704_110040` naturally exited with `data_failures=0`, but it occurred before the final summary data-failure count patch and still had 0.0% evidence coverage with `hard_logic_level=NONE` for all signals. The final-code validation result above is therefore kept conservative.
