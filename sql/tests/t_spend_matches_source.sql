-- T05 staged spend equals the source file (no row lost or doubled). PASS = 0 rows.
SELECT s.total AS staged, r.total AS source
FROM (SELECT round(sum(amount_usd), 2) AS total FROM stg_spend) s,
     (SELECT round(sum(amount_usd), 2) AS total FROM read_parquet('data/sim/spend_daily.parquet')) r
WHERE abs(s.total - r.total) > 0.01;
