# Investor Decision V4 P0 — additive presentation contract

**Status:** P0 implementation proposal; no broker execution capability or production acceptance. This is a *projection* of existing authorized records, not a parallel trading strategy. Code: `src/strategies/genge_opportunity_discovery/investor_decision_v4_projection.py`. Scope remains intentionally narrower than P1–P5.

## Field → source → as-of → freshness → fallback

| V4 display | Existing authoritative source | As-of requirement | Freshness / mismatch behavior |
| --- | --- | --- | --- |
| Formal action / lifecycle | finalized Canonical mirrored by `data/investor_decision_dashboard/latest.json` | exact Canonical snapshot and prior persisted action lifecycle | display recorded state only; no executable P0 order; unknown/sync loss becomes research-only |
| Positions and confirmed cost | `CURRENT_HOLDINGS.md` through existing holdings reconciliation | broker evidence timestamp mandatory for P1 execution | P0 quantity/reference only; no inferred shares, fund positions or extra orders |
| Confirmed funds | `CURRENT_FUNDS.md` where user-confirmed | explicit broker/owner confirmation timestamp | unverified = latest holdings not persisted, NEVER zero confirmed fund positions |
| Planning cash | `CURRENT_CAPITAL.json` via dashboard capital deployment | planning confirmation vs brokerage balance separately | planning estimate only; cash is not order permission |
| Execution consumption | `CURRENT_EXECUTION_STATE.json` via existing formal lifecycle | exact Canonical ID + dated user-confirmed evidence | prior consumption is never reset by overlay regeneration |
| EOD market/breadth | existing `dashboard.market` / regime | completed exchange session as-of, not pipeline generation time | label EOD; stale or unknown cannot create entry permission |
| Live executable quote | current validated price overlay, when P1 wired | quote source + actual observation time + exact market session | **P0 unavailable**: zero executable shares |
| Formal opportunities | existing Canonical + validated terminal mirror | exact source Canonical/session, complete validity and capital conjunction | P0 empty until P1/P2 verify all conditions; research BUY not Formal BUY |
| Jev and terminal leads | terminal research and Jev advisory snapshot | original source run + advisory timestamp | audit/drilldown only; never infer Formal eligibility |
| Trends / cycles | `data/era_radar/latest.json` + research handoff | `research_as_of`, per-claim source publication/effective dates | research-only; no trade authority; missing sources cannot be promoted |
| Corporate events | existing event decision and official-source provenance | separately track publication, proposal, effective/outcome and observation dates | P1 needed; missing outcome must not be described as approved |
| Investor decision questions | `data/decision_center/latest.json` | exact canonical snapshot and market trade date comparison | a mismatch is labeled `CROSS_FEED_LINEAGE_MISMATCH`; never blend epochs |

## Home layout and top-level semantics

1. **Holdings first**: confirmed stock/fund status, recorded action vs executable action, share/lot constraints, material changes. Recorded Formal HOLD/REDUCE is not itself evidence of present execution feasibility.
2. **Qualified opportunities**: P0 emits empty executable lists even if older upstream terminal lists contain `buy_now`; those counts remain audit-only. P1/P2 must prove formal authority, current Canonical, fresh price, broker reconciliation, unconsumed lifecycle, cash/lot and market eligibility together before changing this.
3. **Trends and cycle**: independent research evidence; never produces a Formal decision by itself.
4. **Material changes and capital plan**: P1–P4 only. P0 never emits an executable order, synthetic realized P&L or assumed balance.

`NEW`, `UNCHANGED`, `SUSPENDED`, `CLEARED` are **observed persisted lifecycle labels**, not automatically commands. `RESEARCH_ONLY` cannot be relabeled executable from Jev `ENTRY_NOW`, research `BUY`, an apparent discount, or a green workflow.

## P0 acceptance / exclusions

- P0 tests cover stale source, missing fund evidence, cross-feed lineage mismatch, forbidden parallel authority, no lot rounding, research BUY leak and idempotent projection.
- P0 is **not** a user-facing production release. P1 requires complete feed-specific timestamps and live reconciled holdings/consumption/quotes. P2 requires qualified opportunity list, bounded issuer evidence and genuine out-of-sample exit validation. P3/P4 connect trends, events, frontend, Markdown and JSON parity.
- Review/rollback: remove this isolated projection and its tests; pre-existing V3 dashboard, Canonical authority, workflows, persisted data and research lane remain unchanged.
