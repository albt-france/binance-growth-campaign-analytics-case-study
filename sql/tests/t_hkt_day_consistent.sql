-- T07 the operations day (UTC+8) is derived consistently: the tracker launch date (typed in UTC+8)
-- equals the UTC launch timestamp + 8 h, and readouts use that UTC+8 day. PASS = 0 rows.
SELECT c.campaign_id, c.start_date_hkt, c.start_date_hkt_entered, d.day1_date_hkt_used
FROM stg_campaigns c JOIN campaign_day1_utc_vs_hkt d USING (campaign_id)
WHERE c.start_date_hkt <> c.start_date_hkt_entered OR d.day1_date_hkt_used <> c.start_date_hkt;
