-- T08 every expected weekly partition of the simulated tables is present. PASS = 0 rows.
WITH w AS (SELECT strftime(d, '%Y-%m-%d') AS week
           FROM range(DATE '2026-08-24', DATE '2026-11-17', INTERVAL 7 DAY) t(d))
SELECT 'users' AS t, week FROM w WHERE week NOT IN
    (SELECT DISTINCT CAST(week AS VARCHAR) FROM read_parquet('data/sim/users/*/*.parquet', hive_partitioning = true))
UNION ALL SELECT 'deposits', week FROM w WHERE week NOT IN
    (SELECT DISTINCT CAST(week AS VARCHAR) FROM read_parquet('data/sim/deposits/*/*.parquet', hive_partitioning = true))
UNION ALL SELECT 'trades_daily', week FROM w WHERE week NOT IN
    (SELECT DISTINCT CAST(week AS VARCHAR) FROM read_parquet('data/sim/trades_daily/*/*.parquet', hive_partitioning = true));
