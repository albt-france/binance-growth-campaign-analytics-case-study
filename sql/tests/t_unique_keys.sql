-- T01 unique keys: user_id, event_id (after staging), deposit_id, invoice_id, campaign_id. PASS = 0 rows.
SELECT 'stg_users' AS t, user_id AS k FROM stg_users GROUP BY 2 HAVING count(*) > 1
UNION ALL SELECT 'stg_funnel_events', event_id FROM stg_funnel_events GROUP BY 2 HAVING count(*) > 1
UNION ALL SELECT 'stg_deposits', deposit_id FROM stg_deposits GROUP BY 2 HAVING count(*) > 1
UNION ALL SELECT 'stg_spend', invoice_id FROM stg_spend GROUP BY 2 HAVING count(*) > 1
UNION ALL SELECT 'stg_campaigns', campaign_id FROM stg_campaigns GROUP BY 2 HAVING count(*) > 1;
