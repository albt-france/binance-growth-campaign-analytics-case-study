-- D01 detector on RAW deposits: days with re-sent event_ids (expected: the 27 Oct pipeline replay).
SELECT CAST(ts AS DATE) AS day, count(*) AS raw_rows, count(DISTINCT event_id) AS events,
       round(count(*) / count(DISTINCT event_id), 3) AS ratio
FROM read_parquet('data/sim/deposits/*/*.parquet', hive_partitioning = true)
GROUP BY 1 HAVING count(*) > count(DISTINCT event_id) ORDER BY 1;
