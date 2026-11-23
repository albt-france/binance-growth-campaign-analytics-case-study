-- T06 no duplicate event_id after staging (catches the 27 Oct pipeline replay). PASS = 0 rows.
SELECT 'deposits' AS t, event_id, count(*) AS n FROM stg_deposits GROUP BY ALL HAVING count(*) > 1
UNION ALL SELECT 'funnel', event_id, count(*) FROM stg_funnel_events GROUP BY ALL HAVING count(*) > 1;
