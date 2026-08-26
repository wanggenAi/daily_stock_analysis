# GenGe Model Changelog

## V3.1 -> V3.1.1 Production

Production version: `GEN_GE_V3_1_1_PRODUCTION`.

Promotion decision: `PROMOTE_CONFIDENCE_GATE_ONLY`.

Unchanged from V3.1:

- all five hard gates, A1/A2/A3 qualification and score weights;
- Shanghai/Shenzhen main-board execution universe;
- normalized-earnings/scenario/expectation-gap BUY requirements;
- margin-of-safety BUY references at 0.85/0.75/0.65;
- immediate valuation SELL ladder at 1.00/1.20/1.40/1.70;
- Hard Gate FAIL -> EXIT;
- personal cost basis is never a SELL input;
- human execution only.

Added in V3.1.1:

- explicit Valuation Confidence HIGH/MEDIUM/LOW/INVALID;
- LOW/INVALID -> HOLD_REVIEW before mechanical valuation BUY/SELL;
- one production action vocabulary: BUY, WAIT, HOLD, HOLD_NO_ADD,
  HOLD_REVIEW, REDUCE_25, REDUCE_50, CORE_ONLY, EXIT;
- production outputs for normalized earnings, realistic/implied growth,
  expectation gap, neutral value, price/neutral, confidence and reason codes;
- candidate and confirmed-holding production scanner integration;
- immutable production version and separate frozen research candidate version.

Not promoted:

- V3.2's two-consecutive-month valuation SELL confirmation. It passed return,
  Sharpe, drawdown, cash and integrity thresholds on Round 9, but failed the
  pre-frozen 12-month SELL opportunity-cost limit. It remains research evidence,
  not production behavior.

## Validation record

Round 8 discovery passed all frozen candidate thresholds. Round 9 untouched
confirmation passed PIT, confidence, Sharpe, drawdown, CAGR and average-cash
checks. Full V3.2 failed only SELL opportunity cost, so the predeclared fallback
V3.1.1 was promoted without further tuning.

No Round 10 or later optimization is authorized. Research resumes only after an
explicit request to start V3.3.
