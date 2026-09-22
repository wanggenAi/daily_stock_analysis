# Current Mission

## Goal
Eliminate the production false-positive path where generic management-system certifications can satisfy the strict multi-year moat entry-barrier rule, then re-verify the exact Deep -> Provenance -> Terminal -> Investor -> Three-Pillar chain without weakening any authority guardrail.

## Current Phase
GENERIC_CERTIFICATION_MOAT_FALSE_POSITIVE_PR_OPEN_AWAITING_CI

## Last Verified Main
- PR #268 merged as `bc927ef143b9eff9f2cf4e58708f0707e2bd5f76`.
- The post-merge production Deep code epoch is `bc927ef143b9eff9f2cf4e58708f0707e2bd5f76`.
- Live main had advanced through Terminal persistence `44e17cbcf65847c646d143ceb7d57ff2c98efb1f` when this fix branch was created.
- Live GitHub refs / Actions / persisted data always override this checkpoint.

## Active Branch
- `fix/moat-generic-certification-false-positive-20260922`.

## Active PR
- #269 `fix: reject generic certifications as moat barriers`: open against `main`.

## CI
- PR #269 opened; live checks on the latest PR head must pass before merge.
- PR #268 final head had passed its blocking CI before merge.
- Post-merge CI for `bc927ef...` was still running when production Deep verification began; re-read live CI before final delivery.

## Production / Artifact
- Deep `35683878901`: SUCCESS, requested=22, processed=22, missing=0, unresolved_requested_gate_count=89, progressed_gate_count=7, predictability_resolved_gate_count=1, moat_resolved_gate_count=4.
- Deep code epoch: `bc927ef143b9eff9f2cf4e58708f0707e2bd5f76`.
- Deep artifact: `genge-v31-deep-calculation-35683878901`.
- Provenance `35684308809`: SUCCESS; all PASS gates had verified evidence, but semantic audit found one overly broad moat rule.
- Terminal `35684310876`: SUCCESS and bound to Deep `35683878901`; requested=22, RESEARCH_GAP=22, BUY=0, WAIT_PRICE=0, REJECT=0.
- New automatic moat PASS codes were `000576`, `002375`, `603160`, `603396`.
- `603396` is the production false-positive case: repeated `entry_barrier` evidence came from generic ISO9001/ISO14001/ISO45001 management-system certification language plus patent support. This does not prove a durable replication barrier.

## Completed
- Recovered from live GitHub rather than chat state.
- Verified #268 was already merged; did not repeat the completed implementation/merge work.
- Verified the replacement post-merge Deep `35683878901` succeeded and reduced unresolved gates from 93 to 89.
- Verified Provenance and exact-lineage Terminal completion.
- Audited all four new automatic moat PASS paths instead of accepting workflow success alone.
- Located the false-positive root cause in the third `entry_barrier` regex: generic `国家级|国际 ... 认证|资质` language was treated as a strong moat.
- Removed only that generic certification pattern.
- Added regression coverage proving ISO9001/ISO14001/ISO45001 remain insufficient while ASIL-D remains recognized.
- Updated moat evidence documentation and changelog.

## Current Findings
- The first production run proves the overall strict moat mechanism can resolve real gates, but its 4/4 count cannot be accepted as semantically clean because `603396` is a false positive under the current-main rule.
- `000576`, `002375`, and `603160` are not dependent on the removed generic-certification rule; their repeated strong categories are market-leadership based.
- The fix remains PASS-only and fail-closed. It can reduce automatic moat PASS count; it cannot manufacture a FAIL or a Formal action.
- Jev/TypeSafe did not determine any moat gate in this mission. The moat closure is deterministic official-evidence logic.

## TypeSafe / Jev
- Live Jev shadow uses pinned `typesafe-sdk==0.7.0`, `JEV_MODEL=jev-latest`, and `TYPESAFE_API_KEY`.
- Jev produces typed attention/evidence/routing judgments only.
- Current orchestration is: Jev typed routing -> deterministic research orchestrator -> bounded eligible-code dispatch -> Deep.
- `jev_direct_dispatch_allowed=false`; the deterministic orchestrator may dispatch research work, but Jev cannot create Formal BUY or mutate trading authority.
- No new Jev call was required for this deterministic moat false-positive repair.

## Blockers
- None currently. The next blocker, if any, must come from PR CI/review or post-merge production evidence.

## Next Action
1. Read PR #269 blocking CI/review on the latest head; fix any failures without broadening the moat rule.
2. Merge only when blocking checks are green and the PR is safely current/mergeable against live main.
3. Verify live main and trigger/observe the resulting evidence-layer Deep.
4. Audit the new production moat PASS set; `603396` must no longer PASS from generic ISO certification evidence.
5. Verify exact Deep -> Provenance -> Terminal -> Investor -> Three-Pillar lineage and update this checkpoint to completion.

## Do Not Repeat
- Do not redo PR #268.
- Do not rerun old Deep `35679085547` or treat cancelled push Deep `35683870241` as a failure.
- Do not broaden moat rules to recover pass count.
- Do not loosen long_term_demand, predictability, financial-safety, earnings-authenticity, valuation, BUY/WAIT_PRICE/REJECT, Candidate Lifecycle, or Formal authority rules.
- Do not report Jev usage unless an actual TypeSafe/Jev workflow log proves that call occurred.

## Guardrails
- GitHub live state is the source of truth.
- Jev direct dispatch=false.
- Deterministic bounded research dispatch is research-only.
- Formal trading authority=false.
- Automatic Formal BUY=false.
- UNKNOWN != PASS.
- no_auto_trade=true.
