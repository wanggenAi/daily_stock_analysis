# GenGe V3.1 Terminal Research Decisions

- requested: **13**
- BUY: **1** / WAIT_PRICE: **0** / RESEARCH_GAP: **12** / REJECT: **0**
- all requested terminal: **True**
- authority: **RESEARCH_ONLY**; Formal/Production authority unchanged; UNKNOWN != PASS; no auto-trade.

## Urgent evidence queue

- None

## Risk-budget capital advisory

- BUILD: **1** / PROBE: **2** / WATCH: **4** / BLOCK: **6**
- Advisory only: sizing uncertainty is not evidence promotion; UNKNOWN != PASS; no auto-trade.
- 603596 伯特利: **BUILD** / conviction=0.889 / max_portfolio=3.0%
- 002352 顺丰控股: **PROBE** / conviction=0.6588 / max_portfolio=0.84%
- 002468 申通快递: **PROBE** / conviction=0.6394 / max_portfolio=0.77%

## Terminal rows

- 603596 伯特利: **BUY** / ALL_HARD_GATES_PASS_AND_PE_DISCOUNT_AT_LEAST_20PCT
- 002352 顺丰控股: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 603605 珀莱雅: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 601808 中海油服: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 601965 中国汽研: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 601816 京沪高铁: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 605116 奥锐特: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 002468 申通快递: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 000526 学大教育: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 002842 翔鹭钨业: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 600961 株冶集团: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 001309 德明利: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 000682 东方电子: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY

# GenGe V3.1 Deep Decision Closure V2

- decision ready: **1/13** (7.7%)
- evidence complete: **1/13** (7.7%)
- FULL_EVIDENCE: **1**
- DECISION_READY_WITH_UNCERTAINTY: **0**
- DECISIVE_REJECT: **0**
- RESEARCH_REQUIRED: **12**
- UNKNOWN remains UNKNOWN. Bounded uncertainty never grants Formal BUY or auto-trade.

- 603596 伯特利: **FULL_EVIDENCE**; decision_ready=True; unknown=NONE
- 002352 顺丰控股: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,long_term_demand
- 603605 珀莱雅: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,long_term_demand,moat,financial_safety,earnings_authenticity
- 601808 中海油服: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,long_term_demand,moat,financial_safety,earnings_authenticity
- 601965 中国汽研: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,long_term_demand,moat,financial_safety,earnings_authenticity
- 601816 京沪高铁: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,long_term_demand,moat
- 605116 奥锐特: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,long_term_demand,moat
- 002468 申通快递: **RESEARCH_REQUIRED**; decision_ready=False; unknown=long_term_demand,moat
- 000526 学大教育: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,long_term_demand,moat
- 002842 翔鹭钨业: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,moat,financial_safety,earnings_authenticity
- 600961 株冶集团: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,moat
- 001309 德明利: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,moat,financial_safety,earnings_authenticity
- 000682 东方电子: **RESEARCH_REQUIRED**; decision_ready=False; unknown=long_term_demand,moat,financial_safety,earnings_authenticity
