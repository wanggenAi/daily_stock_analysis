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

## Resume rule

A new session working on market/model research should read:

```text
AGENTS.md
CURRENT_MARKET_RESEARCH.md
MODEL_EVOLUTION_LOG.md
latest MARKET_RESEARCH_LOG_*.md
```

Then inspect current `main`, open valuation/factor PRs, and fetch fresh market data before continuing analysis.
