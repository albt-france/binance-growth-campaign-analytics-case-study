-- Q010 stg_funnel_events / stg_deposits (SIMULATED)
-- Question : one clean row per business event.
-- Grain    : one row per event_id
-- Tables   : data/sim/funnel_events, data/sim/deposits
-- Trap     : a pipeline replay re-sent rows with the SAME event_id and a later ingested_at (27 Oct):
--            keep the latest ingestion of each event_id (QUALIFY), never count raw rows.
CREATE OR REPLACE TABLE stg_funnel_events AS
SELECT user_id, event, event_ts, event_id, ingested_at,
       CAST(event_ts AS DATE) AS date_utc, CAST(event_ts + INTERVAL 8 HOUR AS DATE) AS date_hkt
FROM read_parquet('data/sim/funnel_events/*/*.parquet', hive_partitioning = true)
QUALIFY row_number() OVER (PARTITION BY event_id ORDER BY ingested_at DESC) = 1;

CREATE OR REPLACE TABLE stg_deposits AS
SELECT deposit_id, event_id, user_id, ts, CAST(ts AS DATE) AS date_utc,
       CAST(ts + INTERVAL 8 HOUR AS DATE) AS date_hkt, amount_usd, amount_local, currency, asset, region,
       is_first, ingested_at
FROM read_parquet('data/sim/deposits/*/*.parquet', hive_partitioning = true)
QUALIFY row_number() OVER (PARTITION BY event_id ORDER BY ingested_at DESC) = 1;
