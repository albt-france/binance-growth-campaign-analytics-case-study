-- Q306 crm_experiment_users / crm_experiment (SIMULATED)
-- Question : did the CRM campaigns reactivate dormant users, against a randomised 10% holdout?
-- Grain    : one row per targeted user (crm_experiment_users) ; campaign x arm (crm_experiment)
-- Tables   : stg_holdouts, stg_crm_base, stg_trades_daily
-- Trap     : the outcome window (14 days) starts at assignment for BOTH arms; the holdout never receives
--            the message, so "opened the message" is never a valid comparison.
CREATE OR REPLACE TABLE crm_experiment_users AS
SELECT h.campaign_id, h.user_id, h.arm, b.pre_active_days_90, b.days_since_last_active,
       EXISTS (SELECT 1 FROM stg_trades_daily t
               WHERE t.user_id = h.user_id
                 AND t.date_utc BETWEEN CAST(h.assigned_at AS DATE) + 1 AND CAST(h.assigned_at AS DATE) + 14)
           AS reactivated_14d
FROM stg_holdouts h JOIN stg_crm_base b USING (user_id);

CREATE OR REPLACE TABLE crm_experiment AS
SELECT campaign_id, arm, count(*) AS users, sum(reactivated_14d::INT) AS reactivated,
       round(avg(reactivated_14d::INT), 5) AS reactivation_rate, round(avg(pre_active_days_90), 3) AS pre_active_mean
FROM crm_experiment_users GROUP BY ALL ORDER BY ALL;
