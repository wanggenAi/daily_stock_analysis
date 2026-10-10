# GenGe V3.1 Terminal Research Decisions

- requested: **21**
- BUY: **1** / WAIT_PRICE: **0** / RESEARCH_GAP: **20** / REJECT: **0**
- all requested terminal: **True**
- authority: **RESEARCH_ONLY**; Formal/Production authority unchanged; UNKNOWN != PASS; no auto-trade.

## Urgent evidence queue

- 603605 珀莱雅: quant=53.0108, PE/history=0.3817923186344239, unknown=predictability,long_term_demand,moat,financial_safety,earnings_authenticity, financial_blockers=CASH_CONVERSION_RATIO_BELOW_PASS_THRESHOLD,EARNINGS_QUALITY_SCORE_BELOW_PASS_THRESHOLD, urgent=P0_EVIDENCE_BLOCKED
- 002468 申通快递: quant=39.1824, PE/history=0.5492842535787321, unknown=long_term_demand,moat, financial_blockers=NONE, urgent=P0_EVIDENCE_BLOCKED
- 600406 国电南瑞: quant=32.6435, PE/history=0.8265532544378699, unknown=predictability,long_term_demand,moat,financial_safety,earnings_authenticity, financial_blockers=CASH_CONVERSION_RATIO_BELOW_PASS_THRESHOLD,EARNINGS_QUALITY_SCORE_BELOW_PASS_THRESHOLD, urgent=P0_EVIDENCE_BLOCKED
- 601318 中国平安: quant=32.5186, PE/history=0.7503001200480192, unknown=predictability,long_term_demand,moat,financial_safety,earnings_authenticity, financial_blockers=EARNINGS_QUALITY_SCORE_BELOW_PASS_THRESHOLD, urgent=P0_EVIDENCE_BLOCKED
- 603993 洛阳钼业: quant=30.7987, PE/history=0.7479546054367907, unknown=predictability, financial_blockers=NONE, urgent=P0_EVIDENCE_BLOCKED
- 001316 润贝航科: quant=23.3155, PE/history=0.6673434856175973, unknown=predictability,long_term_demand,moat, financial_blockers=NONE, urgent=P0_EVIDENCE_BLOCKED
- 002811 郑中设计: quant=65.6, PE/history=0.32763068567549214, unknown=predictability,long_term_demand,moat,financial_safety,earnings_authenticity, financial_blockers=CASH_CONVERSION_RATIO_BELOW_PASS_THRESHOLD,EARNINGS_QUALITY_SCORE_BELOW_PASS_THRESHOLD, urgent=QUANTITATIVELY_ATTRACTIVE_EVIDENCE_BLOCKED

## Risk-budget capital advisory

- BUILD: **1** / PROBE: **2** / WATCH: **8** / BLOCK: **10**
- Advisory only: sizing uncertainty is not evidence promotion; UNKNOWN != PASS; no auto-trade.
- 603596 伯特利: **BUILD** / conviction=0.889 / max_portfolio=3.0%
- 002352 顺丰控股: **PROBE** / conviction=0.6588 / max_portfolio=0.84%
- 002468 申通快递: **PROBE** / conviction=0.6394 / max_portfolio=0.77%

## Terminal rows

- 603596 伯特利: **BUY** / ALL_HARD_GATES_PASS_AND_PE_DISCOUNT_AT_LEAST_20PCT
- 002811 郑中设计: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 002352 顺丰控股: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 603605 珀莱雅: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 601808 中海油服: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 600318 新力金融: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 601965 中国汽研: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 601816 京沪高铁: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 605116 奥锐特: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 002468 申通快递: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 600406 国电南瑞: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 601318 中国平安: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 000526 学大教育: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 603993 洛阳钼业: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 000783 长江证券: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 002842 翔鹭钨业: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 601069 西部黄金: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 600961 株冶集团: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 001309 德明利: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 001316 润贝航科: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 000682 东方电子: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY

# GenGe V3.1 Deep Decision Closure V2

- decision ready: **2/21** (9.5%)
- evidence complete: **1/21** (4.8%)
- FULL_EVIDENCE: **1**
- DECISION_READY_WITH_UNCERTAINTY: **1**
- DECISIVE_REJECT: **0**
- RESEARCH_REQUIRED: **19**
- UNKNOWN remains UNKNOWN. Bounded uncertainty never grants Formal BUY or auto-trade.

- 603596 伯特利: **FULL_EVIDENCE**; decision_ready=True; unknown=NONE
- 002811 郑中设计: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,long_term_demand,moat,financial_safety,earnings_authenticity
- 002352 顺丰控股: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,long_term_demand
- 603605 珀莱雅: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,long_term_demand,moat,financial_safety,earnings_authenticity
- 601808 中海油服: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,long_term_demand,moat,financial_safety,earnings_authenticity
- 600318 新力金融: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,long_term_demand,moat,financial_safety,earnings_authenticity
- 601965 中国汽研: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,long_term_demand,moat,financial_safety,earnings_authenticity
- 601816 京沪高铁: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,long_term_demand,moat
- 605116 奥锐特: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,long_term_demand,moat
- 002468 申通快递: **RESEARCH_REQUIRED**; decision_ready=False; unknown=long_term_demand,moat
- 600406 国电南瑞: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,long_term_demand,moat,financial_safety,earnings_authenticity
- 601318 中国平安: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,long_term_demand,moat,financial_safety,earnings_authenticity
- 000526 学大教育: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,long_term_demand,moat
- 603993 洛阳钼业: **DECISION_READY_WITH_UNCERTAINTY**; decision_ready=True; unknown=predictability
- 000783 长江证券: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,long_term_demand,moat
- 002842 翔鹭钨业: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,moat,financial_safety,earnings_authenticity
- 601069 西部黄金: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,moat
- 600961 株冶集团: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,moat
- 001309 德明利: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,moat,financial_safety,earnings_authenticity
- 001316 润贝航科: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,long_term_demand,moat
- 000682 东方电子: **RESEARCH_REQUIRED**; decision_ready=False; unknown=long_term_demand,moat,financial_safety,earnings_authenticity
