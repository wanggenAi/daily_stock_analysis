# Current Mission

## Goal
Maintain a trustworthy stock-research pipeline that produces current, evidence-backed candidates and actionable research-layer entry guidance without granting Formal or automatic trading authority.

## Current Phase
DORMANT_PRIORITY_FIX_MERGED_AWAITING_PRODUCTION_VERIFICATION

## Last Verified Main
- PR #300 squash-merged as `0713f3c242bef7e990fbed6fc1183c04d263b0f4`.
- Live GitHub refs / Actions / persisted data always override this checkpoint.
- PR #299 / 603596 current-lineage Jev milestone remains production-accepted and must not be replayed for freshness alone.

## Active Branch
- None required after #300 merge.

## Active PR
- None for the current mission. PR #300 is merged.

## CI
- PR #300 final head `b51350913bcbdbdf104940c0437dfd08170e69f0`.
- CI `35902995467`: SUCCESS (ai-governance, backend-gate, docker-build; web-gate skipped).
- Jev Research Orchestrator contracts `35902995447`: SUCCESS; includes dormant-exhaustion regression coverage.
- Opportunity Discovery `35902995418`: SUCCESS.
- Legacy Risk-Capped `35902995465`: SUCCESS.
- Near-BUY Evidence Recovery `35902995427`: SUCCESS.
- Success Archetype Recall `35902995426`: SUCCESS.
- Merge-push CI `35904993413` is still running at this checkpoint.

## Production / Artifact
- Candidate lifecycle before post-merge rebuild: 126 = 123 ACTIVE + 3 DORMANT.
- Current DORMANT names: `600816 建元信托`, `601020 华钰矿业`, `000504 南华生物`.
- Deterministic strategy ledger proves all 5 supported unresolved hard-gate strategies exhausted for each in its prior evidence epoch.
- Latest pre-merge priority now shows:
  - `000504`: NEW_EVIDENCE_REUNDERWRITE_LEAD / WEAKENING_RESEARCH_SIGNAL, score 65 — genuine new material evidence; re-entry is allowed.
  - `600816`: NEW_EVIDENCE_REUNDERWRITE_LEAD / WEAKENING_RESEARCH_SIGNAL, score 65 — genuine new material evidence; re-entry is allowed.
  - `601020`: LOW_MATERIALITY_OR_NEUTRAL_EVIDENCE_ONLY, score 20 only from generic hourly RAISE + mapping noise — this is the production counterexample #300 fixes.
- Merge-triggered Research Learning `35904993386` is running and must persist the first post-fix priority proof.
- Broad Discovery remains independent from lifecycle.

## Completed
- Identified downstream priority leakage rather than changing lifecycle exhaustion semantics.
- #300 suppresses price-only, generic hourly RAISE, mapping-gap, near-buy recovery and success-archetype ordering boosts for DORMANT non-holdings without real reactivation evidence.
- Genuine material evidence, current-holding protection and current-runtime Deep 5/5 PASS remain eligible to regain research priority.
- Regression, governance, backend, Docker, discovery and research-adjacent CI all passed.
- #300 merged without changing hard gates, valuation, BUY/WAIT_PRICE/REJECT, Jev authority, Formal authority or execution permission.

## Current Findings
- DORMANT is not a permanent blacklist: 000504 and 600816 already demonstrate legitimate material-evidence re-entry signals.
- 601020 is the clean stale-noise control case and should become score 0 / P3 after post-merge Research Learning.
- A naturally persisted research-priority update should wake Jev Shadow through the existing `data/research_priority/**` push path.
- Jev may classify/reroute the refreshed queue, but deterministic strategy ledger must prevent same-evidence-epoch exhausted work from being redispatched.

## Blockers
- Awaiting post-merge Research Learning persistence and resulting Jev/orchestration convergence.
- No user/login/approval blocker.

## Next Action
1. Observe Research Learning `35904993386` to SUCCESS and identify its persistence commit.
2. Verify post-fix research_priority: 601020 score=0 with dormant suppression reason; 000504/600816 remain eligible only because of genuine material evidence.
3. Observe the naturally triggered TypeSafe/Jev shadow run from the priority persistence; record actual live Jev usage.
4. Verify deterministic orchestration does not redispatch same-epoch exhausted work; any redispatch must be backed by a changed evidence epoch / schedulable strategy.
5. Verify downstream Decision Center/Three-Pillar remains fail-closed and no Formal/auto-trade authority changes.
6. Then continue broader candidate-quality convergence from live state.

## Do Not Repeat
- Do not reopen #300 or replay #299.
- Do not duplicate Jev for Deep `35891640120` merely to make it newer.
- Do not lower hard-gate, research-selection, valuation, BUY/WAIT_PRICE/REJECT or Jev thresholds.
- Do not treat UNKNOWN as PASS.
- Do not convert DORMANT into Formal REJECT.
- Do not promote Research BUY / BUILD / Jev ENTRY_NOW into Canonical Formal BUY.

## Guardrails
- Broad Discovery is never filtered by lifecycle.
- DORMANT is research-control state only.
- Jev is ADVISORY_ONLY; deterministic code owns evidence epochs, eligibility, dispatch, dedupe, numeric validation and authority boundaries.
- Formal actions remain Canonical-only; `formal_buy_authorized=false`.
- `automatic_execution_allowed=false`; `no_auto_trade=true`.
