# GenGe realtime data → research architecture

## Goal

The repository maintains investment facts continuously; research consumes a frozen snapshot. Acquisition and reasoning are separate responsibilities.

## Layer 1 — data producers

Producers may access public networks and update durable source data incrementally. They never create Formal BUY/SELL authority.

Primary producers include:

- All-A production scan → `data/market_snapshots/`
- Era Capital Trend Radar → `data/era_radar/`
- Global Market Pulse → `data/global_market_pulse/`
- Evidence slow lanes → `data/evidence_events/` and research mapping
- intraday execution quote producer → `data/live_execution_quotes/`

`GenGe Realtime Data Package` runs hourly and after important producer workflows. It does not rerun full history. It fingerprints current producer outputs and writes:

- `data/data_package/latest.json`
- `data/data_package/snapshots/<snapshot_id>.json`
- `data/data_package/watermarks.json`

Freshness uses business timestamps/trade dates, never checkout file mtimes. The All-A snapshot must match the latest valid A-share trade date reported by Global Market Pulse. Weekends/holidays therefore keep the latest completed trading session instead of becoming stale merely because the exchange is closed.

Execution-critical source degradation determines `READY / STALE / INVALID`. Optional source degradation is exposed separately through `completeness_state` and does not by itself manufacture an execution block.

## Layer 2 — research consumers

Research does not fetch the internet by default. Before a research run, `scripts/genge_research_input.py` locks one immutable Data Package snapshot and writes a receipt under `data/research_input/`.

Default network policy: `CANONICAL_PACKAGE_ONLY`.

A stale package may be used for research/audit when explicitly allowed, but `execution_allowed=false`.

Hourly research should inspect changes/events/price-zone transitions. EOD research may perform the full market/industry/company/valuation process. Slow weekly/monthly research may update structural assumptions. These cadences do not change the authority boundary.

## Emergency fresh evidence

A material fact discovered before normal ingestion may be recorded with `scripts/genge_external_fresh_evidence.py`.

It is always tagged `EXTERNAL_FRESH_EVIDENCE`, has `formal_action_authority=NONE`, and remains `PENDING_CANONICAL_INGEST` until a normal producer absorbs it. It may trigger re-research but cannot itself authorize a trade.

## Layer 3 — Decision Center

`GenGe Three-Pillar Decision Center` is a consumer. It locks a Data Package before calculation and then binds the exact snapshot provenance to `data/decision_center/latest.json` and the ChatGPT handoff.

If the package is not execution-ready, historical Formal actions remain visible for audit/research, but immediate executable quantities and immediate cash deployment are forced to zero. The data layer never recomputes Formal actions.

## Live quotes

Live quote acquisition and consumption are physically separated:

1. `scripts/genge_live_quote_snapshot.py` fetches and persists quote facts only.
2. `scripts/genge_apply_live_quote_snapshot.py` is network-free and may update display/execution-reference prices only.
3. A live quote can never mutate a finalized Formal action.

## Manual recovery / trigger order

When GitHub Actions automatic triggering is unavailable, use this order:

1. Run `Era Capital Trend Radar Live` and `GenGe Global Market Pulse` when their source data needs refresh.
2. Run `GenGe All-A V3.1.1 One Shot` after the latest completed A-share session when a new full-market snapshot is required.
3. Run `GenGe Postscan Market Data Publish` with the successful All-A run id if the automatic `workflow_run` handoff did not fire.
4. Run `GenGe Realtime Data Package` to seal the newest source state into an immutable snapshot.
5. Run `GenGe Three-Pillar Decision Center` to consume that snapshot and produce the final result.
6. Before acting on any result, verify `data_package_provenance.snapshot_id`, `package_status=READY`, `data_freshness_execution_guard.execution_allowed=true`, and the expected latest A-share trade date.

The unique investor-facing destination remains the Decision Center. Data collection exists to feed it; research exists to interpret the package; neither layer is an excuse to create trades without evidence.
