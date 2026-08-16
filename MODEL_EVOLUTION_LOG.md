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

- `688012 中微公司`: 2026Q1 headline profit was materially higher than recurring/core profit because of investment income and fair-value gains. A model capitalizing headline profit would overstate sustainable earnings.
- `688072 拓荆科技`: 2026Q1 headline profit was heavily affected by fair-value-change gains while recurring profit was much smaller. This is a direct earnings-quality failure case.
- `301308 江波龙` and `688525 佰维存储`: 2026 memory-cycle profits accelerated dramatically. Treating peak/current-cycle earnings as a permanent normalized base would overvalue a cyclical boom.

### Model gaps identified

1. Headline profit, recurring/core operating profit, and non-operating asset value must be separated.
2. `forward_cycle_profit` and `through_cycle_normalized_profit` must be separate concepts for cyclical industries.
3. Removing non-recurring gains from earnings must **not** implicitly value the underlying investment/non-operating assets at zero.
4. Missing cycle-normalization assumptions must fail closed rather than invent a haircut.

### Code change

Draft PR: `#25 feat: add fundamental reverse valuation core`

Branch:

```text
feat/fundamental-reverse-valuation
```

Initial commits:

```text
71b551d3f5b21e4f8b5eea3fa094356800cb5b76  Add fundamental valuation core
3a84398944412e55feed3058c18ffe232b084d18  Test fundamental valuation core
```

New valuation primitives include:

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

- no arbitrary cycle haircut is hardcoded;
- cyclical names without explicit through-cycle evidence stay LOW confidence / normalization required;
- negative normalized profit returns `PE_MODEL_NOT_APPLICABLE`;
- missing market cap/multiple does not produce fake implied profit;
- NaN/None inputs fail closed;
- this first PR does not alter Formal BUY, Risk-Capped, market regime, entry, stop, exit, invalidation, or position sizing.

### Validation status

- Targeted unit tests are included in PR #25.
- Local test execution was not available in the originating ChatGPT container because that container could not resolve `github.com` for cloning.
- GitHub CI/review is the executable validation path before production integration.
- PR #25 is deliberately a draft and does not yet wire the valuation core into the production opportunity pipeline.

### Follow-up integration

After the valuation core passes validation:

1. map verified provider financial fields into the valuation input contract;
2. add data-freshness fields and fail-closed current-price requirements;
3. expose valuation diagnostics in the Research Pool / reports;
4. add the new valuation/fundamental score to research ranking without making it a single dominant factor;
5. keep Formal BUY gates unchanged until separately tested;
6. account for the open Factor-IC / sector-regime work (PR #23) and avoid duplicated/conflicting pipeline wrappers.

## 2026-08-16 — Forward share-count / dilution awareness

### Triggering live case

- `688120 华海清科`: multi-year fair-value work exposed that 2027/2028 per-share valuation can be wrong when today's share count is reused despite known equity incentives / financing issuance. Third-party consensus EPS may also use a different share-count denominator around capital changes.

### Model gap identified

A multi-year equity valuation needs to distinguish:

```text
current_shares
known_or_explicit_potential_shares
valuation_shares
current_share_fair_price
diluted_fair_price
```

Forecast net profit plus an explicit share-count bridge is safer than blindly trusting third-party EPS after bonus issues, equity incentives, private placements or other capital changes.

### Code change

PR #25 was extended with dilution-aware share-count primitives and tests.

Safety behavior:

- no arbitrary future dilution rate is invented;
- only explicit/verified potential-share inputs are used;
- current-share and diluted per-share fair values remain separately visible;
- missing future share-count information lowers confidence rather than silently assuming zero dilution.

## 2026-08-16 — R&D capitalization earnings-quality diagnostic

### Triggering live case

- `300604 长川科技`: 2025 annual report disclosed total R&D investment of about 12.68 亿 RMB, R&D expense of about 9.36 亿 RMB and capitalized R&D of about 3.32 亿 RMB. The capitalization rate rose to 26.18% from 5.63% in 2024. The company explicitly stated that the decline in R&D expense was related to increased capitalization from newly capitalized semiconductor-equipment R&D projects.

### Model gap identified

A sharp change in R&D capitalization policy can make reported profit growth look stronger than an economic comparison made under a constant capitalization policy, even when headline and recurring profit are otherwise clean.

This is **not** evidence of improper accounting by itself. The model needs a diagnostic, not an automatic rejection/restatement.

Required concepts:

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

### Code change

PR #25 was extended with:

```text
src/strategies/genge_opportunity_discovery/rnd_capitalization.py
tests/test_genge_rnd_capitalization.py
```

Safety behavior:

- capitalization is not automatically treated as aggressive or improper;
- no baseline capitalization rate is inferred automatically;
- no normalized net-profit adjustment is produced without an explicit baseline capitalization rate **and** effective tax rate;
- the output is an earnings-quality sensitivity test, not an accounting restatement;
- a material R&D reconciliation gap lowers confidence.

### Live stress-test interpretation

Using 2024's 5.63% capitalization rate purely as a comparison baseline, 2025 additional capitalized R&D versus that baseline is about 2.61 亿 RMB. With an explicit 15% tax-rate stress assumption, adjusted attributable profit would be about 2.22 亿 RMB lower than reported, roughly a 16.6% sensitivity. This is a research stress scenario only and must never replace reported financial statements.

## 2026-08-16 — Fresh price-source priority refined

### Triggering live case

Public web search indexes failed to return reliable 2026-08-14 closes for several A-shares even though fresh fundamental data was available.

The repository's own completed full-A production artifact for 2026-08-14 provided:

```text
price_data_coverage_ratio: 1.0
raw price source: tencent_raw
qfq source: akshare_sina_qfq
explicit latest_trade_date per security
```

For `300604 长川科技`, the artifact verified a 2026-08-14 close of 283.05 RMB.

### Research data-source priority

For ongoing ChatGPT/Codex research on this repository, prefer:

```text
latest completed repository production snapshot
  -> authoritative exchange/company filing data for fundamentals/events
  -> direct stable market-data provider / secondary public source
  -> web-search indexed quote page as fallback
```

Never use an older searchable quote merely because it is easier to retrieve when a newer validated production snapshot exists.

This is a research-handoff/data-governance rule. Production data-provider changes remain subject to separate code review and testing.

## 2026-08-16 — Financial-asset-income double-count guard

### Triggering live case

- `688019 安集科技`: the company has a meaningful cash/financial-asset balance, while recurring/扣非 net profit still includes recurring interest/financial income effects. A valuation that multiplies that equity-profit number by a PE-like multiple **and then adds net cash again** can count the same cash economics twice.

### Model gap identified

The model must distinguish two valid but different approaches:

```text
plain equity PE on recurring/equity net profit
```

versus:

```text
core operating / asset-bridge profit × multiple
+ verified non-operating financial assets / net cash
```

The second approach requires stripping explicitly verified after-tax financial income from the profit base and adding back explicitly verified after-tax financing cost before separately bridging net cash/assets.

### Code change

PR #25 was extended with:

```text
src/strategies/genge_opportunity_discovery/financial_asset_bridge.py
tests/test_genge_financial_asset_bridge.py
```

Safety behavior:

- no tax rate is guessed;
- no financial-asset yield is guessed;
- only explicit interest income, interest expense and recurring investment income are adjusted;
- incomplete finance-line detail is flagged rather than silently claimed complete;
- plain equity-PE valuation does not require this adjustment if net cash is not separately added.

## 2026-08-16 — Primary financing dilution must include proceeds

### Triggering live case

- `688019 安集科技`: the company's H-share plan creates a potential future share-count increase, but unlike equity incentive dilution, a primary H-share issuance also brings capital into the company. Treating all potential financing shares as denominator-only dilution would mechanically undervalue post-financing per-share equity value.

### Model gap identified

Primary financing requires an explicit two-sided bridge:

```text
post_financing_equity_value = pre_financing_equity_value + verified_net_proceeds
post_financing_shares = current_shares + financing_shares
post_financing_fair_price = post_financing_equity_value / post_financing_shares
```

No future ROIC on the proceeds should be assumed unless separately modeled.

### Code change

PR #25 was extended with:

```text
src/strategies/genge_opportunity_discovery/financing_dilution.py
tests/test_genge_financing_dilution.py
```

Safety behavior:

- announced financing shares without an issue price or verified net proceeds do not generate a fake post-financing fair price;
- verified net proceeds take priority over a gross issue-price approximation;
- financing dilution stays separate from zero/low-proceeds incentive dilution;
- no assumed reinvestment return is embedded automatically.

## 2026-08-16 — Segment-aware cycle normalization

### Triggering live case

- `603986 兆易创新`: memory represented roughly 71% of 2025 product revenue and about 76% of disclosed product gross profit, while MCU, sensors and analog products had materially different earnings durability. A single company-level `is_cyclical` flag would either over-haircut the stable platform segments or under-haircut peak memory earnings.

### Model gap identified

Mixed business models require segment-level cycle treatment:

```text
segment_forward_profit
segment_is_cyclical
segment_through_cycle_profit OR segment_through_cycle_ratio
aggregate_forward_profit
aggregate_through_cycle_normalized_profit
cycle_exposure_ratio
```

The primitive must not infer segment net profit from revenue or gross profit automatically.

### Code change

PR #25 was extended with:

```text
src/strategies/genge_opportunity_discovery/segment_cycle_blend.py
tests/test_genge_segment_cycle_blend.py
```

Safety behavior:

- cyclical segments require explicit through-cycle assumptions;
- non-cyclical segments can retain forward profit by default;
- any unnormalized cyclical segment makes aggregate normalized profit unavailable;
- no company-wide arbitrary cycle haircut is substituted for missing segment evidence.

## 2026-08-16 — Multi-share-class market-cap bridge

### Triggering live case

- `603986 / 03986 兆易创新/GigaDevice`: after the H-share listing, the company had both A and H shares outstanding. Multiplying the A-share quote by total A+H shares would incorrectly label an A-price-implied equity value as actual consolidated market cap.

### Model gap identified

For dual/multi-listed share classes:

```text
actual consolidated market cap = Σ(class shares × class price × explicit FX)
```

A reference-class quote may still be useful to calculate a separately labelled price-implied total equity value, but it is not actual market cap.

### Code change

PR #25 was extended with:

```text
src/strategies/genge_opportunity_discovery/share_class_market_cap.py
tests/test_genge_share_class_market_cap.py
```

Safety behavior:

- each class requires explicit shares, quote and FX conversion;
- missing class quote/FX returns `INCOMPLETE_SHARE_CLASS_PRICING`;
- the reference-class implied total equity value remains separately visible;
- no A/H premium or discount is guessed.

## Resume rule

A new session working on market/model research should read:

```text
AGENTS.md
CURRENT_MARKET_RESEARCH.md
MODEL_EVOLUTION_LOG.md
latest MARKET_RESEARCH_LOG_*.md
```

Then inspect current `main`, open valuation/factor PRs, and fetch fresh market data before continuing analysis.