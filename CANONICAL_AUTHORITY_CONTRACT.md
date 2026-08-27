# GenGe V3.1.1 Canonical Production Authority Contract

## Purpose

GenGe V3.1.1 has exactly one formal production truth **per authorized production cycle**: the validated native Canonical Snapshot.

There may be more than one legitimate production cycle on a trading day. In particular, the system can produce a fresh premarket snapshot and a later post-close snapshot. This does not create competing truths because each cycle is identified by its own source run and immutable `snapshot_id`; downstream consumers must use one finalized snapshot at a time and may never mix components across cycles.

This contract separates computation, authorization, portfolio reconciliation, and candidate memory so that scheduled monitoring, daily settlement, holdings review, and candidate metabolism cannot silently create competing BUY/ADD/HOLD/REDUCE/EXIT states.

## Authorized production chains

### Premarket cycle

```text
GenGe Opportunity Premarket Dispatch
  -> GenGe All-A V3.1.1 One Shot
      -> full current-market Discovery
      -> deep review / valuation
      -> V3.1.1 strict-PIT candidate + holding decisions
      -> canonical_snapshot/latest.json
          -> GenGe V3.1.1 Production Finalizer
              -> production_authority.json
              -> holdings_reconciliation.json
              -> operating_views/hourly.json
              -> operating_views/daily.json
              -> candidate_lifecycle/candidate_lifecycle_state.json
              -> candidate_lifecycle/V31_CANDIDATE_LEDGER.md
```

### Post-close cycle

```text
GenGe Opportunity Discovery
  -> GenGe V3.1.1 Every-Industry Research
      -> ledger-independent Discovery Pool
      -> deep review / valuation
      -> V3.1.1 production decisions
      -> canonical_snapshot/latest.json
          -> GenGe V3.1.1 Production Finalizer
              -> production_authority.json
              -> holdings_reconciliation.json
              -> operating_views/hourly.json
              -> operating_views/daily.json
              -> candidate_lifecycle/candidate_lifecycle_state.json
              -> candidate_lifecycle/V31_CANDIDATE_LEDGER.md
```

The two producer workflows are allowed to create a new formal action because both execute the frozen V3.1.1 research/production contract and build a native Canonical Snapshot. The Finalizer never creates a new action.

## Ownership of responsibilities

### Discovery

- Scans the current tradable A-share universe with high recall.
- Candidate lifecycle state and the generated candidate ledger are not allowed to filter broad Discovery.
- Discovery does not grant a Formal BUY/ADD/REDUCE/EXIT action.

### Authorized research / production producer

- `GenGe All-A V3.1.1 One Shot` is the premarket full production cycle.
- `GenGe V3.1.1 Every-Industry Research` is the post-close full production cycle.
- Each performs hard-logic research, deep review, valuation, strict-PIT production decisioning, holdings decisioning, and candidate research before building its native Canonical Snapshot.
- Only these authorized research/production stages may create or change a Formal production action.

### Canonical Snapshot

- Stamps discovery, deep review, candidate decisions, and holding decisions with one `snapshot_id`.
- Records the source run, upstream run, source hashes, latest trade date, and production version.
- A valid Canonical Snapshot is immutable for downstream consumers.
- Components from different `snapshot_id` values must never be combined into a synthetic decision state.

### Production Finalizer

- Does not rank stocks.
- Does not recalculate valuation.
- Does not re-run a Top5 bridge.
- Does not create a second production decision table.
- Accepts only the two authorized canonical producer workflows.
- Validates the native Canonical Snapshot and writes the cryptographic authority receipt.
- Derives read-only hourly/daily operating views from that exact snapshot.
- Reconciles the canonical holding universe against the current confirmed holdings file.
- Applies the finalized snapshot to candidate lifecycle memory exactly once.
- Fails closed when producer identity, source run identity, source hashes, trade-date evidence, schema, snapshot synchronization, holdings reconciliation identity, or lifecycle state validity is invalid.

### Hourly consumer

Responsibility: incremental monitoring.

It may overlay fresh price, filings, announcements, or news for research/monitoring, but the overlay cannot overwrite the canonical Formal action. A Formal action change requires a newly validated and finalized Canonical Snapshot.

### Daily consumer

Responsibility: full daily settlement and lifecycle review.

It reads the complete canonical discovery/deep-review/production state, the holdings reconciliation result, and the machine candidate lifecycle state. It may prepare evidence-backed research and explicit lifecycle transitions for a later authorized state update, but it must not mutate the already-finalized Canonical Snapshot or manually rewrite machine lifecycle counters.

## Candidate metabolism

Candidate metabolism is downstream memory, not an upstream Discovery filter.

### Machine source of truth

The durable lifecycle source of truth is:

```text
data/opportunity_snapshots/candidate_lifecycle_state.json
```

The finalized artifact also publishes the exact state used for that cycle:

```text
authoritative/candidate_lifecycle/candidate_lifecycle_state.json
```

`V31_CANDIDATE_LEDGER.md` is a generated human-readable projection of that machine state. It is not an independent lifecycle authority and must not be manually edited to change `seen_count`, ACTIVE/ARCHIVED/INVALIDATED state, research recall, or lifecycle vetoes.

On the first machine migration only, the pre-state-machine Markdown ledger may be imported for candidate identity, membership, research tier, and audit context. Its historical `seen_count` is retained as audit metadata only because old hourly/manual updates were not guaranteed canonical-idempotent. Machine `seen_count` starts at the lifecycle migration epoch and counts distinct canonical observations only.

The old prose-heavy ledger is preserved once as:

```text
V31_CANDIDATE_RESEARCH_NOTES_LEGACY.md
```

That file is historical research context only. It cannot create a Formal action or override current canonical evidence.

### Lifecycle rules

- Broad Discovery is never filtered by lifecycle state.
- Only deep-review / production candidate observations enter machine candidate metabolism.
- The same `canonical_snapshot_id` may be applied at most once; replay is a NOOP and must not increment `seen_count`.
- A new snapshot that observes an ACTIVE candidate records RESEEN and increments machine `seen_count` once.
- Absence from one or more snapshots never automatically archives or invalidates a candidate.
- Archived/INVALIDATED names may reappear in broad Discovery or deep review, but rediscovery only creates `REDISCOVERED_REVIEW_REQUIRED`; it cannot reactivate the name automatically.
- UPGRADED, DOWNGRADED, PRICE_ONLY_CHANGE, ARCHIVED, INVALIDATED, and REACTIVATED transitions require explicit new evidence with a unique `evidence_id`, `evidence_observed_at`, and reason.
- Reusing an evidence ID is idempotent.
- REACTIVATED is the only event allowed to restore an Archived/INVALIDATED name to ACTIVE recall.
- An older unprocessed canonical snapshot may not overwrite a newer lifecycle state.
- If machine lifecycle JSON exists but is invalid, research recall fails closed; it must not silently fall back to Markdown.
- Legacy Markdown recall is allowed only before the machine lifecycle JSON has ever been established.

### Research recall

`industry_valuation_bridge` uses ACTIVE machine lifecycle names for durable re-underwriting and suppresses Archived/INVALIDATED lifecycle names from ordinary durable recall. This recall mechanism is downstream of broad Discovery and cannot grant a Formal BUY or relax any V3.1.1 gate.

## Holdings

Confirmed holdings are part of the production decision layer and must share the same Canonical Snapshot as candidate decisions. Hourly and daily views therefore cannot use holdings from one run and candidate actions from another run.

The Finalizer publishes `holdings_reconciliation.json` against the current `CURRENT_HOLDINGS.md`:

- `HOLDINGS_IN_SYNC`: canonical holding Formal actions remain usable for the current portfolio.
- `HOLDINGS_OUT_OF_SYNC`: holding Formal actions from that snapshot are suspended for the current portfolio until a new authorized production cycle includes the changed holdings.
- A holdings mismatch does not invalidate canonical candidate actions.
- A downstream consumer may still publish timestamped holdings research overlays while out of sync, but it must not manufacture replacement holding Formal actions.

## Formal action rules

1. One authorized production cycle has one Formal `snapshot_id` truth.
2. A newer successfully finalized production cycle may supersede an older cycle, but components from the two cycles may not be mixed.
3. Only an authorized research/production producer may create a new Formal action.
4. Finalizer authenticates; it never recomputes the action.
5. Hourly and daily consumers read the same finalized canonical truth but perform different jobs.
6. Fresh overlays may add context but may not overwrite a Formal action.
7. Formal action changes require a new validated Canonical Snapshot.
8. Candidate lifecycle events cannot manufacture or overwrite Formal trading actions.
9. Holdings reconciliation can suspend stale holding actions but cannot create replacement actions.
10. Production thresholds and the V3.1.1 hard-logic policy are not changed by synchronization or lifecycle code.
11. `no_auto_trade` remains true: the system produces research/decision support, not unattended order execution.

## Fail-closed conditions

Do not authorize or consume a Formal action when any applicable condition below is true:

- native canonical snapshot is missing;
- source workflow is not one of the two authorized canonical producers;
- snapshot `source_kind` does not match the producer workflow;
- snapshot schema or production version is invalid;
- canonical `source_run_id` does not match the completed producer run;
- `upstream_run_id` is missing;
- canonical source hashes are missing;
- latest trade date is missing or production price freshness is invalid;
- discovery/deep-review/production sections do not share one `snapshot_id`;
- an hourly/daily view points to a different `snapshot_id`;
- authority receipt and canonical file digest do not match;
- holdings reconciliation points to a different canonical snapshot/source run;
- a holding action is consumed while holdings reconciliation is OUT_OF_SYNC;
- machine candidate lifecycle JSON exists but fails its contract validation;
- lifecycle state is updated from a duplicate/out-of-order snapshot in violation of idempotency/order rules;
- a downstream consumer attempts to recompute or overwrite a Formal action.

## Production proof

A production cycle is considered natively proven only after a successful authorized producer run (`GenGe All-A V3.1.1 One Shot` or `GenGe V3.1.1 Every-Industry Research`) is followed by a successful `GenGe V3.1.1 Production Finalizer` run that publishes:

```text
authoritative/canonical_snapshot/latest.json
authoritative/production_authority.json
authoritative/holdings_reconciliation.json
authoritative/operating_views/hourly.json
authoritative/operating_views/daily.json
authoritative/candidate_lifecycle/candidate_lifecycle_state.json
authoritative/candidate_lifecycle/summary.json
authoritative/candidate_lifecycle/V31_CANDIDATE_LEDGER.md
```

The authority, operating views, holdings reconciliation, and lifecycle summary must resolve to the same canonical `snapshot_id` and canonical source run. The machine lifecycle state must record that snapshot as its latest persisted canonical observation. Only after those checks pass may the Finalizer persist the lifecycle JSON and generated Ledger projection back to `main`.
