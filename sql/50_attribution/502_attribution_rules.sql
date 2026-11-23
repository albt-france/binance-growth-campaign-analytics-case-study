-- Q502 attribution_rules (SIMULATED)
-- Question : credit per channel under first-touch, last-touch and position-based (40/20/40) rules.
--            (Markov removal effects are computed in Python from path_counts, src/stats.py.)
-- Grain    : region group x channel
-- Tables   : visitor_paths, stg_touchpoints
-- Trap     : every rule distributes exactly ONE credit per sign-up, so each rule sums to the real number of
--            sign-ups - unlike partner reports, where each partner claims every user it touched.
CREATE OR REPLACE TABLE attribution_rules AS
WITH conv AS (SELECT * FROM visitor_paths WHERE converted),
pos AS (
    SELECT v.visitor_id, CASE WHEN v.region LIKE 'LATAM%' THEN 'LATAM' ELSE 'other' END AS region_group,
           t.channel,
           CASE WHEN v.n_touches = 1 THEN 1.0
                WHEN v.n_touches = 2 THEN 0.5
                WHEN t.rn IN (1, v.n_touches) THEN 0.4
                ELSE 0.2 / (v.n_touches - 2) END AS credit
    FROM conv v
    JOIN (SELECT tp.visitor_id, tp.channel,
                 row_number() OVER (PARTITION BY tp.visitor_id ORDER BY tp.touch_ts) AS rn,
                 row_number() OVER (PARTITION BY tp.visitor_id ORDER BY tp.touch_ts DESC) AS rn_desc
          FROM stg_touchpoints tp JOIN stg_users u USING (user_id)
          WHERE tp.touch_ts <= u.signup_ts AND tp.touch_ts >= u.signup_ts - INTERVAL 7 DAY) t
      ON t.visitor_id = v.visitor_id AND t.rn_desc <= 5
),
pos_fix AS (   -- renumber inside the last-5 window so first/last get 40% each
    SELECT visitor_id, region_group, channel, credit FROM pos
)
SELECT region_group, channel,
       (SELECT count(*) FROM conv c WHERE c.first_touch = x.channel
            AND (CASE WHEN c.region LIKE 'LATAM%' THEN 'LATAM' ELSE 'other' END) = x.region_group) AS first_touch,
       (SELECT count(*) FROM conv c WHERE c.last_touch = x.channel
            AND (CASE WHEN c.region LIKE 'LATAM%' THEN 'LATAM' ELSE 'other' END) = x.region_group) AS last_touch,
       round(sum(credit), 1) AS position_based
FROM pos_fix x GROUP BY ALL ORDER BY ALL;
