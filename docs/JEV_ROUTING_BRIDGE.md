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

A successful manual **GenGe Jev Shadow Evaluation** run persists:

- data/jev_shadow/latest.json
- data/jev_shadow/latest_routing.json
- JEV_RESEARCH_ROUTING.md

The persistence job exists only for workflow_dispatch and owns the write permission.
The secret-bearing live PR job remains contents:read.

PR smoke runs still upload artifacts but never persist them to main.

## Why automatic dispatch is still off

This phase makes Jev operationally visible and durable, but it intentionally does not
launch Deep or Evidence workflows yet. We first need repeated live calibration showing
that route selection is stable and useful. Deterministic research obligations always
remain in force and Jev can never suppress them.

A later promotion may allow Jev to accelerate already-eligible research work, but only
after calibration and with deterministic override/fail-closed semantics.

## Low-confidence deterministic fallback

Jev route confidence is advisory and is not a safety authority. When the persisted evidence state is `INSUFFICIENT` and deterministic triage already marks the entity as a holding, urgent research, or P0/P1/P2, the research orchestrator may still dispatch the existing bounded Deep evidence refresh even when Jev route confidence is below 0.50. The plan records `dispatch_mode=DETERMINISTIC_SAFE_FALLBACK`.

A Jev `HUMAN_REVIEW` route is also downgraded to the same read-only evidence refresh only when the state is ruleable `INSUFFICIENT`. `CONFLICTED` and other genuinely non-ruleable cases remain in human review. This fallback never grants Formal trading authority and cannot convert UNKNOWN to PASS.

