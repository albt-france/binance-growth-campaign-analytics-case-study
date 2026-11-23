-- Q501 visitor_paths / path_counts (SIMULATED)
-- Question : the ordered channel path of every visitor in the 7 days before sign-up (or before the last
--            touch for visitors who never signed up) - the input of first/last/position/Markov attribution.
-- Grain    : one row per visitor (visitor_paths) ; path x region group (path_counts)
-- Tables   : stg_touchpoints, stg_users
-- Trap     : touches AFTER the sign-up must not get credit; repeated consecutive channels are kept
--            (they are separate clicks) but the path is capped at the last 5 touches (list_slice).
CREATE OR REPLACE TABLE visitor_paths AS
WITH t AS (
    SELECT tp.visitor_id, tp.user_id, tp.channel, tp.touch_ts, tp.region, u.signup_ts
    FROM stg_touchpoints tp LEFT JOIN stg_users u USING (user_id)
    WHERE u.signup_ts IS NULL OR (tp.touch_ts <= u.signup_ts AND tp.touch_ts >= u.signup_ts - INTERVAL 7 DAY)
),
g AS (   -- one list of touches per visitor, in time order (no window function: faster on 8 M touches)
    SELECT visitor_id, any_value(user_id) AS user_id, any_value(region) AS region,
           list(channel ORDER BY touch_ts) AS chans
    FROM t GROUP BY visitor_id
)
SELECT visitor_id, user_id, region,
       array_to_string(list_slice(chans, -5, -1), ' > ') AS path,          -- last 5 touches
       list_slice(chans, -5, -1)[1] AS first_touch,                           -- first of the kept touches
       chans[-1] AS last_touch,
       len(list_slice(chans, -5, -1)) AS n_touches, user_id IS NOT NULL AS converted
FROM g;

CREATE OR REPLACE TABLE path_counts AS
SELECT CASE WHEN region LIKE 'LATAM%' THEN 'LATAM' ELSE 'other' END AS region_group, path,
       count(*) FILTER (WHERE converted) AS conversions, count(*) FILTER (WHERE NOT converted) AS non_conversions
FROM visitor_paths GROUP BY ALL;
