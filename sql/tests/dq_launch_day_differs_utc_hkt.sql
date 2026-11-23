-- D02 detector: campaigns whose UTC launch day differs from the UTC+8 launch day (16:00-23:59 UTC).
SELECT campaign_id, start_ts_utc, start_date_utc, start_date_hkt FROM stg_campaigns
WHERE start_date_utc <> start_date_hkt;
