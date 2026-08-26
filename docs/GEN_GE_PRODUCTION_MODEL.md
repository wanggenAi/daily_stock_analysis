# GenGe Production Model

## Current production version

`GEN_GE_V3_1_1_PRODUCTION` (`GenGe V3.1.1 Production`)

Production decision: `PROMOTE_CONFIDENCE_GATE_ONLY`.

Authoritative production policy source:

`gen_ge_v3_1_1_confidence_gate_only_round8_round9_validated`

The implementation entry point is `production_model.py`, which delegates to
`selection_framework_v311.py`. Production does **not** import or execute
`selection_framework_v32.py`. The rejected V3.2 two-month SELL confirmation is
explicitly disabled.

The model is frozen. Future research cannot directly change this module. A
future model version requires an explicit user request, separate research code,
frozen out-of-sample tests and a new promotion decision while V3.1.1 remains
live.

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
4. the explicit valuation/risk/exposure/market-position V3.1 buy conditions
   must PASS;
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

## Exact V3.1.1 Valuation Confidence contract

This section is intentionally narrow: it documents the confidence gate that was
actually used by the frozen Round-8/9 `v31_1_confidence_gate_only` variant. It
must not silently inherit additional V3.2 research rules.

Required finite current inputs are current price, positive normalized earnings,
realistic growth, market-implied growth and positive neutral value. Missing or
non-positive required valuation inputs are `INVALID`. When both a financial
availability date and decision date are provided, a financial date later than
the decision date is also `INVALID`.

With required valuation inputs valid, confidence is `LOW` if any of the
following frozen Round-8/9 conditions is true:

- normalized-earnings observation count is below 3;
- deduct-profit quality factor is missing or below 0.50;
- cash conversion is missing or non-positive;
- four-report realistic-growth range is above 0.15;
- implied-growth status is `INPUT_INCOMPLETE` or
  `IMPLIED_ABOVE_SEARCH_RANGE`.

It is `MEDIUM` when no LOW condition exists but any of these conditions is true:

- normalized-earnings observation count is below 4;
- deduct-profit quality factor is below 0.80;
- cash conversion is below 0.80;
- four-report realistic-growth range is above 0.10;
- realistic growth is at either frozen model boundary (<=0% or >=30%).

Otherwise confidence is `HIGH`.

LOW/INVALID always returns `HOLD_REVIEW` and cannot create mechanical valuation
BUY, REDUCE or CORE_ONLY. Hard Gate FAIL remains the higher-priority override
and always returns EXIT. MEDIUM/HIGH preserves the original immediate V3.1
valuation action.

Fields introduced only by the research-only V3.2 confidence implementation —
for example valuation routing confidence, generic execution-state checks or
extra financial-review status gates — are **not** part of this promoted V3.1.1
confidence contract.

## Policy-parity protection

A historical upstream candidate row is not trusted merely because it carries
`GEN_GE_V3_1_1_PRODUCTION`. Earlier code briefly used that same human-facing
version label while delegating to a different V3.2-backed implementation.

`production_decision_scan.py` therefore reuses an upstream decision only when
both of these fields match the current frozen contract:

- `production_model_version == GEN_GE_V3_1_1_PRODUCTION`;
- `production_policy_source == gen_ge_v3_1_1_confidence_gate_only_round8_round9_validated`.

Otherwise the row is recomputed through the current production model. Reports
record whether an upstream exact-policy decision was reused.

## HOLD_REVIEW conditions

`HOLD_REVIEW` is required when the V3.1 valuation itself is incomplete, or when
the exact V3.1.1 confidence gate is LOW/INVALID. It is a safe request for an
evidence/valuation refresh, not a hidden BUY or SELL.

## Data requirements

- strict PIT financial availability uses the later profit/cash-flow notice date;
- mutable update timestamps cannot move financial data backward in time;
- daily price and valuation must be dated and code-normalized;
- normalized earnings and confidence inputs must preserve source provenance;
- current holdings require explicit user evidence; cost is display-only;
- production reports must include the exact policy source, reason codes and all
  valuation fields above.

## Historical simulator integrity

The Round-8/9 final execution replay corrected a simulator-only issue without
changing economic parameters: sparse-symbol returns are never forward-filled,
missing/suspended quote days contribute zero return, and execution requires an
observed valid quote on that exact date. The frozen confidence-gate promotion
survived this corrected replay.

## Not suitable for

- automatic broker execution or intraday high-frequency trading;
- STAR, ChiNext, BSE or non-A-share production BUY signals;
- companies whose economics cannot be represented by the executed and reviewed
  valuation model;
- decisions based only on technical momentum, popularity, low PE/PB or the
  holder's cost basis.

## Known risks

- confidence protection can leave names in HOLD_REVIEW and retain cash;
- valuation inputs and qualitative hard gates still require reliable current
  evidence and can be unavailable between filings;
- some sectors need specialized valuation rather than the generic 10-year
  earnings model;
- SELL can be followed by further price gains; this is not itself a model bug;
- OOS is fixed-universe valuation/execution testing, not a historical replay of
  every qualitative moat judgment.
