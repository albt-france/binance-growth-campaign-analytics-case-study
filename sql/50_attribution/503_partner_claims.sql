-- Q503 partner_claims (SIMULATED)
-- Question : partners (affiliate/KOL and paid social) each report the sign-ups they touched. Together, how
--            many do they claim versus the real number of sign-ups they touched, and versus a single rule?
-- Grain    : region group (LATAM vs other)
-- Tables   : stg_partner_reports, visitor_paths, stg_touchpoints, stg_users
-- Trap     : a user touched by both partners is claimed twice. The fix is a user-level path table and ONE
--            rule for everybody (last touch, then Markov), which sums back to 100%.
CREATE OR REPLACE TABLE partner_claims AS
WITH touched AS (
    SELECT DISTINCT tp.user_id, u.region
    FROM stg_touchpoints tp JOIN stg_users u USING (user_id)
    WHERE tp.channel IN ('paid_social', 'affiliate_kol')
      AND tp.touch_ts <= u.signup_ts AND tp.touch_ts >= u.signup_ts - INTERVAL 7 DAY
),
claims AS (
    SELECT CASE WHEN region LIKE 'LATAM%' THEN 'LATAM' ELSE 'other' END AS region_group,
           sum(claimed_signups) FILTER (WHERE channel = 'affiliate_kol') AS claimed_affiliate_kol,
           sum(claimed_signups) FILTER (WHERE channel = 'paid_social') AS claimed_paid_social
    FROM stg_partner_reports GROUP BY 1
),
real AS (
    SELECT CASE WHEN region LIKE 'LATAM%' THEN 'LATAM' ELSE 'other' END AS region_group,
           count(*) AS real_signups_touched FROM touched GROUP BY 1
),
lt AS (
    SELECT CASE WHEN region LIKE 'LATAM%' THEN 'LATAM' ELSE 'other' END AS region_group,
           count(*) FILTER (WHERE last_touch IN ('paid_social', 'affiliate_kol')) AS last_touch_credit
    FROM visitor_paths WHERE converted GROUP BY 1
)
SELECT region_group, claimed_affiliate_kol, claimed_paid_social,
       claimed_affiliate_kol + claimed_paid_social AS claimed_total, real_signups_touched,
       round((claimed_affiliate_kol + claimed_paid_social) / real_signups_touched, 4) AS claimed_over_real,
       last_touch_credit
FROM claims JOIN real USING (region_group) JOIN lt USING (region_group) ORDER BY 1;
