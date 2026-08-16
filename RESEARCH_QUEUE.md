# Research Queue

> Durable autonomous queue for ongoing market / sector / stock research.
>
> User instruction: do **not** stop after every single stock waiting for a manual “继续”. Process this queue continuously in priority order. Only pause when a decision genuinely requires user preference/approval, safety/data-integrity blocks execution, or the current session is approaching context exhaustion and must first persist an exact handoff.

## Fresh-data hard rule

Every formal market review / sector ranking / stock valuation / BUY decision must obey `CURRENT_MARKET_RESEARCH.md`:

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
-> update durable GitHub research log
-> if reproducible model failure: minimal code fix + regression test in valuation PR
-> immediately continue to next queue item
```

Do not create a new metric merely because a case is unusual. Reuse existing primitives where they already model the failure correctly.

## Queue status — corrected 2026-08-16

The old version of this file incorrectly stopped at `000400 许继电气 IN_PROGRESS`. That status was stale.

The repository contains completed research through:

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
MARKET_RESEARCH_MASTER_RANKING_2026-08-16.md
```

**The initial deep-research universe is complete. Do not restart from 许继电气.**

## Completed P0 / cross-sector names

```text
002378 章源钨业       DONE / RECHECK_ON_EVENT
000682 东方电子       DONE / RECHECK_ON_EVENT
600406 国电南瑞       DONE / RECHECK_ON_EVENT
000400 许继电气       DONE / RECHECK_ON_EVENT
600312 平高电气       DONE
601567 三星电气       DONE / RECHECK_ON_EVENT
601020 华钰矿业       DONE / RECHECK_ON_EVENT
600497 驰宏锌锗       DONE
002428 云南锗业       DONE
000962 东方钽业       DONE / RECHECK_ON_EVENT
```

## Completed semiconductor / storage breadth

```text
688120 华海清科       DONE
300604 长川科技       DONE
688019 安集科技       DONE
300666 江丰电子       DONE / RECHECK_ON_EVENT
603986 兆易创新       DONE / RECHECK_ON_EVENT
002371 北方华创       DONE / RECHECK_ON_EVENT
688012 中微公司       DONE / RECHECK_ON_EVENT
688072 拓荆科技       DONE / RECHECK_ON_EVENT
301308 江波龙         DONE / RECHECK_ON_EVENT
688525 佰维存储       DONE / RECHECK_ON_EVENT
300054 鼎龙股份       DONE
001309 德明利         DONE
300475 香农芯创       DONE
300223 北京君正       DONE
688766 普冉股份       DONE
301666 大普微         DONE / PRICE_UNVERIFIED
```

## Completed AI hardware / data-center infrastructure breadth

```text
300502 新易盛         DONE / RECHECK_ON_EVENT
300308 中际旭创       DONE / A_H_MARKET_CAP_PRECISION
300394 天孚通信       DONE
300476 胜宏科技       DONE / A_H_MARKET_CAP_PRECISION
002463 沪电股份       DONE
002916 深南电路       DONE
002837 英维克         DONE / FUNDAMENTAL_RECOVERY_REQUIRED
```

## Completed first-batch carryovers

```text
600549 厦门钨业       DONE / PRICE_REFRESH_REQUIRED
000657 中钨高新       DONE / RECHECK_ON_EVENT / PRICE_REFRESH_REQUIRED
002028 思源电气       DONE / PRICE_REFRESH_REQUIRED
002270 华明装备       DONE / RECHECK_ON_EVENT
```

## Current master ranking breakpoint

`MARKET_RESEARCH_MASTER_RANKING_2026-08-16.md` is the current cross-sector source of truth.

Current top expectation-vs-earnings research set:

```text
600406 国电南瑞
000682 东方电子
000400 许继电气
300502 新易盛
300308 中际旭创   # lower confidence: A/H precision + H1 pending
002463 沪电股份
688019 安集科技
600312 平高电气
002270 华明装备
```

Current cycle research set:

```text
001309 德明利
603986 兆易创新
600549 厦门钨业
000657 中钨高新
301308 江波龙
688525 佰维存储
```

## Data-quality corrections / open defects

### 000400 许继电气 — Batch 9 correction

Do not reuse the incorrect Batch 9 headline/revenue basis.

Verified filing basis to carry forward:

```text
2025 revenue: ~149.92 亿
2025 attributable profit: ~11.67 亿
2025 recurring attributable profit: ~11.22 亿
2026Q1 revenue: ~23.78 亿
2026Q1 attributable profit: ~1.11 亿
2026Q1 recurring attributable profit: ~1.07 亿
```

2026 UHV order optionality also includes two disclosed wins of roughly `12.75 亿` and `12.45 亿`.

### 300223 canonical security name

Production data has been observed labelling `300223` as `君正股份`; the correct security is `北京君正`. This is a security-master/data-quality defect, not a valuation issue.

### A/H market cap

For `603986`, `300308`, `300476` and other dual-listed names, do not label `A price × all economic shares` as actual consolidated market cap. Use class-specific share counts, class prices and FX or mark consolidated market cap `UNVERIFIED`.

## Event-driven recheck queue

Re-run only once the filing is actually available; dates are scheduling references and must be verified.

| Date | Code | Name | Event | Status |
|---|---|---|---|---|
| 2026-08-19 | 603986 | 兆易创新 | 2026H1 report | RECHECK_ON_EVENT |
| 2026-08-20 | 688012 | 中微公司 | 2026H1 report | RECHECK_ON_EVENT |
| 2026-08-20 | 000682 | 东方电子 | 2026H1 report | RECHECK_ON_EVENT |
| 2026-08-20 | 000400 | 许继电气 | 2026H1 report | RECHECK_ON_EVENT |
| 2026-08-21 | 688072 | 拓荆科技 | 2026H1 report | RECHECK_ON_EVENT |
| 2026-08-24 | 000657 | 中钨高新 | 2026H1 report | RECHECK_ON_EVENT |
| 2026-08-24 | 300308 | 中际旭创 | 2026H1 report | RECHECK_ON_EVENT |
| 2026-08-25 | 002378 | 章源钨业 | 2026H1 report | RECHECK_ON_EVENT |
| 2026-08-25 | 688525 | 佰维存储 | 2026H1 report | RECHECK_ON_EVENT |
| 2026-08-25 | 300666 | 江丰电子 | 2026H1 report | RECHECK_ON_EVENT |
| 2026-08-25 | 300502 | 新易盛 | 2026H1 report | RECHECK_ON_EVENT |
| 2026-08-26 | 002371 | 北方华创 | 2026H1 report | RECHECK_ON_EVENT |
| 2026-08-27 | 301308 | 江波龙 | 2026H1 report | RECHECK_ON_EVENT |
| 2026-08-27 | 600406 | 国电南瑞 | 2026H1 report | RECHECK_ON_EVENT |
| 2026-08-29 | 688120 | 华海清科 | 2026H1 report | RECHECK_ON_EVENT |
| 2026-08-29 | 002270 | 华明装备 | 2026H1 report | RECHECK_ON_EVENT |

## Current model / code work

- PR #25 `feat: add fundamental reverse valuation core` — Draft, mergeable, but **main CI still failing** in `backend-gate -> Offline test suite` at head `33da10391bd5d27354ff96c42a74dab2f9e0954a`. Three specialized GenGe workflows are green. Do not integrate into Formal BUY until CI is fully green.
- PR #23 `Add rolling factor IC and multi-horizon sector regime` — separate market-adaptation layer; validate independently.

## Immediate next work

Priority order from this breakpoint:

```text
1. Diagnose PR #25 backend-gate offline-test failure; only minimal evidence-backed fix.
2. Correct the 300223 security-master canonical-name defect if the exact source is found and a minimal regression can be added.
3. Preserve the 000400 filing correction in future logs/rankings; do not silently reuse Batch 9 bad numbers.
4. No random new-stock expansion before the next market snapshot.
5. After 2026-08-17 market close, refresh the top master-ranking candidates first and recompute expectation gaps / entry readiness.
6. On or after scheduled filing dates, run the event-driven rechecks automatically when the filing is actually available.
```

## Autonomous continuation rule for a new session

A new ChatGPT/Codex session should read, in order:

```text
AGENTS.md
CURRENT_MARKET_RESEARCH.md
RESEARCH_QUEUE.md
MODEL_EVOLUTION_LOG.md
MARKET_RESEARCH_MASTER_RANKING_2026-08-16.md
latest MARKET_RESEARCH_LOG_*.md
```

Then:

1. inspect `main` and open PRs;
2. do **not** restart the completed stock queue;
3. take the highest-priority item under `Immediate next work`;
4. persist every meaningful batch/status change;
5. continue automatically without waiting for “继续”;
6. before context exhaustion, stop expansion and persist exact completed work, breakpoint, remaining queue, PR/CI state and next steps, then ask the user to open a new window.
