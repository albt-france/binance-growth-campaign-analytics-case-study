-- Q303 region_daily_panel (SIMULATED outcomes, REAL market data)
-- Question : one panel for incrementality: per region and day, sign-ups, first deposits, deposits, trades,
--            with the real BTC volatility of the day (the "cycle").
-- Grain    : region x UTC day (9 x 91 rows)
-- Tables   : stg_users, stg_funnel_events, stg_deposits, stg_trades_daily, stg_market
-- Trap     : a region-day with no event must be a 0, not a missing row (CROSS JOIN on the calendar).
CREATE OR REPLACE TABLE region_daily_panel AS
WITH cal AS (
    SELECT r.region, d::DATE AS date_utc
    FROM (SELECT DISTINCT region FROM stg_users) r
    CROSS JOIN range(DATE '2026-08-24', DATE '2026-11-23', INTERVAL 1 DAY) t(d)
),
reg AS (SELECT region, signup_date_utc AS date_utc, count(*) AS signups FROM stg_users GROUP BY ALL),
fd AS (SELECT u.region, f.date_utc, count(*) AS first_deposits
       FROM stg_funnel_events f JOIN stg_users u USING (user_id) WHERE f.event = 'first_deposit' GROUP BY ALL),
dp AS (SELECT region, date_utc, count(*) AS deposits, sum(amount_usd) AS deposits_usd FROM stg_deposits GROUP BY ALL),
tr AS (SELECT region, date_utc, sum(n_trades) AS trades, count(*) AS active_traders FROM stg_trades_daily GROUP BY ALL),
mk AS (SELECT date_utc, abs_log_return AS btc_abs_return, quote_volume AS btc_quote_volume
       FROM stg_market WHERE symbol = 'BTCUSDT')
SELECT c.region, c.date_utc, coalesce(signups, 0) AS signups, coalesce(first_deposits, 0) AS first_deposits,
       coalesce(deposits, 0) AS deposits, coalesce(deposits_usd, 0) AS deposits_usd,
       coalesce(trades, 0) AS trades, coalesce(active_traders, 0) AS active_traders,
       mk.btc_abs_return, mk.btc_quote_volume, dayofweek(c.date_utc) AS dow
FROM cal c LEFT JOIN reg USING (region, date_utc) LEFT JOIN fd USING (region, date_utc)
LEFT JOIN dp USING (region, date_utc) LEFT JOIN tr USING (region, date_utc) LEFT JOIN mk USING (date_utc)
ORDER BY 1, 2;
