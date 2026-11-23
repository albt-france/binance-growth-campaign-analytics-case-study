-- Q102 onchain_daily / onchain_daily_hkt (PUBLIC DATA)
-- Question : R1 - deposits, sweeps, withdrawals and active addresses per day, asset and list definition.
-- Grain    : definition x day x asset x flow (UTC day) ; the same in UTC+8 days for definition B_union
-- Tables   : onchain_classified
-- Trap     : clean counts exclude failed transactions, zero-value transfers (address poisoning) and
--            internal Binance-to-Binance moves; distinct counts are exact (count DISTINCT on hashed ids).
CREATE OR REPLACE TABLE onchain_daily AS
SELECT definition, date_utc, asset, flow,
       count(*) AS n_transfers,
       count(DISTINCT from_id) AS n_senders,
       count(DISTINCT to_id) AS n_receivers
FROM onchain_classified
WHERE succeeded AND NOT zero_value AND flow <> 'internal'
GROUP BY ALL;

CREATE OR REPLACE TABLE onchain_daily_hkt AS
SELECT date_hkt, asset, flow,
       count(*) AS n_transfers, count(DISTINCT from_id) AS n_senders, count(DISTINCT to_id) AS n_receivers,
       date_hkt = DATE '2026-05-25' AS partial_day                -- 00:00-08:00 HKT of day 1 is before the window
FROM onchain_classified
WHERE definition = 'B_union' AND succeeded AND NOT zero_value AND flow <> 'internal'
GROUP BY ALL;
