# Current Mission

## Goal
Deliver trustworthy, up-to-date, official-evidence-backed A-share research candidates and research-only entry/exit guidance. Preserve deterministic quality gates and **zero Formal or automatic trading authorization**.

## Current Phase
`PR303_POSTMERGE_VERIFIED_WAIT_GENUINE_20260924_ALL_A_EVIDENCE_EPOCH`

## Last Verified Main
- Immediately before this docs checkpoint: `acb16668882db622bc9d21eee20c91f9faa6715c` (2026-09-24 04:36:32Z+). **Always re-read live main**: runtime [skip ci] persistence advances this ref.
- PR #303 normal squash merge: `524da0bf39d7eaf0fbde745de821aa5ca19cafda`, 2026-09-24 04:20:14Z; exact PR head `22a32553f4e57c713f15657414879763b5614dc1`.
- #299/#300/#301/#302/#303 completed or merged and **consumed**. #302 docs-only merge `c3c751b5bc9428f2c13bc3a0975d1ea1a2fb1350`; do not treat #302/#303 merge SHAs as live main.

## Active Branch
- This one-file `TASK_STATE.md` checkpoint branch is docs-only: `docs/stock-pr303-postmerge-verified-checkpoint-20260924`.
- An *unchanged*, unmerged investigation branch `fix/deep-trigger-skip-cache-only-20260924` was created to isolate a workflow guard; **no code changes or PR** were made. Workflow write was blocked by tool safety checks; follow-up documented in merged PR #303 comment 5807747928.

## Active PR
- #304 is the current docs-only checkpoint. No open *business* PR for this mission; other old open repository PRs are unrelated unless live evidence proves otherwise.
- Volatile task cursor: `state/chatgpt-recovery:recovery/tasks/stock-system-convergence.json`. Audit sidecar: `recovery/research/stock-candidate-quality-baseline-20260924.json` on the same recovery branch. The **latest live** CAS generation, branch and artifacts override this stable handoff.
## CI
- PR #303 exact-head CI `35953529795`: **SUCCESS**; companion Opportunity fixture `35953529804`, Legacy tests `35953529751`, Review `35953529921`: SUCCESS where expected. Fixture jobs are **not** production scans.
- PR #303 **normal non-[skip ci]** squash merge `524da0bf`; exact merge-push CI `35955214939`: **SUCCESS** at 2026-09-24 04:36:32Z. Backend offline tests, governance, Docker and change detection passed; Web gate expected skipped. Offline pytest diagnostics artifact `10790721519`.
- Merge-push Opportunity fixture `35955215040`: SUCCESS; **All-A production job was skipped**. No 2026-09-24 genuine broad-scan success claimed.

## Production / Artifact
- Distinct, real All-A `35937745622` artifact `10784936699`, **market as-of 2026-09-23**: official universe 5,222; effective 4,515 (full price coverage); 80 deep reviewed; **0 strict-ready**, 79/80 company-evidence gate failures, 80/80 exit-profile failures. Its 98/98 automatic evidence tasks were cache hits, **zero actual fetches**, 94 audit rows (30 OK, 51 MISSING, 13 FAILED). Original exit history 168/168 covered yet zero validated exit cohorts: `NO_VALIDATED_EXIT_EDGE` is a strategy-validation blocker, not simply a missing fetch.
- Independent broad discovery has 751 research-only rows across 83 industries; e.g. `603105` was rank 90, outside the Top80 evidence queue, **not** a qualified BUY. The 80-deep / ~30 official-company-collection default scope must be measured on the next genuine epoch before safely expanding expensive evidence collection.
- PR #303 only changes `EvidenceCache` negative-cache TTL: FAILED to 6h, MISSING to 24h; successful cached evidence TTL unchanged. **Cache fix merged and CI validated; genuine next-epoch effectiveness not yet proven**.
- Post-#303 evidence-code push auto-trigger `35955215076` dispatched Deep `35955222216`: SUCCESS; provenance audit `35955570041`, terminal `35955571857` SUCCESS. However Deep resolved **the identical exhausted upstream Every-Industry run `35886039426`** already consumed by old Deep `35934671719`. Direct old/new persisted evidence comparison: **same 23 company + 14 industry rows** and same 152 audit identities/status counts (114 MISSING/22 OK/16 FAILED); both 15/15 EVIDENCE_EXHAUSTED, 64 unresolved, 3 per-run progressed gates. The per-run `new_evidence_count=37` represents collected rows, **zero net-new verified issuer/industry rows versus the old epoch**. Never replay this source or promote its gates.
- Actual TypeSafe/Jev post-Deep shadow `35955691559`: **25/25 successful calls, all served by `jev-1.13.0`**. Advisory routes: 12 DEEP_RESEARCH, 12 EVIDENCE_REFRESH, 1 VALUATION_CLOSURE. Deterministic orchestrator `35955845032` and reconciler `35955921104` succeeded; 24 exhausted/ineligible same-epoch research routes not redispatched and one existing **research-only** valuation closure. Jev cannot set Formal actions.
- Latest checked Three-Pillar generated 2026-09-24 04:35:51Z for **trade date 2026-09-23**: four holdings still partial Deep (0/4 complete); 0 new formal BUY, one **research-only** BUY (`603596`) plus 15 RESEARCH_GAP. Formal authorizations remain absent.
- Source triage: `001316` 2026-08-24 original SZSE withdrawal of planned convertible financing needs future funding/materiality follow-up, **not** moat/demand PASS. 2026-09-24 proposed restricted stock cancellation needs original source/shareholder result. `603993` Sep19 TAZARA joint-venture guarantee reported in designated China Securities Journal; original SSE full PDF remained inaccessible, and predictability stays UNKNOWN. No primary-file lineage/materiality-based promotions.

## Completed
- Consumed and merged #303 after exact-head green CI; confirmed exact merge-sha push CI and successful fixture while distinguishing skipped full-A production.
- Downloaded/audited actual preceding All-A artifact and preserved independent quantitative baseline in the task-scoped recovery sidecar.
- Consumed actual auto-trigger Deep, authoritative persisted source IDs, provenance, terminal, 25 real TypeSafe/Jev calls, deterministic orchestration, and current Decision Center; proved old/new Deep evidence identical despite per-run `new_evidence_count`.
- Documented cache-only collector-change triggering exhausted duplicate Deep in PR #303 comment 5807747928. No bypass of blocked workflow write. No speculative new evidence or trading authority.

## Current Findings
- Candidate quality depends on verified *new* official filings and exit-strategy independent validation, not replayed same-upstream evidence. The 30-versus-80 evidence coverage cap is bounded by code and should be measured before any safe capacity change.

## Blockers
- Next completed-market 2026-09-24 All-A production artifact is not available before its scheduled 18:30 China run. No authentication/approval blocker for continued read-only verification.
- Protected-workflow write was blocked by tool safety checks; this remains an explicitly documented later maintenance action, not an applied code fix.

## Next Action
1. **Actual future data gate**: `.github/workflows/genge-opportunity-discovery.yml` runs genuine weekday All-A production at `10:30 UTC = 18:30 Asia/Shanghai`. After the completed **2026-09-24** market close, locate the next *scheduled* real production job, check its source/head/trade epoch and artifact. As of this checkpoint, this market/evidence epoch was **not yet available**. Do not confuse push fixture, code-change Deep or an old cached result for it.
2. In that genuine new artifact, compare `EvidenceCache` actual network fetches and issuer report dates versus previous 98/98 cache hits and zero actual fetches. Evaluate official primary PDF content, time validity, scope, counter-evidence and materiality for `001316`, `603993` and diversified 751-row discovery; surface evidence gaps honestly. `NO_VALIDATED_EXIT_EDGE` persists until genuinely validated independent strategy cohorts emerge.
3. Before any new automated Deep/TypeSafe dispatch, reconcile **new** compatible upstream research/evidence fingerprint with strategy ledger; old upstream `35886039426` and Deep `35934671719` / `35955222216` are consumed. Fix erroneous **cache-only** workflow-trigger replay only through a properly authorized, tested and exact-head green workflow PR; proposed path exclusion + tests are recorded in PR #303 comment.
4. This docs-only checkpoint PR itself must pass exact-head required checks, then may merge with `[skip ci]` as recovery-only integration; no synthetic production trigger. Re-read live main and latest volatile cursor afterward.

## Do Not Repeat
- No duplicate #299-#303 business PRs, no repeated same-epoch Deep or Jev and no skipped-fixture promoted to production.

## Guardrails
- Formal decisions only from current finalized compatible canonical state; stale input must fail closed. **`formal_trading_authority=false`, `formal_buy_authorized=false`, `automatic_execution_allowed=false`, `no_auto_trade=true`, `UNKNOWN != PASS`**.
- Jev remains `SHADOW / ADVISORY_ONLY`; deterministic code owns evidence epochs, arithmetic, thresholds and bounded research dispatch. A research `BUY` is never execution authorization.
