# Era & Capital Trend Radar V1

Status: DESIGN CONTRACT

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

1. POLICY_CAPITAL
   - national plans and policy direction
   - fiscal expenditure / special funds
   - central/local government implementation
   - SOE capital expenditure and procurement

2. INDUSTRIAL_CAPITAL
   - capacity expansion
   - equipment procurement
   - R&D expenditure
   - M&A and strategic investment
   - hiring / project construction / order growth

3. FINANCIAL_CAPITAL
   - sector market activity and institutional allocation
   - ETF/fund flows when PIT-safe data is available
   - financing / IPO / VC / PE evidence
   - valuation and crowding changes

4. REAL_DEMAND
   - sales / orders / utilization
   - inventory and price signals
   - exports/imports
   - penetration/adoption
   - supply-demand gaps

5. TECHNOLOGY
   - cost curves
   - technical breakthroughs
   - substitution risk
   - bottlenecks and enabling technologies

6. GLOBAL_STRUCTURE
   - trade and supply-chain relocation
   - energy/resource constraints
   - demographic changes
   - major-economy industrial policy
   - geopolitical supply-chain effects, treated as evidence rather than prediction

## Three horizons

Every trend is scored independently on three horizons:

- STRUCTURAL: 10-20 years. Question: what will society/economy need?
- INDUSTRIAL: 3-10 years. Question: where can sustained real capital expenditure and profit pools form?
- CYCLICAL: 6-36 months. Question: is the long-term thesis currently entering an earnings/ordering acceleration phase?

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

Events:

- NEW
- RESEEN
- STRENGTHENED
- WEAKENED
- CROWDING_INCREASED
- CROWDING_EASED
- HORIZON_CHANGED
- FALSIFIED
- REACTIVATION_REVIEW_REQUIRED

Rules:

- absence from one scan MUST NOT automatically falsify a trend
- FALSIFIED trends MUST NOT auto-reactivate
- same evidence snapshot replay MUST be idempotent
- out-of-order evidence snapshots fail closed
- evidence must carry source, observed_at, published_at when available, retrieved_at and freshness classification
- low-quality duplicated news must not create multiple independent confirmations

## Causal chain

For every high-priority trend the system must be able to render:

STRUCTURAL_DRIVER
-> POLICY_RESPONSE (optional; policy is not required for every valid trend)
-> REAL_DEMAND
-> CAPITAL_EXPENDITURE
-> SUPPLY_CHAIN_BOTTLENECKS
-> PROFIT_POOL
-> INVESTABLE_LINKS
-> A_SHARE_MAPPING
-> V3_1_1_DEEP_REVIEW

A broken causal link reduces confidence. Policy headlines alone cannot establish a trend.

## Example: ageing / longevity economy

The system should be capable of deriving, rather than hard-coding, a thesis such as:

population ageing
-> increasing chronic-care, rehabilitation, assisted-living and productivity needs
-> policy/fiscal/insurance responses
-> real spending and capacity formation
-> differentiated profit pools across healthcare, devices, insurance, rehabilitation, automation and elder services

It must then distinguish social importance from investability. An elder-care service may have strong demand but poor returns; a medical-device link may have stronger margins and barriers. The Radar therefore ranks industry-chain profit pools, not merely themes.

## Scoring contract

Each trend snapshot records 0-100 component scores:

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

Derived scores:

- structural_score
- industrial_score
- cyclical_score
- confidence_score

`financial_crowding` is a risk/temperature measure, not a positive contribution by default.

No score may be emitted without an evidence bundle and a deterministic scoring explanation.

## Required machine outputs

Planned durable outputs:

- `data/era_radar/latest.json`
- `data/era_radar/trend_lifecycle_state.json`
- `data/era_radar/evidence/<snapshot_id>.json`
- `data/era_radar/history/<snapshot_id>.json`

Human projection:

- `ERA_CAPITAL_TREND_RADAR.md`

The Markdown file is projection only. JSON is machine truth.

## Daily human view

The report should lead with the economy/era, not ticker symbols:

1. Top structural trends
2. New/emerging trends
3. Accelerating trends
4. Crowded but structurally valid trends
5. Weakening/falsified trends
6. Policy-capital changes
7. Industrial-capital changes
8. Real-demand changes
9. Key bottlenecks / profit pools
10. Shanghai/Shenzhen A-share research mapping
11. What changed since the previous snapshot
12. Counter-evidence and uncertainty

## Investment handoff

Radar may emit `RESEARCH_HANDOFF` records only when:

- trend confidence clears the research threshold
- a causal profit pool is identified
- the company is in the user's tradable Shanghai/Shenzhen A-share universe for actionable research
- provenance/freshness requirements are satisfied

A handoff is NOT BUY. It only enters Broad Discovery / Deep Review prioritization. V3.1.1 independently re-underwrites company moat, earnings, valuation, margin of safety and timing.

Conceptual investment chain:

RIGHT_TREND x RIGHT_COMPANY x RIGHT_PRICE x RIGHT_TIMING

The Radar is primarily responsible for RIGHT_TREND and industry-chain mapping. It must not impersonate the downstream decision kernel.

## Anti-bias requirements

- no hard-coded conclusion that an industry is a future winner
- no inference from stock-price appreciation alone
- no policy-headline = investable-industry shortcut
- explicitly search for counter-evidence
- separate social necessity from corporate profitability
- separate structural direction from current cycle
- separate capital attention from valuation attractiveness
- preserve negative/neutral evidence

## V1 acceptance criteria

V1 implementation is complete only when automated tests prove:

1. deterministic scoring from a frozen evidence fixture
2. independent three-horizon scores
3. lifecycle idempotency on duplicate snapshot
4. fail-closed out-of-order replay
5. no auto-reactivation after FALSIFIED
6. duplicated evidence does not double-count confirmation
7. counter-evidence can downgrade a trend
8. crowding cannot by itself upgrade structural confidence
9. policy-only evidence cannot create CONFIRMED trend
10. A-share mapping produces research handoff, never Formal action
11. existing V3.1.1 model/gates remain byte-for-byte unaffected by the feature PR unless an explicitly reviewed adapter is added
12. fixture includes ageing/longevity but the expected result is derived from evidence, not hard-coded by industry name

## Rollout

Phase 1: contract + schema + deterministic engine + fixtures/tests.

Phase 2: evidence collectors with PIT/provenance/freshness and source-quality controls.

Phase 3: trend lifecycle persistence and daily report projection.

Phase 4: read-only research handoff into Broad Discovery / V3.1.1 Deep Review.

Phase 5: production scheduling, observability, replay validation and longitudinal calibration against realized industry fundamentals.

The feature does not receive Formal trading authority in any phase.