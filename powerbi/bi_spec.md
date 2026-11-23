# Power BI specification (fallback if the PBIP does not open)

Data: CSV files of `data/processed/` (SIMULATED exchange). No relationship is needed: each page uses one table.

## Measures (DAX) - same as `measures.dax`
```
First depositors   = SUM ( campaign_scorecard[attributed_first_depositors] )
Media USD          = SUM ( campaign_scorecard[media_usd] )
Promo USD          = SUM ( campaign_scorecard[promo_usd] )
CAC                = DIVIDE ( [Media USD], [First depositors] )
ROI 30d            = VAR c = FILTER ( campaign_scorecard, NOT ISBLANK ( campaign_scorecard[revenue_30d_per_depositor] ) )
                     VAR rev = SUMX ( c, campaign_scorecard[revenue_30d_per_depositor] * campaign_scorecard[attributed_first_depositors] )
                     VAR cost = SUMX ( c, campaign_scorecard[media_usd] + campaign_scorecard[promo_usd] )
                     RETURN DIVIDE ( rev - cost, cost )
Registrations      = SUM ( funnel_by_region_channel[registrations] )
First deposit 7d   = SUM ( funnel_by_region_channel[first_deposit_7d] )
Sign-up to deposit % = DIVIDE ( [First deposit 7d], [Registrations] )
Cohort retention   = DIVIDE ( SUM ( cohort_matrix_weekly[active_users] ), SUM ( cohort_matrix_weekly[cohort_size] ) )
Retention D30      = DIVIDE ( SUMX ( retention_by_channel_month, [retention_d30] * [depositors_full_30d] ),
                              SUM ( retention_by_channel_month[depositors_full_30d] ) )
```

## Pages
| Page | Visuals | Filters |
|---|---|---|
| Campaign scorecard | 4 cards (First depositors, CAC, ROI 30d, Campaigns); table (campaign, type, region, channel, depositors, CAC, ROI, withdrew >= 90%, DiD lift, status); bar chart ROI 30d by campaign | status, type |
| Funnel | slicers region and channel; column chart of the 5 steps (measures); bar chart sign-up to deposit % by channel | region, channel |
| Cohorts & retention | matrix cohort week x weeks since with Cohort retention (colour scale); column chart Retention D30 by channel, series = month | month |

Each page title states its conclusion (read from `findings.json`) and each visual is tagged SIMULATED.
