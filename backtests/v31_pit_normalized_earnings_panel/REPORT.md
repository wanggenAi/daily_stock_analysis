# Strict-PIT normalized-earnings input panel

> Infrastructure only. No neutral-value formula and no BUY/SELL result is produced.

## Availability contract

- Historical observations are keyed by report period but become usable only on `available_date`.
- `available_date = max(profit NOTICE_DATE, cash-flow NOTICE_DATE)` for metrics that combine both statements.
- `UPDATE_DATE` is deliberately ignored because later database revisions can rewrite it.
- Q1/H1/Q3 TTM values use current cumulative + previous FY - previous-year same-period cumulative.
- TTM basic EPS is labelled approximate because weighted-average shares can change across periods.

## Audit

|   code | name   |   rows | first_report   | last_report   | first_available   |   ttm_eps_ready |   ttm_np_ready |   ttm_cfo_ready |   availability_before_report_errors |
|-------:|:-------|-------:|:---------------|:--------------|:------------------|----------------:|---------------:|----------------:|------------------------------------:|
| 600183 | 生益科技   |    109 | 1995-12-31     | 2026-06-30    | 1998-09-14        |              92 |            105 |              99 |                                   0 |
| 002463 | 沪电股份   |     75 | 2003-12-31     | 2026-06-30    | 2007-01-22        |              71 |             71 |              71 |                                   0 |
| 002916 | 深南电路   |     52 | 2008-12-31     | 2026-03-31    | 2012-03-31        |              40 |             46 |              46 |                                   0 |
| 603160 | 汇顶科技   |     49 | 2011-12-31     | 2026-06-30    | 2014-05-06        |              45 |             46 |              46 |                                   0 |

## Errors

None.

## Next gate

Only after these PIT inputs are validated should a normalized-earnings neutral-value formula be frozen. The formula must be specified before its next untouched OOS result is observed.