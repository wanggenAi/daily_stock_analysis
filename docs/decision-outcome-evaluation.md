# GenGe V3.1.1 Decision Outcome Evaluation

## Purpose

This sidecar evaluates whether finalized GenGe decisions are producing useful real-world outcomes over a sufficiently large sample. It is deliberately **observer-only**. It does not alter the frozen V3.1.1 production contract, Confidence Gate, Hard Gate, BUY/SELL thresholds, SELL rationale gate, canonical schema, candidate lifecycle state, holdings reconciliation, or no-auto-trade policy.

A profitable day is not treated as proof of edge. The evaluator is intended to accumulate auditable evidence across 20, 50, and 100 completed decision/execution loops.

## Separation of authorities

There are three distinct facts:

1. **Canonical decision** — imported from a finalized canonical snapshot. This is immutable observational evidence of what the production system decided at that time.
2. **Execution** — recorded only when an explicit execution is supplied. The evaluator never assumes that BUY/ADD/REDUCE/EXIT was executed.
3. **Outcome metric** — derived only from the explicit decision/execution ledger. It is analysis, not a production decision and cannot feed back into Formal action.

Canonical decisions and executions use separate append-only JSONL ledgers. A stable decision id is derived from canonical `snapshot_id`, `source_run_id`, symbol, and action. Importing the same snapshot again is therefore idempotent and returns `NOOP`.

## Files

Recommended durable paths:

```text
data/decision_outcomes/decision_events.jsonl
data/decision_outcomes/execution_events.jsonl
data/decision_outcomes/summary.json
```

The repository intentionally does **not** seed historical execution rows. Existing holdings, cost basis, screenshots, inferred fills, or current prices are not silently converted into executions.

## Automatic finalized-decision observation

`GenGe V3.1.1 Decision Outcome Observer` runs only after a successful `GenGe V3.1.1 Production Finalizer` (or an explicit manual replay of a successful Finalizer run). Before importing anything it downloads the authoritative artifact from that exact Finalizer run and validates the authority/canonical/hourly/holdings/lifecycle identity chain, including authorization, production version, Finalizer run id, canonical snapshot id, canonical source run id, canonical SHA256, source hashes, latest trade date, research timestamp, and no-auto-trade contract.

Only after that validation does it append canonical decision observations to `data/decision_outcomes/decision_events.jsonl`. Persistence uses optimistic replay from the latest `main`: a non-fast-forward push discards the generated attempt, fetches the new remote state, and re-imports the same canonical snapshot. This preserves concurrent durable writers and keeps repeated observation of the same snapshot idempotent.

The automatic observer never creates or modifies `execution_events.jsonl`. A Formal BUY/ADD/REDUCE/EXIT is evidence that the system made a decision; it is not evidence that the user executed it. Real executions must still be supplied explicitly.

## Usage

Import a finalized canonical snapshot projection:

```bash
python scripts/decision_outcome_evaluator.py import-canonical \
  --canonical authoritative/canonical_snapshot/latest.json \
  --decisions data/decision_outcomes/decision_events.jsonl
```

Persist that finalized observation to the latest durable `main` with optimistic replay:

```bash
python -m scripts.decision_outcome_git_persistence \
  --canonical authoritative/canonical_snapshot/latest.json \
  --repo-root . --remote origin --branch main
```

Record a real execution only after it is explicitly known:

```bash
python scripts/decision_outcome_evaluator.py record-execution \
  --executions data/decision_outcomes/execution_events.jsonl \
  --symbol 600309 --side BUY --quantity 100 --price 77.50 \
  --executed-at 2026-09-04T06:30:00Z \
  --decision-id dec_xxxxxxxxxxxxxxxxxxxxxxxx
```

The example above is syntax only; it is not a statement that any trade occurred.

Generate a summary:

```bash
python scripts/decision_outcome_evaluator.py evaluate \
  --decisions data/decision_outcomes/decision_events.jsonl \
  --executions data/decision_outcomes/execution_events.jsonl \
  --summary data/decision_outcomes/summary.json
```

## Metrics and interpretation

The summary reports canonical action counts, decisions linked to explicit executions, open explicit quantities, FIFO realized P&L, closed-sell win rate, average win/loss, profit factor, expectancy, and a realized-P&L-series drawdown. Open positions are excluded from win/loss and expectancy.

`ADD`/`REDUCE` effectiveness is intentionally labelled observational. Without a valid counterfactual there is no defensible causal statement that an ADD improved returns or that a REDUCE prevented a loss. The evaluator therefore refuses to manufacture that conclusion.

Max drawdown is only reported over the chronological explicit realized-sell P&L sequence. It is not presented as portfolio equity drawdown unless a complete, time-aligned equity series is explicitly available.

## Milestones

At 20 closed loops, the sample is useful for first diagnostic review but is still small. At 50, compare action-specific expectancy, loss concentration, execution compliance, and repeated failure modes. At 100, the system has enough accumulated observations to justify a more serious out-of-sample review, while still checking market-regime dependence and selection bias.

These milestones are evaluation checkpoints, not permission to optimize the frozen V3.1.1 contract against the same sample. Any future model change belongs in a separately versioned research/OOS process.

## Safety properties

- Re-importing an identical canonical snapshot adds zero decision events.
- Canonical payloads are deep-copied/checked and never mutated.
- Automatic observation requires one fully validated authoritative Finalizer artifact.
- Durable decision-event persistence replays from the latest remote branch after a rejected push.
- Executions are caller-supplied facts and remain separate from decisions.
- Selling more shares than the explicit execution ledger has bought fails closed instead of inferring inventory from holdings.
- No broker connection and no automatic trading are introduced.
- No workflow in this change writes evaluator results back into production decision inputs.
