# V31_DURABLE_HANDOFF

> Compact production handoff for GenGe V3.1.1. Repository `main`, `V31_CANONICAL_SNAPSHOT.json`, `V31_CANDIDATE_LEDGER.md`, `CURRENT_HOLDINGS.md` and dated market logs form the durable evidence chain.

## Canonical synchronization — verified 2026-08-27 10:09:57 CST

- `canonical_snapshot_id`: `d32ab6d5787f0e571296`
- `source_run_id`: `33021974261`
- `upstream_run_id`: `33020092050`
- `source_artifact_id`: `9626921839`
- `latest_trade_date`: `2026-08-26`
- `research_as_of`: `2026-08-27T08:09:00+08:00`
- Production version: `GEN_GE_V3_1_1_PRODUCTION`
- Downloaded artifact hashes exactly match the durable projection for discovery/deep-review/production CSVs.
- The source success run predates native canonical publishing and its artifact does **not** contain `reports/canonical_snapshot/latest.json` or the new ledger-independent `reports/discovery_pool/...` layer.
- Current workflow code now requires both layers and publishes native canonical snapshots, but the latest relevant Every-Industry run `33031337070` was `skipped` by its authoritative-trigger condition. Therefore no newer successful native canonical artifact exists yet.
- Synchronization health: **DEGRADED_NATIVE_CANONICAL_NOT_YET_PROVEN**.

## Fail-closed consequence for the 2026-08-27 open session

- Do not combine 2026-08-27 intraday prices with 2026-08-26 production actions to manufacture Formal BUY/ADD/REDUCE/EXIT.
- Fresh filings/news may be used only as timestamped research overlays.
- Formal BUY/ADD from today's intraday overlay: **NOT AUTHORIZED**.
- Price-only REDUCE/EXIT from today's intraday overlay: **NOT AUTHORIZED**.
- Existing canonical production actions for all 378 candidates and all four confirmed holdings remain `HOLD_REVIEW` because valuation confidence is INVALID in the source production artifact.
- No threshold, ranking rule or BUY/SELL policy was relaxed.

## Confirmed holdings source of truth

`CURRENT_HOLDINGS.md` remains authoritative:

- `603369 今世缘` — 300 shares, average cost 29.5003
- `001316 润贝航科` — 200 shares, average cost 26.0955
- `600276 恒瑞医药` — 100 shares, average cost 46.4115
- `600406 国电南瑞` — 200 shares, average cost 23.1258

Canonical production action for all four: **HOLD_REVIEW**. No same-snapshot REDUCE/EXIT or hard-thesis invalidation is established.

## Durable candidate research queue

Research overlay remains downstream of Discovery and never filters it:

1. `600312 平高电气` — WATCH / BUY_REVIEW / Formal BUY NO. Prior working Bear/Base/Bull ~17.9 / 23.5 / 31.6; H2 delivery/cash conversion and final production gates remain blockers.
2. `603416 信捷电气` — WATCH / NEW / Formal BUY NO. 2026H1 operating/cash-flow evidence improved; moat, normalized earnings and reverse valuation incomplete. The 2026-08-27 H1 disclosure is consistent with the existing overlay and does not independently promote a BUY.
3. `600309 万华化学` — A1-QUALITY / WAIT_PRICE / Formal BUY NO; through-cycle segment valuation and explicit MOS required.
4. `603993 洛阳钼业` — A1 / WAIT_PRICE / Formal BUY NO; prior preferred 17–18 research entry zone remains below the 8/26 close 19.59.
5. `601899 紫金矿业` — A1 / WAIT_PRICE / Formal BUY NO; normalized copper/gold assumptions and MOS required.
6. `601168 西部矿业` — A2 / WAIT_PRICE / Formal BUY NO; 8/26 rally lowered immediate odds and cycle normalization remains mandatory.
7. `603658 安图生物` — WAIT / DOWNGRADED / Formal BUY NO; one more moat/normalized-earnings review before queue removal if A-grade economics cannot be re-established.

No ledger `seen_count` is incremented merely by rereading the same canonical snapshot; candidate lifecycle deltas require genuinely new canonical/evidence state.

## Required next production proof

The next authoritative `GenGe Opportunity Discovery` schedule/workflow-dispatch success must trigger `GenGe V3.1.1 Every-Industry Research` and successfully upload an artifact containing:

- `reports/discovery_pool/ledger_independent_discovery.csv`
- `reports/v31_review_enriched/v31_review_queue_enriched.csv`
- `reports/production_decisions/production_decisions.csv`
- `reports/canonical_snapshot/latest.json`

Only after those sections validate under one new snapshot id may hourly/daily consumers promote a new same-snapshot action.
