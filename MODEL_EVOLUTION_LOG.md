# Model Evolution Log

> Durable record of model changes triggered by real market/stock analysis.
>
> This document explains **why** the research model changes. `AGENTS.md` and actual repository code remain the source of truth for implementation behavior.

## Working rule

A live analysis may trigger a model/code improvement only when it reveals a concrete and reproducible failure mode.

Workflow:

```text
fresh market/fundamental data
  -> live analysis
  -> identify reproducible model failure
  -> record evidence / counterexample
  -> minimal model change
  -> regression test
  -> CI / review
  -> production integration only after validation
```

Do not add decorative indicators merely because a new metric is available. Preserve existing Formal BUY, Risk-Capped, market-regime, entry, exit, stop, invalidation, and position-sizing controls unless a separately validated change explicitly targets them.

## 2026-08-16 — Fundamental reverse-valuation core

### Triggering live cases

- `688012 中微公司`: headline profit materially exceeded recurring/core profit because of investment/fair-value gains.
- `688072 拓荆科技`: headline profit was heavily affected by fair-value gains.
- `301308 江波龙` and `688525 佰维存储`: peak/current-cycle memory earnings could not be treated as permanent normalized earnings.

### Model gaps identified

1. Headline profit, recurring/core operating profit, and non-operating asset value must be separated.
2. `forward_cycle_profit` and `through_cycle_normalized_profit` must be separate concepts for cyclical industries.
3. Removing non-recurring gains from earnings must not implicitly value the underlying investment/non-operating assets at zero.
4. Missing cycle-normalization assumptions must fail closed rather than invent a haircut.

### Code change

Draft PR: `#25 feat: add fundamental reverse valuation core`
Branch: `feat/fundamental-reverse-valuation`

Core primitives include:

```text
normalized_core_operating_profit
recurring_profit_ratio
non_recurring_profit_share
earnings_quality_score
forward_cycle_profit
through_cycle_normalized_profit
peak_earnings_discount
cycle_profit_gap
core_operating_value
non_operating_asset_value
net_cash_or_investment_adjustment
fair_equity_value
implied_core_profit
required_profit_growth
expectation_gap
bear/base/bull scenario bridge
```

Safety behavior:

- no arbitrary cycle haircut;
- negative normalized profit => PE model not applicable;
- missing market cap/multiple => no fake implied profit;
- NaN/None inputs fail closed;
- no changes to Formal BUY, Risk-Capped, market regime, entry, stop, exit, invalidation, or position sizing.

## 2026-08-16 — Forward share-count / dilution awareness

### Triggering live case

`688120 华海清科`: 2027/2028 per-share valuation could not reuse today's share count despite known incentive/financing issuance. Third-party consensus EPS could also use inconsistent denominators around capital changes.

### Model response

```text
current_shares
known_or_explicit_potential_shares
valuation_shares
current_share_fair_price
diluted_fair_price
```

Forecast net profit + an explicit share-count bridge is preferred to blindly trusting third-party EPS after capital changes.

Safety behavior:

- no arbitrary future dilution rate;
- only explicit/verified potential-share inputs;
- current-share and diluted fair values remain separate;
- missing future share-count information lowers confidence.

## 2026-08-16 — R&D capitalization earnings-quality diagnostic

### Triggering live case

`300604 长川科技`: 2025 total R&D investment ~12.68 亿, R&D expense ~9.36 亿, capitalized R&D ~3.32 亿; capitalization rate rose to 26.18% from 5.63% in 2024.

### Model response

```text
r_and_d_capitalization_rate
baseline_capitalization_rate
capitalization_rate_change
capitalized_r_and_d_to_net_profit
excess_capitalized_r_and_d_vs_baseline
after_tax_profit_adjustment
normalized_net_profit
earnings_quality_penalty
warning_flags
```

Safety:

- capitalization is not automatically improper;
- no baseline is inferred;
- no normalized-profit adjustment without explicit baseline + tax rate;
- diagnostic is a sensitivity test, not a financial-statement rewrite.

## 2026-08-16 — Fresh price-source priority refined

### Triggering live case

Public search indexes lagged exact 2026-08-14 A-share closes while the repository's completed full-A production artifact had full coverage.

### Research data-source priority

```text
latest completed repository production snapshot
  -> authoritative exchange/company filing data for fundamentals/events
  -> direct stable market-data provider / secondary public source
  -> web-search indexed quote page as fallback
```

Never use an older searchable quote merely because it is easier to retrieve when a newer validated production snapshot exists.

## 2026-08-16 — Financial-asset-income double-count guard

### Triggering live case

`688019 安集科技`: multiplying recurring/equity profit by a PE-like multiple and then adding net cash can double count recurring interest/financial income already present in profit.

### Model response

Distinguish:

```text
plain equity PE on recurring/equity net profit
```

from:

```text
core operating / asset-bridge profit × multiple
+ verified non-operating financial assets / net cash
```

The second method strips explicitly verified after-tax financial income and adds back explicitly verified after-tax financing cost before separately bridging assets.

Safety:

- no tax rate or financial-asset yield is guessed;
- incomplete finance detail stays flagged;
- plain equity-PE does not separately add net cash.

## 2026-08-16 — Primary financing dilution must include proceeds

### Triggering live case

`688019 安集科技`: primary H-share issuance increases share count **and** brings capital to the company. Denominator-only dilution is economically incomplete.

### Model response

```text
post_financing_equity_value = pre_financing_equity_value + verified_net_proceeds
post_financing_shares = current_shares + financing_shares
post_financing_fair_price = post_financing_equity_value / post_financing_shares
```

Safety:

- financing shares without issue price / verified net proceeds do not generate a fake post-financing fair price;
- no future ROIC on proceeds is assumed automatically.

## 2026-08-16 — Segment-aware cycle normalization

### Triggering live case

`603986 兆易创新`: memory is highly cyclical, while MCU / analog / sensor businesses are structurally steadier. A single company-level cycle haircut either over-penalizes non-memory profit or under-normalizes peak memory profit.

### Model response

Cycle normalization can now operate at segment level and aggregate into company-level normalized earnings. Missing segment profit/cycle assumptions fail closed rather than being invented.

## 2026-08-16 — Multi-share-class market-cap bridge

### Triggering live case

`603986 兆易创新`, later reinforced by `300308 中际旭创` and `300476 胜宏科技`: after A/H dual listing, `A price × A+H total shares` is not the actual consolidated market cap.

### Model response

Actual consolidated market cap requires:

```text
sum(class_shares × class_price × fx_to_reporting_currency)
```

When only one class quote is available, the model may expose:

```text
reference_class_implied_total_equity_value
```

but must never mislabel it actual consolidated market cap.

## 2026-08-16 — Future terminal value must be discounted to today

### Triggering live cases

The AI-hardware batch (`300502 新易盛`, `300308 中际旭创`, `300394 天孚通信`, `300476 胜宏科技`, `002463 沪电股份`, `002916 深南电路`, `002837 英维克`) exposed a time-value error in multi-year growth valuation.

A formula such as:

```text
2028E profit × 2028 terminal PE
```

creates a **2028 terminal equity value**. It cannot be directly compared with today's market cap unless the multiple is explicitly a *current forward P/2028E* convention.

### Model gap identified

Two multiple semantics must be separated:

```text
CURRENT_FORWARD_PE
TERMINAL_PE
```

- `CURRENT_FORWARD_PE`: today's price divided by a future earnings estimate. No extra discounting.
- `TERMINAL_PE`: a multiple assumed at a future horizon. The future equity value must be discounted to the analysis date using an explicit required return.

### Code change

PR #25 was extended with:

```text
src/strategies/genge_opportunity_discovery/valuation_horizon.py
tests/test_genge_valuation_horizon.py
```

New primitives include:

```text
valuation_horizon_years
required_return
multiple_semantics
horizon_equity_value
present_equity_value
discount_factor
required_terminal_equity_value
required_terminal_profit
required_profit_cagr
```

Core equations:

```text
terminal_equity_value = terminal_profit × terminal_PE
present_equity_value = terminal_equity_value / (1 + required_return)^years

required_terminal_equity_value = current_market_cap × (1 + required_return)^years
required_terminal_profit = required_terminal_equity_value / terminal_PE
required_profit_cagr = (required_terminal_profit/current_normalized_profit)^(1/years) - 1
```

Safety behavior:

- terminal PE with a non-zero future horizon requires an explicit required return;
- no terminal multiple, hurdle rate or growth horizon is invented;
- `CURRENT_FORWARD_PE` is not double-discounted;
- the output is a duration/expectation stress test, not an automatic target price.

### Why it matters

This refinement is central to the project's original goal. It allows a high current-PE stock to remain in the research pool when the market price requires less future profit than a credible forward earnings path, while preventing long-duration growth stocks from being overvalued by comparing an undiscounted 2028 terminal value with today's price.

## Resume rule

A new session working on market/model research should read:

```text
AGENTS.md
CURRENT_MARKET_RESEARCH.md
MODEL_EVOLUTION_LOG.md
latest MARKET_RESEARCH_LOG_*.md
```

Then inspect current `main`, open valuation/factor PRs, and fetch fresh market data before continuing analysis.