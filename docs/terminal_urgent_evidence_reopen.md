# Terminal Urgent Evidence Reopen

`GenGe Terminal Urgent Evidence Reopen` closes the scheduling feedback gap between the four-hour Evidence Slow Lane and the V3.1 Deep Calculation Lambda.

A successful Slow Lane completion is treated as a new evidence epoch. The bridge does **not** claim that Deep directly consumes the persisted `data/evidence_events` store. Instead, it uses the new evidence epoch to reopen research and lets Deep run its own same-run official-source collection and verification again.

The bridge validates the persisted terminal snapshot and requires at least one `urgent_research_queue` row that remains `REJECT / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY`, is explicitly reopenable on new evidence, has no known hard-gate failure, and retains `RESEARCH_ONLY` / no-auto-trade authority.

When such urgent rows exist, Deep receives the **complete previous terminal workset**, not only the urgent subset. This preserves terminal snapshot continuity: if 34 names were terminal before the new evidence epoch and 11 are urgent, the Deep request remains 34 names while the 11 urgent names are separately identified as the reason for reopening. The following Terminal run therefore cannot silently shrink to 11 merely because the reopen trigger was urgent-focused.

The workflow listens to successful Evidence Slow Lane completion, not Deep or Terminal completion. Therefore the production chain is one-way: Slow Lane -> urgent reopen -> Deep -> Terminal. It cannot form a Terminal -> Deep -> Terminal self-trigger loop.

Specialized industries are allowed into evidence recovery because evidence collection is independent of valuation methodology. The downstream terminal valuation rules remain authoritative; this bridge cannot infer a hard-gate PASS or create a Formal BUY.
