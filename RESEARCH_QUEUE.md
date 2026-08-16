# Research Queue

> Durable autonomous queue for ongoing market / sector / stock research.
>
> User instruction: do **not** stop after every single stock waiting for a manual “继续”. Process this queue continuously in priority order. Only pause for the user when a decision genuinely requires user preference/approval, when safety/data-integrity rules block further execution, or when the current chat/session context is approaching its practical limit.
>
> **Session rollover rule:** before a long-running session is near context exhaustion, stop expanding the task, persist completed work + exact breakpoint + remaining queue + open PR/CI state + next actions here / in the latest research log, then explicitly tell the user to open a new window. The new session must read the durable handoff files and resume from the breakpoint instead of restarting.

Every item must still obey the fresh-data hard rule in `CURRENT_MARKET_RESEARCH.md`: old prices/statuses are context only; refresh the latest available market/fundamental/industry data before a new formal conclusion.

## Operating rule

For each queued stock / sector:

```text
fresh Analysis Snapshot
-> latest production price snapshot
-> latest filing / earnings preview / material event
-> latest industry / commodity driver
-> earnings-quality normalization
-> cycle normalization where relevant
-> Bear / Base / Bull
-> reverse implied expectations
-> valuation horizon / dilution / asset bridge where relevant
-> research status
-> update GitHub research log
-> if a reproducible model failure appears: minimal code fix + regression test in valuation PR
-> immediately continue to next queue item
```

Do not create a new metric merely because a case is unusual. If existing primitives already handle the case correctly, add a regression case rather than another feature.

## Queue statuses

```text
QUEUED
IN_PROGRESS
DONE
RECHECK_ON_EVENT
BLOCKED_DATA
```

# Current durable state — 2026-08-16

The initial deep-research universe is complete through:

```text
MARKET_RESEARCH_LOG_2026-08-16_BATCH13.md
```

Latest A-share trading-day price snapshot used by the completed master ranking:

```text
2026-08-14
repository production artifact / tencent_raw
market regime: YELLOW
market position multiplier: 0.5
```

Batch 13 is the current master cross-sector research ranking. It supersedes stale queue statuses below from older handoffs.

No Formal BUY was created by the master ranking.

## Master Top 10 research priority — not a BUY list

```text
1. 600406 国电南瑞
2. 300502 新易盛
3. 000682 东方电子
4. 000400 许继电气
5. 300308 中际旭创
6. 300476 胜宏科技
7. 688019 安集科技
8. 002463 沪电股份
9. 600312 平高电气
10. 600549 厦门钨业
```

See Batch 13 for valuation semantics, confidence and category assignments.

# Completed initial deep-research universe

## Grid / power infrastructure

| Code | Name | Status |
|---|---|---|
| 002028 | 思源电气 | DONE / WAIT_FOR_PRICE |
| 000682 | 东方电子 | DONE / RECHECK_ON_EVENT |
| 600406 | 国电南瑞 | DONE / RECHECK_ON_EVENT |
| 000400 | 许继电气 | DONE / RECHECK_ON_EVENT |
| 600312 | 平高电气 | DONE |
| 601567 | 三星电气 | DONE / RECHECK_ON_EVENT |
| 002270 | 华明装备 | DONE / RECHECK_ON_EVENT |

## Strategic scarce resources

| Code | Name | Status |
|---|---|---|
| 600549 | 厦门钨业 | DONE / RECHECK_ON_EVENT |
| 000657 | 中钨高新 | DONE / RECHECK_ON_EVENT |
| 002378 | 章源钨业 | DONE / RECHECK_ON_EVENT |
| 601020 | 华钰矿业 | DONE / RECHECK_ON_EVENT |
| 600497 | 驰宏锌锗 | DONE / RECHECK_ON_EVENT |
| 002428 | 云南锗业 | DONE / WAIT_FOR_PRICE |
| 000962 | 东方钽业 | DONE / RECHECK_ON_EVENT |

## Semiconductor equipment / materials

| Code | Name | Status |
|---|---|---|
| 002371 | 北方华创 | DONE / RECHECK_ON_EVENT |
| 688012 | 中微公司 | DONE / RECHECK_ON_EVENT |
| 688072 | 拓荆科技 | DONE / RECHECK_ON_EVENT |
| 688120 | 华海清科 | DONE / RECHECK_ON_EVENT |
| 300604 | 长川科技 | DONE / WAIT_FOR_PRICE |
| 688019 | 安集科技 | DONE |
| 300666 | 江丰电子 | DONE / RECHECK_ON_EVENT |
| 300054 | 鼎龙股份 | DONE / WAIT_FOR_PRICE |

## Storage / memory

| Code | Name | Status |
|---|---|---|
| 603986 | 兆易创新 | DONE / RECHECK_ON_EVENT |
| 688525 | 佰维存储 | DONE / RECHECK_ON_EVENT |
| 301308 | 江波龙 | DONE / RECHECK_ON_EVENT |
| 001309 | 德明利 | DONE / WAIT_FOR_PRICE |
| 300475 | 香农芯创 | DONE / WAIT_FOR_PRICE |
| 300223 | 北京君正 | DONE / WAIT_FOR_PRICE |
| 688766 | 普冉股份 | DONE / WAIT_FOR_PRICE |
| 301666 | 大普微 | DONE / BLOCKED_DATA_PRICE |

## AI hardware / data-center infrastructure

| Code | Name | Status |
|---|---|---|
| 300502 | 新易盛 | DONE / RECHECK_ON_EVENT |
| 300308 | 中际旭创 | DONE / RECHECK_ON_EVENT |
| 300394 | 天孚通信 | DONE / WAIT_FOR_PRICE |
| 300476 | 胜宏科技 | DONE / RECHECK_ON_EVENT |
| 002463 | 沪电股份 | DONE |
| 002916 | 深南电路 | DONE / WAIT_FOR_PRICE |
| 002837 | 英维克 | DONE / RECHECK_ON_EVENT |

# Immediate autonomous code/model queue

## P0 — Fix Research Pool recall without weakening Formal BUY

Status:

```text
IN_PROGRESS
```

Primary real-world regression case:

```text
600312 平高电气
```

Observed production behavior:

```text
2026-08-14 close: 19.53
2026E consensus profit reference: ~14.12 亿
approx 2026E PE: ~18.8x
Q1 recurring profit: +14.45% YoY
legacy outer quant status: HARD_REJECT
legacy hard blocker: price_too_high
5y price percentile: 91.2%
```

Concrete failure mode:

```text
all_a_full_scan.quant_screen()
  5y price percentile > 75%
  -> price_too_high
  -> HARD_REJECT

but

later opportunity-engine / fundamental / reverse-valuation logic
  may never get a chance to inspect the stock
```

PR #23 already softens the **inner** research-pipeline price-position blocker for `STRONG_TREND_RESEARCH` / `EARNINGS_INFLECTION`.

The remaining failure is the **outer full-A quant-screen admission layer**.

Do not solve this by blindly deleting `price_too_high`, because:

```text
priority + secondary queues already exceed the 80-name fundamental budget
```

and a simple hard->soft change can still leave evidence-backed candidates buried in `LOW_PRIORITY`.

Required design:

```text
bounded high-recall research admission
+ existing evidence / opportunity semantics
+ no minimum quota
+ no fake score bonus
+ preserve compute budget
+ preserve Formal BUY strictness
```

Success criteria:

1. Pinggao-like evidence-backed cases can reach Research Pool/deep review.
2. Historical high price still appears as expectation/crowding/entry-risk evidence.
3. Formal BUY / Risk-Capped / market-regime / entry / stop / exit / invalidation / sizing controls are unchanged.
4. Regression test proves the outer-screen recovery path.
5. Full-A validation reports recovered research candidates separately from Formal BUY.
6. No uncontrolled explosion of the deep-review queue.

## P0 — PR #25 valuation core

PR:

```text
#25 feat: add fundamental reverse valuation core
branch: feat/fundamental-reverse-valuation
```

Latest known session fix:

```text
tests/test_genge_scenario_odds.py
import corrected to src.strategies...
head observed after fix: 33da10391bd5d27354ff96c42a74dab2f9e0954a
```

At the time of the previous check:

```text
GenGe Risk-Capped Opportunity Discovery: SUCCESS
GenGe Opportunity Discovery: SUCCESS
CI: was still running
GenGe Cycle Bottom: was still running
```

A new session must re-check current PR/CI state rather than trusting this transient status.

PR #25 remains Draft and must not be wired directly into Formal BUY without separate validation.

## P0 — PR #23 market-adaptation / research-policy layer

PR:

```text
#23 Add rolling factor IC and multi-horizon sector regime
branch: feat/factor-ic-market-regime
```

Key relationship to the current regression:

- PR #23 already handles inner pipeline price-position resilience.
- It does **not** by itself solve the outer `all_a_full_scan.quant_screen()` `price_too_high` early-rejection path.
- Avoid duplicate wrappers / conflicting parallel implementations.
- PR #23 and PR #25 previously had no changed-file overlap.

# Event-driven recheck queue

These events supersede prior preview/Q1 assumptions. Re-run automatically when analysis occurs after the event date **and** the filing is actually available.

| Date | Code | Name | Event | Status |
|---|---|---|---|---|
| 2026-08-19 | 603986 | 兆易创新 | 2026H1 report | RECHECK_ON_EVENT |
| 2026-08-20 | 688012 | 中微公司 | 2026H1 report | RECHECK_ON_EVENT |
| 2026-08-20 | 000682 | 东方电子 | 2026H1 report | RECHECK_ON_EVENT |
| 2026-08-21 | 688072 | 拓荆科技 | 2026H1 report | RECHECK_ON_EVENT |
| 2026-08-24 | 000657 | 中钨高新 | 2026H1 report | RECHECK_ON_EVENT |
| 2026-08-24 | 300308 | 中际旭创 | 2026H1 report | RECHECK_ON_EVENT |
| 2026-08-25 | 002378 | 章源钨业 | 2026H1 report | RECHECK_ON_EVENT |
| 2026-08-25 | 688525 | 佰维存储 | 2026H1 report | RECHECK_ON_EVENT |
| 2026-08-25 | 300666 | 江丰电子 | 2026H1 report | RECHECK_ON_EVENT |
| 2026-08-25 | 300502 | 新易盛 | 2026H1 report | RECHECK_ON_EVENT |
| 2026-08-25 | 002837 | 英维克 | 2026H1 report | RECHECK_ON_EVENT |
| 2026-08-26 | 002371 | 北方华创 | 2026H1 report | RECHECK_ON_EVENT |
| 2026-08-27 | 301308 | 江波龙 | 2026H1 report | RECHECK_ON_EVENT |
| 2026-08-27 | 600406 | 国电南瑞 | 2026H1 report | RECHECK_ON_EVENT |
| 2026-08-29 | 688120 | 华海清科 | 2026H1 report | RECHECK_ON_EVENT |
| 2026-08-29 | 002270 | 华明装备 | 2026H1 report | RECHECK_ON_EVENT |
| 2026-08-31 | 601567 | 三星电气 | 2026H1 report | RECHECK_ON_EVENT |

Dates are scheduling references from the research session and must be re-verified if a filing is not found.

# Completed durable research logs

```text
MARKET_RESEARCH_LOG_2026-08-16_BATCH2.md
MARKET_RESEARCH_LOG_2026-08-16_BATCH3.md
MARKET_RESEARCH_LOG_2026-08-16_BATCH4.md
MARKET_RESEARCH_LOG_2026-08-16_BATCH5.md
MARKET_RESEARCH_LOG_2026-08-16_BATCH6.md
MARKET_RESEARCH_LOG_2026-08-16_BATCH7.md
MARKET_RESEARCH_LOG_2026-08-16_BATCH8.md
MARKET_RESEARCH_LOG_2026-08-16_BATCH9.md
MARKET_RESEARCH_LOG_2026-08-16_BATCH10.md
MARKET_RESEARCH_LOG_2026-08-16_BATCH11.md
MARKET_RESEARCH_LOG_2026-08-16_BATCH12.md
MARKET_RESEARCH_LOG_2026-08-16_BATCH13.md
```

# New-session resume protocol

Read in order:

```text
AGENTS.md
CURRENT_MARKET_RESEARCH.md
RESEARCH_QUEUE.md
MODEL_EVOLUTION_LOG.md
MARKET_RESEARCH_LOG_2026-08-16_BATCH13.md
latest relevant earlier batch log when drilling into a stock
```

Then:

1. inspect latest `main` and open PRs;
2. re-check PR #23 / #25 CI and mergeability;
3. if the date is still before the next event filing, continue the P0 outer quant-screen research-admission regression;
4. if an event filing is now available, freshen price + filing + industry data and run the event recheck before reusing old conclusions;
5. persist every meaningful batch;
6. update this queue immediately so it cannot lag behind the durable research logs again;
7. continue without asking the user to type “继续”;
8. before session context gets close to exhaustion, stop, persist the exact breakpoint, and tell the user to open a new window.
