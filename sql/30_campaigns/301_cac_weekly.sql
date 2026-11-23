-- Q301 cac_weekly (SIMULATED)
-- Question : weekly CAC = acquisition spend / new first depositors, by ACTIVITY date and by BOOKING date.
-- Grain    : one row per week (Monday, UTC)
-- Tables   : stg_spend, stg_funnel_events
-- Trap     : finance books partner invoices when they arrive; a backlog booked in one week makes the
--            booking-date CAC jump with no change in what happened. Decisions use the activity date.
--            Promo bonuses and CRM messages are not acquisition spend (they are in the ROI, not the CAC).
CREATE OR REPLACE TABLE cac_weekly AS
WITH acq AS (
    SELECT * FROM stg_spend WHERE cost_type IN ('media', 'partner_fee') AND channel <> 'crm_lifecycle'
),
by_act AS (SELECT date_trunc('week', activity_date)::DATE AS week, sum(amount_usd) AS spend_activity
           FROM acq GROUP BY 1),
by_book AS (SELECT date_trunc('week', booking_date)::DATE AS week, sum(amount_usd) AS spend_booking
            FROM acq GROUP BY 1),
deps AS (SELECT date_trunc('week', event_ts)::DATE AS week, count(*) AS new_depositors
         FROM stg_funnel_events WHERE event = 'first_deposit' GROUP BY 1)
SELECT d.week, d.new_depositors, a.spend_activity, b.spend_booking,
       round(a.spend_activity / d.new_depositors, 2) AS cac_activity,
       round(b.spend_booking / d.new_depositors, 2) AS cac_booking,
       round(cac_activity / lag(cac_activity) OVER (ORDER BY d.week) - 1, 4) AS wow_activity,
       round(cac_booking / lag(cac_booking) OVER (ORDER BY d.week) - 1, 4) AS wow_booking
FROM deps d LEFT JOIN by_act a USING (week) LEFT JOIN by_book b USING (week)
WHERE d.week BETWEEN DATE '2026-08-24' AND DATE '2026-11-16'
ORDER BY d.week;
