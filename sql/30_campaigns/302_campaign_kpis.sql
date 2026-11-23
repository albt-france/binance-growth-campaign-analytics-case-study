-- Q302 campaign_kpis (SIMULATED)
-- Question : per campaign, the "reported" scorecard: attributed sign-ups and first depositors, CAC,
--            30-day net revenue, 30-day ROI, 30-day retention and the full-withdrawal guardrail.
-- Grain    : one row per acquisition campaign (CRM campaigns are measured with their holdout, Q307)
-- Tables   : user_funnel, stg_spend, stg_trades_daily, stg_deposits, stg_withdrawals, stg_campaigns
-- Trap     : these numbers are ATTRIBUTED (users who clicked the campaign), not incremental. A campaign can
--            have a great CAC and still lose money: promo bonuses and withdrawals sit outside the CAC.
CREATE OR REPLACE TABLE campaign_kpis AS
WITH u AS (
    SELECT * FROM user_funnel WHERE attributed_campaign IS NOT NULL
),
dep AS (SELECT user_id, sum(amount_usd) AS deposited_30d FROM stg_deposits d JOIN u USING (user_id)
        WHERE d.ts <= u.dep_ts + INTERVAL 30 DAY GROUP BY 1),
wd AS (SELECT user_id, sum(amount_usd) AS withdrawn_30d FROM stg_withdrawals w JOIN u USING (user_id)
       WHERE w.ts <= u.dep_ts + INTERVAL 30 DAY GROUP BY 1),
rev AS (SELECT t.user_id, sum(fee_usd) AS fees_30d,
               bool_or(t.date_utc BETWEEN CAST(u.dep_ts AS DATE) + 24 AND CAST(u.dep_ts AS DATE) + 30)
                   AS active_d24_30
        FROM stg_trades_daily t JOIN u USING (user_id)
        WHERE t.date_utc BETWEEN CAST(u.dep_ts AS DATE) AND CAST(u.dep_ts AS DATE) + 30 GROUP BY 1),
cost AS (SELECT campaign_id,
                sum(amount_usd) FILTER (WHERE cost_type = 'media') AS media_usd,
                sum(amount_usd) FILTER (WHERE cost_type = 'promo_bonus') AS promo_usd
         FROM stg_spend WHERE campaign_id IS NOT NULL GROUP BY 1),
per_user AS (
    SELECT u.attributed_campaign AS campaign_id, u.user_id, u.dep_ts IS NOT NULL AS depositor,
           u.dep_ts + INTERVAL 30 DAY <= TIMESTAMP '2026-11-22 23:59:59' AS full_30d,
           coalesce(r.fees_30d, 0) AS fees_30d, coalesce(r.active_d24_30, FALSE) AS active_d24_30,
           coalesce(w.withdrawn_30d, 0) >= 0.9 * nullif(d.deposited_30d, 0) AS withdrew_90pct
    FROM u LEFT JOIN rev r USING (user_id) LEFT JOIN dep d USING (user_id) LEFT JOIN wd w USING (user_id)
),
agg AS (
    SELECT c.campaign_id, c.name, c."type", c.region, c.channel, c.objective, c.start_date_utc,
           CAST(c.end_ts_utc AS DATE) AS end_date_utc,
           count(*) AS attributed_signups,
           count(*) FILTER (WHERE depositor) AS attributed_first_depositors,
           any_value(coalesce(k.media_usd, 0)) AS media_usd, any_value(coalesce(k.promo_usd, 0)) AS promo_usd,
           sum(fees_30d) FILTER (WHERE depositor AND full_30d) AS fees_30d_full,
           count(*) FILTER (WHERE depositor AND full_30d) AS depositors_with_30d,
           avg(active_d24_30::INT) FILTER (WHERE depositor AND full_30d) AS retention_d30,
           avg(withdrew_90pct::INT) FILTER (WHERE depositor AND full_30d) AS share_withdrew_90pct_30d
    FROM stg_campaigns c
    JOIN per_user p USING (campaign_id)
    LEFT JOIN cost k USING (campaign_id)
    WHERE NOT c.has_holdout
    GROUP BY c.campaign_id, c.name, c."type", c.region, c.channel, c.objective, c.start_date_utc, c.end_ts_utc
)
SELECT campaign_id, name, "type", region, channel, objective, start_date_utc, end_date_utc,
       attributed_signups, attributed_first_depositors, round(media_usd, 2) AS media_usd,
       round(promo_usd, 2) AS promo_usd,
       round(media_usd / nullif(attributed_first_depositors, 0), 2) AS cac_first_deposit,
       round(fees_30d_full / nullif(depositors_with_30d, 0), 2) AS revenue_30d_per_depositor,
       -- 30-day ROI: (30-day net revenue per depositor x depositors - media - promo) / (media + promo)
       round((fees_30d_full / nullif(depositors_with_30d, 0) * attributed_first_depositors - media_usd - promo_usd)
             / nullif(media_usd + promo_usd, 0), 4) AS roi_30d,
       round(retention_d30, 4) AS retention_d30, round(share_withdrew_90pct_30d, 4) AS share_withdrew_90pct_30d,
       depositors_with_30d
FROM agg ORDER BY campaign_id;
