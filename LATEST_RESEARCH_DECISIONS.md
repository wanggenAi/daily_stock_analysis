# GenGe V3.1 Terminal Research Decisions

- requested: **16**
- BUY: **1** / WAIT_PRICE: **0** / RESEARCH_GAP: **15** / REJECT: **0**
- all requested terminal: **True**
- authority: **RESEARCH_ONLY**; Formal/Production authority unchanged; UNKNOWN != PASS; no auto-trade.

## Urgent evidence queue

- 600406 国电南瑞: quant=37.7596, PE/history=0.8265532544378699, unknown=predictability,long_term_demand,moat,financial_safety,earnings_authenticity, financial_blockers=CASH_CONVERSION_RATIO_BELOW_PASS_THRESHOLD,EARNINGS_QUALITY_SCORE_BELOW_PASS_THRESHOLD, urgent=P0_EVIDENCE_BLOCKED
- 001316 润贝航科: quant=36.2154, PE/history=0.6673434856175973, unknown=predictability,long_term_demand,moat, financial_blockers=NONE, urgent=P0_EVIDENCE_BLOCKED
- 601318 中国平安: quant=33.1137, PE/history=0.7503001200480192, unknown=predictability,long_term_demand,moat,financial_safety,earnings_authenticity, financial_blockers=EARNINGS_QUALITY_SCORE_BELOW_PASS_THRESHOLD, urgent=P0_EVIDENCE_BLOCKED
- 603993 洛阳钼业: quant=31.3451, PE/history=0.7479546054367907, unknown=predictability, financial_blockers=NONE, urgent=P0_EVIDENCE_BLOCKED

## Risk-budget capital advisory

- BUILD: **1** / PROBE: **1** / WATCH: **2** / BLOCK: **12**
- Advisory only: sizing uncertainty is not evidence promotion; UNKNOWN != PASS; no auto-trade.
- 603596 伯特利: **BUILD** / conviction=0.945 / max_portfolio=3.0%
- 603105 芯能科技: **PROBE** / conviction=0.596 / max_portfolio=0.72%

## Terminal rows

- 603596 伯特利: **BUY** / ALL_HARD_GATES_PASS_AND_PE_DISCOUNT_AT_LEAST_20PCT
- 603105 芯能科技: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 002042 华孚时尚: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 603369 今世缘: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 600610 中毅达: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 600640 国脉文化: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 600816 建元信托: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 002537 海联金汇: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 000504 南华生物: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 600406 国电南瑞: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 002375 亚厦股份: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 001316 润贝航科: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 000703 恒逸石化: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 601318 中国平安: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 603993 洛阳钼业: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
- 601020 华钰矿业: **RESEARCH_GAP** / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY
