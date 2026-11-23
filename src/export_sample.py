"""10,000-row samples of the simulated tables (data/sample/), to try the SQL without running the simulator.

    python src/export_sample.py
"""
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "sample"
TABLES = {"users": "users/*/*.parquet", "funnel_events": "funnel_events/*/*.parquet",
          "deposits": "deposits/*/*.parquet", "trades_daily": "trades_daily/*/*.parquet",
          "touchpoints": "touchpoints/*/*.parquet", "spend_daily": "spend_daily.parquet",
          "campaigns": "campaigns.parquet"}

if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.sql("SET enable_progress_bar=false")
    for name, pat in TABLES.items():
        src = (ROOT / "data" / "sim" / pat).as_posix()
        con.sql(f"""COPY (SELECT * FROM read_parquet('{src}', hive_partitioning = true)
                          USING SAMPLE reservoir(10000 ROWS) REPEATABLE (42))
                    TO '{(OUT / (name + '.csv')).as_posix()}' (HEADER)""")
    print(f"[sample] {len(TABLES)} tables x <= 10,000 rows in data/sample (SIMULATED)")
