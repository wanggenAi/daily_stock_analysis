# V3.1 Deep Evidence Closure

The V3.1 Deep Calculation Lambda is fail-closed: a hard gate remains `UNKNOWN`
unless the current run can prove a strict PASS/FAIL from accepted evidence. An
execution-successful run may therefore end in `EVIDENCE_EXHAUSTED`; this is a
research-process terminal state, not an investment approval.

## Automatic hard-gate evidence

- `financial_safety` and `earnings_authenticity` use same-run PIT financial
  evidence and verified material-event negative overrides.
- `long_term_demand` requires at least two independent verified official source
  families with the same direction.
- `predictability` uses strict multi-year official annual-report accounting
  evidence. Resource/cyclical companies remain fail-closed unless their separate
  cycle-resilience requirement is satisfied.
- `moat` may PASS only from the strict multi-year official-report moat rule
  described below. Absence of moat evidence never creates FAIL.

## Strict multi-year moat rule

The moat rule reuses annual-report bodies already fetched by the predictability
collector; it does not add a second report-download fanout. The extractor accepts only issuer-bound claims (the report text must attribute the
signal to `公司`/`本公司`, not a competitor or industry peer) and only narrow,
auditable signal categories:

- market leadership supported by explicit market-share/ranking/scale language;
- entry barriers such as exclusive/unique rights or high-specificity
  certification language;
- customer embedding supported by quantified designation or mass-production
  programs;
- resource-asset barriers supported by world-class/large-resource language or
  quantified reserves/resources;
- patent scale as supporting evidence only.

A moat PASS requires all of the following:

1. the same **strong** moat category is present in two consecutive fiscal-year
   official annual reports;
2. across those two reports, at least one additional moat category corroborates
   the repeated strong signal;
3. the evidence row is from an accepted official exchange/CNINFO report source
   and is explicitly marked `moat_evidence_status=VERIFIED` and
   `moat_adopted_for_gate=true`.

Generic claims such as “加大研发投入”“保持行业领先”“积极拓展客户” do not satisfy
the rule. Patent counts alone do not satisfy the rule. Any ambiguity remains
`UNKNOWN`.

The rule is research-only. It does not change valuation formulas,
BUY/WAIT_PRICE/REJECT thresholds, Candidate Lifecycle, Formal trading authority,
or `no_auto_trade=true`.
