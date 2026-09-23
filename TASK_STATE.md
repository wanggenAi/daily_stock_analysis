# Current Mission

## Goal
Maintain a trustworthy stock-research pipeline that produces current, evidence-backed candidates and actionable research-layer entry guidance without granting Formal or automatic trading authority.

## Current Phase
DORMANT_PRIORITY_SUPPRESSION_IMPLEMENTED_AWAITING_PR_CI

## Source of Truth
- Live GitHub main/PR/Actions/artifacts and persisted production data override this checkpoint.
- Recovery precedence: live refs/Actions/artifacts/persisted data > orchestration cursor > this file > chat history.

## Last Verified Main
- Live main before this branch: `0386d2ee390efc0656fbb2f1e2521c6e54922435`.
- PR #299 merge-push CI `35896490937` is now fully SUCCESS; the prior checkpoint's running-CI note is obsolete.
- Jev current-lineage entry milestone remains production-accepted; do not replay it.

## Active Branch / PR
- Active branch: `fix/dormant-research-priority-20260924`.
- Active PR: not yet opened at this checkpoint.
- Branch starts exactly from live main `0386d2ee390efc0656fbb2f1e2521c6e54922435`.

## Current Production State
- Candidate lifecycle: 126 durable candidates = 123 ACTIVE + 3 DORMANT.
- DORMANT candidates proven by the current deterministic research-strategy ledger:
  - `600816 建元信托`: all 5 supported unresolved hard-gate strategies EXHAUSTED_NO_PROGRESS.
  - `601020 华钰矿业`: all 5 supported unresolved hard-gate strategies EXHAUSTED_NO_PROGRESS.
  - `000504 南华生物`: all 5 supported unresolved hard-gate strategies EXHAUSTED_NO_PROGRESS.
- Strategy ledger: 164 entries = 104 DISPATCH_ACCEPTED, 3 COMPLETED_GATE_RESOLVED, 37 COMPLETED_EVIDENCE_CHANGED, 20 EXHAUSTED_NO_PROGRESS.
- `000096` has 4 exhausted gates and `603105` has 1; neither is fully exhausted, so neither may be auto-dormanted.
- Broad Discovery remains independent from lifecycle and must stay active.

## Problem Found
- DORMANT lifecycle semantics were correct, but `research_priority_router.py` only removed stale research-tier points.
- DORMANT names could still receive priority from price-only attractiveness, generic hourly `RAISE`, mapping gaps, or stale near-buy/archetype ordering boosts.
- Production example: `601020 华钰矿业` is DORMANT / WAIT_FOR_NEW_RESEARCH_EVIDENCE, yet latest research priority still showed P3 score 20 from `HOURLY_PRIORITY_RAISE` + mapping noise despite LOW_MATERIALITY_OR_NEUTRAL_EVIDENCE_ONLY.
- This creates unnecessary research/Jev churn and conflicts with the rule that exhausted names reopen only on genuinely new evidence / changed evidence epoch.

## Implemented
- In `research_priority_router.py`, DORMANT non-holdings now suppress non-material priority boosts.
- Suppressed while dormant without a real reactivation signal:
  - price-only attractiveness;
  - generic hourly `deep_review_priority=RAISE`;
  - mapping-gap score;
  - near-buy recovery ordering boost;
  - success-archetype ordering boost;
  - stale research-tier boost (already suppressed previously).
- Genuine research progress remains eligible to re-enter priority:
  - current-holding protection;
  - `NEW_EVIDENCE_REUNDERWRITE_LEAD`;
  - material thesis states: REUNDERWRITE_REQUIRED / WEAKENING / MIXED / STRENGTHENING;
  - current-runtime Deep 5/5 hard-gate PASS.
- Added regression proving a DORMANT candidate with price-only attractiveness + generic RAISE + mapping gap stays score 0 / P3 and exposes a suppression reason.
- Existing regression proving explicit new evidence can re-enter priority remains intact.
- Updated `docs/CHANGELOG.md`.
- No BUY/WAIT_PRICE/REJECT threshold, hard-gate threshold, Formal authority, Jev authority, or automatic execution rule changed.

## TypeSafe / Jev
- No new Jev call has been made for this code-fix stage; this is deterministic research-priority control.
- Existing current-lineage Jev run remains `35896676405` for Deep `35891640120`.
- After merge, Research Learning is path-triggered by `research_priority_router.py`; its persisted `data/research_priority/**` update naturally wakes the existing Jev Shadow workflow.
- Production acceptance must verify the next natural priority/Jev cycle does not keep same-epoch DORMANT names artificially elevated.
- Jev remains advisory-only; deterministic orchestration and strategy-ledger evidence epochs control actual Deep dispatch.

## Blockers
- Awaiting PR CI and post-merge production verification.
- No user/login/approval blocker.

## Next Action
1. Open PR from `fix/dormant-research-priority-20260924` to main.
2. Run/inspect blocking CI; fix only real failures.
3. Merge only after blocking CI passes.
4. Verify push-triggered Research Learning rebuilds research priority.
5. Verify DORMANT same-epoch names no longer receive non-material priority boosts.
6. If a new Jev shadow is naturally triggered by the priority persistence, record the actual TypeSafe/Jev run and confirm deterministic orchestration does not redispatch exhausted same-epoch work.
7. Refresh Three-Pillar/decision state only through existing production chain; do not rerun accepted 603596 lineage for freshness alone.
8. Then continue broader candidate-quality convergence from the next live checkpoint.

## Do Not Repeat
- Do not reopen #292/#293/#294 or merge stale #296/#298.
- Do not replay #299; it is merged and production-accepted.
- Do not duplicate Jev for Deep `35891640120` merely to make it newer.
- Do not lower Jev, hard-gate, research-selection, valuation, BUY/WAIT_PRICE/REJECT thresholds.
- Do not treat UNKNOWN as PASS.
- Do not promote Research BUY / BUILD / Jev ENTRY_NOW into Canonical Formal BUY.

## Guardrails
- Broad Discovery is never filtered by lifecycle.
- DORMANT is research-control state only and is never a Formal rejection.
- Jev authority: ADVISORY_ONLY research routing + structured entry judgment.
- Deterministic code owns evidence epochs, eligibility, dispatch, dedupe, numeric validation, and authority boundaries.
- Formal actions remain Canonical-only; `formal_buy_authorized=false`.
- `automatic_execution_allowed=false`; `no_auto_trade=true`.
