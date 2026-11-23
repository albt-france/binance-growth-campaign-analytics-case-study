# Rebuilding the dashboards in DataWind (general mapping)

The job post names DataWind as an example of visualisation tool. This page maps each visual of
`dashboard/index.html` to the generic building blocks any BI tool of that kind uses (dataset, dimensions, measures,
filters). It makes **no claim about DataWind's specific features**, which were not verified here; the same mapping
was implemented in Power BI (`powerbi/`).

| Visual | Dataset (CSV in `data/processed/` or SQL in `sql/`) | Dimensions | Measures | Filters / notes |
|---|---|---|---|---|
| Campaign scorecard table | `campaign_scorecard.csv` | campaign, type, region, channel, status | first depositors, CAC, 30-day ROI, D30 retention, withdrew >= 90%, incremental lift (DiD), naive lift | status; tag SIMULATED |
| CAC vs ROI scatter | `campaign_scorecard.csv` | campaign | x = CAC, y = 30-day ROI, size = first depositors | only campaigns with 30-day data |
| Funnel | `funnel_by_region_channel.csv` | step (5 steps), region, channel | count per step, conversion from first step | region selector |
| Sign-ups by day, UTC vs UTC+8 | `sql/00_staging/011_stg_sim_tables.sql` (`signup_date_utc`, `signup_date_hkt`) | day, time zone | sign-ups | time-zone switch |
| KYC pass rate | `kyc_daily_region.csv` | day, region | passed / submissions | highlight a region |
| Cohort heatmap | `cohort_matrix_weekly.csv` | cohort week, weeks since | retention | colour scale 0-100% |
| Retention by channel and month | `retention_by_channel_month.csv` | month, channel | D7, D30 retention | full 30-day cohorts only |
| Time to first deposit | `km_first_deposit.csv` | day, channel | share deposited (Kaplan-Meier) | |
| Weekly CAC | `cac_weekly.csv` | week | CAC by activity date, CAC by booking date | both lines always shown together |
| Attribution rules | `attribution_latam_shares.csv` | channel, rule | share of credit | LATAM |
| On-chain list definitions | `onchain_r2_definitions.csv` | day, definition | deposit transfers | 7-day mean; tag PUBLIC DATA |
| On-chain flows | `onchain_r1_daily.csv` | day | deposits, withdrawals, active deposit addresses, swept addresses | |
| Coverage | `onchain_coverage_daily.csv` | day, definition | listed senders / all senders | |
| Address cohorts | `onchain_r3_retention_curve.csv` | weeks since | retention with interval | "an address is not a user" note |
| Calendar by type | `calendar_by_type_month.csv` | month, type | announcements | |
| Promotions per day | `calendar_overlap_daily.csv` | day | active promotions | |
| Event study | `event_study_real_campaigns.csv` | campaign start, asset | market-adjusted change, placebo p, BH q, MDE | |

## Refresh
`pipelines/daily_refresh.py` rewrites the CSVs; a BI tool pointing at the folder (or at the DuckDB tables through a
SQL connector) only needs a scheduled refresh after 04:30 UTC.
