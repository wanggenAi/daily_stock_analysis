# GenGe V3.1 Terminal Research Decisions

- requested: **4**
- BUY: **1** / WAIT_PRICE: **0** / RESEARCH_GAP: **3** / REJECT: **0**
- all requested terminal: **True**
- authority: **RESEARCH_ONLY**; Formal/Production authority unchanged; UNKNOWN != PASS; no auto-trade.

## Urgent evidence queue

- 601318 中国平安: quant=32.5312, PE/history=0.7503001200480192, unknown=predictability,long_term_demand,moat,financial_safety,earnings_authenticity, financial_blockers=EARNINGS_QUALITY_SCORE_BELOW_PASS_THRESHOLD, urgent=P0_EVIDENCE_BLOCKED
- 600406 国电南瑞: quant=31.8877, PE/history=0.8265532544378699, unknown=predictability,long_term_demand,moat,financial_safety,earnings_authenticity, financial_blockers=CASH_CONVERSION_RATIO_BELOW_PASS_THRESHOLD,EARNINGS_QUALITY_SCORE_BELOW_PASS_THRESHOLD, urgent=P0_EVIDENCE_BLOCKED
- 603993 洛阳钼业: quant=30.5444, PE/history=0.7479546054367907, unknown=predictability, financial_blockers=NONE, urgent=P0_EVIDENCE_BLOCKED

## Risk-budget capital advisory

- BUILD: **1** / PROBE: **0** / WATCH: **1** / BLOCK: **2**
- Advisory only: sizing uncertainty is not evidence promotion; UNKNOWN != PASS; no auto-trade.
- 603596 伯特利: **BUILD** / conviction=0.8906 / max_portfolio=3.0%

## Terminal rows

- 603596 伯特利: **BUY** / ALL_HARD_GATES_PASS_AND_PE_DISCOUNT_AT_LEAST_20PCT
- 601318 中国平安: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 600406 国电南瑞: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 603993 洛阳钼业: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
