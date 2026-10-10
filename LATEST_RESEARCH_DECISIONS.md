# GenGe V3.1 Terminal Research Decisions

- requested: **3**
- BUY: **1** / WAIT_PRICE: **0** / RESEARCH_GAP: **2** / REJECT: **0**
- all requested terminal: **True**
- authority: **RESEARCH_ONLY**; Formal/Production authority unchanged; UNKNOWN != PASS; no auto-trade.

## Urgent evidence queue

- None

## Risk-budget capital advisory

- BUILD: **1** / PROBE: **1** / WATCH: **0** / BLOCK: **1**
- Advisory only: sizing uncertainty is not evidence promotion; UNKNOWN != PASS; no auto-trade.
- 603596 伯特利: **BUILD** / conviction=0.889 / max_portfolio=3.0%
- 002352 顺丰控股: **PROBE** / conviction=0.6588 / max_portfolio=0.84%

## Terminal rows

- 603596 伯特利: **BUY** / ALL_HARD_GATES_PASS_AND_PE_DISCOUNT_AT_LEAST_20PCT
- 002352 顺丰控股: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 603605 珀莱雅: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY

# GenGe V3.1 Deep Decision Closure V2

- decision ready: **1/3** (33.3%)
- evidence complete: **1/3** (33.3%)
- FULL_EVIDENCE: **1**
- DECISION_READY_WITH_UNCERTAINTY: **0**
- DECISIVE_REJECT: **0**
- RESEARCH_REQUIRED: **2**
- UNKNOWN remains UNKNOWN. Bounded uncertainty never grants Formal BUY or auto-trade.

- 603596 伯特利: **FULL_EVIDENCE**; decision_ready=True; unknown=NONE
- 002352 顺丰控股: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,long_term_demand
- 603605 珀莱雅: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,long_term_demand,moat,financial_safety,earnings_authenticity
