# GenGe V3.1 Terminal Research Decisions

- requested: **2**
- BUY: **1** / WAIT_PRICE: **0** / RESEARCH_GAP: **1** / REJECT: **0**
- all requested terminal: **True**
- authority: **RESEARCH_ONLY**; Formal/Production authority unchanged; UNKNOWN != PASS; no auto-trade.

## Urgent evidence queue

- 603605 珀莱雅: quant=None, PE/history=None, unknown=predictability,long_term_demand,moat,financial_safety,earnings_authenticity, financial_blockers=FINANCIAL_REVIEW_STATUS_NOT_OK,EARNINGS_QUALITY_CONFIDENCE_NOT_HIGH,CASH_CONVERSION_RATIO_MISSING,EARNINGS_QUALITY_SCORE_MISSING,NORMALIZED_CORE_OPERATING_PROFIT_MISSING,OPERATING_CASH_FLOW_MISSING, urgent=P0_EVIDENCE_BLOCKED

## Risk-budget capital advisory

- BUILD: **1** / PROBE: **0** / WATCH: **0** / BLOCK: **1**
- Advisory only: sizing uncertainty is not evidence promotion; UNKNOWN != PASS; no auto-trade.
- 603596 伯特利: **BUILD** / conviction=0.899 / max_portfolio=3.0%

## Terminal rows

- 603596 伯特利: **BUY** / ALL_HARD_GATES_PASS_AND_PE_DISCOUNT_AT_LEAST_20PCT
- 603605 珀莱雅: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY

# GenGe V3.1 Deep Decision Closure V2

- decision ready: **1/2** (50.0%)
- evidence complete: **1/2** (50.0%)
- FULL_EVIDENCE: **1**
- DECISION_READY_WITH_UNCERTAINTY: **0**
- DECISIVE_REJECT: **0**
- RESEARCH_REQUIRED: **1**
- UNKNOWN remains UNKNOWN. Bounded uncertainty never grants Formal BUY or auto-trade.

- 603596 伯特利: **FULL_EVIDENCE**; decision_ready=True; unknown=NONE
- 603605 珀莱雅: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,long_term_demand,moat,financial_safety,earnings_authenticity
