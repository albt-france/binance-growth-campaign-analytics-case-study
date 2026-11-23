-- Q201 user_funnel / funnel_weekly / funnel_by_region_channel (SIMULATED)
-- Question : how many sign-ups reach KYC, a first deposit within 7 days, and a first trade?
-- Grain    : one row per user (user_funnel); sign-up week x region x channel (funnel_weekly)
-- Tables   : stg_users, stg_funnel_events (deduplicated)
-- Trap     : a step only counts if it happens AFTER the previous one and inside its time window
--            (7 days from sign-up); late conversions of the last week are censored, not "lost".
CREATE OR REPLACE TABLE user_funnel AS
WITH e AS (
    SELECT user_id,
           min(event_ts) FILTER (WHERE event = 'register') AS reg_ts,
           min(event_ts) FILTER (WHERE event = 'kyc_submitted') AS kyc_sub_ts,
           min(event_ts) FILTER (WHERE event = 'kyc_passed') AS kyc_pass_ts,
           min(event_ts) FILTER (WHERE event = 'first_deposit') AS dep_ts,
           min(event_ts) FILTER (WHERE event = 'first_trade') AS trade_ts
    FROM stg_funnel_events GROUP BY user_id
)
SELECT u.user_id, u.region, u.channel, u.signup_week, u.signup_ts, u.attributed_campaign,
       e.kyc_sub_ts, e.kyc_pass_ts, e.dep_ts, e.trade_ts,
       e.kyc_sub_ts IS NOT NULL AND e.kyc_sub_ts <= u.signup_ts + INTERVAL 7 DAY AS kyc_sub_7d,
       e.kyc_pass_ts IS NOT NULL AND e.kyc_pass_ts <= u.signup_ts + INTERVAL 7 DAY AS kyc_pass_7d,
       e.dep_ts IS NOT NULL AND e.dep_ts >= e.kyc_pass_ts AND e.dep_ts <= u.signup_ts + INTERVAL 7 DAY AS dep_7d,
       e.trade_ts IS NOT NULL AND e.trade_ts >= e.dep_ts AND e.trade_ts <= u.signup_ts + INTERVAL 7 DAY AS trade_7d,
       u.signup_ts + INTERVAL 7 DAY <= TIMESTAMP '2026-11-22 23:59:59' AS window_complete
FROM stg_users u LEFT JOIN e USING (user_id);

CREATE OR REPLACE TABLE funnel_weekly AS
SELECT signup_week, region, channel,
       count(*) AS registrations,
       count(*) FILTER (WHERE kyc_sub_7d) AS kyc_submitted,
       count(*) FILTER (WHERE kyc_pass_7d) AS kyc_passed,
       count(*) FILTER (WHERE kyc_pass_7d AND dep_7d) AS first_deposit_7d,
       count(*) FILTER (WHERE kyc_pass_7d AND dep_7d AND trade_7d) AS first_trade_7d,
       bool_and(window_complete) AS window_complete
FROM user_funnel GROUP BY ALL ORDER BY ALL;

CREATE OR REPLACE TABLE funnel_by_region_channel AS
SELECT region, channel, sum(registrations) AS registrations, sum(kyc_submitted) AS kyc_submitted,
       sum(kyc_passed) AS kyc_passed, sum(first_deposit_7d) AS first_deposit_7d,
       sum(first_trade_7d) AS first_trade_7d,
       round(sum(first_deposit_7d) / sum(registrations), 4) AS reg_to_deposit_7d
FROM funnel_weekly WHERE window_complete GROUP BY ALL ORDER BY ALL;
