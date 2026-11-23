-- D04 detector (PUBLIC DATA): days whose AWS partition landed more than 6 h after the end of the day.
SELECT date_utc, tx_last_modified, round(hours_after_day_end, 1) AS hours_late FROM onchain_quality_daily
WHERE hours_after_day_end > 6 ORDER BY 1;
