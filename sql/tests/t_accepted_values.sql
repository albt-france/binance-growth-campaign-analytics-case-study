-- T03 accepted values (regions, channels, events, cost types). PASS = 0 rows.
SELECT 'region' AS col, region AS v FROM stg_users
WHERE region NOT IN ('LATAM-BR', 'LATAM-AR', 'LATAM-MX', 'TR', 'SEA-VN', 'SEA-PH', 'CIS-KZ', 'MENA', 'EU')
UNION ALL SELECT 'channel', channel FROM stg_users
WHERE channel NOT IN ('organic', 'paid_search', 'paid_social', 'affiliate_kol', 'referral', 'app_store_ads')
UNION ALL SELECT 'event', event FROM stg_funnel_events
WHERE event NOT IN ('register', 'kyc_submitted', 'kyc_passed', 'first_deposit', 'first_trade')
UNION ALL SELECT 'cost_type', cost_type FROM stg_spend
WHERE cost_type NOT IN ('media', 'partner_fee', 'referral_reward', 'promo_bonus');
