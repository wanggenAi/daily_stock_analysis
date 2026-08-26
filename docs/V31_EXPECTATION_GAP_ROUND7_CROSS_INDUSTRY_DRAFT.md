# V3.1 Round-7 cross-industry expectation-gap replication

Status: **research only; frozen before any Round-7 OOS result**.

Round 6 was economically unsuccessful. Round 7 does not tune the observed sample and does not attempt to rescue returns. It is a fresh cross-industry replication intended to test whether the same failure modes persist outside an electronics/software-heavy universe.

Production V3.1 remains unchanged.

## 1. Frozen economic model

Round 7 reuses the Round-6 model without changing an economic parameter:

- strict PIT availability uses `NOTICE_DATE`; mutable `UPDATE_DATE` is ignored;
- require positive TTM basic EPS and positive TTM parent net profit;
- `deduct_factor = clip(TTM deduct-parent net profit / TTM parent net profit, 0, 1)`;
- `clean_eps = TTM basic EPS * deduct_factor`;
- normalized EPS is the median of the latest four positive clean-EPS observations, minimum two;
- operating cash flow remains diagnostic and does not multiply EPS;
- approximately three-year normalized-EPS CAGR and revenue CAGR are required;
- `realistic_growth = clip(min(eps_cagr, revenue_cagr + 5pp), 0%, 30%)`;
- valuation horizon is 10 years;
- discount rate is 10%;
- starting growth fades linearly toward 3% in year 10;
- terminal perpetual growth is 3%;
- terminal multiple is `1 / (10% - 3%)`;
- market-implied starting growth is solved over 0%-100% with the identical valuation equation;
- expectation gap remains diagnostic only; no new fitted gap threshold is introduced.

## 2. Frozen execution

- month-end rebalance;
- 0.10% one-way friction;
- BUY_STAGED at `price / neutral <= 0.85`;
- BUY_A_LEVEL at `<= 0.75`;
- BUY_FULL_MARGIN at `<= 0.65`;
- REDUCE_25 at `>= 1.20`;
- REDUCE_50 at `>= 1.40`;
- CORE_ONLY at `>= 1.70`;
- missing valuation remains `HOLD_REVIEW`;
- SELL uses only current price/current neutral value, never cost basis;
- execute reductions first, then proportionally scale only incremental BUY requests if cash is insufficient.

## 3. Untouched OOS universe

All names are Shanghai/Shenzhen main-board securities, were listed before 2018, comply with the formal BUY prefix contract, and did not appear in Round 1-6 valuation OOS universes.

| Code | Company | Research type |
|---|---|---|
| 601100 | 恒立液压 | High-end manufacturing / hydraulics |
| 002747 | 埃斯顿 | Industrial automation / robotics |
| 002050 | 三花智控 | Thermal-management components |
| 600845 | 宝信软件 | Industrial software / data infrastructure |
| 002027 | 分众传媒 | Consumer advertising platform |
| 600489 | 中金黄金 | Resource producer |
| 600089 | 特变电工 | Grid equipment / energy infrastructure |
| 600887 | 伊利股份 | Mature consumer cash flow |

No security may be substituted after the first result exists. A pre-result substitution is allowed only for a documented data-comparability failure such as a later listing date, and must be committed before any successful result.

## 4. Comparators

The same eight securities must be compared under:

1. `EXPECTATION_GAP_10Y`;
2. frozen `ROUND5_5Y_15X`;
3. `UNIVERSAL_GEOMEAN` using the shifted trailing 756-day PE/PB anchor;
4. literal first-day equal-dollar, zero-rebalance buy-and-hold;
5. CSI 300.

Buy-and-hold must include the initial 0.10% cost relative to the original RMB 1,000,000 capital. It must not normalize the cost away.

## 5. Required diagnostics

In addition to final capital, total return, CAGR, maximum drawdown, Sharpe, best/worst year, trades, turnover and average cash, Round 7 must save:

- per-company fraction of days where realistic growth is floored at 0% or capped at 30%;
- implied-growth solver status counts;
- days at BUY_STAGED or better;
- every genuine valuation SELL's 6/12/24-month endpoint return and maximum upside;
- first SELL after an intervening BUY as a non-independent sell-regime diagnostic;
- basic PIT availability and trade-sign audit results.

No completed-trade win rate or holding-period statistic may be reported without a separately validated episode-pairing contract.

## 6. Decision criteria

Round 7 is diagnostic, not a promotion gate. The unchanged model is considered structurally unstable if the fresh universe again shows one or more of the following:

- material numbers of investable companies with zero trades;
- average cash remains near the Round-6 level;
- backward growth is frequently floored at 0% for economically cyclical companies;
- most complete 12/24-month SELL observations remain positive;
- return improvement versus Round 5 is small relative to added drawdown;
- risk reduction versus Universal/buy-and-hold is primarily explained by cash.

These are directional falsification criteria, not fitted numerical pass thresholds.

## 7. Anti-overfit rule

The formula, eight-stock universe, dates, parameters, comparators, cost and execution bands are frozen by this document and the Round-7 runner before any Round-7 result is generated. Any later economic formula change requires a new untouched universe.
