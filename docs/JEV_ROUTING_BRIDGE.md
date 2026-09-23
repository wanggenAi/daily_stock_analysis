# Jev Research Routing Bridge

This is phase 2 of the TypeSafe AI Jev integration.

The shadow layer answers bounded typed questions. The routing bridge converts those
answers into a durable **advisory research queue** without giving Jev any Formal or
trading authority.

## What it produces

For each successful shadow row, the bridge records:

- research route: NO_ESCALATION / EVIDENCE_REFRESH / DEEP_RESEARCH / VALUATION_CLOSURE / HUMAN_REVIEW;
- attention priority: LOW / MEDIUM / HIGH;
- evidence state;
- needs-more-evidence and needs-deep-research typed judgments;
- served model, state fingerprint, confidence metadata, and full Choice probability distributions for later calibration.

The queue is sorted for operator visibility only.

## Structured entry judgment

The shadow question set also asks Jev for a bounded research entry judgment:
`ENTRY_NOW`, `WAIT_PRICE`, `WAIT_EVIDENCE`, `DO_NOT_CHASE`,
`INVALIDATED`, or `NO_JUDGMENT`.

Jev supplies the categorical judgment and confidence; it does **not** invent an
entry price or position size. The routing bridge deterministically validates the
judgment against the exact current Deep lineage, hard-gate status, Terminal
research decision, verified price mapping, `research_buy_price_ceiling`, and
risk-budget cap.

An `ENTRY_NOW` survives validation only when all five hard gates are explicit
PASS, the current Terminal decision is research BUY, the verified reference
price is at or below the research buy-price ceiling, and a valid advisory
risk-budget cap exists. The initial manual research position is capped at the
smaller of 1% and the validated risk-budget cap. Jev can be more conservative
than the deterministic state, but it cannot escalate a blocked state.

Any hard-gate UNKNOWN/RESEARCH_GAP forces `WAIT_EVIDENCE`; explicit hard-gate
FAIL/REJECT forces `INVALIDATED`; price above the verified ceiling forces at
least `WAIT_PRICE` and may preserve a Jev `DO_NOT_CHASE`; stale lineage,
unverified price mapping, unsupported invalidation, or authority drift becomes
`NO_JUDGMENT`.

Every persisted entry judgment remains `ADVISORY_ONLY` with
`formal_buy_authorized=false`, `automatic_execution_allowed=false`, and
`no_auto_trade=true`. The Three-Pillar report exposes only judgments whose
Deep lineage exactly matches the current runtime.

## Authority boundary

The bridge is deliberately fail-closed:

- automatic_dispatch_allowed=false;
- formal_trading_authority=false;
- mutates_authoritative_decision=false;
- may_suppress_existing_research=false;
- may_create_or_mutate_formal_action=false;
- UNKNOWN != PASS;
- no_auto_trade=true.

A malformed shadow contract, failed shadow execution, or global guardrail drift
produces a refused bridge instead of a usable routing queue.

## Persistence

A successful **GenGe Jev Shadow Evaluation** run from `workflow_dispatch` or a
qualifying `main` push persists:

- data/jev_shadow/latest.json
- data/jev_shadow/latest_routing.json
- JEV_RESEARCH_ROUTING.md

The persistence job owns the write permission. The secret-bearing live PR job remains
`contents: read`; PR smoke runs upload artifacts but never persist them to `main`.

A persisted research-priority change under `data/research_priority/**` is also an
explicit main-branch wake signal for Jev. This matters because Research Learning can
promote an already-qualified candidate into the bounded priority queue without changing
Jev source code. The wake only refreshes the 25-entity advisory evaluation and its
deterministic downstream routing; it does not expand Formal authority, change research
thresholds, or enable automatic trading.

## Automatic research dispatch boundary

The routing bridge itself remains advisory: `automatic_dispatch_allowed=false`.
A separate deterministic research orchestrator may consume the persisted advisory
queue and dispatch the existing bounded Deep research workflow only when deterministic
eligibility and fail-closed guardrails also permit it. Jev never dispatches work
directly, never suppresses deterministic research obligations, and never grants Formal
trading authority.

## Post-Deep valuation and price closure

A candidate whose exact current research state has all five hard gates explicitly PASS and whose research decision is already BUY or WAIT_PRICE has no remaining hard-gate research problem. Jev may select `VALUATION_CLOSURE` for this state. The deterministic orchestrator also recognizes the same state directly, so a low-confidence or stale `DEEP_RESEARCH` advisory cannot force an already-resolved candidate back through Deep or stop it at HUMAN_REVIEW.

Valuation closure reuses the existing Terminal research workflow. It remains `RESEARCH_ONLY`: it may preserve or recompute research BUY / WAIT_PRICE and reverse-solve the existing PE BUY threshold into a research buy-price ceiling, but it cannot create Canonical Formal BUY or orders. Current 5/5-PASS priority follow-ups are carried into Terminal even when a later bounded Deep workset omits them, provided the current profile still proves all five gates PASS.

## Low-confidence deterministic fallback

Jev route confidence is advisory and is not a safety authority. When the persisted evidence state is `INSUFFICIENT` and deterministic triage already marks the entity as a holding, urgent research, or P0/P1/P2, the research orchestrator may still dispatch the existing bounded Deep evidence refresh even when Jev route confidence is below 0.50. The plan records `dispatch_mode=DETERMINISTIC_SAFE_FALLBACK`.

A Jev `HUMAN_REVIEW` route is also downgraded to the same read-only evidence refresh only when the state is ruleable `INSUFFICIENT`. `CONFLICTED` and other genuinely non-ruleable cases remain in human review. This fallback never grants Formal trading authority and cannot convert UNKNOWN to PASS.

## Research strategy ledger

The orchestrator persists a fail-closed research strategy ledger at `data/jev_shadow/research_strategy_ledger.json`. Each attempt is keyed semantically by stock code, unresolved hard gate, strategy family, and a **hard-gate-local evidence epoch**. Runtime-only lineage such as a Jev or Deep workflow id is excluded. The broader stock-level research fingerprint is retained only as trace metadata and does not decide whether an individual gate strategy may reopen.

The gate-local epoch includes the gate's semantic evidence summary (including Deep gap-closure evidence) and, for financial gates, the same-run PIT financial diagnostics. Retrieval timestamps and workflow lineage are excluded so a re-fetch of identical evidence does not create a false new epoch. The ledger records the unresolved reason, strategy/source/query family, gate-local evidence epoch, dispatch status, accepted Deep run id, whether new evidence appeared, whether the gate changed, and whether that strategy is exhausted. A strategy is not judged until the exact accepted Deep run is visible in a later Jev research state. If that gate's local evidence epoch is unchanged and the gate remains unresolved, the strategy becomes `EXHAUSTED_NO_PROGRESS` and is not scheduled again in that epoch. Only a change in that same gate's evidence state reopens its supported strategy; progress in an unrelated gate does not reopen an already exhausted path.

Deep profile state is authoritative for whether a supported hard gate is still researchable. If the exact Deep profile explicitly marks a gate PASS or FAIL, an older routing-level `unresolved_gates` missing-evidence projection cannot reopen that gate. An exact UNKNOWN profile state may supply retry scope when the routing projection is empty. A missing Deep profile/workset is tracked as workset coverage blocked rather than evidence exhaustion, so it cannot consume a Deep retry budget or create a false no-progress conclusion.

This is research-control state only. It cannot authorize a trade, weaken a hard gate, or convert UNKNOWN to PASS. New source/query families can be added later without changing the ledger contract.

## Autonomous continuation after downstream convergence

When an exact Jev-triggered Deep run has fully converged through Terminal Research Decision, Investor Terminal Research Overlay, and the Three-Pillar Decision Center, the reconciler schedules one lineage-keyed **Jev Shadow Evaluation** for that exact Deep run. The continuation run carries `continuation_from_deep_run_id`, and the reconciler de-duplicates it by the run display title before dispatch. This closes the research loop without allowing Jev to call Deep directly.

The new Jev result still passes through the deterministic Jev Research Orchestrator. After the Jev persistence job has committed the exact routing lineage to main, it explicitly dispatches the orchestrator with that Jev run id and de-duplicates by the lineage-keyed orchestrator run title. This avoids leaving a persisted continuation routing unconsumed when a secondary workflow-completion trigger is not created, while keeping Jev itself advisory: only the deterministic orchestrator may decide whether another bounded Deep research dispatch is warranted. If no eligible work remains, the cycle terminates as a no-op. Formal trading authority remains false, UNKNOWN remains distinct from PASS, and no-auto-trade remains true.



## Research-exhaustion lifecycle convergence

The deterministic strategy ledger can feed candidate lifecycle dormancy after
the exact Jev routing lineage is reconciled. A non-holding candidate can enter
`DORMANT` only when every supported unresolved hard gate has an exact
code/gate/strategy/evidence-epoch ledger entry closed as
`EXHAUSTED_NO_PROGRESS`. Workset gaps, accepted work, changed evidence, and
never-attempted current epochs cannot produce dormancy.

`DORMANT` is research-control state, not `REJECT` or `FAIL`. It removes
stale lifecycle-tier priority boost while Broad Discovery remains independent.
A new schedulable evidence epoch, terminal research progress, or current-holding
protection deterministically reactivates the candidate. Jev remains advisory;
Formal actions remain Canonical-only, UNKNOWN is never promoted to PASS, and
automatic trading remains disabled.
