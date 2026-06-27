# GenGe Cycle Bottom Strategy Implementation Plan

## Goal

Add an independent, deterministic historical validation module for the "根哥周期底部硬逻辑策略 / GenGe Cycle Bottom Strategy".

The first phase will cover historical data scanning, signal generation, 5-year/10-year walk-forward backtesting, CSV/JSON/Markdown report output, tests, and documentation.

This module will not connect to any broker, place orders, read account data, or use an LLM to decide signals.

## Existing Modules To Reuse

- `data_provider.DataFetcherManager`
  - Reuse `get_daily_data()` for A-share daily bars and benchmark index data.
  - Keep provider failover behavior and readable data-source errors.
- `data_provider.base.normalize_stock_code`
  - Normalize A-share codes accepted by the CLI.
- `src.storage.DatabaseManager` and `src.repositories.StockRepository`
  - Keep compatibility with existing daily-bar storage, but the first strategy module will operate on DataFrames so it is easy to test and can run without mutating existing DB workflows.
- `src.core.backtest_engine`
  - Use its pure-logic style as the reference pattern; the new walk-forward engine will stay DB-agnostic.
- Existing `tests/` style
  - Add focused `unittest`/pytest-compatible tests with synthetic data.

## Files To Add

- `src/strategies/genge_cycle_bottom/__init__.py`
- `src/strategies/genge_cycle_bottom/signals.py`
  - Signal constants / enum and signal dataclass.
- `src/strategies/genge_cycle_bottom/features.py`
  - Price percentile, valuation score, financial safety, trend stabilization, market environment, no-lookahead slicing helpers.
- `src/strategies/genge_cycle_bottom/strategy.py`
  - Deterministic strategy scoring and signal classification.
- `src/strategies/genge_cycle_bottom/backtest.py`
  - Walk-forward scan and future return / drawdown / benchmark comparison.
- `src/strategies/genge_cycle_bottom/metrics.py`
  - Summary aggregation, win rates, median/average return, benchmark outperformance, consecutive losses.
- `src/strategies/genge_cycle_bottom/report.py`
  - `signal_details.csv`, `summary.json`, and Chinese `summary.md` writers.
- `src/strategies/genge_cycle_bottom/cli.py`
  - `python -m src.strategies.genge_cycle_bottom.cli ...` entrypoint.
- `docs/genge_cycle_bottom_strategy.md`
  - Usage, data assumptions, no-lookahead constraints, output format, and limitations.
- `tests/test_genge_cycle_bottom_features.py`
- `tests/test_genge_cycle_bottom_strategy.py`
- `tests/test_genge_cycle_bottom_backtest.py`
- `tests/test_genge_cycle_bottom_no_lookahead.py`

## Files To Modify

No existing production behavior should be changed for phase one. Existing modules should only be imported by the new strategy package.

If a small compatibility change becomes necessary, it must be isolated and covered by tests, but the current plan does not require one.

## Data And No-Lookahead Rules

- Every feature calculation receives an explicit `as_of_date`.
- Price/volume/trend windows are filtered to rows with `date <= as_of_date`.
- Future return calculations are only performed after a signal has been generated and are stored as validation outputs, never as inputs.
- Valuation and financial data are optional DataFrames. If disclosure dates are unavailable or fields are missing, the strategy records `missing_fields` and lowers confidence instead of looking ahead.
- The first CLI version supports optional CSV inputs for valuation/financial data; if omitted, those scores are conservative and marked missing.

## CLI Design

Examples:

```bash
python -m src.strategies.genge_cycle_bottom.cli \
  --codes 002714,000100 \
  --years 5 \
  --benchmark 000300 \
  --output-dir reports/genge_cycle_bottom
```

```bash
python -m src.strategies.genge_cycle_bottom.cli \
  --stock-pool-file stock_pool_genge.txt \
  --years 10 \
  --benchmark 000300 \
  --output-dir reports/genge_cycle_bottom
```

Additional test-friendly options:

```bash
python -m src.strategies.genge_cycle_bottom.cli \
  --codes 002714,000100 \
  --price-data-dir tests/fixtures/genge_prices \
  --benchmark-file tests/fixtures/genge_prices/000300.csv \
  --output-dir reports/genge_cycle_bottom_smoke
```

## Output

Each run writes a timestamped directory under the selected output directory:

- `signal_details.csv`
- `summary.json`
- `summary.md`

The CSV includes signal fields, component scores, risk/missing fields, 20/60/120/250-day future returns, max drawdowns, benchmark returns, and benchmark outperformance flags.

## Test Plan

- Feature tests:
  - Low historical percentile scores higher than high percentile.
  - Insufficient history records `missing_fields`.
  - Missing valuation/financial data does not crash.
- Strategy tests:
  - `REJECT`, `WATCH`, `LEFT_SMALL_BUY`, and `CONFIRM_BUY` classification thresholds.
  - Financial risk caps signals as required.
- Backtest tests:
  - Future 20/60/120/250-day returns and max drawdown are calculated correctly.
  - Benchmark outperformance is calculated correctly.
- No-lookahead tests:
  - Data after `as_of_date` cannot affect feature scores or signal classification.

## Validation Commands

```bash
pytest tests/test_genge_cycle_bottom_features.py \
       tests/test_genge_cycle_bottom_strategy.py \
       tests/test_genge_cycle_bottom_backtest.py \
       tests/test_genge_cycle_bottom_no_lookahead.py
```

```bash
python -m src.strategies.genge_cycle_bottom.cli \
  --codes 002714,000100 \
  --years 5 \
  --benchmark 000300 \
  --output-dir reports/genge_cycle_bottom
```

```bash
python -m src.strategies.genge_cycle_bottom.cli \
  --codes 002714,000100 \
  --years 10 \
  --benchmark 000300 \
  --output-dir reports/genge_cycle_bottom
```

## Known Phase-One Limits

- Industry "hard logic" is represented as configurable industry/logic tags and market environment, not as LLM or news interpretation.
- Financial and valuation history are optional inputs; missing data lowers confidence and appears in diagnostics.
- The module validates historical signal expectancy; it does not produce trading instructions or execute trades.
