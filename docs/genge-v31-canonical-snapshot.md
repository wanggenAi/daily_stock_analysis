# GenGe V3.1.1 Canonical Snapshot

## Purpose

`reports/canonical_snapshot/latest.json` is the synchronization contract for hourly refreshes, pre-open reports and other downstream consumers of GenGe V3.1.1 Production.

It does **not** create a new stock score, change BUY/SELL thresholds, or replace the V3.1.1 decision model. Its only job is to make every consumer read one coherent production state instead of independently combining files from different runs or timestamps.

## Layering

The production research path is intentionally layered:

```text
All-A universe
  -> broad Discovery Pool
  -> V3.1 Deep Review
  -> V3.1.1 Production Decisions
  -> durable Candidate Ledger / hourly and daily presentation
```

`V31_CANDIDATE_LEDGER.md` is downstream durable memory. It must never be used to cap or filter the upstream Discovery Pool. A ledger with one or two high-priority names therefore does not mean only one or two A-share names were discovered.

## Snapshot identity

Every canonical snapshot contains one `snapshot_id` derived from:

- production/schema version;
- current Every-Industry run id;
- upstream All-A run id;
- latest observed trade date;
- hashes of the broad discovery, deep-review and production-decision source CSVs.

The `discovery`, `deep_review` and `production` sections repeat the same `snapshot_id`. Consumers must fail closed if those section ids do not match, or if a report attempts to combine data from another source run without an explicit newer snapshot.

## Canonical source

The authoritative synchronization source is the successful **GenGe V3.1.1 Every-Industry Research** artifact because that run contains all three layers needed for one coherent view:

- `reports/final_valuation_source/all_a_quant_screen.csv` — broad discovery/recall;
- `reports/v31_review_enriched/v31_review_queue_enriched.csv` — strict V3.1 deep review;
- `reports/production_decisions/production_decisions.csv` — V3.1.1 candidate and confirmed-holding actions.

Postscan research remains additional research evidence. It may refine research priorities, but downstream hourly/daily presentation must not silently replace one section of an Every-Industry snapshot with a Postscan section from a different run.

## Hourly and daily consumer contract

Hourly refresh and daily/pre-open report generation must:

1. resolve the newest successful canonical snapshot;
2. record its `snapshot_id`, `source_run_id`, `upstream_run_id` and `latest_trade_date`;
3. update Ledger / market log / current research presentation from that same snapshot;
4. add newer filing/news evidence only as a timestamped overlay, never by silently replacing stale market-price or production-decision fields;
5. preserve the fresh-data invariant: stale/unverified prices cannot create BUY/ADD or price-dependent REDUCE/EXIT;
6. preserve `CURRENT_HOLDINGS.md` as the only holding-universe source of truth.

If the canonical snapshot cannot be verified, the consumer may report the data/CI problem but must not promote a new Formal BUY/ADD.

## Discovery breadth versus Formal BUY strictness

Discovery is deliberately high recall. The canonical snapshot publishes a broad execution-eligible discovery view and a separate deep-review view. This prevents the durable ledger from becoming an accidental upstream filter.

Formal BUY remains fail-closed and unchanged. Expanding discovery does not relax long-term demand, moat/ASML, earnings quality, normalized-profit, expectation-gap, valuation, downside, falsification or fresh-price requirements.
