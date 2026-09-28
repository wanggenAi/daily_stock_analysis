# Holding valuation watch: discounted prices without trading-authority escalation

**Scope:** A read-only, additive section in the existing `GenGe Three-Pillar Decision Center` JSON/Markdown (not a second valuation/decision model). The goal is to answer: "A holding is below its model value floor and I have planning cash, so why is its executable add zero?" This document is the bounded recovery checkpoint for the 2026-09-29 owner request; read live `main`, `TASK_STATE.md`, PRs and current datasets before continuation.

## Exact behavior

- Automatically screen *all existing confirmed holdings* for numeric positive price, known model value floor, HIGH confidence and EOD price below the model floor. No hard-coded company, valuation, BUY threshold or new authorization.
- Publish `holding_valuation_watch` with price date, lower value band, discount, registered-stock concentration, current Deep PASS/UNKNOWN count, unchanged formal action, market regime, prior add consumption and a 100-share *illustrative* cash/average-cost arithmetic scenario. Source: the same finalized Canonical dashboard the existing three-pillar center consumes. Watch values are estimated from the last persisted user-confirmed quantities/cost and persisted daily close; portfolio concentration is only among **registered stocks**, not the entire portfolio.
- Require freshness-contract date agreement with market and Canonical dates; report a blocker when stale. Require current Deep profile lineage; report a blocker rather than promoting old PASS. Explain each independent reason for 0 authorized new shares: RED/no-new-buy, no current Formal ADD, previously consumed allowance, unproven gates, unverified brokerage cash and absent live execution quote.
- Every output is `VALUATION_WATCH_NOT_ACTIONABLE` / `READ_ONLY_RESEARCH_SCENARIO`; `buy_now=[]`, `executable_orders=[]`, `executable_shares=0`, `order_limit_price=null` under **all** inputs, including permissive GREEN and unconsumed authorized fixtures. A what-if does not reserve or deploy funds.
- In the existing Markdown, add a short "估值折价观察（非买单）" section immediately beside holding detail; JSON adds the same data under `holding_valuation_watch`. Existing `today_account_plan`, `formal_action_source`, BUY thresholds, `no_auto_trade`, Jev advice, and production authority remain untouched.

## Price-sensitive acceptance

Expected persisted example from Sept 28 (not a pre-authorized price/limit): CMOC 603993 had 1,100 saved shares, saved average ¥18.6244, EOD ¥16.83 and model floor ≈¥18.03; illustrative 100 shares would cost ≈¥1,683 before fees and change average cost to ≈¥18.4749 if executed at the assumed EOD price. **Do not submit a ¥16.83 order based on a previous close.** Today’s actual quote, issuer material filings, copper-market downside, persisted authority + consumed history, current broker positions and available cash, session rules and position exposure must all be checked again.

## Validation and limitations

CI: `python -m pytest -q tests/test_three_pillar_decision_center.py tests/test_three_pillar_decision_center_runtime.py tests/test_holding_valuation_watch.py` plus backend and Docker CI. PR-triggered report contracts run tests only and do not publish synthetic market data. Real production acceptance requires postmerge `GenGe Three-Pillar Decision Center` workflow, same-date/latest Canonical lineage, `data/decision_center/latest.json` containing the watch, and `LATEST_DECISION_CENTER.md` showing the explainer. A workflow success alone is insufficient.

This feature **does not** lift the global RED gate, rearm consumed 100 shares, source a fresh broker feed, predict a bottom, label hypothetical scenarios as executable orders or integrate V4 Web UI. Any V4 UI integration must reuse this published read-only contract and remain separately verified. A future approved real Formal ADD is a separate upstream authority transition, not a response to the watch projection.

## Rollback

Revert this helper, runtime import/integration/Markdown addition, tests and small workflow contract-trigger edit. Original three-pillar payload fields and external downstream execution semantics remain unchanged.
