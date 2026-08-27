# GenGe V3.1.1 Canonical Snapshot

## Purpose

`reports/canonical_snapshot/latest.json` is the synchronization contract for hourly refreshes, pre-open reports and other downstream consumers of GenGe V3.1.1 Production.

It does **not** create a new stock score, change BUY/SELL thresholds, or replace the V3.1.1 decision model. Its only job is to make every consumer read one coherent production state instead of independently combining files from different runs or timestamps.

## Layering

The production research path is intentionally layered:

```text
All-A current-run evidence
  -> ledger-independent broad Discovery Pool
  -> valuation/deep-research recall + candidate metabolism
  -> V3.1 Deep Review
  -> V3.1.1 Production Decisions
  -> durable Candidate Ledger / hourly and daily presentation
```

`V31_CANDIDATE_LEDGER.md` is downstream durable memory. It must never be used to cap or filter the upstream Discovery Pool. A ledger with one or two high-priority names therefore does not mean only one or two A-share names were discovered.

Candidate metabolism is deliberately downstream of Discovery. Active ledger names may be recalled into valuation/deep research so previously identified hard-logic companies are not forgotten by a bounded research budget. Archived/INVALIDATED names may be suppressed from that expensive downstream recall until evidence-backed reactivation. Neither behavior changes whether a name can appear in the current-run broad Discovery Pool.

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

- `reports/discovery_pool/ledger_independent_discovery.csv` — current-run high-recall Discovery Pool; built from All-A + industry evidence and explicitly does not read the Candidate Ledger;
- `reports/v31_review_enriched/v31_review_queue_enriched.csv` — strict V3.1 deep review after downstream research recall/metabolism;
- `reports/production_decisions/production_decisions.csv` — V3.1.1 candidate and confirmed-holding actions.

The separate `reports/industry_valuation_source/all_a_quant_screen.csv` remains a downstream valuation-research recall source. It is allowed to use Active ledger recall and Archived/INVALIDATED suppression because that is where candidate metabolism belongs; it is **not** the canonical broad Discovery Pool.

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

## Discovery breadth versus candidate metabolism

Discovery is deliberately high recall and stateless with respect to the durable ledger. Its output records `discovery_ledger_filter_applied=False`, `discovery_durable_recall_applied=False`, and a versioned discovery contract so CI can prove this invariant instead of relying on documentation alone.

Candidate metabolism begins only after Discovery: old high-quality names can remain under deep research through durable recall, while invalidated names can leave downstream valuation/deep-review budgets. A genuinely changed company can still reappear in a later current-run Discovery Pool; re-entering the durable deep-research ledger then requires explicit evidence-backed reactivation rather than silent auto-revival.

## Discovery breadth versus Formal BUY strictness

The canonical snapshot publishes a broad execution-eligible discovery view and a separate deep-review view. Expanding discovery does not relax the frozen production decision model.

Formal BUY remains fail-closed and unchanged. Long-term demand, moat/ASML, earnings quality, normalized-profit, expectation-gap, valuation, downside, falsification and fresh-price requirements remain mandatory. Candidate metabolism and synchronization are research-routing mechanisms, not trading-signal shortcuts.
