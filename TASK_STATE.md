# Current Mission

## Goal

Turn the current research system into a convergent autonomous opportunity engine that can actually surface **reference-worthy stock codes** without fabricating certainty or forcing a BUY.

Two linked problems must be solved together:

1. **Autonomous research closure:** for every active non-holding candidate that remains `RESEARCH_GAP`, Jev + the deterministic research stack must keep selecting genuinely new evidence/research paths until either:
   - the hard gates are sufficiently proven and the candidate can progress to the existing valuation / BUY / WAIT_PRICE authority path;
   - a hard gate is disproven and the candidate becomes REJECT; or
   - all supported, credible, non-duplicate research strategies are exhausted. In that case the non-holding candidate loses active-candidate eligibility and moves to a dormant/excluded evidence-exhausted pool, to be reactivated only by a genuinely new evidence epoch/material event.

2. **Candidate-funnel health / Runbei-like opportunity recovery:** diagnose why a market-wide system scanning thousands of A shares is currently producing no research BUY/WAIT_PRICE despite a large research queue. Do **not** assume the answer is to weaken thresholds. Identify whether useful candidates are being lost or stalled in recall, mapping, valuation coverage, Deep workset construction, evidence acquisition, hard-gate semantics, Jev routing, lifecycle persistence, or Terminal promotion.

The product goal is not “always output at least one BUY.” The goal is that the system must make a serious, auditable attempt to find strong opportunities across the broad market and return useful candidate codes when evidence supports them; a zero-result terminal is acceptable only after funnel coverage and research closure are proven healthy.

## Current Phase

AUTONOMOUS_RESEARCH_CLOSURE_AND_CANDIDATE_FUNNEL_AUDIT

## Live Source Of Truth

Always re-read live GitHub state before continuing. The values below are a handoff checkpoint only and may advance.

- Main at checkpoint: `ca3390991034f3fffea2ee800b43b742aa8d53ad` — `Persist terminal deep calculation 35689369644 [skip ci]`.
- Latest persisted Deep at checkpoint: run `35689369644`, trigger `EVERY_INDUSTRY_READY`, execution `SUCCESS`.
- Deep requested **24**, processed **24**, workset coverage complete=true, complete=**0**, evidence-exhausted=**24**.
- Deep gap closure used **2** attempts, acquired **58** new evidence rows, progressed **6** gates, but still has **98** unresolved requested hard gates.
- Latest persisted Terminal observed at checkpoint still points to Deep `35688190313`: **BUY=0 / WAIT_PRICE=0 / RESEARCH_GAP=24 / REJECT=0**. This is older than latest Deep `35689369644`; verify downstream convergence before treating Terminal as current.
- Research Priority queue at checkpoint: **157** candidates; **P0=4**, **P1=8**, **near-buy recovery=110**, **success-archetype recall=0**, mapping gaps=**39** (+1 partial).
- Current P0s are the four holdings; current P1 examples include 华孚时尚 002042、中毅达 600610、国脉文化 600640、中国黄金 600916、红塔证券 601236、今世缘 603369、老百姓 603883、万华化学 600309.
- The system therefore has a large upstream candidate/recovery population but currently converges to no research BUY/WAIT. This is the funnel discrepancy to explain with data rather than intuition.

## Required Workstream A — Autonomous Jev Research Closure

Implement a durable per-`code × hard_gate` research strategy ledger.

The ledger must record at minimum:
- unresolved gate and exact reason;
- research strategy family;
- source family / query family;
- evidence fingerprint / epoch;
- attempt status and timestamps;
- whether new evidence was acquired;
- whether the gate changed;
- whether the strategy is exhausted;
- what untried strategy families remain.

Add a Jev research-strategy planning stage after Deep/Terminal GAP evaluation:
- Jev may propose/route the next research strategy, but remains advisory.
- A deterministic guard must validate source/strategy allowlists, novelty, budget and authority.
- Jev must never directly create Formal BUY/SELL/HOLD, mutate hard-gate truth, or turn UNKNOWN into PASS.
- Low Jev route confidence must not automatically end research for safe read-only evidence collection. It should fall back to the safest deterministic/lowest-cost valid research path when one exists.
- HUMAN_REVIEW should be reserved for genuinely non-ruleable ambiguity, unsupported source classes, material accounting interpretation conflicts, or other explicitly defined cases.

Add an autonomous loop controller:
`GAP -> plan next novel strategy -> collect -> provenance/audit -> Deep -> compare gate/evidence fingerprints -> repeat if novel path remains -> terminal when resolved or policy-exhausted`.

Loop controls are mandatory:
- identical evidence must never create an infinite retry;
- repeated strategy/source/query fingerprints are suppressed;
- per-code and per-run budgets are bounded;
- source failures get bounded retry;
- no progress with no novel path terminates cleanly;
- a new evidence epoch/material event can reactivate a dormant candidate.

Define explicit research terminal reasons, e.g.:
- `HARD_GATE_FAILED`
- `POLICY_EXHAUSTED`
- `SOURCE_EXHAUSTED`
- `DATA_NOT_YET_EXISTS`
- `EVIDENCE_CONFLICTED`
- `BUDGET_EXHAUSTED_RETRYABLE`

## Required Workstream B — Candidate Death / Dormancy Semantics

For **non-holding candidates**:
- If supported credible research paths are exhausted and key evidence still cannot be proven, remove the code from the active candidate/research queue.
- Do not label it as business-quality FAIL unless the evidence actually disproves a hard gate.
- Persist it in a dormant/excluded research pool with the exact exhaustion reason and reactivation conditions.
- Dormant candidates must not consume routine Jev/Deep capacity.
- New annual reports, material company events, new official industry evidence or a changed evidence fingerprint may reactivate them.

For **current holdings**:
- Never “delete” the code merely because evidence is exhausted.
- Evidence exhaustion may block new exposure and raise review/risk status, but SELL/REDUCE still requires the existing Formal authority/rules.
- Preserve `UNKNOWN != PASS` and `no_auto_trade=true`.

## Required Workstream C — Diagnose Why No New Runbei-Like Candidates Emerge

Treat the current zero BUY/WAIT result as a **funnel-health investigation**, not proof that no opportunity exists and not proof that thresholds must be relaxed.

Audit stage-by-stage counts and attrition across:
`All-A universe -> quant screen -> wide recall -> industry-protected recall -> valuation coverage -> research priority -> Deep workset -> hard gates -> Terminal`.

At each stage produce:
- input/output counts;
- codes dropped and exact reasons;
- sector/industry coverage;
- valuation-anchor availability;
- mapping gaps;
- hard-gate UNKNOWN/FAIL distribution;
- evidence-source coverage;
- candidate age/staleness;
- whether durable lifecycle is causing stale GAP accumulation;
- whether newer high-scoring candidates are displaced by old unresolved continuity anchors.

Specifically investigate:
- why `success_archetype_recall_count=0` despite the existing Runbei archetype;
- whether Runbei-like recall is too narrow, stale, disconnected from current All-A output, or blocked downstream;
- why **110 near-buy recovery** candidates do not produce any Terminal WAIT/BUY;
- whether current Deep workset size/continuity (24) is starving the broader 157-candidate queue;
- whether 39 mapping gaps are materially preventing valuation/deep promotion;
- whether hard-gate requirements are valid but evidence collectors are underpowered;
- whether all candidates are being treated with a one-size-fits-all evidence template where industry-specific research is required;
- whether Terminal semantics are over-conservative relative to the intended contract, without changing thresholds merely to create output.

The audit must identify concrete example codes at each major bottleneck and follow several candidates end-to-end.

## Success Criteria

This mission is complete only when all of the following are true:

1. A GAP candidate can autonomously continue through multiple **novel** research strategies without the user saying “继续”.
2. The system can prove when a candidate is genuinely policy/source exhausted rather than merely “not yet searched enough”.
3. Non-holding exhausted candidates leave the active queue and enter durable dormant state with deterministic reactivation rules.
4. Holdings remain managed safely and are never silently dropped.
5. The full-market opportunity funnel has an auditable attrition report explaining where thousands of stocks become the final research set.
6. Runbei-like/success-archetype recall is verified as live and effective, or its failure mode is explicitly fixed.
7. The system produces a useful ranked **research shortlist of stock codes** when evidence supports it, even if no Formal BUY exists yet. The shortlist must distinguish:
   - evidence-complete / valuation-ready;
   - promising but still actively researching;
   - WAIT_PRICE;
   - excluded/dormant.
8. No thresholds, hard gates or authority rules are weakened solely to guarantee non-zero output.
9. Production chain remains fail-closed: `UNKNOWN != PASS`, Formal authority remains Canonical-only, automatic Formal BUY=false, `no_auto_trade=true`.

## Separate Active Work — PR #270

PR #270 remains a separate execution/display consistency fix:
`fix: keep first-use execution report internally consistent`.

At checkpoint:
- PR #270 is open, not merged.
- Head was `6afea42756b866d62dfa93a16f52d2569e07b22d`.
- It fixes consumed staged-add `ADD_LIMIT` resurrection and preservation of fresh broker/direct execution quotes during off-session display while immediate execution remains blocked.

Future sessions must inspect its live CI/mergeability and finish or reconcile it, but **do not conflate PR #270 with the autonomous research/funnel mission**.

## Previously Completed Mission

The generic-certification moat false-positive fix (#269) is complete and production-verified. Do not reopen or weaken it merely to improve candidate counts. Generic ISO9001/ISO14001/ISO45001-style certifications remain insufficient as standalone durable-moat evidence.

## Immediate Next Actions

1. Re-read latest main, Deep, Terminal, research priority, open PRs and CI because bot persistence may have advanced state.
2. Ensure PR #270 is safely completed/reconciled when CI permits.
3. Build a stage-by-stage funnel attrition snapshot from the latest broad-market artifacts and identify the largest real bottleneck.
4. Trace at least several current near-buy/P1 candidates end-to-end and compare with the historical Runbei archetype path.
5. Design/implement the research-strategy ledger + novelty-aware autonomous loop in small guarded PRs.
6. Add dormant/excluded candidate semantics after policy exhaustion.
7. Update the Investor/Three-Pillar display so it shows:
   - what was researched;
   - which strategies were tried;
   - what evidence was gained;
   - why a candidate progressed, was excluded, or remains active;
   - the actual current research shortlist codes.

## Do Not Do

- Do not force at least one BUY/WAIT by lowering thresholds.
- Do not treat “no evidence found” as proof the business is bad.
- Do not keep exhausted non-holding candidates permanently ACTIVE.
- Do not delete or ignore current holdings because evidence is exhausted.
- Do not repeatedly fetch identical evidence.
- Do not let Jev directly mutate Formal/Canonical trading authority.
- Do not repeat already-completed #268/#269 work.
- Do not use chat memory as the source of truth when live GitHub disagrees.

## Guardrails

- GitHub live state is authoritative.
- Jev direct trading dispatch=false.
- Jev may guide research strategy only behind deterministic guardrails.
- Formal trading authority=false outside existing Canonical path.
- Automatic Formal BUY=false.
- UNKNOWN != PASS.
- no_auto_trade=true.
