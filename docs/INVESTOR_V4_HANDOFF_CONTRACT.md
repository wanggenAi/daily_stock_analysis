# V4 H1: persisted handoff contract

The read-only handoff is generated **inside the existing** GenGe Investor Decision Brief production workflow after the dashboard and its existing execution-consumption and research overlays. No additional scheduled workflow, new inference engine, GPT API invocation or trading authority is introduced.

- Machine-readable output: data/investor_chatgpt_handoff/latest.json
- Human entry point: INVESTOR_CHATGPT_HANDOFF.md
- Implementation: src/strategies/genge_opportunity_discovery/investor_chatgpt_handoff.py
- Production inputs: already validated Canonical artifact (passed checksum, Finalizer authority and holdings reconciliation in the existing workflow), final dashboard, and optional persisted decision-center, era-radar, planning-capital, manual quote and historical outcome files.
- A single report Git commit persists both handoff files with the dashboard; the same GitHub Action uploads all four outputs. The digest is the semantic epoch ID, not an assertion that a re-render or newer commit has newer market data.

## Honest status limits

Snapshot/source-run identity must match the authoritative Canonical. If an explicit Canonical date exists, it must equal the dashboard date. A mismatched Canonical fails publication; stale market data or optional missing/mismatched feeds are labeled as such, never promoted. Separately dated cash is a **planning floor**, not current broker-confirmed cash. Broker screenshots can remain dated reference material, not present-day execution proof. Even if the upstream freshness contract reports FRESH, the handoff does not claim independent exchange-calendar or executable intraday broker verification.

The bounded list contains up to 16 reported holdings and five research-only era/cycle trends. Formal buy_now and wait_price arrays stay empty in H1 until actual P1–P3 trading-feasibility and original-source evidence conditions are proved; upstream counts are audit-only. Historical research BUY/Jev suggestions do not grant formal rights. No original issuer event/outcome claim appears without independent verification. Exact existing source paths include SHA-256 content hashes; absent optional sources are marked missing instead of linked. Incoming Canonical itself is an ephemeral verified Finalizer artifact: its SHA-256 and selected run ID are recorded; the market artifact selector is recorded but **not** asserted to be joined to the current date.

All immediate executable quantities are zero in H1. This is a defensible *handoff implementation*, not completion of live web integration or today's opening readiness. On demand ChatGPT must re-fetch latest live main and verify the manifest's source hashes, production ID and source freshness before further synthesis.

## Tests and production acceptance

Deterministic tests cover old/stale as-of, cross-epoch Canonical, time-only rerender semantic IDs, missing broker/fund claims, unverified original events, non-formal research BUY, source-file hash presence, bounded holdings/trends and workflow publication order. Production acceptance requires exact-head PR CI, merged main, a genuine triggered producer run and BOTH persisted handoff outputs pointing to a real validated Canonical artifact. The workflow's successful run is not proof of a fresh trading session, accessible external website or live brokerage data.

Rollback: revert this builder and its workflow integration; the existing V3 dashboard and Formal Canonical path remain unchanged.
