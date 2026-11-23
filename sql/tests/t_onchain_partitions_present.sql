-- T10 every UTC day from 25 May to 22 Nov 2026 has an extracted on-chain partition. PASS = 0 rows.
SELECT d::DATE AS missing_day FROM range(DATE '2026-05-25', DATE '2026-11-23', INTERVAL 1 DAY) t(d)
WHERE d::DATE NOT IN (SELECT date_utc FROM stg_onchain_totals);
