-- Q012 stg_spend_check_fx (SIMULATED spend, REAL exchange rates)
-- Question : does each local-currency invoice equal USD x the real exchange rate of its activity day?
-- Grain    : one row per non-USD invoice line
-- Tables   : stg_spend, stg_fx
-- Trap     : the FX table could miss a day -> ASOF JOIN takes the latest rate at or before the day.
CREATE OR REPLACE TABLE stg_spend_check_fx AS
SELECT s.invoice_id, s.currency, s.activity_date, s.amount_usd, s.amount_local, f.local_per_usd,
       s.amount_usd * f.local_per_usd AS expected_local
FROM stg_spend s
ASOF JOIN stg_fx f ON s.currency = f.currency AND s.activity_date >= f.date_utc
WHERE s.currency <> 'USD';
