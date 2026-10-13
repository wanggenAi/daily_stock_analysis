# UNKNOWN-Safe Research Radar

## Purpose

The existing V3.1 hard-gate contract remains fail-closed: `UNKNOWN != PASS`, and only finalized Canonical output owns Formal trading authority. The research radar adds a downstream visibility layer so candidates with meaningful verified progress are not hidden merely because one or more qualitative hard gates are still `UNKNOWN`.

This layer does **not** relax any BUY / WAIT_PRICE / REJECT threshold and does not modify the Production Finalizer, Canonical snapshot, holdings actions, position sizing, or execution logic.

## Admission contract

A candidate can enter the radar only when all of the following are true:

- zero verified hard-gate `FAIL` values;
- at least two hard gates are verified `PASS`;
- every counted `PASS` has accepted Deep provenance (`EXPLICIT_VERIFIED` or `AUTOMATIC_MACHINE`) and non-empty evidence;
- an unverified upstream `PASS` is treated as `UNKNOWN`, never as evidence progress.

Candidates with five verified PASS gates are labeled `FULL_EVIDENCE`. Candidates that meet the admission floor but still contain one or more UNKNOWN gates are labeled `UNKNOWN_RESEARCH`.

## Ranking

The radar is a research-priority view, not a buy list. Eligible rows are ordered deterministically by:

1. verified PASS gate count descending;
2. quantitative score descending;
3. existing V3.1 review rank ascending;
4. stock code ascending.

The report emits at most ten top rows. It never pads the list when fewer than ten candidates qualify.

## Authority and safety

Every radar artifact is `RESEARCH_ONLY` and must keep all of these invariants:

- `formal_trading_authority=false`
- `automatic_formal_buy_allowed=false`
- `mutates_authoritative_decision=false`
- `unknown_is_pass=false`
- `no_auto_trade=true`

A true hard-gate FAIL is excluded regardless of quantitative score. UNKNOWN candidates may remain visible for evidence closure, but the radar cannot turn them into Formal BUY, create share counts, or authorize execution.

## Production integration

`.github/workflows/genge-v31-unknown-safe-research-radar.yml` consumes the exact artifact from a successful `GenGe V3.1.1 Every-Industry Research` run, executes contract tests, builds the radar, validates the fail-closed invariants, uploads an Actions artifact, then persists only the advisory projections:

- `data/research_radar/latest.json`
- `LATEST_RESEARCH_RADAR.md`

These persisted files are downstream research views only and are not inputs that can grant Formal trading authority.

## Acceptance anchor

Before implementation, the algorithm was replayed against successful Every-Industry run `38149891502`. Its real pipeline contained 5,224 raw securities, 4,485 effective scans, 754 ledger-independent Discovery candidates, and 506 V3.1 deep-review candidates. The radar admitted 108 research candidates, excluded the single true hard-FAIL candidate, kept 397 candidates below the verified-progress floor, and emitted an unpadded Top 10. All safety assertions remained fail-closed.
