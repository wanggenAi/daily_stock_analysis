# Current Mission

## Goal
Maintain a trustworthy stock-research pipeline that produces current, evidence-backed candidates and actionable research-layer entry guidance without granting Formal or automatic trading authority.

## Current Phase
DORMANT_PRIORITY_SUPPRESSION_IMPLEMENTED_AWAITING_PR_CI

## Last Verified Main
- Live main before this branch: `0386d2ee390efc0656fbb2f1e2521c6e54922435`.
- PR #299 merge-push CI `35896490937` is fully SUCCESS.
- Jev current-lineage entry milestone remains production-accepted; do not replay it.
- Live GitHub refs / Actions / persisted data always override this checkpoint.

## Active Branch
- `fix/dormant-research-priority-20260924`, created exactly from `0386d2ee390efc0656fbb2f1e2521c6e54922435`.

## Active PR
- PR #300: `fix: suppress stale dormant research priority boosts`.
- First CI attempt exposed a checkpoint-format failure only; business tests had not run yet.

## CI
- PR #300 first CI `35902840729`: FAILED at ai-governance because this checkpoint used combined headings instead of the required exact headings.
- Root cause: `scripts/check_ai_assets.py` requires separate `## Active Branch`, `## Active PR`, `## CI`, `## Production / Artifact`, `## Completed`, and `## Current Findings`.
- This checkpoint fixes that governance-format error; next PR CI must be consumed before merge.
- Dedicated Jev Research Orchestrator contract workflow also runs `tests/test_research_exhaustion_dormancy.py`.

## Production / Artifact
- Candidate lifecycle: 126 durable candidates = 123 ACTIVE + 3 DORMANT.
- DORMANT: `600816 建元信托`, `601020 华钰矿业`, `000504 南华生物`; each has all 5 supported unresolved hard-gate strategies at `EXHAUSTED_NO_PROGRESS` in the current evidence epoch.
- Strategy ledger: 164 entries = 104 DISPATCH_ACCEPTED, 3 COMPLETED_GATE_RESOLVED, 37 COMPLETED_EVIDENCE_CHANGED, 20 EXHAUSTED_NO_PROGRESS.
- `000096` has 4 exhausted gates and `603105` has 1; neither is fully exhausted and neither may be auto-dormanted.
- Broad Discovery remains independent from lifecycle.

## Completed
- Re-read live main, AGENTS.md, TASK_STATE.md, open PRs, latest Actions, persisted lifecycle, strategy ledger, Jev routing and Decision Center.
- Confirmed the prior 603596 / Jev current-lineage milestone is complete and did not replay it.
- Identified the next real gap: DORMANT candidates could still receive non-material priority boosts.
- Patched `research_priority_router.py` so DORMANT non-holdings suppress stale/non-material ordering boosts.
- Added regression coverage in `tests/test_research_exhaustion_dormancy.py`.
- Updated `docs/CHANGELOG.md`.
- Opened PR #300.

## Current Findings
- Lifecycle dormancy itself is correct; the defect is downstream priority leakage.
- Production example: `601020 华钰矿业` is DORMANT / WAIT_FOR_NEW_RESEARCH_EVIDENCE but latest priority still showed P3 score 20 from generic `HOURLY_PRIORITY_RAISE` plus mapping noise under LOW_MATERIALITY_OR_NEUTRAL_EVIDENCE_ONLY.
- Suppressed while DORMANT without a real reactivation signal: price-only attractiveness, generic hourly RAISE, mapping-gap score, near-buy recovery ordering boost, success-archetype ordering boost, stale research-tier boost.
- Still allowed to regain research priority: current-holding protection, `NEW_EVIDENCE_REUNDERWRITE_LEAD`, material REUNDERWRITE_REQUIRED / WEAKENING / MIXED / STRENGTHENING evidence, or current-runtime Deep 5/5 PASS.
- No hard-gate, valuation, BUY/WAIT_PRICE/REJECT, Jev, Formal, or execution threshold changed.
- No new Jev call has been made for this deterministic code-fix stage.

## Blockers
- PR #300 must pass blocking CI after the checkpoint-format fix.
- Post-merge production priority/Jev convergence is not yet verified.
- No user/login/approval blocker.

## Next Action
1. Consume the new PR #300 CI after this checkpoint commit.
2. Fix only real failures within the dormant-priority contract.
3. Merge after blocking CI passes.
4. Verify push-triggered Research Learning persists a new research-priority state.
5. Verify same-epoch DORMANT names no longer receive non-material priority boosts.
6. If the priority persistence naturally triggers Jev Shadow, record the actual TypeSafe/Jev run and verify deterministic orchestration does not redispatch exhausted same-epoch work.
7. Continue broader candidate-quality convergence from the next live checkpoint.

## Do Not Repeat
- Do not reopen #292/#293/#294 or merge stale #296/#298.
- Do not replay #299 or duplicate Jev for Deep `35891640120` merely to make it newer.
- Do not rerun accepted 603596 lineage for freshness alone.
- Do not lower Jev, hard-gate, research-selection, valuation, BUY/WAIT_PRICE/REJECT thresholds.
- Do not treat UNKNOWN as PASS.
- Do not promote Research BUY / BUILD / Jev ENTRY_NOW into Canonical Formal BUY.

## Guardrails
- Broad Discovery is never filtered by lifecycle.
- DORMANT is research-control state only, never a Formal rejection.
- Jev is ADVISORY_ONLY; deterministic code owns evidence epochs, eligibility, dispatch, dedupe, numeric validation and authority boundaries.
- Formal actions remain Canonical-only; `formal_buy_authorized=false`.
- `automatic_execution_allowed=false`; `no_auto_trade=true`.
