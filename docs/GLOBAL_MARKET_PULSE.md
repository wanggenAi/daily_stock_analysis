# Global Market Pulse

## Purpose

A-share exchange holidays freeze only the China trading-price layer. They must not freeze research about the rest of the world.

`GenGe Global Market Pulse` therefore runs on its own global clock every hour, every day. It persists a research-only package under `data/global_market_pulse/` even when SSE/SZSE are closed.

## Current factors

The first production contract covers liquid public proxies for:

- S&P 500 and Nasdaq risk appetite
- VIX volatility
- US 10-year yield
- DXY and USD/CNH
- copper, gold and WTI crude
- Nikkei 225, Hang Seng and Euro Stoxx 50
- Bitcoin as an auxiliary global liquidity/risk-appetite proxy

The feed is deliberately independent of the A-share calendar. Per-symbol source failures are visible in `coverage.failures`; partial coverage is labelled `PARTIAL`. Complete source loss fails closed instead of publishing a false-fresh package.

## A-share transmission

Company-level transmission is intentionally conservative. This phase only maps global factors to a security when the repository already contains an explicit evidence-backed exposure mapping in `config/commodity_research_benchmarks.json`.

For example, 603993 CMOC has existing primary-source-backed COPPER/GOLD producer exposure. A material copper/gold move may therefore appear as a research-only favorable/adverse transmission signal while China is closed. Securities without explicit mappings are not guessed into a factor exposure.

## Authority boundary

The package always carries:

- `authority=RESEARCH_ONLY`
- `formal_trading_authority=false`
- `formal_action_mutation_allowed=false`
- `automatic_promotion_allowed=false`
- `no_auto_trade=true`

Global changes can raise research priority and provide reopening context. They cannot directly create a Formal BUY/SELL, mutate Canonical value anchors, infer broker cash, or place an order.

## Persistence

The workflow runs hourly but only commits when the semantic market package changes. A different `generated_at` timestamp alone does not create repository churn. Each material update writes `latest.json` and a history snapshot for auditability.

## Next integration boundary

The next bounded step is to consume this persisted package in the investor decision center as a distinct `global_market_pulse` input, preserving the authority boundary above. That integration should not be implemented by pretending an A-share holiday is a missing market session or by changing existing Formal thresholds.
