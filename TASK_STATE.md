# Current Mission

## Goal
Produce trustworthy, current, evidence-backed stock-research candidates and research-only entry guidance without granting Formal or automatic trading authority.

## Current Phase
PR301_PRODUCTION_VERIFIED_CANDIDATE_QUALITY_CONVERGENCE

## Last Verified Main
- Immediately before this checkpoint branch: `d0b8d7e3419e5add280321be2a46dbb447c6f0bc` (2026-09-24 03:30:19Z). Always re-read live main; runtime persistence advances the ref.
- #301 merged 2026-09-24 03:17:27Z: `27b12cd042c0c4ffb6f22d0a534aa55c2014d779`; final PR head `3a01981185547ae73b231caa67851009a0bba876`.
- #299/#300/#301 work is consumed. Do not replay old branches or previously exhausted evidence epochs.

## Active Branch / PR
- No active *business* PR for this mission at the verified checkpoint. Unrelated older open PRs exist and must not be treated as a current convergence branch.
- This docs-only checkpoint branch may be in PR/merge processing; verify by live PR refs. Volatile execution cursor: `state/chatgpt-recovery:recovery/tasks/stock-system-convergence.json`.

## CI
- #301 exact-head repository CI `35949404048`: SUCCESS.
- #301 PR-head live TypeSafe/Jev shadow `35949404151`: SUCCESS.
- #301 merge-push repository CI `35950836329`: SUCCESS on merge SHA `27b12cd`; independent merge-push Jev `35950836337`: SUCCESS.
- Do not confuse PR-head checks, merge-push workflows, natural Research Learning persistence, or explicit Deep continuation.

## Production / Artifact
- **Verified natural changed-state handoff**: post-merge push Research Learning `35950836333` SUCCESS; job log shows successful changed-state commit/push `37fa1e0fd` at 03:18:24Z, followed by explicit `gh workflow run` at 03:18:27Z. Resulting Jev **workflow_dispatch** `35950900132` SUCCESS, with 25/25 real TypeSafe calls served by `jev-1.13.0`. Persisted `data/research_priority/learning_lineage.json` binds Learning run `35950836333`; persisted `data/jev_shadow/latest_routing.json` binds Jev source `35950900132`, event `workflow_dispatch`.
- Separate independent merge-push Jev `35950836337` also SUCCESS 25/25, but is **not** evidence of the changed-state explicit handoff. Earlier Deep-continuation Jev `35935194769` likewise does not prove it.
- Deterministic orchestrator `35951194702` SUCCESS for explicit Jev source `35950900132`: zero new Deep dispatches, 24 skipped due to same-epoch exhaustion/ineligibility/low attention, one **research-only** valuation closure for `603596`. Latest cursor: `data/jev_shadow/orchestration/latest.json`, `VALUATION_CLOSURE_DISPATCHED`; no pending operation. Downstream terminal `35951305965`, terminal investor overlay `35951428522`, and Three-Pillar `35951609762` SUCCESS; newest `data/decision_center/latest.json` generated 2026-09-24 03:30:19Z.
- Finalizer `35951027897` **failed closed** with `STALE_UPSTREAM: CANONICAL_TRADE_DATE_BEHIND_COMPLETED_SESSION`; stale canonical input was refused. This is expected safety behavior, not a Formal success and not automatically a defect in #301. A valid newer canonical evidence event is required for a fresh Finalizer attempt.
- Latest persisted priority (`2026-09-24T03:18:23Z`): 126 queued, P0=4, P1=3. Dormant `601020` remains suppressed; `000504` and `600816` only have research re-underwrite signals, not Formal BUY.
- Latest terminal research (`2026-09-24T03:25:59Z`): 16 rows, one **research-only** BUY (`603596`) and 15 RESEARCH_GAP. Latest Decision Center reports new_buy_now_count=0, new_wait_price_count=0 and four holdings with partial Deep evidence; do not present research BUY as executable.
- Mapping coverage still has six applicable-unmapped peers: `000415,000426,001316,600309,603416,603658`; commodity gap `600309`. Lack of verified evidence is a visible research gap, not a reason to infer PASS or fabricate peers.

## Completed
- Reconciled stale PR301-awaiting-CI checkpoint against live GitHub and verified PR-head checks, merge-push CI, *actual changed-state Research Learning to explicit Jev handoff*, real TypeSafe calls, same-epoch suppression, and downstream research-only convergence.
- Confirmed stale-input Finalizer safety denial and latest persisted advisory/formal separation.

## Current Findings
- Candidate-quality bottleneck is **novel, verifiable official evidence** and new broad-universe discovery, not another identical Deep pass. `001316` lacks official-evidence closure for long-term demand/moat/predictability and a reviewed PEER mapping; `603993` predictability remains UNKNOWN despite other verified gates. These are research targets, **not** gate promotions.
- `603105` is a separate secondary research lead with missing evidence and price near the previous research ceiling; current date/price/filing must be revalidated before any actionable judgment.
- Historical `data/production_status/latest.json` is older than the latest persisted Decision Center and has code drift; do not treat its dated health summary as fresh canonical authorization.

## Blockers
- No user login/approval blocker identified for independent official-source research and repository checks.
- The existing canonical source for Finalizer `35951027897` is stale and cannot be used for new Formal action. Current, compatible upstream data is a prerequisite, not a reason to disable freshness checks.

## Next Action
1. Consume this checkpoint PR's exact-head CI and merge only when green; use `[skip ci]` squash title for this **docs-only** PR as recovery protocol requires. Then verify live main and checkpoint `TASK_STATE.md` merge; do not launch duplicate production research solely for the documentation update.
2. Continue distinct **candidate-quality** work: read current discovery/terminal artifacts and supported official filings; identify real *new* evidence and its publication date/lineage. Begin with high-attention unresolved evidence (`001316` plus appropriate comparison set), and widen candidate discovery outside exhausted 15-object epochs. Missing official support stays UNKNOWN.
3. Only a genuinely changed compatible evidence/workset epoch may justify subsequent bounded deterministic research dispatch; reconcile the strategy ledger first, then track any new downstream artifacts/Decision Center to terminal.
4. Re-check live main, open mission PRs and current data after any runtime state advance. Keep the volatile recovery state task-scoped, CAS-fenced and aligned to live GitHub.

## Do Not Repeat
- Never reopen #299/#300/#301, duplicate Deep `35934671719`, or replay Jev `35950900132` merely for freshness.
- Do not treat successful explicit Deep-continuation, merge-push Jev, or PR-head Jev as proof of natural changed-state handoff; it is separately verified here.
- No old-snapshot Finalizer retries that override `STALE_UPSTREAM`, no unsupported evidence/peer promotion, no zero-signal DORMANT loops.
- Do not lower hard gates, strategy novelty restrictions, valuation thresholds or research eligibility to manufacture recommendations.

## Guardrails
- Jev: **SHADOW / ADVISORY_ONLY**. Deterministic code owns evidence epochs, numerical validation and bounded research dispatch.
- Formal decisions: **FINALIZED_CANONICAL_ONLY**; `formal_trading_authority=false`, `formal_buy_authorized=false`, `automatic_execution_allowed=false`, `no_auto_trade=true`, `UNKNOWN != PASS`. Research-only `ENTRY_NOW` / BUY do not authorize transactions.
- Broad Discovery is independent of candidate lifecycle and must remain open to new real evidence and opportunities.
