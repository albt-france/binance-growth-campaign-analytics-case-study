-- Q505 touch_sessions (SIMULATED)
-- Question : group clicks into sessions (a new session after 30 minutes without a click) and count
--            sessions before sign-up per channel of entry.
-- Grain    : channel of the session's first click
-- Tables   : stg_touchpoints
-- Trap     : session ids are built with LAG + a running SUM over a window (gaps-and-islands), per visitor.
CREATE OR REPLACE TABLE touch_sessions AS
WITH g AS (
    SELECT visitor_id, user_id, channel, touch_ts,
           CASE WHEN touch_ts - lag(touch_ts) OVER (PARTITION BY visitor_id ORDER BY touch_ts) <= INTERVAL 30 MINUTE
                THEN 0 ELSE 1 END AS new_session
    FROM stg_touchpoints
),
s AS (SELECT *, sum(new_session) OVER (PARTITION BY visitor_id ORDER BY touch_ts) AS session_no FROM g),
sess AS (SELECT visitor_id, session_no, arg_min(channel, touch_ts) AS entry_channel, count(*) AS clicks,
                any_value(user_id) IS NOT NULL AS visitor_converted
         FROM s GROUP BY ALL)
SELECT entry_channel, count(*) AS sessions, round(avg(clicks), 3) AS clicks_per_session,
       round(avg(visitor_converted::INT), 4) AS share_of_converting_visitors
FROM sess GROUP BY 1 ORDER BY 1;
