# Terminal Urgent Evidence Reopen

`GenGe Terminal Urgent Evidence Reopen` closes the scheduling feedback gap between the four-hour Evidence Slow Lane and the V3.1 Deep Calculation Lambda without weakening research gates.

A successful Slow Lane completion is **not** automatically treated as new evidence. The bridge computes a deterministic content fingerprint over the persisted `data/evidence_events/<code>.jsonl` files for the current urgent subset. An automatic Slow Lane-triggered reopen occurs only when that fingerprint differs from the last accepted evidence epoch. Unchanged evidence is suppressed, preserving the rule that identical evidence must not create an unbounded retry loop. Explicit workflow deployment or manual dispatch may intentionally re-underwrite the same evidence after code or operator changes.

The bridge does **not** claim that Deep directly consumes the persisted Evidence Event store as hard-gate proof. Slow-lane policy and competitive events are research context, not automatic PASS evidence. When a genuine evidence-content epoch changes, the bridge reopens research and lets Deep execute its own same-run official-source collection and verification under the existing strict provenance rules.

The bridge validates the persisted terminal snapshot and requires at least one `urgent_research_queue` row that remains `REJECT / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY`, is explicitly reopenable on new evidence, has no known hard-gate failure, and retains `RESEARCH_ONLY` / no-auto-trade authority.

When such urgent rows exist and the evidence epoch is eligible, Deep receives the **complete previous terminal workset**, not only the urgent subset. This preserves terminal snapshot continuity: if 34 names were terminal before the evidence epoch and 11 are urgent, the Deep request remains 34 names while the 11 urgent names are separately identified as the reason for reopening. The following Terminal run therefore cannot silently shrink to 11 merely because the reopen trigger was urgent-focused.

After an accepted dispatch, the bridge persists only the evidence-epoch fingerprint and audit metadata under `data/research_reopen/latest.json`. That marker carries no trading authority. Persistence uses optimistic replay and a `[skip ci]` commit so a scheduling marker cannot become a new research or trading signal.

The workflow listens to successful Evidence Slow Lane completion, not Deep or Terminal completion. Therefore the production chain is one-way: Slow Lane -> urgent reopen -> Deep -> Terminal. It cannot form a Terminal -> Deep -> Terminal self-trigger loop.

Specialized industries are allowed into evidence recovery because evidence collection is independent of valuation methodology. The downstream terminal valuation rules remain authoritative; this bridge cannot infer a hard-gate PASS or create a Formal BUY.
