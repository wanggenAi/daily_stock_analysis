# V4 P1 source-reconciliation increment (not complete P1)

Additive read-only module: `investor_decision_v4_p1_sources.py`. Uses existing V4 P0 projection and accepts **parsed, explicitly user-confirmed** broker positions, display quotes, execution-consumption record and independently verified event records as inputs. It does not discover events, infer current cash, grant execution permissions, connect to a broker or alter the original Canonical. Missing position/fund confirmation remains UNKNOWN, not zero.

The current durable broker quote file `data/manual_execution_quotes/latest.json` has `observed_at=2026-09-22T12:17:51+08:00`; the dashboard's Canonical market trade date remains 2026-09-24. Therefore these prices are historical display-only. The more recent archived broker position evidence in `data/manual_broker_snapshots/2026-09-22_121751.md` confirms four positions, but is not live broker synchronization and does not supply present execution availability. `CURRENT_FUNDS.md` explicitly has no sufficiently current confirmed funds. `CURRENT_EXECUTION_STATE.json` lists previously consumed 603993 staged-add lots; those cannot be rearmed.

| P1 field | Trusted input | Source timestamp | Gate / fallback |
| --- | --- | --- | --- |
| Broker quote | validated user-confirmed quote snapshot | timestamp per snapshot AND per code | show price only if internally consistent; stale market session or missing => no trading permission |
| Holdings quantity / available shares | explicitly parsed confirmed broker screenshot | broker observation timestamp | equal current confirmed portfolio quantity required; historical display-only even if equal |
| Fund positions | independently confirmed current user evidence | dated signed/explicit confirmation | absent => LATEST_HOLDINGS_NOT_PERSISTED; no fabricated zero |
| Consumed authorization | existing persisted CURRENT_EXECUTION_STATE.json | exact consumption timestamp and Canonical ID | historical consumed amounts remain consumed; never issue a new order |
| Corporate event | previously independently verified upstream original URL and publication date | original publication, distinct proposal and outcome dates | proposal != approved resolution; unverified outcomes cannot be upgraded |
| Capital, lot size, T+1 | existing Canonical planner and actual fresh broker evidence | broker session and current plan epoch | NOT yet end-to-end verified in this increment; zero executable shares and zero planned immediate cash |

All P1 source fields are display-only, with `executable_shares=0`; P1 execution-feasible calculations and V4 Web integration are subsequent work. Regression tests include historical and same-session quotes, broker mismatch, consumed authority, proposal/outcome distinction, missing fund data and deterministic replay. No real official event is asserted from test fixtures.

## Original issuer provenance boundary

P1 does **not** autonomously verify issuer documents. Its caller must provide an independently checked, dated original on an explicitly allowlisted SSE/SZSE/CNINFO host and set `original_document_verified=true`; merely supplying an HTTPS string or third-party event title is insufficient. A RESOLUTION can display APPROVED only if `outcome_document_verified=true` and a valid outcome timestamp also accompany a verified original. Unverified records are omitted or their outcome remains `UNVERIFIED_OUTCOME`, never elevated to actionable authority. These synthetic tests do not establish that any particular live issuer proposal or approval actually occurred.
