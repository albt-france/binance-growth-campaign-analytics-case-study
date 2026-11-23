-- Q106 onchain_quality_daily (PUBLIC DATA)
-- Question : R5 - which days are late, incomplete or duplicated in the AWS Public Blockchain Data?
-- Grain    : one row per UTC day
-- Tables   : stg_onchain_totals (written by the extraction for every day)
-- Trap     : a partition usually lands ~1-4 h after midnight UTC; 31 Aug landed on 1 Sep afternoon.
--            Lateness is measured from the end of the day, with the last_modified column as watermark.
CREATE OR REPLACE TABLE onchain_quality_daily AS
SELECT date_utc, tx_total, tt_total, tx_failed, tt_zero_value, tx_duplicate_hash, tt_duplicate_key,
       tx_last_modified,
       datediff('minute', date_utc + INTERVAL 1 DAY, tx_last_modified) / 60.0 AS hours_after_day_end,
       datediff('second', date_utc::TIMESTAMP, tx_min_ts) AS first_block_s,
       datediff('second', tx_max_ts, date_utc + INTERVAL 1 DAY) AS last_block_gap_s,
       (tx_total - avg(tx_total) OVER w) / stddev(tx_total) OVER w AS tx_total_z,
       mb_read, seconds
FROM stg_onchain_totals
WINDOW w AS (ORDER BY date_utc ROWS BETWEEN 14 PRECEDING AND 14 FOLLOWING)
ORDER BY date_utc;
