-- Q203 time_to_first_deposit (SIMULATED)
-- Question : how long from KYC approval to the first deposit (input of the Kaplan-Meier curve)?
-- Grain    : one row per user who passed KYC
-- Tables   : user_funnel
-- Trap     : users who have not deposited YET are censored at the end of the data, not counted as "never".
CREATE OR REPLACE TABLE time_to_first_deposit AS
SELECT user_id, region, channel,
       coalesce(datediff('second', kyc_pass_ts, dep_ts),
                datediff('second', kyc_pass_ts, TIMESTAMP '2026-11-22 23:59:59')) / 86400.0 AS days,
       dep_ts IS NOT NULL AS observed
FROM user_funnel
WHERE kyc_pass_ts IS NOT NULL;
