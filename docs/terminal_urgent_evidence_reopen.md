# Terminal Urgent Evidence Reopen

`GenGe Terminal Urgent Evidence Reopen` closes the research feedback gap between the four-hour Evidence Slow Lane and the V3.1 Deep Calculation Lambda.

It reads only the persisted `urgent_research_queue` from the fail-closed terminal research snapshot and dispatches Deep Calculation only for rows that remain `REJECT / EVIDENCE_INSUFFICIENT_AFTER_BOUNDED_RETRY`, are explicitly reopenable on new evidence, have no known hard-gate failure, and retain `RESEARCH_ONLY` / no-auto-trade authority.

The workflow listens to successful Evidence Slow Lane completion, not Deep or Terminal completion. Therefore the chain is one-way: Slow Lane -> urgent reopen -> Deep -> Terminal. It cannot form a Terminal -> Deep -> Terminal self-trigger loop.

Specialized industries are allowed into evidence recovery because evidence collection is independent of valuation methodology. The downstream terminal valuation rules remain authoritative; this bridge cannot infer a hard-gate PASS or create a Formal BUY.
