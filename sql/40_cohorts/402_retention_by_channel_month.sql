-- Q402 user_retention / retention_by_channel_month (SIMULATED)
-- Question : 7-day and 30-day retention of new depositors, by first-deposit month and acquisition channel.
--            D7 = active (traded) on any day 1-7 after the first deposit; D30 = on any day 24-30.
-- Grain    : one row per depositor (user_retention) ; month x channel (retention_by_channel_month)
-- Tables   : user_funnel, stg_trades_daily
-- Trap     : only depositors with a FULL 30-day follow-up enter the D30 rate (first deposit on or before
--            23 Oct); mixing complete and incomplete windows makes recent months look worse.
CREATE OR REPLACE TABLE user_retention AS
SELECT f.user_id, f.channel, f.region, f.attributed_campaign, date_trunc('month', f.dep_ts)::DATE AS dep_month,
       CAST(f.dep_ts AS DATE) AS dep_date,
       CAST(f.dep_ts AS DATE) + 30 <= DATE '2026-11-22' AS full_30d,
       EXISTS (SELECT 1 FROM stg_trades_daily t WHERE t.user_id = f.user_id
               AND t.date_utc BETWEEN CAST(f.dep_ts AS DATE) + 1 AND CAST(f.dep_ts AS DATE) + 7) AS active_d1_7,
       EXISTS (SELECT 1 FROM stg_trades_daily t WHERE t.user_id = f.user_id
               AND t.date_utc BETWEEN CAST(f.dep_ts AS DATE) + 24 AND CAST(f.dep_ts AS DATE) + 30) AS active_d24_30
FROM user_funnel f WHERE f.dep_ts IS NOT NULL;

CREATE OR REPLACE TABLE retention_by_channel_month AS
SELECT dep_month, channel, count(*) AS depositors_full_30d,
       round(avg(active_d1_7::INT), 4) AS retention_d7, round(avg(active_d24_30::INT), 4) AS retention_d30
FROM user_retention WHERE full_30d GROUP BY ALL
UNION ALL
SELECT dep_month, 'ALL', count(*), round(avg(active_d1_7::INT), 4), round(avg(active_d24_30::INT), 4)
FROM user_retention WHERE full_30d GROUP BY ALL
ORDER BY 1, 2;
