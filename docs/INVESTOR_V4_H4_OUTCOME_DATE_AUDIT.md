# V4 H4: historical forward-outcome date-integrity hardening (partial)

## Verified root cause (2026-09-28)

The existing downstream observer in `src/strategies/genge_opportunity_discovery/formal_decision_outcomes.py` previously keyed every `data/hourly_deep_overlay/YYYY-MM-DD/*.json` entry by the *report generation* date. Genuine `data/hourly_deep_overlay/2026-09-28/07.json` was published 2026-09-28, but the authoritative snapshot `latest_trade_date` and all four quoted equity observations are actually 2026-09-24. Counting that report under 2026-09-28 manufactures later forward-observation dates from stale prices, and multiple identical Formal snapshots of an unchanged HOLD can additionally inflate the apparent sample.

This small fix **does not replace the observer or any investment model**. Its ingestion now requires the explicit original `latest_trade_date`, a six-digit equity code, finite positive price, explicit provider, `latest_price_status=OK`, offset-aware original `latest_price_observed_at`, same actual Shanghai-local market date, and observation not earlier than 15:00 Shanghai. Multiple hourly/replayed reports from the same real source date count as **one** trading-date observation, using the latest valid original observation time (not file iteration or generation time). Missing/mismatched data yield no observation.

## Boundaries and remaining acceptance gaps

- This is a **date-integrity and freshness fix only**. Quote values still represent *unadjusted provider reference prices*, not independently proven official daily close or split/dividend-adjusted prices. They MUST NOT be reported as a fully validated investment recommendation backtest; the result explicitly sets `corporate_action_adjustment_verified=false`, `independent_benchmark_verified=false`, and `full_v4_h4_acceptance=false`.
- Grouped historical outcome statistics from older main/artifacts are **not retroactively proven** and should not be featured as trustworthy unique trade performance until recomputed against real validated market dates and distinct material decision epochs. This patch does **not** claim to deduplicate separate Canonical snapshots with unchanged Formal actions.
- Next H4 phases, in the *existing* observer: validate a separate clean exchange-session EOD reference with adjustments, benchmark/industry comparison, original epoch/signal deduplication, target date quality, and observable drawdown. Independently verified account fills/fees are separately necessary to compute personal realized P&L. No automatic tuning or Formal authority.
- The existing full production scorecard must be regenerated via its already established publisher and its actual original-source and underlying as-of artifacts audited; green PR CI is not production acceptance.

## Scope & tests

Changed only the existing observer ingestion/metadata and tests. Included regression fixtures for the real stale publication-versus-price-date example, absent/bad timezone, mismatched quoted date, pre-close observation, unavailable provider, stale quote status, and multiple genuine observations of a single date. No model, BUY thresholds, cash, brokerage or auto-trading changes.
