# Evidence exhaustion and recovery (investor read-only)

This change makes a finite Deep research run produce an auditable remediation
outcome rather than continually returning only `RESEARCH_GAP`. It **does not**
alter BUY, valuation, five-hard-gate, or capital thresholds.

## Source-linked annual comparative repair

The official multi-year collector first parses each issuer's own annual report.
For a **missing** fiscal-year consolidated metric only, it may read that fiscal
year's explicitly bound value from the comparative table of a later (at most
two years later) official annual report already obtained by the same collector.

Acceptance requires a recognized year-to-value binding and trusted unit
provenance. Narrative figures, divisional revenue, quarterly rows, yearless
values, and inconsistent later annual comparatives are rejected. Every accepted
recovered cell records the source document URL, publication date, source report
year and target fiscal year. The existing strict three-year stability and
volatility thresholds remain unchanged.

The Runbei 2026-09-29 Deep evidence contained a 2023 annual revenue extraction
gap even though its later official annual comparative reports 2023 turnover.
Recovering this cell will allow the **unchanged** financial-volatility rule to
run; it does not warrant a predictability PASS. Runbei's 2023 operating cash
flow of ~4.61m CNY versus ~221.28m CNY in 2025 can still breach the existing
maximum 5x volatility rule.

## Investor-visible bounded terminal diagnosis

When:
- the terminal decision's Deep lambda exactly matches the current runtime;
- execution actually succeeded with `EVIDENCE_EXHAUSTED`;
- at least two bounded same-run evidence attempts completed; and
- an issuer is `RESEARCH_GAP` with explicit unresolved gate reasons,

the existing three-pillar report adds a read-only
`pillar_3_deep_opportunities.research_deadlocks` entry and corresponding
Markdown section. A currently held issuer also receives that exact diagnosis
under its holding row without changing its Formal action.

Each diagnosis lists each unresolved gate, the machine reason and the next
targeted task:
- missing complete years -> audit metric extraction, then apply unchanged
  stability and volatility tests;
- demonstrated instability -> document genuine financial variability, never
  relax thresholds to manufacture PASS;
- insufficient durable moat -> seek independent, repeated multi-year barriers;
- insufficient demand -> verify independent primary-demand corroboration;
- other gaps -> inspect the exact primary-source and gate evidence.

An unchanged scheduled run is **not** a new evidence epoch. The existing
`genge-terminal-urgent-evidence-reopen` workflow already suppresses identical
fingerprints on its slow-lane path; these read-only diagnoses tell the owner
what must change before a meaningful re-underwriting. Existing manual and
code-change workflows retain their own explicit trigger semantics. A diagnosis
is not a claim that an external collection repair has been completed.

## Acceptance

Run `pytest -q tests/test_v31_multi_year_predictability.py
tests/test_three_pillar_decision_center_runtime.py`, compile the changed
modules, and verify exact-head repository CI. After merge, inspect one **real**
new Deep Lambda artifact and resulting three-pillar persisted Markdown/JSON.
For Runbei (001316), compare the new 2023 revenue provenance and resulting
unchanged predictability decision. Check that Formal actions and executable
shares have not changed. Do not claim production completion from tests alone.
