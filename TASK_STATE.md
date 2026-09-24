# Current Mission

## Goal
Produce trustworthy, current, evidence-backed stock-research candidates and research-only entry guidance without granting Formal or automatic trading authority.

## Current Phase
DORMANT_PRIORITY_PRODUCTION_VERIFIED_JEV_HANDOFF_PR301_AWAITING_CI

## Last Verified Main
- Live main at verification: `d618190132b2ab70731d5c3809c34ac89ea58788`. Always re-read live GitHub refs.
- PR #300 merged as `0713f3c242bef7e990fbed6fc1183c04d263b0f4`; do not replay #299/#300.

## Active Branch
- `fix/learning-jev-explicit-handoff-20260924`, based on live main above.

## Active PR
- #301: `fix: dispatch Jev after research learning persistence`.
- PR #301 changes only the Research Learning workflow handoff, a workflow contract test and documentation/checkpoint. No selection or authority logic changes.

## CI
- PR #300 CI `35902995467`: SUCCESS. Merge-push CI `35904993413`: SUCCESS.
- Post-merge Research Learning `35904993386`: SUCCESS; persisted `22a185875a9c3b3d2e7a72688945fee851334c13`; verified from the live job log.
- #301 CI: pending at this checkpoint; re-read exact PR head and checks.

## Production / Artifact
- Latest priority at verification: `data/research_priority/latest.json` generated `2026-09-23T23:41:13Z`, queue=126, P0=4, P1=3.
- DORMANT `601020`: score=0/P3, `RESEARCH_DORMANT_NON_MATERIAL_SIGNALS_SUPPRESSED`. DORMANT `000504` and `600816`: score=65/P1 via evidence-reactivation/re-underwrite signals; neither is a Formal BUY.
- Latest Jev shadow `35935194769`: SUCCESS; 25/25 live TypeSafe/Jev calls served by `jev-1.13.0`; source event `workflow_dispatch` and Deep continuation `35934671719`. This is NOT proof of the Research Learning natural priority-push trigger.
- Latest deterministic orchestration `35935372930`: no new Deep/evidence-refresh dispatch; 24 skipped (same-epoch/no deterministic eligibility/low attention), 1 valuation closure (603596).
- Latest Decision Center `data/decision_center/latest.json` generated `2026-09-23T23:56:02Z`; no_auto_trade=true, formal action source FINALIZED_CANONICAL_ONLY, formal_action_recomputed=false. The latest Deep runtime `35934671719` is EVIDENCE_EXHAUSTED for 15 requested objects; no speculative UNKNOWN promotion.
- Latest terminal research decisions: 16 terminal rows, 1 research BUY (603596), 15 RESEARCH_GAP. These are research-only and may be stale relative to newer market data.

## Completed
- Verified post-merge dormant suppression from live persisted priority and Research Learning log; the original dormant-priority fix is production-proven.
- Verified real Jev advisory invocation, deterministic same-epoch no-redispatch, and downstream Decision Center fail-closed on the newest persisted lineage.
- Identified an unproven automatic handoff: a Research Learning persistence push uses GITHUB_TOKEN, which does not trigger a downstream push workflow. The later observed Jev invocation came from explicit Deep continuation.
- Created #301 to explicitly dispatch existing Jev shadow only after changed Research Learning state was successfully pushed, with regression test and docs.

## Current Findings
- #301 preserves the independent `data/research_priority/**` push trigger for non-GITHUB_TOKEN updates; workflow_dispatch bridges GitHub Actions persistence updates.
- Existing hard-gate strategy ledger remains the dispatch authority and prevents exhausted same-evidence-epoch work.
- Candidate quality is the next distinct workstream: latest 16 terminal research objects contain one research BUY but 15 evidence gaps, so prioritize genuinely new official evidence and broader candidate discovery rather than replaying exhausted work.

## Blockers
- #301 exact-head CI/merge and first post-merge *changed-state* Research Learning -> Jev dispatch must be observed.
- No known user/login/approval blocker at this checkpoint.

## Next Action
1. Confirm PR #301 CI and exact head, then merge only if green and mergeable; re-read live main after merge.
2. Observe the natural merge-triggered Research Learning rebuild when it occurs. Inspect actual successful persistence and the resulting explicit Jev workflow_dispatch; verify 25 real TypeSafe/Jev calls and persisted advisory routing or record the exact blocker. Do not fabricate a natural run from the unrelated Deep continuation.
3. Verify deterministic orchestration still suppresses same evidence epoch and downstream Decision Center/Three-Pillar stays fail-closed.
4. Persist the final production checkpoint to TASK_STATE after verification. If no changed priority was persisted, mark the handoff not-yet-live-verified and use the next real changed-state event.
5. Continue candidate-quality convergence from current Broad Discovery and evidence-mapping gaps, prioritizing verifiable official evidence and novelty over zero-signal retries.

## Do Not Repeat
- Do not reopen #300, replay #299, duplicate Deep `35891640120` for freshness, rerun V3.1.1 repair or recycle stale branches.
- Do not treat a successful explicit Deep-continuation Jev run as proof of priority-persistence automatic handoff.
- Do not issue duplicate Deep requests for exhausted same-epoch strategies.
- Do not lower hard gates, valuation or BUY/WAIT_PRICE/REJECT thresholds or turn DORMANT into Formal REJECT.

## Guardrails
- Broad Discovery is independent of lifecycle.
- Jev remains SHADOW/ADVISORY_ONLY; deterministic code owns evidence epochs, eligibility, dispatch and numeric validation.
- Formal actions are Canonical-only; `formal_trading_authority=false`, `formal_buy_authorized=false`, `automatic_execution_allowed=false`, `no_auto_trade=true`; UNKNOWN != PASS.
