# Model Coverage Matrix — 2026-08-16

> Purpose: define what “model complete enough for historical regression/backtest” means.
>
> This is **not** a claim that every A-share must be manually researched one by one. The production discovery layer already builds an All-A universe from official SSE/SZSE listings. Model completeness instead requires representative, adversarial coverage across materially different business/valuation archetypes before historical backtesting is allowed to become the primary optimization loop.

## 1. Current completion status

**Status: MODEL_INCOMPLETE — EXPAND ARCHETYPE COVERAGE BEFORE BROAD HISTORICAL BACKTEST**

The initial 2026-08-16 deep-research queue is complete, but it is concentrated in:

- power-grid / electrical equipment;
- scarce resources / non-ferrous metals;
- semiconductor equipment, materials and memory;
- AI optical / PCB / cooling hardware.

Those samples were sufficient to expose and implement several important generic primitives — earnings-quality normalization, cycle normalization, reverse implied expectations, share-count / A-H handling, financing and non-operating asset bridges, duration stress tests — but they are **not sufficient to validate one universal equity valuation model**.

## 2. Universe layer: confirmed architecture

Production `all_a_full_scan.py` builds the security universe directly from official exchange listings:

- SSE Main Board + STAR via the Shanghai Stock Exchange official commonQuery endpoint;
- Shenzhen A-shares via the Shenzhen Stock Exchange official ShowReport endpoint;
- repository snapshots are only a bounded-age fallback when the live official listing fetch fails.

Therefore `stock_pools/genge_broad_pool.txt` must **not** be interpreted as the production All-A universe.

### Universe completion gate

Before historical backtesting:

- [x] Official-exchange All-A universe builder exists.
- [x] Listing-date / board / ST / suspension / liquidity fields exist in the universe schema.
- [x] Point-in-time price-history path exists.
- [ ] Canonical security-name resolution defect `300223 -> 北京君正` is located and fixed at the source layer.
- [ ] Historical universe reconstruction is explicitly tested for delisted / renamed / newly listed securities and survivorship-bias controls.

## 3. Valuation/business-model archetype coverage

Legend:

- `VALIDATED`: multiple real names have already been researched deeply enough to exercise the relevant primitives.
- `PARTIAL`: some data/industry support exists, but the valuation adapter is not yet validated across contrasting examples.
- `MISSING`: current generic profit × multiple logic is not sufficient and no validated adapter exists.

| Archetype | Typical sectors | Current status | Existing representative evidence | Required valuation / normalization treatment | Next action |
|---|---|---:|---|---|---|
| High-quality industrial / order-driven | Grid equipment, electrical equipment | VALIDATED | 国电南瑞、东方电子、许继电气、平高电气、思源电气、华明装备、三星电气 | normalized recurring earnings + order/margin confirmation + fair PE + reverse expectations | Keep event-driven H1 refresh |
| Commodity / strategic-resource cycle | Tungsten, rare metals, zinc/germanium | VALIDATED | 章源钨业、厦门钨业、中钨高新、华钰矿业、驰宏锌锗、云南锗业、东方钽业 | forward-cycle vs through-cycle profit; resource scarcity is priority, not valuation proof | Add commodity price / volume point-in-time history for backtest |
| Semiconductor capex / materials quality growth | Equipment, consumables, targets | VALIDATED | 华海清科、长川科技、安集科技、江丰电子、北方华创、中微公司、拓荆科技、鼎龙股份 | core recurring earnings + capex cycle + R&D capitalization diagnostic + duration expectations | H1 event refresh |
| Memory / inventory cycle | DRAM/NOR/NAND controllers/modules | VALIDATED | 兆易创新、江波龙、佰维存储、德明利、北京君正、普冉股份、香农芯创 | inventory/cash-flow + forward-cycle / through-cycle normalization | H1 event refresh |
| AI infrastructure high-duration growth | Optical, PCB, cooling | VALIDATED | 新易盛、中际旭创、天孚通信、胜宏科技、沪电股份、深南电路、英维克 | explicit valuation horizon, required return, terminal multiple, implied future profit | H1 event refresh |
| Stable consumer compounder | Baijiu, food, dairy, appliances | MISSING | none in deep-research set | durable ROIC/ROE, FCF conversion, reinvestment runway, brand/channel durability, normalized margin; PE alone insufficient without growth-duration bridge | **P0 sample batch** |
| Bank | State-owned / joint-stock / city / rural banks | MISSING | industry alias exists, no valuation adapter validation | **PB/ROE + CET1 + NIM + credit cost + NPL/provision + deposit franchise**; generic industrial OCF/PE logic is inappropriate | **P0 sample batch** |
| Insurance | Life / P&C | MISSING | industry alias exists, no deep research | **EV/VNB + NBV growth + solvency + investment spread + CSM/insurance-service quality**; PE only secondary | **P0 sample batch** |
| Broker / capital markets | Securities, wealth/fintech brokers | MISSING | industry alias exists, no deep research | normalized ROE / PB, market turnover sensitivity, proprietary-investment volatility, AUM/wealth economics | **P0 sample batch** |
| Regulated utility / yield asset | Hydro, nuclear, thermal, gas, water | PARTIAL | grid names are not utility operators; aliases/schema exist | DCF/dividend yield / FCFE, tariff and capex cycle, leverage, regulated return; PE only cross-check | P1 sample batch |
| Real estate / property | Developers, property services | MISSING | industry alias/schema exists | NAV / net debt / presales / cash collections / inventory haircut; PE often misleading | P1 sample batch |
| Shipping / aviation / transport | Container, bulk, airlines, airports, logistics | MISSING | industry aliases/schema exist | asset-cycle + freight/yield/load factor + normalized mid-cycle EBITDA/profit + balance sheet | P1 sample batch |
| Agriculture / biological cycle | Hog, poultry, feed | PARTIAL | pig-cycle industry evidence schema exists, but no deep valuation sample in current research logs | biological cycle, cost curve, sow inventory, normalized unit margin, debt survival | P1 sample batch |
| Auto / EV / battery | OEM, parts, battery, materials | MISSING | aliases/schema exist for auto/lithium | product-cycle + capacity utilization + price war + capex/depreciation + battery commodity cycle; separate OEM vs supplier logic | P1 sample batch |
| Solar / wind / storage | PV chain, wind, storage | PARTIAL | industry evidence schema exists, no current deep valuation batch | capacity-clearance cycle, price spread, utilization, balance-sheet survival; avoid peak/negative PE traps | P1 sample batch |
| Coal / oil / petrochemical | Energy resources/refining | MISSING | aliases/schema exist | reserve/production × commodity deck, mid-cycle margins, capex/dividend, policy/tax | P1 sample batch |
| Machinery / automation / robotics | General/special equipment | PARTIAL | electrical equipment samples only | order backlog + utilization + working capital + replacement cycle + normalized ROIC | P2 sample batch |
| Software / SaaS / internet platform | Enterprise software, vertical SaaS/platform | MISSING | no dedicated adapter | ARR/revenue quality, gross margin, S&M/R&D efficiency, FCF, SBC/dilution, Rule-of-40 style diagnostics; PE may be unavailable | P0/P1 depending All-A scan candidates |
| Biotech / pre-profit innovation | Innovative drugs / biotech | MISSING | medical alias exists, no deep research | rNPV / pipeline probability / cash runway / dilution; **PE model must refuse applicability** when pre-profit | **P0 adversarial sample** |
| Defense / aerospace | Defense electronics/equipment | MISSING | no dedicated deep batch | order/backlog, contract liabilities, working capital, customer concentration, procurement cycle, optionality haircut | P1 sample batch |
| High-dividend infrastructure | Toll road, port, selected telecom | MISSING | no deep batch | FCFE/dividend yield, concession life, capex and leverage, growth optionality | P2 sample batch |

## 4. Adapter architecture required before model freeze

The final system should route one security to a **valuation archetype** instead of forcing every company through one monolithic PE model.

Proposed auditable routing contract:

```text
security + point-in-time fundamentals + industry evidence
-> business_model_archetype
-> applicability checks
-> archetype-specific normalized economic metric
-> Bear/Base/Bull assumptions
-> fair equity value / fair price
-> reverse implied expectations
-> confidence + missing-data penalties
-> common ranking layer
-> technical entry readiness
-> market regime / risk-capped gates
-> Formal BUY or WAIT
```

### Common primitives that remain shared

- freshness / point-in-time evidence rules;
- earnings-quality / non-recurring-gain diagnostics where applicable;
- share dilution and multi-share-class market cap;
- explicit Bear/Base/Bull assumptions;
- reverse implied expectations;
- margin of safety / scenario asymmetry;
- confidence reduction rather than fabricated data;
- technical entry and risk gates remain downstream and cannot be bypassed.

### Archetype-specific metric examples

```text
industrial / consumer profitable companies -> normalized earnings / FCF / ROIC + PE/DCF bridge
cyclical commodity/capacity businesses      -> through-cycle profit / NAV / normalized EV metric
bank                                        -> PB <-> sustainable ROE / cost of equity bridge
insurer                                     -> EV/VNB / solvency / investment-spread bridge
broker                                      -> normalized ROE / PB + cycle sensitivity
utility / concession                        -> FCFE / dividend / DCF + leverage
real estate                                 -> NAV + net-debt / inventory / collection haircuts
SaaS                                        -> revenue/FCF unit economics + dilution-aware duration model
pre-profit biotech                          -> probability-adjusted pipeline rNPV + cash runway
```

## 5. Model-completion gates before historical regression/backtest

Historical backtesting must not be used to optimize an architecture that is still structurally wrong. Broad backtest begins only when all gates below are met.

### A. Coverage gates

- [ ] Every material archetype above is either `VALIDATED` or explicitly `OUT_OF_SCOPE` with a hard refusal rule.
- [ ] At least one strong/expensive, one strong/fair-or-cheap, and one weak/false-cheap adversarial sample have been tested for each major archetype where practical.
- [ ] Generic PE path refuses or downgrades confidence when the archetype requires another economic metric.

### B. Data gates

- [ ] Point-in-time fundamentals use publication dates, not future-known annual values.
- [ ] Historical security master handles listing, delisting, rename, A/H share count, splits/dividends/placements.
- [ ] Historical industry/commodity evidence is point-in-time and timestamped.
- [ ] Tradability includes suspension, limit-up/down, lot size and execution timing.
- [ ] Transaction cost and slippage assumptions are explicit and versioned.

### C. Backtest methodology gates

- [ ] No survivorship bias.
- [ ] No look-ahead leakage.
- [ ] Walk-forward / rolling out-of-time validation.
- [ ] Train/calibration period is separated from validation and final holdout.
- [ ] Metrics reported by market regime, industry and archetype — not only pooled average return.
- [ ] BUY/WAIT precision, hit rate, drawdown, turnover, tail loss and opportunity-cost metrics are all retained.
- [ ] Threshold changes require out-of-time improvement, not in-sample curve fitting.

## 6. Immediate execution queue

### P0 — finish current code validation

1. Re-check PR #25 `47208c31...` until main CI / Cycle Bottom conclude; fix only reproducible failures.
2. Re-check PR #23 `a8fe43e6...`; do not merge blindly merely because mergeable=true.
3. Locate and fix canonical security-name source for `300223 北京君正`.

### P0 — financial archetype batch

Research contrasting financial-sector samples first because they most clearly invalidate universal PE logic:

- Banks: `600036 招商银行`, `002142 宁波银行`, `600016 民生银行`.
- Insurance: `601318 中国平安`, `601628 中国人寿`.
- Broker / capital markets: `600030 中信证券`, `300059 东方财富`.

Output must explicitly test what breaks if the current industrial PE/OCF framework is applied and derive minimum auditable adapter inputs. Do not hard-code arbitrary premiums/discounts.

### P0 — stable compounder / PE-duration batch

- `600519 贵州茅台`
- `000333 美的集团`
- `603288 海天味业` or another currently representative food compounder selected from fresh All-A data

Goal: distinguish durable growth at a reasonable price from “low percentile” heuristics and from overpaying for quality.

### P0 — PE-inapplicable adversarial batch

Select at least one pre-profit / pipeline-driven biotech with current point-in-time data. The expected correct behavior may be `PE_MODEL_NOT_APPLICABLE`, followed by an rNPV/cash-runway adapter — **not** forced scenario PE.

## 7. Historical regression/backtest phase (after model freeze)

Planned order:

```text
point-in-time historical dataset contract
-> security-master / corporate-action audit
-> fundamental publication-lag audit
-> archetype router replay
-> signal replay with frozen model version
-> transaction/tradability simulation
-> walk-forward calibration
-> out-of-time validation
-> regime/archetype attribution
-> model changes only from reproducible failure classes
```

Backtesting is therefore the **validation and calibration stage after structural model completion**, not the mechanism used to invent the structural model.

## Durable breakpoint

As of 2026-08-16:

- initial deep-research queue BATCH2–BATCH12: complete;
- Master Ranking: complete for that initial universe;
- All-A official universe builder: confirmed in production source;
- archetype coverage matrix: created here;
- current model: **not frozen / not complete**;
- next research breakpoint: **financial archetype batch**, while PR #25/#23 CI continues in parallel;
- broad historical regression/backtest: **blocked by model-completion gates above**.
