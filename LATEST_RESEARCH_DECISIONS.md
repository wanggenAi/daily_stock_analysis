# GenGe V3.1 Terminal Research Decisions

- requested: **32**
- BUY: **1** / WAIT_PRICE: **0** / RESEARCH_GAP: **30** / REJECT: **1**
- all requested terminal: **True**
- authority: **RESEARCH_ONLY**; Formal/Production authority unchanged; UNKNOWN != PASS; no auto-trade.

## Urgent evidence queue

- 600406 国电南瑞: quant=45.7808, PE/history=0.8265532544378699, unknown=predictability,long_term_demand,moat,financial_safety,earnings_authenticity, financial_blockers=CASH_CONVERSION_RATIO_BELOW_PASS_THRESHOLD,EARNINGS_QUALITY_SCORE_BELOW_PASS_THRESHOLD, urgent=P0_EVIDENCE_BLOCKED
- 601318 中国平安: quant=32.938, PE/history=0.7503001200480192, unknown=predictability,long_term_demand,moat,financial_safety,earnings_authenticity, financial_blockers=EARNINGS_QUALITY_SCORE_BELOW_PASS_THRESHOLD, urgent=P0_EVIDENCE_BLOCKED
- 603993 洛阳钼业: quant=30.5767, PE/history=0.7479546054367907, unknown=predictability, financial_blockers=NONE, urgent=P0_EVIDENCE_BLOCKED
- 001316 润贝航科: quant=22.1976, PE/history=0.6673434856175973, unknown=predictability,long_term_demand,moat, financial_blockers=NONE, urgent=P0_EVIDENCE_BLOCKED

## Risk-budget capital advisory

- BUILD: **1** / PROBE: **1** / WATCH: **6** / BLOCK: **24**
- Advisory only: sizing uncertainty is not evidence promotion; UNKNOWN != PASS; no auto-trade.
- 603596 伯特利: **BUILD** / conviction=0.8974 / max_portfolio=3.0%
- 603198 迎驾贡酒: **PROBE** / conviction=0.6236 / max_portfolio=0.75%

## Terminal rows

- 603596 伯特利: **BUY** / ALL_HARD_GATES_PASS_AND_PE_DISCOUNT_AT_LEAST_20PCT
- 000768 中航西飞: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 000596 古井贡酒: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 601136 首创证券: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 603198 迎驾贡酒: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 003039 顺控发展: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 600338 西藏珠峰: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 002758 浙农股份: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 600406 国电南瑞: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 600318 新力金融: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 000096 广聚能源: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 600523 贵航股份: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 002530 金财互联: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 002420 毅昌科技: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 603098 森特股份: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 601601 中国太保: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 601628 中国人寿: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 600547 山东黄金: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 603268 松发股份: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 601318 中国平安: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 000833 粤桂股份: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 601069 西部黄金: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 000703 恒逸石化: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 603993 洛阳钼业: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 601336 新华保险: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 603038 华立股份: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 000415 渤海租赁: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 002215 诺 普 信: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 603986 兆易创新: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 001316 润贝航科: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 600309 万华化学: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 000557 西部创业: **REJECT** / HARD_GATE_FAIL

# GenGe V3.1 Deep Decision Closure V2

- decision ready: **3/32** (9.4%)
- evidence complete: **1/32** (3.1%)
- FULL_EVIDENCE: **1**
- DECISION_READY_WITH_UNCERTAINTY: **1**
- DECISIVE_REJECT: **1**
- RESEARCH_REQUIRED: **29**
- UNKNOWN remains UNKNOWN. Bounded uncertainty never grants Formal BUY or auto-trade.

- 603596 伯特利: **FULL_EVIDENCE**; decision_ready=True; unknown=NONE
- 000768 中航西飞: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,long_term_demand,moat,financial_safety,earnings_authenticity
- 000596 古井贡酒: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,long_term_demand,moat,financial_safety,earnings_authenticity
- 601136 首创证券: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,long_term_demand,moat,financial_safety,earnings_authenticity
- 603198 迎驾贡酒: **RESEARCH_REQUIRED**; decision_ready=False; unknown=long_term_demand,moat
- 003039 顺控发展: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,long_term_demand,moat,financial_safety,earnings_authenticity
- 600338 西藏珠峰: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,moat
- 002758 浙农股份: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,long_term_demand,financial_safety,earnings_authenticity
- 600406 国电南瑞: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,long_term_demand,moat,financial_safety,earnings_authenticity
- 600318 新力金融: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,long_term_demand,moat,financial_safety,earnings_authenticity
- 000096 广聚能源: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,long_term_demand,moat,financial_safety,earnings_authenticity
- 600523 贵航股份: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,long_term_demand,moat,financial_safety,earnings_authenticity
- 002530 金财互联: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,long_term_demand,moat,financial_safety,earnings_authenticity
- 002420 毅昌科技: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,long_term_demand,moat,financial_safety,earnings_authenticity
- 603098 森特股份: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,long_term_demand,moat,financial_safety,earnings_authenticity
- 601601 中国太保: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,long_term_demand,moat,financial_safety,earnings_authenticity
- 601628 中国人寿: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,long_term_demand,moat,financial_safety,earnings_authenticity
- 600547 山东黄金: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,moat,financial_safety,earnings_authenticity
- 603268 松发股份: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,long_term_demand,moat
- 601318 中国平安: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,long_term_demand,moat,financial_safety,earnings_authenticity
- 000833 粤桂股份: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,long_term_demand,moat,financial_safety,earnings_authenticity
- 601069 西部黄金: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,moat
- 000703 恒逸石化: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,long_term_demand,moat,financial_safety,earnings_authenticity
- 603993 洛阳钼业: **DECISION_READY_WITH_UNCERTAINTY**; decision_ready=True; unknown=predictability
- 601336 新华保险: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,long_term_demand,moat
- 603038 华立股份: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,long_term_demand,moat,financial_safety,earnings_authenticity
- 000415 渤海租赁: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,long_term_demand,moat,financial_safety,earnings_authenticity
- 002215 诺 普 信: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,long_term_demand,moat,financial_safety,earnings_authenticity
- 603986 兆易创新: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,financial_safety,earnings_authenticity
- 001316 润贝航科: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,long_term_demand,moat
- 600309 万华化学: **RESEARCH_REQUIRED**; decision_ready=False; unknown=predictability,long_term_demand,financial_safety,earnings_authenticity
- 000557 西部创业: **DECISIVE_REJECT**; decision_ready=True; unknown=long_term_demand,moat
