# Current Mission

## Goal
Two independent, owner-approved lanes: (V4) complete a compact, actually useful living Investor Decision Report; (R) continue trustworthy official-source A-share research, eliminate verified false negatives and resolve stale Canonical provenance. Do not authorize or automatically execute trades.
- **Mandatory V4 source:** `docs/INVESTOR_DECISION_REPORT_V4_EXECUTION_TASK.md` P0–P5. V4 cursor: `state/chatgpt-recovery:recovery/tasks/investor-decision-report-v4.json`, generation 1, implementation P0 **PENDING**; older V3 dashboard/offline mockup are NOT V4 production.
- **Independent research cursor:** `state/chatgpt-recovery:recovery/tasks/stock-system-convergence.json`, generation 66. Research baseline: `recovery/research/stock-candidate-quality-baseline-20260924.json`. Research freshness blocks Formal BUY, NOT independent V4 P0 work.
- Monitor startup/resume: re-read live main, AGENTS.md, this TASK_STATE, both lane cursors, open PRs/branches, actual CI/workflows/artifacts, canonical and decision data. Precedence: live GitHub > separate per-lane recovery > this file > chat. One editor per task file/branch; CAS only owned cursor, never overwrite another monitor.

## Current Phase
`V4_P0_IMPLEMENTATION_PENDING | R_SEP25_SCHEDULED_ALL_A_ARTIFACT_ASOF_SEP24; FRESH_CANONICAL_BLOCKED`

## Last Verified Main
- Observed during 2026-09-26 monitor-handoff refresh: `50f21db32c811513a7150e3a71ed2d50aa46c790`. Re-read live main before every action; runtime persistence moves the ref. Completed PRs #299–#304 are consumed.

## Active Branch
- No V4 implementation branch created by this task update; V4 executor must check live branches/PRs first, then use an independent feature branch/PR.
- Old unmodified `fix/deep-trigger-skip-cache-only-20260924` was investigation-only; protected workflow write previously blocked.

## Active PR
- No verified open active V4 or research fix PR in this checkpoint. Existing old repository PRs must not be silently absorbed; always query live open PRs. This task sync is docs-only.

## CI
- #303 exact-head and postmerge CI SUCCESS; #304 exact-head docs CI SUCCESS and merged. No reason to replay them.
- 2026-09-26 scheduled PIT backtest `36221138005` SUCCESS, results persisted to main `935fe812...`.
- Production Finalizer `36221434943` FAILURE despite **82 passed tests**: `STALE_UPSTREAM: CANONICAL_TRADE_DATE_BEHIND_COMPLETED_SESSION`; downstream authority handoff `36220732176` failed because this finalizer failed. These are fail-closed, NOT Formal authorization.

## Production / Artifact
- Latest verified genuinely **scheduled** All-A production: `36154161688`, 2026-09-25 trigger, job `108135066076` SUCCESS, artifact `genge-all-a-production-report` ID `10874605479`. Its actual **market as-of is 2026-09-24**, NOT Sep25 (report next_trade_date 2026-09-28 is not an as-of). Universe 5,222, effective scan 4,514, price coverage 100%, 80 Deep reviewed, **0 strict-ready**, company-evidence fail 77/80, exit-confidence fail 78/80; zero independently validated exit cohorts and `NO_VALIDATED_EXIT_EDGE`. Genuine new issuer fetch/net-new stable evidence has NOT YET been independently audited.
- Historical audited Sep23 All-A `35937745622` artifact `10784936699`: universe 5,222, effective 4,515, 80 Deep, 0 strict-ready; 98/98 auto-evidence tasks cache hits, zero true fetches. Compare *actual* new artifact against this exact baseline.
- New Every-Industry `36220774737` SUCCESS, artifact `10898882723`, source SHA `7e2c4c79386d9177b8e2faa9ae4279bd8954df32`; already-dispatched Deep `36221429486` at last check: `completed/success`. Verify latest actual final job/output and stable fingerprint before any dispatch.
- Latest verified `data/decision_center/latest.json`: generated 2026-09-26 05:33:55Z but Canonical trade_date **Sep24**; 4 holdings, 0/4 fully Deep complete, 0 new Formal BUY, 0 Formal WAIT_PRICE, 1 research-only BUY and 18 research gaps. This is not fresh executable pricing.

## Completed
- #299–#304 merged/consumed. Old upstream `35886039426` and Deep `35934671719`/`35955222216` gave identical actual issuer/industry evidence, zero net novelty; not replayable. Historical Jev `35955691559` had 25/25 real advisory calls.
- Durable latest two-lane handoff committed: research generation **66**, independent V4 generation **1**; no V4 production implementation falsely claimed.

## Current Findings
- Production scan workflow runs, but 2026-09-25 triggered scan provided Sep24 data, and Finalizer correctly rejected stale Canonical. Workflow green ≠ fresh trade authorization.
- Latest scan 0/80 strict-ready; diagnose official issuer evidence, actual network refetch after #303 negative-cache TTL, company collection (~30) vs 80 Deep selection and out-of-sample exit cohorts, not merely another Gap report.
- Owner's priority is V4 presentation and feasible holding/opportunity decisions, while R quality verification proceeds independently. Do not force a BUY to meet output targets.

## Blockers
- R authority: resolve actual completed **2026-09-25 session** data/evidence and source lineage before new Formal authorization; stale fail-closed remains intact.
- R quality: zero independently validated exit edge, issuer evidence/coverage gaps. Protected workflow duplicate-trigger modification was blocked by tooling; do not bypass safety.
- V4 P0/P1 design/coding is NOT blocked by either research issue; display honest stale/zero-action states.

## Next Action
0. **At every monitor start:** inspect live refs, AGENTS, both distinct recovery cursors/generations, PR/CI/runs/artifacts, canonical and persisted state. Reconcile older checkpoints forward; do not duplicate another worker.
1. **Start V4 P0 immediately** on a distinct checked V4 branch/PR. Reuse existing investor dashboard, Three-Pillar, holdings/funds, confirmed capital, events, formal lifecycle, trend/cycle and official-source payloads; map field-level authority, feed-specific freshness, fallback and lineage; implement additive V4 presentation contract and tests.
2. **V4 P1:** verified holdings + confirmed funds, issuer announcements, shareholder proposal vs resolution, capital/lot/T+1 constraints, source/current quotes, new vs unchanged vs consumed Formal action and material-change feed. Test staleness, missing/unsynced positions and invalid quantities.
3. **V4 P2:** only current qualified `FORMAL_ACTIONABLE`/`FORMAL_WAIT_PRICE` on the investor home; research-only, parked exhausted and hard rejections separate. Bounded official-evidence search, reopen only genuinely new issuer period/fingerprint, independent valuation/exit; show explicit zero eligible instead of fabricating buys.
4. **V4 P3–P4:** officially evidenced secular trends and cycle bottoms → independent industry bottleneck/profit pool/company underwriting → Deep/valuation, then compact existing Web/JSON/Markdown cockpit with source drilldowns, material event diffs, executable cash plan and measured performance. No duplicate decision engine; test UI/back-end/projection parity and update CHANGELOG/docs.
5. **V4 P5:** per phase commit → independent PR → exact-head required green CI → approved merge → real production artifact/current live UI and source freshness evidence. Update V4 recovery only on *verified* milestones; offline mockup/V3/fixture is not acceptance.
6. **Research now:** download/audit genuine artifact `10874605479` for real fresh official PDF/report dates, noncached fetches and **net-new** immutable source identities vs old evidence; find a genuinely completed Sep25 **market** epoch or retain stale blocker. Track in-flight Deep `36221429486`, automatic Terminal/Jev/Overlay/Three-Pillar exactly once using source IDs; no blind restart.
7. **R corrective action:** trace why `36221434943` refuses stale Canonical and dependent `36220732176` fails. Repair source freshness/lineage only with validated new actual market inputs, tests and genuine end-to-end production; no forced stale-data promotion. Check ~30 company vs 80 selection, 40 rotating exit exploration, historical independent cohorts and original 001316/603993 events; fix proven false negatives within budget without relaxing gates.
8. **Later maintenance:** cache-only Deep duplicate trigger requires authorized isolated workflow PR/exact-head CI; do not bypass tool safety. Use actual TypeSafe/Jev calls for advisory triage where appropriate and document served model/count; deterministic code owns eligibility, dispatch and all formal arithmetic.

## Do Not Repeat
- No rerun #299–#304 or consumed same-epoch `35886039426` + duplicate Deep `35934671719`/`35955222216`. Do not redispatch new source `36220774737` while `36221429486` already exists. Do not infer net-new official evidence from a per-run count.
- Do NOT treat Sep25 scheduled run `36154161688` as Sep25 **data**: recorded as-of Sep24. Research BUY/Jev ENTRY_NOW is not Formal BUY; never overwrite another lane's state.

## Guardrails
- `formal_trading_authority=false` (monitor), `formal_buy_authorized=false`, `automatic_execution_allowed=false`, `no_auto_trade=true`, `UNKNOWN != PASS`; existing current finalized Canonical only. Stale trade inputs fail closed. Jev is `SHADOW / ADVISORY_ONLY`, no automatic execution or fabricated capital/holdings, and actual brokerage orders need explicit owner approval.
