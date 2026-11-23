-- T13 the published calendar carries no announcement title (Binance's text). PASS = 0 rows.
SELECT column_name FROM (DESCRIBE SELECT * FROM read_csv_auto('data/processed/campaign_calendar.csv'))
WHERE lower(column_name) IN ('title', 'body', 'name');
