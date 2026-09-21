# Current Mission

## Goal
Converge the existing stock system into one trustworthy daily decision surface before adding new models. Preserve Candidate Lifecycle, valuation/decision thresholds, Formal authority separation, UNKNOWN != PASS, and no_auto_trade=true.

## Current Phase
Production-verify merged #232 fail-closed material-event persistence on a fresh Deep run. Do not merge #230/#231 until this safety repair is proven in production.

## Active Branch
None for the current safety repair; #232 has merged.

## Active PR
- #232 — `fix: preserve verified material-event failures across deep runs` — merged as `07dd4ca72e94c7576e3f2672a5df38266c1deddb`.
- #230 (SSE annual-report discovery) and #231 (MIIT industry evidence depth) remain open and held until #232 production verification passes.

## CI
- #232 final PR head `dabfb27a1e74b3ce21641d1bf54993505e4e266f` completed PR CI successfully before merge.
- Main merge commit `07dd4ca72e94c7576e3f2672a5df38266c1deddb` triggered push CI run `35556361160` and production evidence workflows.

## Last Verified Main
- PR #229 merged into main as `c8693a1d89794fb351bde5cf563f5cf2ef9c4cc9`.
- Current business-code main baseline for this verification: `07dd4ca72e94c7576e3f2672a5df38266c1deddb` (#232 squash merge).
- Live GitHub refs / PRs / Actions / artifacts / persisted data always override this checkpoint.

## PR / CI State
- #232 — `fix: preserve verified material-event failures across deep runs` — merged; production verification in progress.
- #230 — `fix: restore SSE multi-year annual-report discovery` — open; its latest observed CI is green, but merge is held behind #232.
- #231 — `fix: deepen MIIT industry evidence discovery` — open and independent; merge is held behind #232.
- #229 — `fix: front-load strict predictability evidence collection` — is merged.
- Final PR head: `3493029639c2ec64a20eca4231c574d222ce18c4`.
- Required CI/review checks were green before merge.
- Scope remained scheduling-only; no evidence gate, provider authority, MIN_COMPLETE_YEARS, valuation, BUY/WAIT_PRICE/REJECT, Candidate Lifecycle, Formal authority, UNKNOWN != PASS, or no_auto_trade semantics changed.

## Production / Artifact
- Post-#229 Deep run `35551673513` completed successfully at code baseline `c8693a1d89794fb351bde5cf563f5cf2ef9c4cc9`.
- Terminal artifact: `genge-v31-deep-calculation-35551673513`.
- requested=852; processed=852; complete=0; evidence_exhausted=852.
- predictability verified=0; predictability_resolved_gate_count=0.
- All 852 predictability rows ended `INSUFFICIENT_CONSECUTIVE_COMPLETE_FISCAL_YEARS`: 273 0-prefix, 109 3-prefix, 470 6-prefix.
- #229 materially changed Shenzhen/ChiNext transport behavior: the old 0/3-prefix query-failure shape disappeared and 23 0-prefix rows obtained report metrics/source URLs, but none reached the strict multi-year resolution threshold.
- Raw same-workset comparison to terminal run `35549602593` exposed 18 disappeared historical material-event FAIL gates: 16 became UNKNOWN and 2 became PASS.
- Revalidating the 13 underlying historical rows with corrected current title semantics removes 5 stale/non-assertive rows: 3 explicit resolution rows and 2 "是否存在..." due-diligence classifications.
- The strict carry-forward set is therefore 8 still-active official rows mapping to 12 hard-gate FAILs.
- After semantic correction, the demonstrated true FAIL -> PASS regression is `000557 financial_safety`; `000603` must not be restored because its disclosure says the funds occupation was already resolved.

## Locked Comparison Baseline
- Prior terminal run: `35549602593`.
- requested=852; processed=852.
- predictability verified=0; predictability_resolved_gate_count=0.
- Terminal predictability unresolved:
  - 377 = `ANNUAL_REPORT_QUERY_FAILED:PRIMARY:ConnectionError,CNINFO:HTTPError:403`
    - 269 codes with 0-prefix
    - 108 codes with 3-prefix
  - 470 = `INSUFFICIENT_CONSECUTIVE_COMPLETE_FISCAL_YEARS`
- Earlier pre-#225 exact query-failure baseline: 375.
- #225 therefore did not improve the production transport bucket.

## Current Findings
- #225 browser-form CNINFO headers alone were insufficient in production.
- Previous production showed first-party SZSE transport degrading later in long Deep runs, followed by CNINFO 403 fallback.
- #229 tests the scheduling/transport-liveness hypothesis by running the unchanged strict predictability collector before high-volume general evidence collection.
- The optimized runtime patch was re-read after merge and confirmed not to bypass this order.
- Transport/query recovery is never evidence PASS; verified annual-report bodies and complete strict metrics remain mandatory.
- Shanghai strict incomplete-consecutive-year cases stay UNKNOWN unless verified official evidence resolves them.
- The prior terminal artifact stored 13 rows as VERIFIED/ACTIVE/HIGH and generated 18 hard-gate FAILs; artifact review showed 5 of those labels were semantically stale/non-assertive under the corrected rules.
- In `35551673513`, SZSE announcement metadata still surfaced those risks, but `disc.static.szse.cn` PDF downloads returned HTTP 403 and later retries sometimes hit SZSE transport failure; the fresh run therefore failed to recreate the verified rows.
- Current closure logic uses only same-run material-event evidence, so transient refetch failure can erase an earlier verified negative gate. This is the demonstrated root cause addressed by #232.
- #232 revalidates persisted rows with the current material-event title classifier before reuse, including expiry at the run as-of date.
- #232 fixes title semantics for explicit "已解决/影响已消除" resolutions and "是否存在..." due-diligence questions so keyword presence alone cannot create a hard FAIL.
- #232 uses compact status files as the bootstrap index instead of scanning every multi-megabyte evidence payload, then writes a cumulative complete risk ledger for future runs.
- Historical PASS evidence, ordinary evidence, resolved/expired events, non-assertive titles, unofficial domains, and lower-severity events are never reused.

## Completed
- #223 Deep liveness fix remains production-proven.
- #225 was merged, production-tested, and correctly classified as unsuccessful for its intended transport recovery.
- #229 passed required CI/review and merged.
- #232 passed PR CI and merged as `07dd4ca72e94c7576e3f2672a5df38266c1deddb`.
- Evidence Change Trigger run `35556361159` succeeded and launched Deep production run `35556365712`.
- Main production code path was verified after merge.
- Volatile web-session checkpoint is stored on `state/chatgpt-recovery` at `recovery/tasks/stock-system-convergence.json`; live GitHub remains authoritative.

## Blockers
Fresh post-merge Deep production evidence for #232 is still required before #230/#231 may merge.

## Next Action
1. Resume production Deep run `35556365712` on main baseline `07dd4ca72e94c7576e3f2672a5df38266c1deddb` (triggered by Evidence Change Trigger run `35556361159`).
2. If it fails, inspect the exact failing job/step and repair only the demonstrated cause.
3. If it succeeds, inspect terminal artifact and persisted history/ledger.
4. Verify the revalidated 8-row / 12-gate historical risk set remains fail-closed when current refetch fails.
5. Specifically verify `000557 financial_safety` is FAIL, while resolved/non-assertive historical rows such as `000603` and `301251` are not resurrected.
6. Verify cumulative risk-ledger counters, Deep -> Provenance -> Terminal -> Investor convergence, UNKNOWN != PASS, and no_auto_trade=true.
7. Only after #232 is production-proven, resume #230 Shanghai SSE annual-report discovery verification and then #231 long-term-demand evidence depth.

## Do Not Repeat
- Do not reopen solved Candidate Lifecycle continuity work.
- Do not treat #225 as a successful transport fix.
- Do not recreate or reopen #229; it is merged.
- Do not restart from generic CNINFO-header speculation.
- Do not use stale `latest_status.json` as the result of run `35551673513`.
- Do not merge #230 or #231 ahead of the #232 fail-closed safety repair.
- Do not treat current-source unavailability as evidence that a previously VERIFIED/ACTIVE/HIGH material risk disappeared.
- Do not change multiple transport variables while a production experiment is being isolated.
- Do not promote metadata/query success itself to evidence PASS.
- Do not loosen predictability, valuation, BUY/WAIT_PRICE/REJECT, Candidate Lifecycle, Formal authority, UNKNOWN != PASS, or no_auto_trade.

## Guardrails
- GitHub live state is the source of truth.
- Preserve exact run/profile/source/code-epoch lineage.
- Production artifacts are required in addition to tests.
- Formal/Production authority remains separate from Research outputs.
- UNKNOWN != PASS.
- no_auto_trade=true.

## Parallel Jev Integration Checkpoint
- TypeSafe AI Jev Phase 1 merged in PR #237: live API path and shadow-only typed research-routing judgments were validated; real smoke served model `jev-1.13.0`.
- Jev Phase 2 merged in PR #240 as `a14b3b0c4b7efcdfd0e85d2b7e402105327d3cb3`.
- Phase 2 adds `GEN_GE_JEV_ROUTING_BRIDGE_V1`: typed advisory routes `NO_ESCALATION / EVIDENCE_REFRESH / DEEP_RESEARCH / HUMAN_REVIEW`, priority/evidence-state/confidence metadata, artifact generation, and manual persistence support.
- Authority remains non-trading and fail-closed: `automatic_dispatch_allowed=false`, `formal_trading_authority=false`, `mutates_authoritative_decision=false`, `UNKNOWN != PASS`, `no_auto_trade=true`.
- Current main does not yet contain `data/jev_shadow/latest.json`, `data/jev_shadow/latest_routing.json`, or `JEV_RESEARCH_ROUTING.md`; a successful manual `GenGe Jev Shadow Evaluation` workflow_dispatch is still required to persist the first production advisory snapshot.
- Do not let Jev override deterministic research obligations or Formal BUY/WAIT_PRICE/REJECT. Promotion to automatic research dispatch requires repeated calibration first.


## Jev Automatic Research Orchestration — Current Checkpoint

### Mission
Turn the already-built Jev layer into a usable closed research loop instead of a standalone advisory report.

### Target Chain
`GenGe Jev Shadow Evaluation -> GenGe Jev Research Orchestrator -> GenGe V3.1 Deep Calculation Lambda -> GenGe V3.1 Terminal Research Decision -> GenGe Investor Terminal Research Overlay -> GenGe Three-Pillar Decision Center`

### Durable State
- Jev advisory truth: `data/jev_shadow/latest.json`, `data/jev_shadow/latest_routing.json`, `JEV_RESEARCH_ROUTING.md`.
- Automatic research-loop cursor: `data/jev_shadow/orchestration/latest.json`.
- The cursor must record `source_workflow_run_id`, lifecycle state, selected codes, and accepted Deep run id when dispatch occurs.
- Same Jev source run must never dispatch Deep twice.

### Lifecycle
`JEV_READY -> ORCHESTRATION_PENDING -> DEEP_DISPATCH_ACCEPTED -> DEEP_COMPLETE -> TERMINAL_COMPLETE -> INVESTOR_OVERLAY_COMPLETE -> DECISION_CENTER_REFRESHED`

The persisted cursor directly stores the first three states. Later stages are reconciled from GitHub Actions and persisted downstream data.

### Resume Rule
When the user says only "继续" in a future session:
1. Read current live main / PRs / Actions.
2. Read this file.
3. Read `data/jev_shadow/latest_routing.json`.
4. Read `data/jev_shadow/orchestration/latest.json` if present.
5. If cursor is `ORCHESTRATION_PENDING`, search Actions for the exact `JEV_ORCHESTRATOR_<source_workflow_run_id>` Deep run before any retry.
6. If cursor is `DEEP_DISPATCH_ACCEPTED`, follow its `deep_run_id`; then follow the automatically chained Terminal -> Investor Overlay -> Three-Pillar runs.
7. If the chain has completed, inspect the newest terminal decisions and investor-facing result, then decide the next research action from real persisted evidence.
8. Never ask the user to restate this project background and never restart completed stages.

### Authority
- Jev direct dispatch: false.
- Deterministic bounded research dispatch: allowed by the orchestrator only when Jev route and existing deterministic triage agree.
- Formal trading authority: false.
- Automatic Formal BUY: false.
- UNKNOWN != PASS.
- no_auto_trade=true.

### Current Engineering Work
- Phase 1 (#237) and Phase 2 (#240) are merged.
- First manual production Jev run `35569181282` succeeded 25/25 on `jev-1.13.0` and persisted its advisory.
- The first production sample showed 25/25 `EVIDENCE_REFRESH`, exposing overly homogeneous input selection.
- Phase 3 priority-triage logic was validated on PR smoke: current holdings became `needs_deep_research=true`, while route uncertainty remained visible rather than being hidden.
- Replacement implementation branch: `feat/jev-auto-orchestrator-20260921`.
- This branch replays Phase 3 onto current main and adds deterministic bounded auto-research orchestration with write-ahead intent, exact Jev run lineage, duplicate-dispatch reconciliation, and automatic Deep handoff.
- Old PR #241 is superseded by this combined implementation and should not be merged separately.

### Next Action
Finish CI for the combined Jev auto-orchestration PR, merge only when green, then verify on main that the merge-triggered 25-entity Jev production run:
1. persists exact source workflow lineage,
2. triggers the Jev Research Orchestrator,
3. selects only deterministically eligible bounded research codes,
4. dispatches exactly one Deep run,
5. persists `DEEP_DISPATCH_ACCEPTED`,
6. automatically continues through Terminal -> Investor Overlay -> Three-Pillar,
7. produces a fresh investor-facing research result without changing Formal authority or enabling auto trade.
