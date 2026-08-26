# GenGe V3.2 Round 8/9 Frozen Contract

Status: frozen before the first Round 8 result. This contract authorizes exactly
Round 8 discovery OOS and Round 9 untouched confirmation OOS. It does not
authorize Round 10, parameter search, or result-driven universe replacement.

## Candidate contract

- Base model: unchanged Round-6/7 strict-PIT normalized-earnings expectation-gap model.
- Valuation: 10 years, 10% discount rate, growth fades to 3%, terminal multiple `1/(r-g)`.
- Realistic growth: `clip(min(three-year normalized EPS CAGR, three-year revenue CAGR + 5pp), 0%, 30%)`.
- BUY bands: price/neutral `<=0.85`, `<=0.75`, `<=0.65`; unchanged.
- SELL bands: price/neutral `>=1.20`, `>=1.40`, `>=1.70`; unchanged.
- Cost basis is never an input to SELL.
- Hard Gate FAIL always returns `EXIT`, before every confidence or confirmation rule.

## Valuation Confidence Gate

`INVALID` means a required price, normalized earnings, realistic growth,
market-implied growth, neutral value, or PIT-integrity input is invalid.

`LOW` means the model is numerically executable but at least one material input
is weak: fewer than three positive normalized observations, deduct-profit factor
below 0.50, non-positive cash conversion, realistic-growth four-report range
above 15pp, failed valuation/financial diagnostic, or unreliable implied growth.

`MEDIUM` means the inputs are usable but less robust: exactly three normalized
observations, deduct-profit factor below 0.80, cash conversion below 0.80,
routing confidence below 0.80, realistic growth at the 0%/30% model boundary,
or four-report growth range above 10pp.

Everything else is `HIGH`. `LOW` and `INVALID` always return `HOLD_REVIEW`; they
cannot produce a mechanical valuation BUY or SELL. HIGH/MEDIUM use the unchanged
V3.1 valuation bands.

## SELL candidate and fallback

- Full V3.2 candidate: the first monthly valuation SELL is
  `HOLD_REVIEW / VALUATION_SELL_CONFIRMATION_PENDING`; the second consecutive
  monthly SELL condition executes the current V3.1 reduction band.
- V3.1.1 gate-only fallback: uses the Confidence Gate but retains the immediate
  V3.1 SELL ladder.
- A hard-gate failure never waits for monthly confirmation.

## Frozen OOS universes

Round 8 discovery:

| code | name |
| --- | --- |
| 600031 | 三一重工 |
| 002008 | 大族激光 |
| 002920 | 德赛西威 |
| 600588 | 用友网络 |
| 600519 | 贵州茅台 |
| 601088 | 中国神华 |
| 601877 | 正泰电器 |
| 600276 | 恒瑞医药 |

Round 9 untouched confirmation:

| code | name |
| --- | --- |
| 601766 | 中国中车 |
| 002444 | 巨星科技 |
| 002415 | 海康威视 |
| 600536 | 中国软件 |
| 000895 | 双汇发展 |
| 600188 | 兖矿能源 |
| 600580 | 卧龙电驱 |
| 600809 | 山西汾酒 |

No security above appears in the Round 1-7 valuation-OOS universes. Round 9's
universe is frozen before Round 8 is run and cannot be replaced after seeing a
result.

## Comparators and promotion decision

Each round saves CURRENT_V31_BASELINE, V31_1_CONFIDENCE_GATE_ONLY,
V32_CANDIDATE, UNIVERSAL_GEOMEAN, corrected TRUE_BUYHOLD, and CSI300.

After Round 9, full V3.2 passes when all integrity/tests pass and, versus
CURRENT_V31_BASELINE on Round 9:

- Sharpe is not lower;
- maximum drawdown is not worse by more than 5 percentage points;
- CAGR is not lower by more than 1.5 percentage points;
- average cash is below 80%;
- completed 12m and 24m median post-SELL maximum upside is not worse by more
  than 5 percentage points (use all SELL events if fewer than five regime-entry
  observations are complete).

Near-boundary results prioritize economic logic, risk-adjusted return and
stability as instructed. The terminal choice is exactly one of:

1. `PROMOTE_V32_TO_PRODUCTION`;
2. `PROMOTE_CONFIDENCE_GATE_ONLY`;
3. `KEEP_V31_PRODUCTION`.

Round 9 ends parameter changes for this version. Further model research requires
an explicit future request to start V3.3 in a separate research module/branch.
