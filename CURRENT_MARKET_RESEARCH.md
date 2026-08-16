# Current Market Research Handoff

> Purpose: durable handoff for ongoing market/sector/stock research across ChatGPT/Codex sessions.
>
> This file is **not** a static recommendation list. Every new session must refresh market data before reusing any conclusion below.

## Repository context

- Repository: `wanggenAi/daily_stock_analysis`
- Branch: `main`
- Repository state observed before this handoff: latest commit `deb3a7202d15cc076916127e4689a6b92efd1c7a` (`Fail closed on incomplete recovery profiles`)
- Research handoff created: 2026-08-16 (Asia/Singapore / China Standard Time)

## Hard research invariant: fresh data first

Before **every** formal market review, sector ranking, stock valuation, full-A-share scan, or BUY decision:

1. Re-fetch the latest available market data.
2. Record the analysis time and latest trading day.
3. Refresh current price / market cap before calculating valuation, implied profit, margin of safety, odds, or entry zones.
4. Refresh the latest annual/quarterly/semiannual report, earnings preview/flash report, major orders, capacity changes, product/commodity prices, regulation/export restrictions, and other material events when relevant.
5. Refresh the relevant industry driver (examples: tungsten concentrate/APT for tungsten, antimony price for antimony, DRAM/NAND/HBM supply/price for storage, grid tender/order data for power equipment).
6. If the latest price/market-cap data cannot be verified, mark price freshness `UNVERIFIED`, lower valuation confidence, and **do not produce a new Formal BUY from stale prices**.
7. Old conclusions are prior context only. Recompute today's state from today's data.

Required snapshot fields:

```text
analysis_as_of
analysis_run_time
latest_trading_day
price_timestamp
fundamental_data_as_of
industry_data_as_of
commodity_data_as_of
news_cutoff_time
market_data_freshness
price_freshness
fundamental_freshness
industry_freshness
commodity_freshness
news_freshness
```

Freshness enum:

```text
FRESH
ACCEPTABLE
STALE
UNVERIFIED
```

Core rule:

> Historical analysis is context; latest verified data is the fact base for the current decision.

## Research architecture currently agreed

The research system should follow:

```text
Fresh-data snapshot
  -> broad discovery / high recall
  -> true Hard Reject gates
  -> industry / commodity driver
  -> normalized sustainable earnings
  -> earnings quality
  -> bear / base / bull scenarios
  -> dynamic fair multiple
  -> fair market cap / fair price
  -> reverse implied market profit
  -> required profit growth / expectation gap
  -> margin of safety
  -> valuation odds
  -> valuation confidence
  -> research ranking
  -> technical entry readiness
  -> market regime / Risk-Capped / stop / invalidation / position sizing
  -> Formal BUY or WAIT
```

Design principles:

- Hard risks eliminate; soft conditions rank.
- Research Pool is broad; Formal BUY remains strict.
- Valuation/fundamentals decide **what** is worth owning; technical/risk controls decide **when** to enter.
- Static PE must not be a standalone hard reject when forward earnings are inflecting.
- Strategic scarcity is a research-priority factor, not proof that a stock is cheap.
- For cyclicals, low PE near peak earnings can be dangerous; normalize the cycle.
- Do not force a minimum number of BUY signals.
- Data gaps lower confidence; never invent missing data.

## Current market research status

### Analysis snapshot

- Analysis date: 2026-08-16 (Sunday)
- Latest A-share trading day expected: 2026-08-14 (Friday)
- Fundamental/industry data: refreshed during the session where available
- Exact 2026-08-14 A-share closing prices: **not reliably verified from the public web sources available in-session**
- Therefore: current precise MOS / BUY / entry-price outputs remain gated until price freshness is verified

### Current sector research priority

This is a **research priority**, not a BUY ranking:

1. `P0` Grid / AIDC power infrastructure
2. `P0` Strategic scarce resources: tungsten / antimony / germanium / tantalum-niobium etc.
3. `P0` Semiconductor equipment / materials
4. `P0 research, P1 price` Storage (very strong earnings, but high expectation/crowding risk)
5. `P1` CPO / optical modules / PCB / liquid cooling
6. `P1` Innovative drugs / CXO
7. `P1` Energy storage / power electronics
8. `P2` Commercial space
9. `P2` Robotics

The intended daily output should contain two different rankings:

- `Trend Top`: strongest sectors/themes now.
- `Mispricing Top`: strongest earnings/industry drivers where current market expectations appear insufficiently priced.

Do not merge these two concepts.

## First deep-valuation batch

### 600549 厦门钨业

Current research view: `VALUE_CANDIDATE / PRIORITY_RESEARCH`, **not Formal BUY until fresh price verification**.

Latest fundamental basis used in the session:

- 2026H1 attributable net profit around 22.16bn RMB? **Unit check required before reuse.** The session source reported `22.16 亿人民币`, i.e. about **2.216bn RMB**. Future sessions must preserve Chinese-unit conversion carefully.
- 2026H1 recurring attributable profit around `21.76 亿人民币` (about **2.176bn RMB**).
- H1 profit was close to the prior full-year level and recurring/non-recurring gap was small.
- Business mix: tungsten/molybdenum + new-energy materials + rare earth; more diversified than a pure upstream miner.

Working normalized-profit scenarios from the session (must be revalidated against latest filings and commodity prices):

```text
Bear: 32-34 亿 RMB
Base: 37-40 亿 RMB
Bull: 44-47 亿 RMB
```

Working model example used previously:

```text
Bear: 33 亿 @ 15x
Base: 38.5 亿 @ 20x
Bull: 45.5 亿 @ 24x
```

Key thesis:

- Scarcity + resource ownership + downstream processing.
- Better earnings predictability than a pure tungsten-beta stock, but still materially cyclical.

Primary next calculation:

- Re-fetch current price/market cap.
- Re-fetch latest tungsten concentrate/APT prices.
- Reverse solve implied normalized profit and implied tungsten-price/cycle assumption.

### 000657 中钨高新

Current research view: `PRIORITY_RESEARCH / CYCLE_VALUATION_REQUIRED`; prior historical-price test indicated `EXPECTATION_HIGH / WAIT_FOR_PRICE`.

Latest fundamental basis used in the session:

- 2026H1 attributable net-profit preview: about `19.7-21.7 亿 RMB`.
- 2026H1 recurring net-profit preview: about `19.55-21.55 亿 RMB`.
- Very high earnings quality in the preview: headline and recurring profit are close.
- Major drivers: tungsten raw-material price, self-owned resources, integrated tungsten chain, PCB micro-drill/high-end tool demand.

Working normalized-profit scenarios (must be revalidated):

```text
Bear: 29-31 亿 RMB
Base: 34-36 亿 RMB
Bull: 40-42 亿 RMB
```

Working model example used previously:

```text
Bear: 30 亿 @ 18x
Base: 35 亿 @ 24x
Bull: 41 亿 @ 30x
```

Key warning:

- Do **not** annualize H1 by simply multiplying by two.
- Tungsten prices were highly volatile in 2026; the cycle driver must be normalized.
- A strong company/commodity thesis can still be a poor stock price if current market cap already requires a Bull scenario.

Primary next calculation:

- Reverse-solve implied tungsten price / implied normalized profit from a newly verified current market cap.

### 002028 思源电气

Current research view: `HIGH_QUALITY / PRIORITY_RESEARCH / WAIT_FOR_PRICE`, pending fresh current-price verification.

Latest fundamental basis used in the session:

- 2026H1 revenue roughly `108.03 亿 RMB`, +27.14% YoY.
- 2026H1 attributable net profit roughly `14.87 亿 RMB`, +15.03% YoY.
- 2026H1 recurring net profit roughly `14.19 亿 RMB`, +14.83% YoY.
- Headline/recurring profit are close -> high earnings quality.
- Revenue growth remained strong while profit growth decelerated versus 2025; do not extrapolate 2025's very high profit-growth rate mechanically.

Working normalized-profit scenarios (must be revalidated):

```text
Bear: 32-34 亿 RMB
Base: 35-37 亿 RMB
Bull: 39-41 亿 RMB
```

Working model example used previously:

```text
Bear: 33 亿 @ 25x
Base: 36 亿 @ 32x
Bull: 40 亿 @ 38x
```

Key thesis:

- Grid capex + overseas transmission/distribution + AIDC power infrastructure.
- Lower commodity-cycle sensitivity and higher earnings predictability than tungsten names.
- Company quality can justify a quality premium, but a high-quality company is not automatically a high-odds price.

Primary next calculation:

- Re-fetch current price/market cap and latest H1/full filing status.
- Compute implied profit at reasonable quality-adjusted multiples and compare to normalized Base.

### 002270 华明装备

Current research view: `SECONDARY_RESEARCH / WAIT_FOR_FUNDAMENTAL_CONFIRMATION`.

Reason:

- 2025 quality/profitability was strong, but the latest 2026Q1 data used in the session showed slower revenue growth and negative net-profit growth.
- This is an important negative-control case: a strong grid sector does not mean every grid-equipment company has a current earnings inflection.

Do not promote solely because the sector is hot.

## Next deep-valuation batch

Run in this order, with a fresh data snapshot before calculations:

1. `002371 北方华创`
2. `688012 中微公司`
3. `688072 拓荆科技`
4. `301308 江波龙`
5. `688525 佰维存储`

Purpose of this batch:

> Test whether a high static PE is truly expensive, or whether forward earnings growth compresses the valuation enough to create a positive expectation gap.

For storage names, explicitly normalize cycle earnings instead of valuing on peak H1 profit.

## Wider research universe already identified

### Strategic scarce resources

```text
000657 中钨高新
002378 章源钨业
600549 厦门钨业
601020 华钰矿业
600497 驰宏锌锗
002428 云南锗业
000962 东方钽业
```

### Storage

```text
603986 兆易创新
688525 佰维存储
301308 江波龙
001309 德明利
300475 香农芯创
300223 北京君正
688766 普冉股份
301666 大普微
```

### Semiconductor equipment / materials

```text
002371 北方华创
688012 中微公司
688072 拓荆科技
688120 华海清科
300604 长川科技
688019 安集科技
300666 江丰电子
300054 鼎龙股份
```

### Grid / AI power infrastructure

```text
002028 思源电气
000400 许继电气
600312 平高电气
600406 国电南瑞
601567 三星医疗
002270 华明装备
```

### AI hardware / highly crowded watchlist

```text
300502 新易盛
300308 中际旭创
300394 天孚通信
300476 胜宏科技
002463 沪电股份
002916 深南电路
002837 英维克
```

These names should carry an explicit `expectation_penalty` / crowding check. Strong industry growth does not imply good stock-level odds.

## Required per-stock output

For every candidate with adequate data, output at minimum:

```text
Current Price
Current Market Cap
Normalized Profit Bear/Base/Bull
EPS Bear/Base/Bull
Fair Multiple Bear/Base/Bull
Fair Price Bear/Base/Bull
Static PE
TTM PE
Forward PE Bear/Base/Bull
Implied Profit
Implied EPS
Required Profit Growth
Expectation Gap
Margin of Safety
Valuation Odds
Valuation Confidence
Earnings Quality
Cycle Stage / Cycle Risk
Strategic Scarcity (when applicable)
Watch Price
First Entry Price
Ideal Entry Price
Core Thesis
Earnings Driver
Valuation Driver
Key Catalyst
Key Risk
Why Now
Why Not Buy Yet
```

## Resume protocol for a new session

A new ChatGPT/Codex session should do this first:

1. Read `AGENTS.md` and this file.
2. Inspect the current `main` branch and latest commit; repository code is the source of truth.
3. **Do not trust the old prices in this file as current.** Create a fresh Analysis Snapshot.
4. Re-fetch the latest A-share trading-day market snapshot and current prices for the next batch.
5. Re-fetch the latest filing / earnings preview and relevant industry/commodity drivers.
6. Continue the `Next deep-valuation batch` above.
7. Update this file after each meaningful analysis batch with:
   - as-of time,
   - verified data freshness,
   - new rankings/status,
   - completed names,
   - next names,
   - unresolved data-quality issues.
8. Keep `Research Pool = broad` and `Formal BUY = strict`.

## Known unresolved issue

The current research session found that public web pages/search indexes can lag or mix dates when retrieving exact A-share closes. The production system should treat current-price retrieval as a first-class data-provider/freshness problem:

```text
primary reliable market source
  -> secondary/fallback source
  -> cross-check trading date
  -> freshness gate
  -> valuation
```

Do not let a sophisticated valuation engine consume a stale or wrong `current_price` silently.
