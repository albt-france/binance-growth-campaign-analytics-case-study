-- Q305 calendar_by_type_month / calendar_overlap_daily (PUBLIC DATA)
-- Question : what does Binance's real campaign calendar look like: types per month, and how many promotions
--            run on the same day?
-- Grain    : month x type ; UTC day
-- Tables   : stg_calendar (titles are never loaded: only code, dates and derived categories)
-- Trap     : announcements without a detectable promotion period are counted, not dropped silently;
--            overlap uses only announcements whose period was found (share reported in the findings).
CREATE OR REPLACE TABLE calendar_by_type_month AS
SELECT date_trunc('month', release_ts_utc)::DATE AS month, "type", count(*) AS announcements
FROM stg_calendar GROUP BY ALL ORDER BY ALL;

CREATE OR REPLACE TABLE calendar_overlap_daily AS
SELECT d::DATE AS date_utc,
       count(c.article_code) AS active_promotions,
       count(c.article_code) FILTER (WHERE c."type" IN ('deposit', 'earn_apr')
                                     AND c.asset IN ('USDT', 'USDC')) AS active_usd_stable_deposit_earn
FROM range(DATE '2026-05-25', DATE '2026-11-23', INTERVAL 1 DAY) t(d)
LEFT JOIN stg_calendar c ON c.period_start_utc <= d + INTERVAL 1 DAY - INTERVAL 1 SECOND
                        AND c.period_end_utc >= d
GROUP BY 1 ORDER BY 1;
