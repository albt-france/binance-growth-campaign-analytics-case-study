-- Q003 stg_market / stg_fx / stg_calendar
-- Question : official daily market data and the real campaign calendar, typed.
-- Grain    : symbol x day (stg_market); currency x day (stg_fx); announcement (stg_calendar)
-- Tables   : data/processed/market_daily.csv, data/processed/campaign_calendar.csv
-- Trap     : kline open times switched from milliseconds to microseconds (handled in Python on load);
--            EURUSDT is quoted as USD per EUR, so it is inverted to "EUR per USD" like the other pairs.
CREATE OR REPLACE TABLE stg_market AS
SELECT symbol, CAST("date" AS DATE) AS date_utc, open, high, low, close, volume, quote_volume, trades,
       abs(ln(close / lag(close) OVER (PARTITION BY symbol ORDER BY "date"))) AS abs_log_return
FROM read_csv_auto('data/processed/market_daily.csv');

CREATE OR REPLACE TABLE stg_fx AS
SELECT date_utc,
       CASE symbol WHEN 'USDTBRL' THEN 'BRL' WHEN 'USDTTRY' THEN 'TRY' WHEN 'USDTMXN' THEN 'MXN'
                   WHEN 'USDTARS' THEN 'ARS' WHEN 'EURUSDT' THEN 'EUR' END AS currency,
       CASE WHEN symbol = 'EURUSDT' THEN 1 / close ELSE close END AS local_per_usd
FROM stg_market WHERE symbol IN ('USDTBRL', 'USDTTRY', 'USDTMXN', 'USDTARS', 'EURUSDT');

CREATE OR REPLACE TABLE stg_calendar AS
SELECT article_code, CAST(release_date_utc AS TIMESTAMP) AS release_ts_utc,
       CAST(period_start_utc AS TIMESTAMP) AS period_start_utc,
       CAST(period_end_utc AS TIMESTAMP) AS period_end_utc,
       "type", region, asset, detail_in_scope, detail_read
FROM read_csv_auto('data/processed/campaign_calendar.csv');
