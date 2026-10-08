# GenGe V3.1 Terminal Research Decisions

- requested: **12**
- BUY: **1** / WAIT_PRICE: **0** / RESEARCH_GAP: **11** / REJECT: **0**
- all requested terminal: **True**
- authority: **RESEARCH_ONLY**; Formal/Production authority unchanged; UNKNOWN != PASS; no auto-trade.

## Urgent evidence queue

- 601318 中国平安: quant=32.5312, PE/history=0.7503001200480192, unknown=predictability,long_term_demand,moat,financial_safety,earnings_authenticity, financial_blockers=EARNINGS_QUALITY_SCORE_BELOW_PASS_THRESHOLD, urgent=P0_EVIDENCE_BLOCKED
- 600406 国电南瑞: quant=31.8877, PE/history=0.8265532544378699, unknown=predictability,long_term_demand,moat,financial_safety,earnings_authenticity, financial_blockers=CASH_CONVERSION_RATIO_BELOW_PASS_THRESHOLD,EARNINGS_QUALITY_SCORE_BELOW_PASS_THRESHOLD, urgent=P0_EVIDENCE_BLOCKED
- 603993 洛阳钼业: quant=30.5444, PE/history=0.7479546054367907, unknown=predictability, financial_blockers=NONE, urgent=P0_EVIDENCE_BLOCKED
- 001316 润贝航科: quant=23.9734, PE/history=0.6673434856175973, unknown=predictability,long_term_demand,moat, financial_blockers=NONE, urgent=P0_EVIDENCE_BLOCKED

## Risk-budget capital advisory

- BUILD: **1** / PROBE: **0** / WATCH: **2** / BLOCK: **9**
- Advisory only: sizing uncertainty is not evidence promotion; UNKNOWN != PASS; no auto-trade.
- 603596 伯特利: **BUILD** / conviction=0.8906 / max_portfolio=3.0%

## Terminal rows

- 603596 伯特利: **BUY** / ALL_HARD_GATES_PASS_AND_PE_DISCOUNT_AT_LEAST_20PCT
- 601965 中国汽研: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 601318 中国平安: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 000703 恒逸石化: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 600406 国电南瑞: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 603993 洛阳钼业: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 000833 粤桂股份: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 603986 兆易创新: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 000415 渤海租赁: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 001309 德明利: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 603416 信捷电气: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 001316 润贝航科: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY

# GenGe V3.1 Deep Decision Closure V2

- decision ready: **2/12** (16.7%)
- evidence complete: **1/12** (8.3%)
- FULL_EVIDENCE: **1**
- DECISION_READY_WITH_UNCERTAINTY: **1**
- DECISIVE_REJECT: **0**
- RESEARCH_REQUIRED: **10**
- UNKNOWN remains UNKNOWN. Bounded uncertainty never grants Formal BUY or auto-trade.

- 603596 伯特利: **FULL_EVIDENCE**; decision_ready=True; unknown=NONE
- 601965 中国汽研: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,long_term_demand,moat,financial_safety,earnings_authenticity
- 601318 中国平安: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,long_term_demand,moat,financial_safety,earnings_authenticity
- 000703 恒逸石化: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,long_term_demand,moat,financial_safety,earnings_authenticity
- 600406 国电南瑞: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,long_term_demand,moat,financial_safety,earnings_authenticity
- 603993 洛阳钼业: **DECISION_READY_WITH_UNCERTAINTY**; decision_ready=True; unknown=predictability
- 000833 粤桂股份: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,long_term_demand,moat,financial_safety,earnings_authenticity
- 603986 兆易创新: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,financial_safety,earnings_authenticity
- 000415 渤海租赁: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,long_term_demand,moat,financial_safety,earnings_authenticity
- 001309 德明利: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,moat,financial_safety,earnings_authenticity
- 603416 信捷电气: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,long_term_demand,moat,financial_safety,earnings_authenticity
- 001316 润贝航科: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,long_term_demand,moat
