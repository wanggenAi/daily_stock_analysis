# GenGe Production Decision

Decision: `PROMOTE_CONFIDENCE_GATE_ONLY`.

Current production: `GEN_GE_V3_1_1_PRODUCTION`.

## Round 8 discovery

| variant | CAGR | Max drawdown | Sharpe | Average cash |
| --- | ---: | ---: | ---: | ---: |
| Current V3.1 baseline | 10.43% | -23.90% | 0.742 | 43.53% |
| V3.1.1 Confidence Gate | 9.65% | -18.25% | 0.781 | 47.93% |
| Full V3.2 candidate | 9.45% | -18.21% | 0.755 | 46.90% |

Strict PIT passed, future financial merges were zero, BUY/SELL direction errors
were zero, cost basis was not used, and LOW/INVALID mechanical actions were zero.
Full V3.2 passed all Round 8 frozen thresholds.

## Round 9 untouched confirmation

| variant | CAGR | Max drawdown | Sharpe | Average cash |
| --- | ---: | ---: | ---: | ---: |
| Current V3.1 baseline | 39.24% | -91.53% | 0.840 | 38.44% |
| V3.1.1 Confidence Gate | 37.81% | -26.89% | 1.243 | 39.96% |
| Full V3.2 candidate | 38.14% | -27.51% | 1.239 | 38.11% |

Strict PIT passed for all eight stocks, future financial merges were zero,
BUY/SELL direction errors were zero, cost basis was not used, and the Confidence
Gate emitted zero LOW/INVALID mechanical valuation actions.

The full V3.2 candidate failed the frozen SELL opportunity-cost check: completed
12-month regime-entry median maximum upside was 28.19% versus 9.89% for the
current V3.1 baseline, a deterioration of 18.30 percentage points versus the
allowed 5 points. This is not a near-boundary difference. The two-month SELL
confirmation is therefore rejected.

The Confidence Gate is retained because it behaved deterministically, removed
all LOW/INVALID mechanical actions, preserved CAGR within 1.5 percentage points,
raised Sharpe materially, reduced maximum drawdown materially and kept average
cash below 80%. The original immediate V3.1 SELL ladder remains production.
