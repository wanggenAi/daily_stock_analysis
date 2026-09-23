# Current Mission

## Goal
Maintain a trustworthy stock-research pipeline that produces current, evidence-backed candidates and actionable research-layer entry guidance without granting Formal or automatic trading authority.

## Current Phase
JEV_ENTRY_JUDGMENT_PRODUCTION_ACCEPTED

## Source of Truth
- Live GitHub main/PR/Actions/artifacts and persisted production data override this checkpoint.
- Recovery precedence remains: live refs/Actions/artifacts/persisted data > orchestration cursor > recovery checkpoint > this file > chat history.

## Last Verified Main
- Business/runtime fix merged through PR #299 as `81c005ea8413073f0c2d5d78884eafacd7dce1b7`.
- Last verified production decision-center persistence before this checkpoint: `d439c52f65077eb7c379f18712f4a8a6ea50191b`.
- Production persistence may move main after this checkpoint; always re-read live main before any new mutation.

## Active Branch / PR
- No active feature branch for this milestone.
- PR #299 `fix: replay post-terminal Jev refresh on current main`: MERGED.
- #298 is superseded and must not be merged.

## CI
- #299 newest-head CI passed before merge:
  - CI `35893424341`: SUCCESS
  - Opportunity Discovery `35893424343`: SUCCESS
  - Legacy Risk-Capped Research `35893424311`: SUCCESS
- Merge-push CI `35896490937`: ai-governance SUCCESS, docker-build SUCCESS; backend offline suite was still running at this checkpoint.
- No failure requiring rollback has been observed.

## Production Acceptance
- Merge-triggered Terminal run `35896490998`: SUCCESS.
- Terminal persisted exact current Deep lineage `35891640120`.
- New post-Terminal wake step executed successfully.
- Exact lineage-keyed Jev V4 run `35896676405` (`GenGe Jev Shadow Evaluation / 35891640120`): SUCCESS.
- Pinned TypeSafe SDK contract checks: SUCCESS.
- Live Jev shadow evaluation: SUCCESS.
- Routing bridge + persisted advisory: SUCCESS.
- Artifact: `genge-jev-shadow-35896676405-1`, artifact id `10766888595`, digest `sha256:e26320b9eb174576a44a70da53ee53ad333e55b2a343f057a876dbbd440d0bb4`.
- Routing persistence commit: `a207391703b79bea52f6c35e7fa8cbea4d8df219`.
- Deterministic Jev Research Orchestrator `35896896445`: SUCCESS.
- Three-Pillar Decision Center `35896895126`: SUCCESS and persisted current-lineage Jev entry judgment.
- Follow-up valuation-closure Terminal `35897118130`: SUCCESS.
- Same Deep lineage dedupe verified: only one Jev run exists with title `GenGe Jev Shadow Evaluation / 35891640120`; repeated Terminal convergence did not create a duplicate Jev run.
- Reconciler `35897320012`: SUCCESS at this checkpoint.

## Current Jev Routing
- source_workflow_run_id: `35896676405`
- continuation_from_deep_run_id: `35891640120`
- routing_count: 25
- entry judgments: ENTRY_NOW=1, WAIT_EVIDENCE=24
- routes: DEEP_RESEARCH=12, EVIDENCE_REFRESH=12, VALUATION_CLOSURE=1
- Weak/incomplete candidates are not promoted by UNKNOWN; UNKNOWN != PASS remains enforced.

## 603596 伯特利 — Accepted Current Research Case
- Current lineage: Deep `35891640120` -> Jev `35896676405`.
- Hard gates: 5/5 PASS; no FAIL; no UNKNOWN.
- Terminal research decision: BUY.
- Jev validated judgment: ENTRY_NOW.
- Jev judgment confidence: 0.76; ENTRY_NOW probability: 0.80.
- Deterministic validation: `JEV_ENTRY_NOW_PASSES_DETERMINISTIC_GUARDS`.
- Reference price: 28.72, trade date 2026-09-23, basis `RAW_LATEST_CLOSE`.
- Research buy ceiling / entry zone high: 43.072.
- Initial manual research position: 1%.
- Maximum manual research position: 3%.
- Add condition: `REVALIDATE_5_OF_5_PASS_AND_TERMINAL_BUY_WITH_PRICE_AT_OR_BELOW_CEILING`.
- Do-not-chase condition: `PRICE_ABOVE_43.0720_REQUIRES_REVALUATION`.
- Invalidation: `ANY_HARD_GATE_FAIL_OR_UNKNOWN_OR_STALE_LINEAGE_INVALIDATES_ENTRY`.
- Capital layer: BUILD, conviction 0.8954, advisory max 3%.
- Formal BUY: false.
- automatic_execution_allowed: false.
- no_auto_trade: true.
- Decision Center user-facing action is research/manual-build advisory only, not an executable order.

## Completed
- Structured Jev entry judgment implementation is live.
- The stale-lineage gap was fixed by waking one exact-lineage Jev V4 run after Terminal convergence.
- Current-lineage Jev routing is persisted and consumed by deterministic orchestration.
- Current 603596 entry guidance is visible in the final Three-Pillar Decision Center.
- Repeated Terminal convergence is deduplicated against the same Deep lineage.
- No stale Jev row is promoted as current.

## Current Findings
- The system now has one defensible current entry candidate rather than forcing broad BUY output.
- 24/25 Jev rows remain WAIT_EVIDENCE, which is intentional under the evidence/hard-gate contract.
- 603596 is the current leading research-layer candidate; its result is based on the 2026-09-23 persisted reference close, not a promise about a future/live market price.
- The remaining project problem is broader candidate-quality convergence: distinguish evidence-exhausted names that should be retired/archived from names worth reopening only when genuinely new evidence appears.

## Blockers
- No user/login/approval blocker.
- No production acceptance blocker for the Jev current-lineage entry milestone.
- Tail CI/overlay/decision-center refresh jobs may still be finishing; consume live Actions state rather than restarting the chain.

## Next Action
1. Re-read live main, Actions, latest routing/orchestration, and Decision Center.
2. Finish/inspect any remaining tail CI only if still active; fix only real failures.
3. Do not rerun the accepted 603596 lineage merely to make it newer.
4. Continue the broader stock-selection objective:
   - classify persistent WAIT_EVIDENCE / exhausted candidates;
   - archive or remove candidates when credible evidence cannot be obtained after bounded attempts;
   - reopen only on genuinely new evidence or a changed evidence epoch;
   - keep broad discovery active so new candidates can enter;
   - preserve thresholds instead of lowering them to manufacture BUY signals.
5. Report leading candidates with buy-now-or-not research status, verified trigger/price basis, initial size, add condition, max size, do-not-chase, and invalidation.

## Do Not Repeat
- Do not reopen #292/#293/#294 or merge stale #296/#298.
- Do not replay #299 again; it is merged and production-accepted.
- Do not duplicate Jev for Deep `35891640120`; run `35896676405` is the accepted exact-lineage evaluation.
- Do not reuse historical 29.15 / 2026-09-22 as current 603596 price truth; accepted reference is 28.72 / 2026-09-23 until a newer verified snapshot replaces it.
- Do not lower Jev, hard-gate, research-selection, or valuation thresholds to force more candidates.
- Do not treat UNKNOWN as PASS.
- Do not promote Research BUY / BUILD / Jev ENTRY_NOW into Canonical Formal BUY.

## Guardrails
- Jev authority: ADVISORY_ONLY research routing + structured entry judgment.
- Deterministic code owns eligibility, lineage, numeric price/sizing validation, dispatch, dedupe, and authority boundaries.
- Formal actions remain Canonical-only; `formal_buy_authorized=false`.
- `automatic_execution_allowed=false`; `no_auto_trade=true`.
- Risk-budget sizing caps Jev suggestions.
- Missing verified inputs produce WAIT_EVIDENCE / explicit unlock conditions, never invented numbers.
