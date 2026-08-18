# GenGe Fresh Validation Trigger

Updated 2026-08-18 to force a fresh All-A validation run from the latest `main` after long-term financial-review priority and the long-term Formal BUY decision layer were integrated.

Expected chain:

Fresh All-A (progress runner) -> `genge-all-a-production-report` -> `GenGe Postscan Research Pipeline` -> industry coverage + long-term second pass + long-term-priority reverse valuation + valuation routing + long-term Formal BUY review + zero-BUY audit.

Validation must prove:

- percentage / throughput / ETA progress logs are live;
- every clean industry remains represented;
- every long-term second-pass candidate reaches valuation and gets first claim on bounded financial review;
- `valuation_research_routed.csv` exists;
- non-defensive zero long-term Formal BUY cannot be explained by missing model execution / missing financial review / missing valuation inputs.

This marker can be removed after end-to-end validation succeeds.
