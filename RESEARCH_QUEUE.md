# Research Queue

> Durable autonomous queue for ongoing market / sector / stock research.
>
> User instruction: do **not** stop after every single stock waiting for a manual “继续”. Process this queue continuously in priority order. Only pause for the user when a decision genuinely requires user preference/approval, or when safety/data-integrity rules block further execution.
>
> Every item must still obey the fresh-data hard rule in `CURRENT_MARKET_RESEARCH.md`: old prices/statuses are context only; refresh the latest available market/fundamental/industry data before a formal conclusion.

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

## P0 — Active cross-sector valuation queue

Purpose: compare scarce resources, grid/power infrastructure, semiconductor equipment/materials, storage and AI hardware on one odds framework.

| Order | Code | Name | Theme | Status | Main research question |
|---:|---|---|---|---|---|
| 1 | 002378 | 章源钨业 | Tungsten | IN_PROGRESS | How much of H1 tungsten windfall is sustainable through-cycle? |
| 2 | 000682 | 东方电子 | Grid / distribution automation | QUEUED | Is valuation materially cheaper than premium grid leaders while earnings quality stays high? |
| 3 | 600406 | 国电南瑞 | Grid / power automation | QUEUED | Quality anchor: what premium multiple is justified and what growth is already priced? |
| 4 | 000400 | 许继电气 | Grid / UHV | QUEUED | UHV/order cycle versus current expectation. |
| 5 | 600312 | 平高电气 | UHV / high-voltage equipment | QUEUED | Order conversion, margin expansion, overseas optionality. |
| 6 | 601567 | 三星医疗 | Distribution / smart metering / overseas | QUEUED | Overseas growth quality versus valuation. |
| 7 | 601020 | 华钰矿业 | Antimony / precious metals | QUEUED | Scarcity and commodity-cycle normalization. |
| 8 | 600497 | 驰宏锌锗 | Zinc / germanium | QUEUED | Germanium scarcity versus zinc-cycle dilution. |
| 9 | 002428 | 云南锗业 | Germanium | QUEUED | Strategic scarcity versus actual sustainable profit. |
| 10 | 000962 | 东方钽业 | Tantalum / niobium | QUEUED | Scarcity + downstream value-add versus current expectations. |

## P1 — Semiconductor / storage expansion queue

Already completed core names are kept for event-driven rechecks below. Continue breadth after the P0 cross-sector set.

| Code | Name | Status |
|---|---|---|
| 688120 | 华海清科 | DONE |
| 300604 | 长川科技 | DONE |
| 688019 | 安集科技 | DONE |
| 300666 | 江丰电子 | DONE |
| 603986 | 兆易创新 | DONE |
| 002371 | 北方华创 | DONE / RECHECK_ON_EVENT |
| 688012 | 中微公司 | DONE / RECHECK_ON_EVENT |
| 688072 | 拓荆科技 | DONE / RECHECK_ON_EVENT |
| 301308 | 江波龙 | DONE / RECHECK_ON_EVENT |
| 688525 | 佰维存储 | DONE / RECHECK_ON_EVENT |
| 300054 | 鼎龙股份 | QUEUED |
| 001309 | 德明利 | QUEUED |
| 300475 | 香农芯创 | QUEUED |
| 300223 | 北京君正 | QUEUED |
| 688766 | 普冉股份 | QUEUED |
| 301666 | 大普微 | QUEUED |

## P1 — AI hardware / data-center infrastructure queue

The valuation PR already contains a valuation-horizon refinement triggered by an AI-hardware batch. Formal research logs should still be completed/normalized and compared cross-sector.

```text
300502 新易盛
300308 中际旭创
300394 天孚通信
300476 胜宏科技
002463 沪电股份
002916 深南电路
002837 英维克
```

Status: QUEUED unless a durable research log already explicitly marks the name complete.

Primary question:

> Does current price require less future profit than a credible earnings path after properly distinguishing CURRENT_FORWARD_PE from discounted TERMINAL_PE?

## P1 — Strategic-resource breadth queue

```text
002378 章源钨业       (active above)
600549 厦门钨业       DONE / recheck with fresh tungsten price
000657 中钨高新       DONE / recheck after H1
601020 华钰矿业       queued above
600497 驰宏锌锗       queued above
002428 云南锗业       queued above
000962 东方钽业       queued above
```

## Event-driven recheck queue

These events supersede prior preview/Q1 assumptions. Re-run automatically when analysis occurs after the event date and the filing is available.

| Date | Code | Name | Event | Status |
|---|---|---|---|---|
| 2026-08-19 | 603986 | 兆易创新 | 2026H1 report | RECHECK_ON_EVENT |
| 2026-08-20 | 688012 | 中微公司 | 2026H1 report | RECHECK_ON_EVENT |
| 2026-08-20 | 000682 | 东方电子 | 2026H1 report | RECHECK_ON_EVENT |
| 2026-08-21 | 688072 | 拓荆科技 | 2026H1 report | RECHECK_ON_EVENT |
| 2026-08-24 | 000657 | 中钨高新 | 2026H1 report | RECHECK_ON_EVENT |
| 2026-08-25 | 002378 | 章源钨业 | 2026H1 report | RECHECK_ON_EVENT |
| 2026-08-25 | 688525 | 佰维存储 | 2026H1 report | RECHECK_ON_EVENT |
| 2026-08-25 | 300666 | 江丰电子 | 2026H1 report | RECHECK_ON_EVENT |
| 2026-08-26 | 002371 | 北方华创 | 2026H1 report | RECHECK_ON_EVENT |
| 2026-08-27 | 301308 | 江波龙 | 2026H1 report | RECHECK_ON_EVENT |
| 2026-08-27 | 600406 | 国电南瑞 | 2026H1 report | RECHECK_ON_EVENT |
| 2026-08-29 | 688120 | 华海清科 | 2026H1 report | RECHECK_ON_EVENT |

Dates are scheduling references from the research session and must be re-verified if a filing is not found.

## Completed durable research logs

```text
MARKET_RESEARCH_LOG_2026-08-16_BATCH2.md
MARKET_RESEARCH_LOG_2026-08-16_BATCH3.md
MARKET_RESEARCH_LOG_2026-08-16_BATCH4.md
MARKET_RESEARCH_LOG_2026-08-16_BATCH5.md
MARKET_RESEARCH_LOG_2026-08-16_BATCH6.md
```

## Current model / code work

- PR #25 `feat: add fundamental reverse valuation core` — Draft; continue adding only evidence-backed primitives/regressions.
- PR #23 `Add rolling factor IC and multi-horizon sector regime` — separate market-adaptation layer; avoid conflicting wrappers.
- Temporary validation PRs are not production features and should not be treated as the code source of truth.

## Autonomous continuation rule for a new session

A new ChatGPT/Codex session should read, in order:

```text
AGENTS.md
CURRENT_MARKET_RESEARCH.md
RESEARCH_QUEUE.md
MODEL_EVOLUTION_LOG.md
latest MARKET_RESEARCH_LOG_*.md
```

Then:

1. inspect `main` and open PRs;
2. refresh latest market/fundamental/industry data;
3. pick the highest-priority `IN_PROGRESS`, otherwise first `QUEUED` item;
4. run it to completion;
5. write/update durable research output;
6. advance queue status;
7. continue immediately to the next item without asking the user to type “继续”.
