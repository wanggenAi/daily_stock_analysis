# Era & Capital Trend Radar V1

Status: IMPLEMENTATION CONTRACT

## Purpose

Build an upstream intelligence layer that answers, with evidence and explicit uncertainty:

1. What long-duration social/economic changes are underway?
2. Which industries are likely to be structurally important to China and the global economy?
3. Where are policy capital, industrial capital, financial capital and real demand moving?
4. Which trends are strengthening, weakening, crowded, or being falsified?
5. Which industry-chain links can convert the trend into durable corporate earnings?
6. Which Shanghai/Shenzhen A-share companies deserve downstream V3.1.1 Deep Review?

The Radar is a discovery/research system. It MUST NOT issue or alter Formal BUY/ADD/HOLD/REDUCE/EXIT actions.

## Non-negotiable boundary

The existing GEN_GE_V3_1_1_PRODUCTION decision kernel remains authoritative. This feature MUST NOT relax or rewrite:

- generalized ASML/moat test
- long-term demand gate
- hard logic
- earnings/cash-flow gate
- reverse valuation
- margin of safety
- Confidence Gate / Hard Gate
- PIT, provenance and freshness requirements
- Canonical Authority
- holdings reconciliation
- no-auto-trade
- candidate lifecycle invariants
- Broad Discovery independence

Radar output may change research priority and create evidence-backed discovery candidates. Formal actions remain downstream of the existing Canonical production chain.

## Core model

A trend is not a hot theme. A trend requires multi-source causal evidence.

The Radar tracks six evidence families:

1. POLICY_CAPITAL — policy direction, fiscal implementation, SOE capital expenditure and procurement.
2. INDUSTRIAL_CAPITAL — capacity, equipment, R&D, M&A, hiring, projects and orders.
3. FINANCIAL_CAPITAL — market allocation, financing and crowding; price/flow alone is never causal confirmation.
4. REAL_DEMAND — sales, orders, utilization, inventory, prices, trade, penetration and supply-demand gaps.
5. TECHNOLOGY — cost curves, breakthroughs, substitution, bottlenecks and enabling technologies.
6. GLOBAL_STRUCTURE — demographics, trade, energy/resources, supply chains and major-economy industrial policy.

## Three horizons

Every trend is scored independently on three horizons:

- STRUCTURAL: 10-20 years — what will society/economy need?
- INDUSTRIAL: 3-10 years — where can sustained real capex and profit pools form?
- CYCLICAL: 6-36 months — is the long-term thesis currently entering an earnings/orders acceleration phase?

Do not collapse these horizons into one score. A structurally strong industry can be cyclically weak or financially overcrowded.

## Trend lifecycle

Machine states:

- EMERGING
- ACCELERATING
- CONFIRMED
- MATURE
- CROWDED
- WEAKENING
- FALSIFIED

Lifecycle rules:

- absence from one scan MUST NOT automatically falsify a trend
- FALSIFIED trends MUST NOT auto-reactivate
- same evidence snapshot replay MUST be idempotent
- out-of-order evidence snapshots fail closed
- evidence carries source, observed_at, published_at when available, retrieved_at and freshness
- duplicated publications do not create independent confirmation

## Causal chain

For every high-priority trend the system must be able to render:

STRUCTURAL_DRIVER
-> POLICY_RESPONSE (optional)
-> REAL_DEMAND
-> CAPITAL_EXPENDITURE
-> SUPPLY_CHAIN_BOTTLENECKS
-> PROFIT_POOL
-> INVESTABLE_LINKS
-> A_SHARE_MAPPING
-> V3_1_1_DEEP_REVIEW

A broken causal link reduces confidence. Policy headlines alone cannot establish a trend.

## Examples are fixtures, not conclusions

Ageing/longevity is only one test example. The same engine must derive unrelated hypotheses such as grid modernization, compute/power infrastructure, resource constraints, advanced manufacturing, changing consumer structures, or a trend unknown when this code was written. Topic names never determine scores.

The system must also distinguish social importance from investability. A socially necessary industry can have weak returns, while a narrow enabling link can have stronger economics and barriers.

## Scoring contract

Each trend records 0-100 components:

- structural_demand
- policy_commitment
- industrial_capex
- real_demand_confirmation
- technology_enablement
- global_confirmation
- profit_pool_quality
- investable_bottleneck_strength
- financial_crowding
- evidence_quality

Derived outputs:

- structural_score
- industrial_score
- cyclical_score
- confidence_score

`financial_crowding` is temperature/risk. Pure financial crowding MUST NOT increase causal evidence breadth or structural confidence.

## PIT and provenance

Every admitted evidence record must identify its source and PIT timestamps. Future information and stale evidence fail closed. Only registered source classes can cross the normalization boundary. Exact normalized evidence used for a persisted snapshot is saved with that snapshot for audit/replay.

## Durable machine truth

- `data/era_radar/latest.json`
- `data/era_radar/trend_lifecycle_state.json`
- `data/era_radar/evidence/<snapshot_id>.json`
- `data/era_radar/history/<snapshot_id>.json`

Human projection:

- `ERA_CAPITAL_TREND_RADAR.md`

Markdown is projection only. JSON is machine truth.

## Collector and discovery boundary

V1 defines an industry-agnostic collector protocol plus a deterministic JSON observation adapter. Source-specific adapters emit normalized observations with topic keys, source identity, PIT timestamps, direction, quality and component exposures.

Discovery groups observations into hypotheses without using the topic label as evidence. Financial-market attention alone produces only a WATCH hypothesis; causal evidence must come from real demand, industrial capital, technology, policy and/or global structure.

The JSON collector format is the replay format for CI and historical audits.

## Daily human view

The report is organized around the economy/era, not ticker symbols:

1. Top structural trends
2. New/emerging trends
3. Accelerating trends
4. Crowded but structurally valid trends
5. Weakening/falsified trends
6. Policy-capital changes
7. Industrial-capital changes
8. Real-demand changes
9. Key bottlenecks/profit pools
10. Shanghai/Shenzhen A-share research mapping
11. What changed since the prior snapshot
12. Counter-evidence and uncertainty

## Investment handoff

Radar may emit research-only handoffs when trend confidence, causal profit pool, provenance/freshness and Shanghai/Shenzhen A-share eligibility are satisfied.

A handoff is NOT BUY. V3.1.1 independently re-underwrites moat, earnings, valuation, margin of safety and timing.

Conceptual chain:

RIGHT_TREND x RIGHT_COMPANY x RIGHT_PRICE x RIGHT_TIMING

Radar is responsible primarily for RIGHT_TREND and industry-chain mapping. It cannot impersonate the downstream Formal decision kernel.

## Anti-bias requirements

- no hard-coded future winners
- no inference from stock-price appreciation alone
- no policy-headline = investable-industry shortcut
- explicitly preserve/search counter-evidence
- separate social necessity from corporate profitability
- separate structural direction from current cycle
- separate capital attention from valuation attractiveness

## V1 acceptance criteria

Automated tests must prove:

1. deterministic scoring from frozen evidence
2. independent three-horizon scores
3. lifecycle idempotency on duplicate snapshot
4. fail-closed out-of-order replay
5. no auto-reactivation after FALSIFIED
6. duplicate evidence does not double-count confirmation
7. counter-evidence can downgrade a trend
8. crowding cannot upgrade structural confidence
9. policy-only evidence cannot create CONFIRMED
10. A-share mapping is research-only, never Formal action
11. V3.1.1 model/trading/PIT gates are not relaxed
12. ageing/longevity result is derived from evidence, not its name
13. unregistered sources fail closed
14. persisted snapshots contain auditable evidence bundles
15. CLI replay generates deterministic machine truth and human projection

## V1 production boundary

The scheduled workflow is an auditable deterministic replay/regression gate. It is NOT a claim that all live official-source adapters are already production-authoritative. Each live adapter must separately prove parsing, PIT timestamps, provenance, source quality and failure semantics before its output is admitted to durable Radar truth.

This is deliberate fail-closed staging: the intelligence architecture, lifecycle, persistence and research-only authority boundary can ship before any unproven live parser is allowed to influence research truth.

The feature does not receive Formal trading authority in any phase.
