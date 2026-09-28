# V4 owner operating contract: automated evidence + on-demand ChatGPT Web (NO GPT API)

**Owner approval:** 2026-09-27. **State:** SPEC_CAPTURED_ONLY until implementation, exact-head CI and production artifact verification. **Parent:** [Investor Decision Report V4](INVESTOR_DECISION_REPORT_V4_EXECUTION_TASK.md), P0–P5. This document **refines** its operating mode; do not start a duplicate V4 implementation, overwrite another task cursor or abandon independent All-A/Deep verification.

## 1. Exactly what the owner wants

The owner wants to open the stock website and see an **automatically refreshed, decision-useful, evidence-linked report**, without entering daily trade forms, prompting data collectors, reviewing CI, or scheduling LLM calls. For complex synthesis, the owner opens **ChatGPT Web**, asks once for the latest investment report, and ChatGPT uses the **connected GitHub repository** to read a bounded, fresh, provenance-validated handoff. The owner remains responsible for deciding whether to place actual trades.

**Do not add GPT API usage or require an unattended GPT model in GitHub Actions.** ChatGPT Web runs only following a user-initiated prompt in that ChatGPT conversation. Opening the separate stock website **does not and cannot by itself invoke this ChatGPT session**. The stock site must therefore present useful continuously refreshed deterministic/program-generated findings *even when no ChatGPT Web session is open*. Never imply the two interfaces provide identical on-demand model inference.

Existing independently configured TypeSafe/Jev shadow advisory may continue under existing rules; this owner request specifically prohibits **adding GPT API to the automated V4 path**, not silently disabling established Jev jobs. Neither Jev nor ChatGPT is Formal trading authority. If the owner later requests absolutely zero background LLM API activity, handle that as a separately scoped explicit change, with dependency audit.

## 2. Existing verified components; reuse instead of rebuilding

- `.github/workflows/genge-investor-decision-dashboard.yml`: existing scheduled/triggered report publisher, scheduled on weekdays at `20 8 * * 1-5` UTC (16:20 Beijing when UTC+8). Observe actual workflow outcomes; a scheduled invocation is not proof of new exchange-session data.
- `data/investor_decision_dashboard/latest.json`, `data/decision_center/latest.json`, `LATEST_DECISION_CENTER.md`: persisted investor output, Three-Pillar report and Canonical lineage. Their generated-at time does not confer market/issuer/position freshness.
- `CURRENT_HOLDINGS.md`, `CURRENT_FUNDS.md`, `CURRENT_CAPITAL.json`, `data/manual_broker_snapshots/`, `data/manual_execution_quotes/`: existing dated portfolio and cash evidence. As of task capture, broker portfolio is **not** automatically connected, and `data/transactions/holdings_projection.json` declares `migration_required_before_production_use=true`. Do not substitute the stale transaction projection for validated current holdings, or present planning cash as verified live cash.
- `src/strategies/genge_opportunity_discovery/investor_decision_v4_projection.py` and `investor_decision_v4_p1_sources.py`: merged read-only V4 P0/partial P1, **not** full Web/API integration or live execution authority. Continue these contracts and existing `investor_decision_dashboard*` / `three_pillar_decision_center*`.
- Existing official issuer collectors, event-closure and independent research lane, `data/era_radar/`, Jev advisory + deterministic research router.
- `data/formal_decision_history/`, `data/formal_decision_outcomes/latest.json`, `scripts/decision_outcome_evaluator.py` and existing decision-outcome observer; the observer is downstream of finalized Canonical and must not silently tune trading gates.

## 3. Implementation tasks in dependency order

### [ ] H1 — stable, bounded GitHub handoff, produced by existing automated report path (V4 P1/P4)

Do not create another investment decision engine or start a new schedule if the current investor publisher is sufficient. After upstream validation, persist atomically:
- `data/investor_chatgpt_handoff/latest.json`: compact, strictly versioned manifest;
- `INVESTOR_CHATGPT_HANDOFF.md`: concise human-readable entry point mirroring the manifest, with stable links and current warnings.

Minimum manifest contract, using **source pointers, not full duplicated financial reports**:
- `contract_version`, `generated_at`, `market_session_as_of`, `canonical_snapshot_id`, `canonical_source_run_id`, immutable source hashes/paths, cross-feed lineage-validity and production-run/artifact identifiers when verified;
- separate timestamp/quality/authority entries for: exchange calendar + EOD breadth, reference and *executable* quotes, independently dated original issuer publications/outcomes, confirmed equities, confirmed funds, *planning vs broker-verified cash*, official-company/industry source coverage, qualified Formal vs research-only opportunities, era/cycle research-only hypotheses, and historical decision outcomes;
- at most a small holdings-first summary, materially changed events and a bounded list of formally eligible candidates; all exhaustive evidence/audit remains via exact drill-down references. Report `UNKNOWN`, `STALE`, `MISSING`, `UNVERIFIED` explicitly; any unsupported data field is absent rather than fabricated;
- original source URLs, issuer/document publication period, evidence fingerprint/content hash when present, verification level, valuation inputs and bull/bear/invalidation/source references for every material conclusion;
- no secrets, login cookies, raw screenshots, broker identity/account numbers or new personal details in a public repository.

Acceptance: a single GitHub fetch yields an actionable **entry point** and bounded drill-down references; every linked source/file truly exists and source scopes/timestamps match. Re-rendering an unchanged input epoch preserves snapshot identity and does not invent new news/authority. Production handoff must come from genuine latest validated artifacts, not fixtures or Markdown template alone. Preserve fail-closed stale Canonical and missing-official-evidence states; a green workflow is not proof of a new trading day.

### [ ] H2 — durable ChatGPT Web on-demand instructions (V4 P4)

Maintain `docs/INVESTOR_V4_CHATGPT_WEB_PROMPT.md`, a copyable one-sentence request plus a concise execution checklist for ChatGPT:

> Read the live `wanggenAi/daily_stock_analysis` main and current `INVESTOR_CHATGPT_HANDOFF.md` / `data/investor_chatgpt_handoff/latest.json`; verify source freshness, original evidence, Formal-versus-research scope and important conflicts; drill into referenced files as required and produce today's concise holdings-first investment research report, evidence-backed opportunities, market/era/cycle change, capital constraints, falsifiers and historical decision scorecard. Label every stale/unknown element; do not invent live quotes, account trades, official sources, investment authority or performance.

For every user-initiated report: actually fetch the current main, the manifest and necessary source files through the connected GitHub tool; do **not** assume the conversation or last report is current. Distinguish facts already verified by code from ChatGPT's additional inference, cite clickable original issuer evidence and exact repository report paths, and avoid restating an old study BUY as an executable Formal BUY. If connection is unavailable, say so; do not claim fresh access. No automatic invocation of ChatGPT Web is promised or required. Do not use GPT API for this path.

### [ ] H3 — daily stock website works without ChatGPT (V4 P1–P4)

Use existing `apps/dsa-web` and API, not a parallel app. On owner opening the stock site, show the latest persisted, *as-of-labeled* holdings and funds status, conditional market state, formally eligible decisions with price/quantity/expiry and evidence drill-down, research-only queue kept separate, cash planning versus real broker balance, new significant issuer/policy events and independently validated trends/cycles. When latest data are stale, show the last valid observation and why no fresh execution claim is possible. An optional **copy handoff prompt / open ChatGPT** affordance must be truthful: navigation/copy only, not silent conversation control. Web/UI screenshots belong in the eventual implementation PR description, not one-off repo files.

### [ ] H4 — independent automatic historical decision outcome validation (V4 P5)

Extend existing observer instead of recreating it. Freeze original finalized decision/evidence/as-of *before* future observations; retain stable decision epoch identities and avoid counting unchanged persisted HOLD snapshots as independent successful stock picks. Evaluate day-5/day-20/day-60 adjusted forward returns (handle splits/corporate actions), matched benchmark/industry comparison, adverse excursion/drawdown and thesis invalidation where observable; distinguish pending vs fully observed horizons and verified vs research-only authority. Do not use look-ahead evidence, conflate selection with execution-layer backtests, or modify Formal gates as a side effect of outcome feedback.

**Two independent result ledgers:**
1. Automatic *recommendation market outcome* needs **no owner trading or forms**. This is the mandatory default scorecard.
2. *Actual personal account realized P&L* requires real verified execution evidence (fills/costs/fees). If an explicitly owner-authorized compliant broker read-only feed or non-interactive authorized export can be supported, reconcile it into existing portfolio/transaction services with credentials kept outside GitHub; otherwise show **account execution/realized P&L unknown**, not estimates mislabeled as fact. Public market prices alone do not establish new fills.

### [ ] H5 — real end-to-end production acceptance (V4 P5)

Proof must show, on actual market/issuer data and a true production run, that:
1. unattended data refresh publishes a current or honestly stale handoff and matching existing site report without user daily forms or GPT API;
2. the user can explicitly ask ChatGPT Web to read the live latest handoff and produce a cited, original-evidence-linked, current-or-honestly-stale, holdings-first synthesis;
3. source mismatches, stale quotes, missing funds, missing fills, old issuer *proposals* vs approved meeting *resolutions*, prior consumed authorization, empty qualified list and holiday/non-trading dates all fail closed;
4. independently recorded advice can be revisited after 5/20/60 sessions with benchmarked scorecard even if no trade was executed; real account results never fabricated;
5. code, exact-head CI, approved merge, main verification, workflow artifacts and deployed/accessible actual Web/API are independently demonstrated. A mockup, plan, offline fixture or completed workflow without valid payload is not sufficient.

## 4. Coordination and next executable action

1. Before coding, re-read live `main`, `AGENTS.md`, `TASK_STATE.md`, `docs/INVESTOR_DECISION_REPORT_V4_EXECUTION_TASK.md`, task-scoped `state/chatgpt-recovery:recovery/tasks/investor-decision-report-v4.json`, **separate** research cursor, open PR/branches, required exact-head CI and latest artifacts. Do not overwrite PR #311's `TASK_STATE.md` or another worker's cursor. Latest actual GitHub always supersedes stale numbers here.
2. First implementation PR should be **H1** only: inventory real dashboard/Three-Pillar source schemas, implement a bounded read-only handoff builder and integrate it with the existing publication path, add schema/provenance/freshness/missing-data regression tests and production proof. Preserve V4 P0/P1 work and keep old report outputs compatible.
3. Then implement H2 and H3 in smallest compatible PRs, H4 using existing history/observer after source semantics are stable, and H5 real proof. Finish each PR with tests, exact-head required CI and live main/production re-read, and register only verified milestones in V4-specific recovery sidecar.
4. Keep unrelated independent research coverage/exit validation running. No new GPT API automation, no browser automation against the ChatGPT website, no auto-trading and no unauthorized broker access.

**Milestone semantics:** `SPEC_CAPTURED` → `H1_CODE_MERGED` → `HANDOFF_PRODUCTION_VERIFIED` → `ON_DEMAND_CHATGPT_PROVEN` → `SITE_INTEGRATION_VERIFIED` → `OUTCOME_SCORECARD_VERIFIED`. Do not collapse these into a single `DONE`.


## 5. Owner-directed monitor kickoff and next-session readiness (2026-09-27)

**Owner instruction:** Start the existing external Codex/ChatGPT monitor and continue implementation now. This is a durable next-action and acceptance checklist, **not** evidence that a monitor is running or that the 2026-09-28 opening is ready. Do not spawn a competing monitor, add a ChatGPT API call, or bypass browser/login/permission boundaries. The monitor must read live refs on *each* recovery and perform real work rather than only write status.

### Ordered startup (no replay)

- Read current GitHub `main` SHA and latest history; `AGENTS.md`; live `TASK_STATE.md` with its known possible staleness; the parent V4 execution plan; this owner operating contract; the **V4 and research task sidecars separately** on `state/chatgpt-recovery`; all overlapping live PRs, required exact-head CI/reviews/threads, relevant workflows and real latest artifacts. Do not rely on generation 7/72 as immutable current truth or overwrite a task file owned by another worker. Reconcile current main versus branch/file blobs before writes.
- Resolve rather than duplicate pending coordination: inspect PR #311 (dual-lane TASK_STATE reconciliation) and PR #312 (this operating contract). If another worker merged/changed either PR, consume the new live result. Only merge a reviewed, mergeable **current** head with required green checks; if branch has drift/conflict, build a minimal fresh-main replacement PR preserving both independent lanes and audit trail. Do not silently declare this unmerged document active on main.
- Preserve V4 P0 and partial P1 merged history; complete the missing real source feed and actual production Web/API projection from H1-H3 in independently verifiable small PRs. First deliver H1 bounded source-validated GitHub handoff via the **existing** investor publication workflow, with deterministic freshness flags, lineage and original source drilldowns. H2 on-demand prompt already exists as documentation in PR #312 but only counts as end-to-end completed after an actual ChatGPT-Web-to-live-handoff test. H3 means the existing stock Web site has a genuinely deployed, usable holdings-first V4 view without launching ChatGPT. H4/H5 follow with measured real artifacts.
- Independent research lane: PR #310 issuer-coverage instrumentation has been observed merged 2026-09-27; **verify it on current main and the next genuinely executed All-A artifact before claiming production evidence coverage**. Audit separately annual issuer collection, material-event collection, touched/attempted/noncached/cached/not-attempted and net-new immutable official-source fingerprints. Investigate the previous 80-queue/30-ish company coverage and zero independent new issuer fingerprints; adjust only demonstrated coverage/fetch bugs, never loosen evidence or buy gates to get a favorable recommendation. Preserve terminal/candidate lifecycle and parked historical research; do not redispatch already-consumed Deep/Terminal/Jev runs simply to repeat gap reports.
- Before the 2026-09-28 A-share open, publish an **honest readiness gate** against the last genuinely completed exchange session, not a regenerated-at timestamp: market as-of, Canonical source epoch, quote/feed time, current broker-confirmed holdings/funds if available, issuer evidence, current Formal authorization and exact last CI/production run IDs. Existing investor latest.json produced 2026-09-27 may still have market trade_date 2026-09-24; a report dated today is *not* today's market data. No verifiable fresh input => clearly mark stale / show historical research only and immediate executable quantities = 0 when guards require it. Distinguish prep before open, intraday reference quotes and completed-session EOD evaluation; a weekday 16:20 Beijing publisher alone is **not** proof of a ready 09:30 opening dashboard.
- Run narrow tests for stale Canonical, mismatch/missing broker balances, proposal-versus-adopted issuer resolutions, price/lot/T+1 quantity, consumed authorization, exact lineage and freshness, candidate evidence audit and Web/API/report parity. Then exact-head CI, reviewed merge, postmerge main, actual scheduled/triggered production artifact, source as-of, accessible live Web view/screenshot or explicit not-deployed blocker. Advance only the owned task cursor by compare-and-swap after **verified** milestones and keep root TASK_STATE coordinated rather than racing PR #311.

### Owner-visible operating acceptance (do not mark green prematurely)

1. On opening the actual existing stock website, the owner sees the latest **verified-or-explicitly-stale** holding-level action rationale, concrete conditional price/share/cash plan when fully supported, original-evidence drilldown, meaningful changes, qualified separate opportunities and trend/cycle research; missing evidence never turns into a fabricated BUY. Useful report must exist with no new GPT API and no mandatory owner daily form.
2. On demand in ChatGPT Web, fetching a real H1 manifest from the current GitHub main generates a concise evidence-cited synthesis; opening the stock website is not described as calling ChatGPT automatically. The H1 files must exist **before** replacing the current fallback path in the prompt.
3. Independent historical advice results can advance with later real sessions even if the user made no trade; account realized P&L remains unknown without verified fills. Neither advisory Jev nor research BUY changes Formal rights or automatically trades.
4. Report three separate verdicts at each checkpoint: `REPORT_AVAILABLE` (historical read), `MARKET_SESSION_FRESH` (proven as-of and source epoch), `OPENING_DECISION_READY` (all relevant source, capital, authorization, and actual deployment checks pass). Do **not** infer opening readiness from successful CI, a new runtime persistence commit, or research-only results.

**If running into auth, external monitor setup, broker-data permission or deployment secrets blockers:** record the exact blocker and preserve the checkpoint; continue independently available engineering/research work rather than waiting silently. Existing monitor scheduling/execution is outside this task document: its actual runtime status must be verified in the monitoring environment and must never be claimed from this commit.

### 2026-09-28 report source-session regression guard (incremental safety repair)

The existing Investor Brief publisher must not replace a previously published *newer real market trade date* with an older Finalizer or event-replay snapshot merely because the replay workflow completed later. The incremental guard compares the existing published investor JSON `latest_trade_date` with each would-be persisted candidate after every fresh-main fetch/retry. It rejects malformed dates or a regressive date before any `main` push and leaves the previously published output untouched. This is a publication integrity safeguard, **not** proof that the desired completed market session has been collected, nor a repair for currently choosing a stale Finalizer. After a rejection, trace original Finalizer artifact/selection and genuine post-close session source, and keep `STALE_UPSTREAM` / new Formal exposure blocked until independently verified. Tests: `tests/test_guard_investor_report_epoch.py`. No GPT API, threshold or authority change.
