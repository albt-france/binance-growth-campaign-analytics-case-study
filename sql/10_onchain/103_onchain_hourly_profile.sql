-- Q103 onchain_hourly_profile (PUBLIC DATA)
-- Question : at what hour (UTC and UTC+8) do people pay into Binance deposit addresses?
-- Grain    : hour of day (0-23)
-- Tables   : onchain_classified (definition B_union, clean deposits)
-- Trap     : the profile is used to anchor the SIMULATED sign-up times, in UTC (the storage time zone).
CREATE OR REPLACE TABLE onchain_hourly_profile AS
WITH d AS (SELECT hour_utc, hour_hkt FROM onchain_classified
           WHERE definition = 'B_union' AND flow = 'deposit' AND succeeded AND NOT zero_value),
u AS (SELECT hour_utc AS hour, count(*) AS n FROM d GROUP BY 1),
k AS (SELECT hour_hkt AS hour, count(*) AS n FROM d GROUP BY 1)
SELECT u.hour AS hour_utc, u.n AS deposits_utc, k.n AS deposits_hkt,
       u.n / sum(u.n) OVER () AS share                 -- share of deposits by UTC hour (simulation anchor)
FROM u JOIN k USING (hour) ORDER BY u.hour;
