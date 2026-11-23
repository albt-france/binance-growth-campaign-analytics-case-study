-- Q011 stg_users / stg_withdrawals / stg_trades_daily / stg_touchpoints / stg_spend / stg_campaigns (SIMULATED)
-- Question : typed, documented copies of the simulated source tables.
-- Grain    : as in the source (user; withdrawal; user x day; touch; invoice line; campaign)
-- Trap     : every timestamp is UTC; the operations day (UTC+8) is derived explicitly as *_hkt;
--            spend carries TWO dates (activity and booking); the campaign tracker launch date was
--            typed in UTC+8 by the Hong Kong team (start_date_hkt_entered).
CREATE OR REPLACE TABLE stg_users AS
SELECT user_id, signup_ts, CAST(signup_ts AS DATE) AS signup_date_utc,
       CAST(signup_ts + INTERVAL 8 HOUR AS DATE) AS signup_date_hkt,
       date_trunc('week', signup_ts)::DATE AS signup_week, region, channel, device_id, referrer_id,
       first_touch_campaign AS attributed_campaign
FROM read_parquet('data/sim/users/*/*.parquet', hive_partitioning = true);

CREATE OR REPLACE TABLE stg_withdrawals AS
SELECT withdrawal_id, user_id, ts, CAST(ts AS DATE) AS date_utc, amount_usd, region, currency
FROM read_parquet('data/sim/withdrawals/*/*.parquet', hive_partitioning = true);

CREATE OR REPLACE TABLE stg_trades_daily AS
SELECT user_id, CAST("date" AS DATE) AS date_utc, region, n_trades, volume_usd, fee_usd
FROM read_parquet('data/sim/trades_daily/*/*.parquet', hive_partitioning = true);

CREATE OR REPLACE TABLE stg_touchpoints AS
SELECT touch_id, visitor_id, user_id, touch_ts, channel, nullif(campaign_id, '') AS campaign_id, region
FROM read_parquet('data/sim/touchpoints/*/*.parquet', hive_partitioning = true);

CREATE OR REPLACE TABLE stg_spend AS
SELECT invoice_id, channel, region, CAST(activity_date AS DATE) AS activity_date,
       CAST(booking_date AS DATE) AS booking_date, cost_type, nullif(campaign_id, '') AS campaign_id,
       amount_usd, amount_local, currency
FROM read_parquet('data/sim/spend_daily.parquet');

CREATE OR REPLACE TABLE stg_campaigns AS
SELECT campaign_id, name, "type", region, channel, objective, start_ts_utc, end_ts_utc,
       CAST(start_ts_utc AS DATE) AS start_date_utc,
       CAST(start_ts_utc + INTERVAL 8 HOUR AS DATE) AS start_date_hkt,
       CAST(start_date_hkt_entered AS DATE) AS start_date_hkt_entered, budget_usd, has_holdout, holdout_share
FROM read_parquet('data/sim/campaigns.parquet');

CREATE OR REPLACE VIEW stg_referrals AS SELECT * FROM read_parquet('data/sim/referrals.parquet');
CREATE OR REPLACE VIEW stg_devices AS SELECT * FROM read_parquet('data/sim/devices.parquet');
CREATE OR REPLACE VIEW stg_holdouts AS SELECT * FROM read_parquet('data/sim/holdout_assignments.parquet');
CREATE OR REPLACE VIEW stg_exposure AS SELECT * FROM read_parquet('data/sim/campaign_exposure.parquet');
CREATE OR REPLACE VIEW stg_crm_base AS SELECT * FROM read_parquet('data/sim/crm_base.parquet');
CREATE OR REPLACE VIEW stg_partner_reports AS SELECT * FROM read_parquet('data/sim/partner_reports.parquet');
