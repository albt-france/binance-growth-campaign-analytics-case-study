# SQL layer (DuckDB)

`python src/run_sql.py` runs every file in order, then the tests, then exports the publishable aggregates to
`data/processed/`. Each file starts with a header: **question, grain, tables, trap avoided**.

## Map
| Folder | File | Builds | Notes |
|---|---|---|---|
| 00_staging | 001_stg_por | `stg_por_membership`, `stg_por_snapshots`, `addr_union`, `addr_nov` | 8 Proof-of-Reserves snapshots, ETH network; hot/cold wins over deposit |
| | 002_stg_onchain | `stg_tx`, `stg_tt`, `stg_onchain_totals` | flags failed and zero-value rows instead of dropping them; UTC and UTC+8 days |
| | 003_stg_market_calendar | `stg_market`, `stg_fx`, `stg_calendar` | EURUSDT inverted; calendar without titles |
| | 010_stg_sim_events | `stg_funnel_events`, `stg_deposits` | **dedup on `event_id`, latest `ingested_at` (QUALIFY)** |
| | 011_stg_sim_tables | users, withdrawals, trades, touchpoints, spend, campaigns, views | explicit `*_hkt` columns |
| | 012_stg_spend_fx_asof | `stg_spend_check_fx` | **ASOF JOIN** to the latest real rate |
| 10_onchain | 101_onchain_classified | `day_snapshot`, `stg_onchain`, `onchain_classified` | 3 list definitions; flows: deposit, sweep, to wallet (unlisted), withdrawal, internal |
| | 102_onchain_daily | `onchain_daily`, `onchain_daily_hkt` | clean counts, exact distinct counts |
| | 103_onchain_hourly_profile | `onchain_hourly_profile` | UTC and UTC+8 hours; anchors the simulation |
| | 104_onchain_coverage_exclusions | `onchain_coverage_daily`, `onchain_exclusions_daily` | coverage of the published list; effect of each exclusion |
| | 105_onchain_address_weeks | `onchain_address_weeks`, `onchain_address_cohorts` | 8-week burn-in; `HAVING >= 20` addresses |
| | 106_onchain_quality | `onchain_quality_daily` | late partitions (watermark), z-score of daily volume (window function) |
| 20_funnel | 201_funnel_windows | `user_funnel`, `funnel_weekly`, `funnel_by_region_channel` | time windows; censoring flag |
| | 202_kyc_daily_region | `kyc_daily_region` | pass rate by submission cohort (LEAD for retries) |
| | 203_time_to_first_deposit | `time_to_first_deposit` | Kaplan-Meier input with censoring |
| 30_campaigns | 301_cac_weekly | `cac_weekly` | **CAC by activity date and by booking date** |
| | 302_campaign_kpis | `campaign_kpis` | CAC, 30-day ROI, retention, withdrawal guardrail |
| | 303_region_daily_panel | `region_daily_panel` | CROSS JOIN calendar so missing days are zeros |
| | 304_campaign_day1_utc_vs_hkt | `campaign_day1_utc_vs_hkt` | day 1 in UTC vs UTC+8 |
| | 305_calendar_real | `calendar_by_type_month`, `calendar_overlap_daily` | real Binance calendar (PUBLIC DATA) |
| | 306_crm_experiment | `crm_experiment_users`, `crm_experiment` | holdout readout input |
| 40_cohorts | 401_cohort_matrix_weekly | `cohort_matrix_weekly` | first-deposit week x weeks since |
| | 402_retention_by_channel_month | `user_retention`, `retention_by_channel_month` | full 30-day cohorts only |
| 50_attribution | 501_paths | `visitor_paths`, `path_counts` | ordered paths, last 5 touches, `string_agg ... ORDER BY` |
| | 502_attribution_rules | `attribution_rules` | first, last, position-based (Markov in Python) |
| | 503_partner_claims | `partner_claims` | partner reports vs user-level paths |
| | 504_referral_abuse_indicators | `referral_abuse_indicators` | `RANGE BETWEEN INTERVAL 60 MINUTE PRECEDING` |
| | 505_sessions | `touch_sessions` | gaps-and-islands sessionisation (LAG + running SUM) |
| tests | `t_*.sql` (13) | assertions | PASS when 0 rows |
| | `dq_*.sql` (4) | detectors on raw data | expected to FIND the planted issues |

## Style guide
- One file = one question; upper-case keywords; `snake_case` names; CTEs named after what they hold.
- Every timestamp is UTC; any UTC+8 field ends in `_hkt` and is derived, never typed.
- Deduplicate in staging, once (`QUALIFY row_number() ... = 1`), never in downstream queries.
- Missing days are zeros (calendar CROSS JOIN), not absent rows.
- Never publish addresses: hash them (`hash()`), aggregate, and keep cells >= 20 addresses.

## Performance notes
- **Read only the needed columns** from the 182 daily Ethereum partitions (Parquet column pruning): the extraction
  reads the selected column chunks only, a fraction of each partition.
- **Push filters down**: the extraction keeps only rows touching a published address (semi-join on a 12-million
  address table) before writing anything.
- **Partitions**: raw data are partitioned by day (`date=YYYY-MM-DD`), simulated data by week; a daily refresh
  touches one partition.
- **Hash the addresses** in analysis tables: 8-byte integers instead of 42-character strings for joins and
  distinct counts.
<!-- PERF -->
- **Distinct counts**: `approx_count_distinct` (HyperLogLog) vs exact `count(DISTINCT)` on daily wallet senders: mean error 9.63%, max 38.98%, 0.06 s vs 0.59 s on this machine; exact counts are kept (the error matters for small cells).
<!-- /PERF -->

## Dialect equivalences (Spark SQL and Hive) for 5 key queries
Nothing here describes Binance's internal platforms; these are the standard translations.

| Construct (DuckDB) | Spark SQL | Hive |
|---|---|---|
| Dedup: `QUALIFY row_number() OVER (PARTITION BY event_id ORDER BY ingested_at DESC) = 1` | sub-query with `row_number()` then `WHERE rn = 1` (Spark 3.4+: no QUALIFY) | same sub-query pattern |
| UTC+8 day: `CAST(ts + INTERVAL 8 HOUR AS DATE)` | `to_date(from_utc_timestamp(ts, 'Asia/Hong_Kong'))` | `to_date(from_utc_timestamp(ts, 'Asia/Hong_Kong'))` |
| FX: `ASOF JOIN stg_fx f ON s.currency = f.currency AND s.activity_date >= f.date_utc` | range join + `row_number()` over the latest `date_utc <= activity_date` | same, or a daily forward-filled FX table |
| Distinct count: `count(DISTINCT x)` / `approx_count_distinct(x)` | `count(DISTINCT x)` / `approx_count_distinct(x, 0.01)` | `count(DISTINCT x)` / no native HLL (UDF) |
| Burst window: `count(*) OVER (PARTITION BY r ORDER BY ts RANGE BETWEEN INTERVAL 60 MINUTE PRECEDING AND CURRENT ROW)` | `RANGE BETWEEN INTERVAL 60 MINUTES PRECEDING AND CURRENT ROW` | order by `unix_timestamp(ts)` with `RANGE BETWEEN 3600 PRECEDING AND CURRENT ROW` |
