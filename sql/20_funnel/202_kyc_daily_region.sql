-- Q202 kyc_daily_region (SIMULATED)
-- Question : KYC pass rate per day and region (is a campaign failing, or is the problem downstream?)
-- Grain    : submission day (UTC) x region
-- Tables   : stg_funnel_events, stg_users
-- Trap     : the pass rate is computed on the SUBMISSION day (cohort of submissions), not on the day the
--            verdict arrives; a user may submit twice (retry after a vendor outage): each submission counts.
CREATE OR REPLACE TABLE kyc_daily_region AS
WITH s AS (
    SELECT f.user_id, u.region, f.event_ts AS sub_ts,
           lead(f.event_ts) OVER (PARTITION BY f.user_id ORDER BY f.event_ts) AS next_sub_ts
    FROM stg_funnel_events f JOIN stg_users u USING (user_id)
    WHERE f.event = 'kyc_submitted'
),
p AS (SELECT user_id, event_ts AS pass_ts FROM stg_funnel_events WHERE event = 'kyc_passed')
SELECT CAST(s.sub_ts AS DATE) AS date_utc, s.region,
       count(*) AS submissions,
       count(*) FILTER (WHERE p.pass_ts >= s.sub_ts AND (s.next_sub_ts IS NULL OR p.pass_ts < s.next_sub_ts))
           AS passed,
       round(passed / submissions, 4) AS pass_rate
FROM s LEFT JOIN p USING (user_id)
GROUP BY ALL ORDER BY ALL;
