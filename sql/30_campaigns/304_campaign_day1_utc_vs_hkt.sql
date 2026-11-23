-- Q304 campaign_day1_utc_vs_hkt (SIMULATED)
-- Question : what does "day 1" of a campaign show if the day is cut in UTC (data) or in UTC+8 (operations)?
-- Grain    : one row per campaign
-- Tables   : stg_campaigns, stg_users (attributed sign-ups), stg_deposits (region deposits)
-- Trap     : a launch at 16:00 UTC is midnight in Hong Kong: the UTC "day 1" holds 8 hours of campaign,
--            the UTC+8 "day 1" holds 24. The readout states its time zone (operations: UTC+8).
CREATE OR REPLACE TABLE campaign_day1_utc_vs_hkt AS
SELECT c.campaign_id, c.region, c.start_ts_utc, c.start_date_utc, c.start_date_hkt,
       (SELECT count(*) FROM stg_deposits d WHERE (d.region = c.region OR c.region = 'ALL')
            AND d.date_utc = c.start_date_utc) AS day1_deposits_utc,
       (SELECT count(*) FROM stg_deposits d WHERE (d.region = c.region OR c.region = 'ALL')
            AND d.date_hkt = c.start_date_hkt) AS day1_deposits_hkt,
       (SELECT count(*) FROM stg_users u WHERE u.attributed_campaign = c.campaign_id
            AND u.signup_date_utc = c.start_date_utc) AS day1_signups_utc,
       (SELECT count(*) FROM stg_users u WHERE u.attributed_campaign = c.campaign_id
            AND u.signup_date_hkt = c.start_date_hkt) AS day1_signups_hkt,
       hour(c.start_ts_utc) AS launch_hour_utc,
       c.start_date_hkt AS day1_date_hkt_used                       -- the readout convention (UTC+8)
FROM stg_campaigns c ORDER BY 1;
