-- T02 non-null keys and timestamps. PASS = 0 rows.
SELECT 'users' AS t, count(*) AS n FROM stg_users
WHERE user_id IS NULL OR signup_ts IS NULL OR region IS NULL OR channel IS NULL HAVING count(*) > 0
UNION ALL SELECT 'funnel', count(*) FROM stg_funnel_events WHERE user_id IS NULL OR event_ts IS NULL HAVING count(*) > 0
UNION ALL SELECT 'deposits', count(*) FROM stg_deposits WHERE amount_usd IS NULL OR ts IS NULL HAVING count(*) > 0
UNION ALL SELECT 'spend', count(*) FROM stg_spend
WHERE amount_usd IS NULL OR activity_date IS NULL OR booking_date IS NULL HAVING count(*) > 0;
