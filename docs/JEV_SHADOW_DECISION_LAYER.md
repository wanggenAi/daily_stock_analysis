# Jev Shadow Decision Layer

This integration adds TypeSafe AI Jev as a **shadow-only research routing layer**.

It does not replace the deterministic stock engine, valuation logic, hard gates, Candidate Lifecycle, Deep Research, or Formal/Production authority.

## Why this exists

The stock system already has durable candidate state, evidence collection, deep research and production reporting. Jev is used only to test whether a cheap, fast typed-decision layer can improve research routing:

- decide whether more verified evidence appears necessary;
- decide whether expensive deep research appears useful now;
- choose a bounded research route;
- assign research-attention priority;
- classify the supplied evidence state.

These are research workflow judgments, not stock recommendations.

## Hard authority boundary

The integration is locked to SHADOW_ONLY.

It cannot:

- mutate BUY / WAIT_PRICE / REJECT;
- mutate Formal holding actions;
- change valuation formulas or thresholds;
- change Candidate Lifecycle state;
- change hard gates;
- turn UNKNOWN into PASS;
- authorize automatic trading;
- delete a candidate.

The output contract always records formal_trading_authority=false, automatic_formal_buy_allowed=false, mutates_authoritative_decision=false, unknown_is_pass=false, and no_auto_trade=true.

## GitHub-only operation

No user-local clone is required.

The workflow is **GenGe Jev Shadow Evaluation**. It can be launched with GitHub Actions workflow_dispatch. The workflow reads already-persisted stock state, calls Jev, publishes a GitHub job summary, and uploads a machine-readable artifact.

The first version does not commit Jev output back to main. This prevents a new experimental model from creating repository churn or becoming an accidental runtime dependency. Artifacts are sufficient for calibration.

## Required GitHub secret

Create a repository Actions secret named TYPESAFE_API_KEY. Never commit the key to the repository.

If the secret is absent, the runner returns SKIPPED_NO_SECRET. The stock system continues normally.

## Configuration

Safe defaults:

- JEV_ENABLED=false
- JEV_SHADOW_MODE=true
- JEV_MODEL=jev-latest
- JEV_TIMEOUT_SECONDS=3
- JEV_MAX_RETRIES=1

The manual GitHub workflow explicitly enables the layer while preserving shadow mode.

The live workflow pins typesafe-sdk==0.7.0 so this early-access dependency cannot silently change under the experiment.

## Inputs

The workflow supports holdings, unresolved, and combined scope. The default first experiment is combined with 25 entities.

Each Jev state is compact. It contains only research-routing context such as current formal action label, valuation/evidence status, unresolved gate reasons, Deep lineage and guardrails. Raw giant evidence artifacts are not sent.

## Questions

Question set version: GEN_GE_JEV_RESEARCH_ROUTING_V1.

Current questions:

- needs_more_evidence — Noul probability;
- needs_deep_research — Noul probability;
- research_route — Choice;
- attention_priority — Choice;
- evidence_state — Choice.

The questions explicitly prohibit trading recommendations.

## Artifacts and calibration

Each successful row records entity id, compact state fingerprint, requested model, served model/version when returned by the SDK, schema versions, typed decisions, latency, usage when returned by the SDK, an existing evidence comparator where applicable, and authority guardrails.

The summary records call counts, success/error status, p50/p95 latency, decision distributions, served model versions, evidence-agreement rate and high-confidence disagreements.

This lets the repository test whether Jev identifies evidence gaps consistently, routes expensive deep research usefully, avoids high-confidence mistakes, and can eventually reduce expensive-model calls without losing valuable candidates.

## Local execution

Local execution is optional and is not required for normal use. The intended execution environment is GitHub Actions.
