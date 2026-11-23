-- Q105 onchain_address_weeks / onchain_address_cohorts (PUBLIC DATA)
-- Question : R3 - weekly cohorts of "swept" addresses (any non-wallet address that sends to a Binance wallet,
--            listed or not), by first week observed; share seen again in week S+1 ... S+12.
-- Grain    : address id x week (internal) ; cohort week x weeks since first seen (published, aggregated)
-- Tables   : onchain_classified (definition B_union, fixed list over the whole window)
-- Trap     : left censoring - an address "new" in the first weeks may be old; the 8 weeks from 25 May to
--            19 Jul are a burn-in and never used as cohorts. An address is NOT a user.
CREATE OR REPLACE TABLE onchain_address_weeks AS
SELECT DISTINCT from_id AS addr_id, date_trunc('week', date_utc)::DATE AS week
FROM onchain_classified
WHERE definition = 'B_union' AND kt = 'hot' AND kf <> 'hot' AND succeeded AND NOT zero_value;

CREATE OR REPLACE TABLE onchain_address_cohorts AS
WITH first_seen AS (
    SELECT addr_id, min(week) AS cohort_week FROM onchain_address_weeks GROUP BY addr_id
)
SELECT f.cohort_week,
       datediff('week', f.cohort_week, w.week) AS weeks_since,
       count(DISTINCT w.addr_id) AS active_addresses,
       max(sz.cohort_size) AS cohort_size
FROM first_seen f
JOIN onchain_address_weeks w USING (addr_id)
JOIN (SELECT cohort_week, count(*) AS cohort_size FROM first_seen GROUP BY cohort_week) sz USING (cohort_week)
WHERE f.cohort_week >= DATE '2026-07-20'            -- after the 8-week burn-in
GROUP BY ALL
HAVING count(DISTINCT w.addr_id) >= 20              -- privacy: never publish a cell under 20 addresses
ORDER BY 1, 2;
