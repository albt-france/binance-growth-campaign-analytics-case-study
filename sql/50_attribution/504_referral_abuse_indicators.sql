-- Q504 referral_abuse_indicators (SIMULATED)
-- Question : which referrers look like a referral farm? Indicators only (concentration, shared devices,
--            sign-up bursts, identical deposit amounts, KYC outcome) - no technique is described.
-- Grain    : one row per referrer with at least 20 referees in the window
-- Tables   : stg_referrals, stg_users, stg_devices, user_funnel, stg_deposits
-- Trap     : one indicator alone flags honest power users (influencers); the flag needs several at once.
CREATE OR REPLACE TABLE referral_abuse_indicators AS
WITH r AS (
    SELECT rf.referrer_id, rf.referee_id, rf.referral_ts, u.device_id, f.kyc_pass_ts IS NOT NULL AS kyc_passed,
           d.amount_usd AS first_deposit_usd
    FROM stg_referrals rf JOIN stg_users u ON u.user_id = rf.referee_id
    LEFT JOIN user_funnel f ON f.user_id = rf.referee_id
    LEFT JOIN stg_deposits d ON d.user_id = rf.referee_id AND d.is_first
),
dev AS (SELECT device_id, count(*) AS accounts_on_device FROM stg_users GROUP BY 1),
burst AS (   -- the largest number of referees signed up within any 60-minute window
    SELECT referrer_id, max(n_in_hour) AS max_referees_60min FROM (
        SELECT referrer_id, count(*) OVER (PARTITION BY referrer_id ORDER BY referral_ts
                                           RANGE BETWEEN INTERVAL 60 MINUTE PRECEDING AND CURRENT ROW) AS n_in_hour
        FROM r) GROUP BY 1
),
amt AS (
    SELECT referrer_id, max(n) / sum(n) AS top_amount_share FROM (
        SELECT referrer_id, first_deposit_usd, count(*) AS n FROM r WHERE first_deposit_usd IS NOT NULL GROUP BY ALL)
    GROUP BY 1
),
per_ref AS (
    SELECT r.referrer_id, count(*) AS referees,
           avg((dev.accounts_on_device > 1)::INT) AS shared_device,
           max(b.max_referees_60min) AS burst_60min,
           avg(r.kyc_passed::INT) AS kyc_pass,
           max(a.top_amount_share) AS identical_deposit
    FROM r JOIN dev USING (device_id) JOIN burst b USING (referrer_id) LEFT JOIN amt a USING (referrer_id)
    GROUP BY r.referrer_id
    HAVING count(*) >= 20
)
SELECT referrer_id, referees, round(shared_device, 4) AS share_shared_device, burst_60min AS max_referees_60min,
       round(kyc_pass, 4) AS kyc_pass_share, round(identical_deposit, 4) AS share_identical_first_deposit,
       (shared_device > 0.5)::INT + (burst_60min >= 10)::INT + (kyc_pass < 0.5)::INT
           + (coalesce(identical_deposit, 0) > 0.8)::INT AS flags
FROM per_ref
ORDER BY flags DESC, referees DESC;
