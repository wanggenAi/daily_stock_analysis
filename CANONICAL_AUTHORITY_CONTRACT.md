# GenGe V3.1.1 Canonical Production Authority Contract

## Purpose

GenGe V3.1.1 has exactly one formal production truth **per authorized production cycle**: the validated native Canonical Snapshot.

There may be more than one legitimate production cycle on a trading day. In particular, the system can produce a fresh premarket snapshot and a later post-close snapshot. This does not create competing truths because each cycle is identified by its own source run and immutable `snapshot_id`; downstream consumers must use one finalized snapshot at a time and may never mix components across cycles.

This contract separates computation from authorization so that scheduled monitoring, daily settlement, holdings review, and candidate metabolism cannot silently create competing BUY/ADD/HOLD/REDUCE/EXIT states.

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
              -> operating_views/hourly.json
              -> operating_views/daily.json
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
              -> operating_views/hourly.json
              -> operating_views/daily.json
```

The two producer workflows are allowed to create a new formal action because both execute the frozen V3.1.1 research/production contract and build a native Canonical Snapshot. The Finalizer never creates a new action.

## Ownership of responsibilities

### Discovery

- Scans the current tradable A-share universe with high recall.
- The durable candidate ledger is not allowed to filter broad discovery.
- Discovery does not grant a Formal BUY/ADD/REDUCE/EXIT action.

### Authorized research / production producer

- `GenGe All-A V3.1.1 One Shot` is the premarket full production cycle.
- `GenGe V3.1.1 Every-Industry Research` is the post-close full production cycle.
- Each performs hard-logic research, deep review, valuation, strict-PIT production decisioning, holdings decisioning, and candidate research before building its native Canonical Snapshot.
- Only these authorized research/production stages may create or change a formal production action.

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
- Validates the native Canonical Snapshot, writes a cryptographic authority receipt, and derives read-only hourly/daily operating views.
- Fails closed when producer identity, source run identity, upstream identity, source hashes, trade-date evidence, schema, or snapshot synchronization is invalid.

### Hourly consumer

Responsibility: incremental monitoring.

It may overlay fresh price, filings, announcements, or news for research/monitoring, but the overlay cannot overwrite the canonical formal action. A Formal action change requires a newly validated and finalized Canonical Snapshot.

### Daily consumer

Responsibility: full daily settlement and lifecycle processing.

It reads the complete canonical discovery/deep-review/production state and may prepare evidence-backed candidate lifecycle changes for the next research cycle. It must not mutate the already-finalized Canonical Snapshot.

## Candidate metabolism

Candidate metabolism is downstream memory, not an upstream discovery filter.

The lifecycle may promote, demote, archive, or invalidate a candidate only from genuinely new evidence/canonical state. Re-reading the same `snapshot_id` must not increment lifecycle evidence counters or manufacture a state transition.

Archived/invalidated names may still reappear in broad market discovery because Discovery is ledger-independent. They require explicit new evidence and downstream re-underwriting before reactivation.

## Holdings

Confirmed holdings are part of the production decision layer and must share the same Canonical Snapshot as candidate decisions. Hourly and daily views therefore cannot use holdings from one run and candidate actions from another run.

## Formal action rules

1. One authorized production cycle has one formal `snapshot_id` truth.
2. A newer successfully finalized production cycle may supersede an older cycle, but components from the two cycles may not be mixed.
3. Only an authorized research/production producer may create a new Formal action.
4. Finalizer authenticates; it never recomputes the action.
5. Hourly and daily consumers read the same finalized canonical truth but perform different jobs.
6. Fresh overlays may add context but may not overwrite a Formal action.
7. Formal action changes require a new validated Canonical Snapshot.
8. Production thresholds and the V3.1.1 hard-logic policy are not changed by synchronization code.
9. `no_auto_trade` remains true: the system produces research/decision support, not unattended order execution.

## Fail-closed conditions

Do not authorize or consume a formal action when any of the following is true:

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
- a downstream consumer attempts to recompute or overwrite a formal action.

## Production proof

A production cycle is considered natively proven only after a successful authorized producer run (`GenGe All-A V3.1.1 One Shot` or `GenGe V3.1.1 Every-Industry Research`) is followed by a successful `GenGe V3.1.1 Production Finalizer` run that publishes:

```text
authoritative/canonical_snapshot/latest.json
authoritative/production_authority.json
authoritative/operating_views/hourly.json
authoritative/operating_views/daily.json
```

All four files must resolve to the same canonical `snapshot_id`, the same canonical source run, and the same producer identity.
