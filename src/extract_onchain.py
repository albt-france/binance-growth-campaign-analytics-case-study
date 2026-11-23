"""Extract, one day at a time, the Ethereum rows that touch an address published by Binance
in its Proof of Reserves (any of the 8 snapshots), from AWS Public Blockchain Data (anonymous access).

For each UTC day D (resumable: a day with a _done marker is skipped):
  data/raw/onchain/date=D/tx.parquet      native ETH transactions with from or to in the address union
  data/raw/onchain/date=D/tt.parquet      token transfers (addresses normalised to 20 bytes) touching the union
  data/raw/onchain/date=D/totals.json     day denominators (all transactions / transfers of the day)
  data/raw/onchain/_log.jsonl             one line per day: seconds, MB read, rows, partition last_modified

Only the useful columns are read (column pruning): about 100 MB per day of transactions
and about 270 MB per day of token transfers instead of ~1.2 GB of full partitions.

Usage:  python src/extract_onchain.py --start 2026-05-25 --end 2026-11-22
"""
import argparse
import json
import time
from datetime import date, timedelta
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
POR = ROOT / "data" / "raw" / "por"
OUT = ROOT / "data" / "raw" / "onchain"
S3 = "s3://aws-public-blockchain/v1.0/eth"

TX_COLS = ["hash", "block_timestamp", "from_address", "to_address", "value", "receipt_status", "last_modified"]
TT_COLS = ["token_address", "from_address", "to_address", "value", "transaction_hash", "log_index",
           "block_timestamp", "last_modified"]


def norm(col: str) -> str:
    """Token-transfer addresses are left-padded to 32 bytes (66 chars): keep the last 20 bytes."""
    return f"('0x' || right(lower({col}), 40))"


def connect() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.sql("INSTALL httpfs; LOAD httpfs;")
    con.sql("SET s3_region='us-east-2'; SET s3_access_key_id=''; SET s3_secret_access_key='';")  # anonymous
    con.sql("SET memory_limit='6GB'; SET preserve_insertion_order=false; SET enable_progress_bar=false;")
    return con


def load_address_union(con):
    """One row per ETH-network address seen in any snapshot (deposit or hot/cold)."""
    union = POR / "eth_addr_union.parquet"
    if not union.exists():
        con.sql(f"""COPY (
            SELECT address,
                   bool_or(kind = 'hotcold') AS is_hotcold,
                   bool_or(kind = 'deposit') AS is_deposit
            FROM read_parquet('{(POR / 'eth_membership.parquet').as_posix()}')
            WHERE address LIKE '0x%' AND length(address) = 42
            GROUP BY address) TO '{union.as_posix()}' (FORMAT parquet)""")
    con.sql(f"CREATE TABLE addr AS SELECT address FROM read_parquet('{union.as_posix()}')")
    return con.sql("SELECT count(*) FROM addr").fetchone()[0]


def mb_read(con, path: str, cols: list[str]) -> float:
    """Compressed bytes of the selected column chunks (what column pruning actually downloads)."""
    q = ", ".join(f"'{c}'" for c in cols)
    v = con.sql(f"SELECT sum(total_compressed_size) FROM parquet_metadata('{path}') "
                f"WHERE path_in_schema IN ({q})").fetchone()[0]
    return round((v or 0) / 1e6, 1)


def extract_day(con, d: date) -> dict:
    folder = OUT / f"date={d.isoformat()}"
    folder.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    tx_src = f"{S3}/transactions/date={d.isoformat()}/*.parquet"
    tt_src = f"{S3}/token_transfers/date={d.isoformat()}/*.parquet"

    # --- native transactions: day table in memory, then keep rows touching the union
    con.sql(f"""CREATE OR REPLACE TEMP TABLE t AS
                SELECT hash, block_timestamp, lower(from_address) AS from_address,
                       lower(to_address) AS to_address, value, receipt_status, last_modified
                FROM read_parquet('{tx_src}')""")
    tx_tot = con.sql("""SELECT count(*), count(*) FILTER (WHERE receipt_status = 0),
                               count(*) - count(DISTINCT hash), max(last_modified)::VARCHAR,
                               min(block_timestamp)::VARCHAR, max(block_timestamp)::VARCHAR FROM t""").fetchone()
    con.sql(f"""COPY (SELECT * FROM t
                      WHERE to_address IN (SELECT address FROM addr)
                         OR from_address IN (SELECT address FROM addr))
                TO '{(folder / 'tx.parquet').as_posix()}' (FORMAT parquet)""")

    # --- token transfers: normalise the padded addresses first
    con.sql(f"""CREATE OR REPLACE TEMP TABLE tt AS
                SELECT lower(token_address) AS token_address, {norm('from_address')} AS from_address,
                       {norm('to_address')} AS to_address, value, transaction_hash, log_index,
                       block_timestamp, last_modified
                FROM read_parquet('{tt_src}')""")
    tt_tot = con.sql("""SELECT count(*), count(*) FILTER (WHERE value = 0),
                               count(*) - count(DISTINCT (transaction_hash, log_index)),
                               max(last_modified)::VARCHAR FROM tt""").fetchone()
    con.sql(f"""COPY (SELECT * FROM tt
                      WHERE to_address IN (SELECT address FROM addr)
                         OR from_address IN (SELECT address FROM addr))
                TO '{(folder / 'tt.parquet').as_posix()}' (FORMAT parquet)""")

    kept_tx = con.sql(f"SELECT count(*) FROM '{(folder / 'tx.parquet').as_posix()}'").fetchone()[0]
    kept_tt = con.sql(f"SELECT count(*) FROM '{(folder / 'tt.parquet').as_posix()}'").fetchone()[0]
    totals = {
        "date": d.isoformat(),
        "tx_total": tx_tot[0], "tx_failed": tx_tot[1], "tx_duplicate_hash": tx_tot[2],
        "tx_last_modified": tx_tot[3], "tx_min_ts": tx_tot[4], "tx_max_ts": tx_tot[5],
        "tt_total": tt_tot[0], "tt_zero_value": tt_tot[1], "tt_duplicate_key": tt_tot[2],
        "tt_last_modified": tt_tot[3],
        "tx_kept": kept_tx, "tt_kept": kept_tt,
    }
    totals["mb_read"] = round(mb_read(con, tx_src, TX_COLS) + mb_read(con, tt_src, TT_COLS), 1)
    totals["seconds"] = round(time.time() - t0, 1)
    (folder / "totals.json").write_text(json.dumps(totals, indent=1))
    (folder / "_done").write_text("ok")
    con.sql("DROP TABLE t; DROP TABLE tt;")
    return totals


def main(start: date, end: date, newest_first: bool = False):
    con = connect()
    n = load_address_union(con)
    print(f"[extract] address union: {n:,} ETH-network addresses", flush=True)
    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    if newest_first:
        days = days[::-1]
    for d in days:
        if (OUT / f"date={d.isoformat()}" / "_done").exists():
            continue                                    # resume: day already extracted
        for attempt in (1, 2):
            try:
                tot = extract_day(con, d)
                break
            except Exception as e:                      # one retry, then move on (logged)
                print(f"[extract] {d} attempt {attempt} failed: {e}", flush=True)
                tot = None
                time.sleep(10)
        if tot:
            with open(OUT / "_log.jsonl", "a") as f:
                f.write(json.dumps(tot) + "\n")
            print(f"[extract] {d} {tot['seconds']}s {tot['mb_read']}MB tx={tot['tx_kept']:,} tt={tot['tt_kept']:,}",
                  flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2026-05-25")
    ap.add_argument("--end", default="2026-11-22")
    ap.add_argument("--newest-first", action="store_true")
    a = ap.parse_args()
    main(date.fromisoformat(a.start), date.fromisoformat(a.end), a.newest_first)
