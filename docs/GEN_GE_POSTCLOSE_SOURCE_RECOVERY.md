# Post-close source recovery (production guard)

## Verified incident (2026-09-28)

The regular Opportunity Discovery schedule is 18:30 Beijing, but Sep 28 did
not have a matching successful `schedule` run. The successful full All-A
One Shot (run 36362003421) was dispatched **before** that day's market close
and is already consumed. Later Every-Industry producers succeeded while
the independent Finalizer rejected their older price/trade date with
`CANONICAL_TRADE_DATE_BEHIND_COMPLETED_SESSION`. Investor Brief continued to
publish dated historical results: latest market session remained Sep 24 even
though its report-generation timestamp advanced on Sep 28.

## Recovery scope

`.github/workflows/genge-postclose-source-recovery.yml` uses two *independent
fallback* weekday triggers (20:30 / 23:10 Beijing), and the already-scheduled
Era Capital Trend Radar Live completion as a separate workflow-run signal.
This does not replace the existing 18:30 full-A schedule or create a competing
valuation model. When the latest published investor dashboard does **not**
prove that `latest_trade_date`, Canonical trade date, market-regime date,
and the `freshness_contract.fresh` flag all match the completed session,
the watchdog:

1. Checks actual schedule/manual production runs from the existing
   `genge-opportunity-discovery.yml` AND explicit `genge-all-a-v31-once.yml`
   One Shot runs. PR/push fixture-only runs do not count.
2. Defers while the corresponding current-session producer, explicit One Shot,
   Every-Industry, or Finalizer is queued/in progress.
3. Allows at most two postclose full-production source *attempts in total* for
   the current local day (existing 18:30 + recovery, or two bounded recoveries
   if 18:30 never started); dispatches the existing Opportunity Discovery
   workflow, whose normal Every-Industry -> Finalizer chain remains authoritative.
   A successful Finalizer now directly triggers Investor Brief refresh; this
   does not bypass the existing strict source-date guards.
4. If both attempts are consumed with no current-session report and no active
   pipeline, fails visibly with `EXHAUSTED` rather than refreshing timestamps
   or fabricating market data.

A successful dispatch is **only an accepted request**, never production
acceptance. GitHub scheduled delivery is best effort; the extra time slots and
independent workflow-run signal reduce but cannot eliminate missing events.
On exchange holidays, the existing weekday-based freshness model deliberately
fails closed; future calendar integration is distinct work.

## Acceptance and remaining limits

To prove a new session, inspect (separately) the newly produced full-A report
artifact's observed source dates and real noncached evidence attempts; a newly
successful exact-lineage Finalizer artifact; the corresponding Investor Brief,
three-pillar and V4 handoff using identical real market dates; and the latest
`main` files. The Finalizer must continue to **reject** stale producer
artifacts. Do not replay the already consumed premarket One Shot
36362003421. Do not interpret previously persisted historical prices, the
20:30/23:10 dispatch, new GitHub commit timestamps, or CI passes as fresh
market data. No broker balance/order is inferred and no automatic trading,
BUY thresholds, or Formal authority changes are permitted.

The existing Investor Brief workflow still selects the latest *successful
Finalizer by run time*; #319 protects against regression to an older published
market epoch but does not choose the globally freshest available Finalizer.
Correcting source selection by verified market epoch remains a separate
required repair and is not claimed complete here.

### Verification

`python -m pytest -q tests/test_decide_postclose_recovery.py`

After merge inspect the *next real* post-close trigger and actual full producer,
Finalizer and consumer artifacts. Undo the fallback by reverting this workflow,
guard and tests; leave the existing primary 18:30 schedule and strict source
freshness protections unchanged.
