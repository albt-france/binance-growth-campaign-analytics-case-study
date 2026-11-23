-- Q104 onchain_coverage_daily / onchain_exclusions_daily (PUBLIC DATA)
-- Question : R2 - how much of the active deposit-address population does the published list cover,
--            and how much do the cleaning rules remove?
-- Grain    : definition x day
-- Tables   : onchain_classified
-- Trap     : coverage = senders to a Binance wallet that ARE listed deposit addresses / all non-wallet senders
--            to a Binance wallet. A sender is not a user; unlisted senders also include other services.
CREATE OR REPLACE TABLE onchain_coverage_daily AS
SELECT definition, date_utc,
       count(DISTINCT from_id) FILTER (WHERE kf = 'dep') AS listed_senders,
       count(DISTINCT from_id) AS all_senders,
       count(DISTINCT from_id) FILTER (WHERE kf = 'dep') / count(DISTINCT from_id) AS coverage
FROM onchain_classified
WHERE kt = 'hot' AND kf <> 'hot' AND src = 'tt' AND succeeded AND NOT zero_value
GROUP BY ALL;

CREATE OR REPLACE TABLE onchain_exclusions_daily AS
SELECT definition, date_utc,
       count(*) AS rows_all,
       count(*) FILTER (WHERE NOT succeeded) AS rows_failed,
       count(*) FILTER (WHERE succeeded AND zero_value AND NOT dust) AS rows_zero_value,
       count(*) FILTER (WHERE succeeded AND dust) AS rows_dust,
       count(*) FILTER (WHERE succeeded AND NOT zero_value AND flow = 'internal') AS rows_internal,
       count(*) FILTER (WHERE succeeded AND NOT zero_value AND flow <> 'internal') AS rows_clean
FROM onchain_classified
GROUP BY ALL;
