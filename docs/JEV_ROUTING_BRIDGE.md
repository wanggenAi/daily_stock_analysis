# Jev Research Routing Bridge

This is phase 2 of the TypeSafe AI Jev integration.

The shadow layer answers bounded typed questions. The routing bridge converts those
answers into a durable **advisory research queue** without giving Jev any Formal or
trading authority.

## What it produces

For each successful shadow row, the bridge records:

- research route: NO_ESCALATION / EVIDENCE_REFRESH / DEEP_RESEARCH / HUMAN_REVIEW;
- attention priority: LOW / MEDIUM / HIGH;
- evidence state;
- needs-more-evidence and needs-deep-research typed judgments;
- served model, state fingerprint, confidence metadata, and full Choice probability distributions for later calibration.

The queue is sorted for operator visibility only.

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

## Automatic research dispatch boundary

The routing bridge itself remains advisory: `automatic_dispatch_allowed=false`.
A separate deterministic research orchestrator may consume the persisted advisory
queue and dispatch the existing bounded Deep research workflow only when deterministic
eligibility and fail-closed guardrails also permit it. Jev never dispatches work
directly, never suppresses deterministic research obligations, and never grants Formal
trading authority.

## Low-confidence deterministic fallback

Jev route confidence is advisory and is not a safety authority. When the persisted evidence state is `INSUFFICIENT` and deterministic triage already marks the entity as a holding, urgent research, or P0/P1/P2, the research orchestrator may still dispatch the existing bounded Deep evidence refresh even when Jev route confidence is below 0.50. The plan records `dispatch_mode=DETERMINISTIC_SAFE_FALLBACK`.

A Jev `HUMAN_REVIEW` route is also downgraded to the same read-only evidence refresh only when the state is ruleable `INSUFFICIENT`. `CONFLICTED` and other genuinely non-ruleable cases remain in human review. This fallback never grants Formal trading authority and cannot convert UNKNOWN to PASS.

## Research strategy ledger

The orchestrator persists a fail-closed research strategy ledger at `data/jev_shadow/research_strategy_ledger.json`. Each attempt is keyed semantically by stock code, unresolved hard gate, strategy family, and a **hard-gate-local evidence epoch**. Runtime-only lineage such as a Jev or Deep workflow id is excluded. The broader stock-level research fingerprint is retained only as trace metadata and does not decide whether an individual gate strategy may reopen.

The ledger records the unresolved reason, strategy/source/query family, gate-local evidence epoch, dispatch status, accepted Deep run id, whether new evidence appeared, whether the gate changed, and whether that strategy is exhausted. A strategy is not judged until the exact accepted Deep run is visible in a later Jev research state. If that gate's local evidence epoch is unchanged and the gate remains unresolved, the strategy becomes `EXHAUSTED_NO_PROGRESS` and is not scheduled again in that epoch. Only a change in that same gate's evidence state reopens its supported strategy; progress in an unrelated gate does not reopen an already exhausted path.

This is research-control state only. It cannot authorize a trade, weaken a hard gate, or convert UNKNOWN to PASS. New source/query families can be added later without changing the ledger contract.

