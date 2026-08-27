# GenGe V3.1.1 Canonical Production Authority Contract

## Purpose

GenGe V3.1.1 has exactly one formal production truth per authorized research cycle: the validated native Canonical Snapshot.

This contract separates computation from authorization so that scheduled monitoring, daily settlement, holdings review, and candidate metabolism cannot silently create competing BUY/ADD/HOLD/REDUCE/EXIT states.

## Authoritative chain

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

## Ownership of responsibilities

### Discovery

- Scans the current tradable A-share universe with high recall.
- The durable candidate ledger is not allowed to filter broad discovery.
- Discovery does not grant a Formal BUY/ADD/REDUCE/EXIT action.

### Every-Industry Research

- Performs hard-logic research, deep review, valuation, strict-PIT production decisioning, holdings decisioning, and candidate research.
- Builds the native Canonical Snapshot.
- This is the only stage allowed to create or change a formal production action.

### Canonical Snapshot

- Stamps discovery, deep review, candidate decisions, and holding decisions with one `snapshot_id`.
- Records the source run, upstream discovery run, source hashes, latest trade date, and production version.
- A valid Canonical Snapshot is immutable for downstream consumers.

### Production Finalizer

- Does not rank stocks.
- Does not recalculate valuation.
- Does not re-run a Top5 bridge.
- Does not create a second production decision table.
- Validates the native Canonical Snapshot, writes a cryptographic authority receipt, and derives read-only hourly/daily operating views.
- Fails closed when source run identity, upstream identity, source hashes, trade-date evidence, schema, or snapshot synchronization is invalid.

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

1. One authorized `snapshot_id` = one formal production truth.
2. Only the research/production stage may create a new Formal action.
3. Finalizer authenticates; it never recomputes the action.
4. Hourly and daily consumers read the same canonical truth but perform different jobs.
5. Fresh overlays may add context but may not overwrite a Formal action.
6. Formal action changes require a new validated Canonical Snapshot.
7. Production thresholds and the V3.1.1 hard-logic policy are not changed by synchronization code.
8. `no_auto_trade` remains true: the system produces research/decision support, not unattended order execution.

## Fail-closed conditions

Do not authorize or consume a formal action when any of the following is true:

- native canonical snapshot is missing;
- snapshot schema or production version is invalid;
- canonical `source_run_id` does not match the completed Every-Industry run;
- `upstream_run_id` is missing;
- canonical source hashes are missing;
- latest trade date is missing or production price freshness is invalid;
- discovery/deep-review/production sections do not share one `snapshot_id`;
- an hourly/daily view points to a different `snapshot_id`;
- a downstream consumer attempts to recompute or overwrite a formal action.

## Production proof

A production cycle is considered natively proven only after a successful authoritative `GenGe V3.1.1 Every-Industry Research` run is followed by a successful `GenGe V3.1.1 Production Finalizer` run that publishes:

```text
authoritative/canonical_snapshot/latest.json
authoritative/production_authority.json
authoritative/operating_views/hourly.json
authoritative/operating_views/daily.json
```

All four files must resolve to the same canonical `snapshot_id`.
