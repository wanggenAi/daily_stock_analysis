# GenGe Production Model

## Current production version

`GEN_GE_V3_1_1_PRODUCTION` (`GenGe V3.1.1 Production`)

Production decision: `PROMOTE_CONFIDENCE_GATE_ONLY`.

The model is frozen. Future research cannot directly change this module. A
future V3.3 requires an explicit request, separate research code/branch, frozen
out-of-sample tests, and a new promotion decision while V3.1.1 remains live.

## Scope

Production BUY eligibility covers Shanghai main-board `600/601/603/605` and
Shenzhen main-board `000/001/002/003` ordinary A shares. Other markets and
boards remain research-only. Outputs support candidates and confirmed holdings
and are manual decision support, not broker orders.

## BUY logic

BUY keeps the complete frozen V3.1 order:

1. predictability, long-term demand, moat, financial safety and earnings
   authenticity hard gates must all PASS;
2. A1/A2/A3 qualification and the 100-point score must be complete;
3. normalized earnings, pessimistic/neutral/optimistic/extreme-stress values,
   realistic growth, market-implied growth, expectation gap, downside,
   risk-adjusted CAGR and falsification must be complete;
4. the explicit quality, expectation-gap, valuation, risk/reward, exposure and
   market-position buy conditions must PASS;
5. price/neutral must reach the unchanged margin-of-safety BUY range, with
   reference bands at 0.85, 0.75 and 0.65;
6. Valuation Confidence must be HIGH or MEDIUM.

If the security has no position and BUY is not fully proven, the action is
`WAIT`. LOW/INVALID confidence never produces a mechanical BUY.

## SELL logic

V3.1.1 retains the original immediate V3.1 intrinsic-value contract:

- below neutral: `HOLD`;
- price/neutral at least 1.00: `HOLD_NO_ADD`;
- at least 1.20: `REDUCE_25` (75% target);
- at least 1.40: `REDUCE_50` (50% target);
- at least 1.70: `CORE_ONLY` (25% target);
- any hard-gate FAIL: `EXIT` (0% target), overriding confidence and valuation.

The rejected V3.2 two-month SELL confirmation is not in production. Personal
purchase cost, unrealized profit and recovery-to-break-even are never SELL
inputs. They may be displayed only for position reconciliation.

## Valuation logic

The promoted expectation-gap research uses normalized clean earnings and a
10-year earning-power model: 10% discount rate, realistic growth fading toward
3%, and terminal multiple `1/(r-g)`. Realistic growth is constrained by both
normalized-EPS and revenue support and clipped to 0%-30%. The model reverse
solves the growth implied by market price and reports:

- normalized earnings;
- realistic growth;
- market-implied growth;
- expectation gap;
- neutral value;
- price/neutral.

Industry-specific executed valuation can supply the frozen V3.1 scenario fields
when its semantics are equivalent and auditable. Missing or inconsistent inputs
do not receive a synthetic value.

## Valuation Confidence

`INVALID` covers missing/non-positive required valuation inputs or failed PIT
integrity. `LOW` covers materially weak earnings history/quality, cash
conversion, diagnostics or unstable growth. `MEDIUM` covers usable but less
robust inputs. Complete robust inputs are `HIGH`.

LOW/INVALID always returns `HOLD_REVIEW` and cannot create valuation BUY,
REDUCE or CORE_ONLY. Hard Gate FAIL remains the only higher-priority override
and always returns EXIT.

## HOLD_REVIEW conditions

`HOLD_REVIEW` is required for missing normalized earnings, realistic/implied
growth, neutral value or price; failed or incomplete valuation/financial
diagnostics; LOW/INVALID valuation confidence; or otherwise unreviewable
current data. It is a safe request for evidence/valuation refresh, not a hidden
BUY or SELL.

## Data requirements

- strict PIT financial availability uses the later profit/cash-flow notice date;
- mutable update timestamps cannot move financial data backward in time;
- daily price and valuation must be dated and code-normalized;
- normalized earnings and confidence inputs must preserve source provenance;
- current holdings require explicit user evidence; cost is display-only;
- production reports must include reason codes and all valuation fields above.

## Not suitable for

- automatic broker execution or intraday high-frequency trading;
- STAR, ChiNext, BSE or non-A-share production BUY signals;
- companies whose economics cannot be represented by the executed and reviewed
  valuation model;
- decisions based only on technical momentum, popularity, low PE/PB or the
  holder's cost basis.

## Known risks

- strict confidence protection can leave many names in HOLD_REVIEW and retain
  cash;
- valuation inputs and qualitative hard gates still require reliable current
  evidence and can be unavailable between filings;
- some sectors need specialized valuation rather than the generic 10-year
  earnings model;
- SELL can be followed by further price gains; this is not itself a model bug;
- OOS is fixed-universe valuation/execution testing, not a historical replay of
  every qualitative moat judgment.
