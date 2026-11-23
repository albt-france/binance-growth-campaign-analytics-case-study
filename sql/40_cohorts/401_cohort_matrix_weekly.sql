-- Q401 user_activity_weeks / cohort_matrix_weekly (SIMULATED)
-- Question : of the users who made a first deposit in week W, what share is active in week W+k?
-- Grain    : first-deposit week x weeks since first deposit
-- Tables   : user_funnel, stg_trades_daily
-- Trap     : a cohort can only be read up to the last complete week; cells beyond the data are absent,
--            not zero (right censoring).
CREATE OR REPLACE TABLE cohort_matrix_weekly AS
WITH c AS (
    SELECT user_id, date_trunc('week', dep_ts)::DATE AS cohort_week FROM user_funnel WHERE dep_ts IS NOT NULL
),
a AS (
    SELECT DISTINCT t.user_id, date_trunc('week', t.date_utc)::DATE AS week FROM stg_trades_daily t
    JOIN c USING (user_id)
),
sz AS (SELECT cohort_week, count(*) AS cohort_size FROM c GROUP BY 1)
SELECT c.cohort_week, datediff('week', c.cohort_week, a.week) AS weeks_since,
       count(DISTINCT a.user_id) AS active_users, max(sz.cohort_size) AS cohort_size,
       round(count(DISTINCT a.user_id) / max(sz.cohort_size), 4) AS retention
FROM c JOIN a USING (user_id) JOIN sz USING (cohort_week)
WHERE a.week >= c.cohort_week AND a.week <= DATE '2026-11-16'
GROUP BY ALL ORDER BY ALL;
