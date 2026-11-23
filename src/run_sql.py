"""Run the SQL layer (DuckDB) in order, then the SQL tests, then export the publishable aggregates.

  sql/00_staging/00x_*   public sources (Proof of Reserves, Ethereum extraction, market data, calendar)
  sql/00_staging/01x_*   simulated exchange
  sql/10_onchain ... sql/50_attribution   analysis queries (one table per file, header = question/grain/trap)
  sql/tests/t_*.sql      assertions: PASS when the query returns 0 rows
  sql/tests/dq_*.sql     detectors on RAW data: they are expected to find the planted data issues

Usage:  python src/run_sql.py [--part all|public|sim] [--no-tests]
"""
import argparse
import sys
import time
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
SQL = ROOT / "sql"
DB = ROOT / "data" / "warehouse.duckdb"
PROC = ROOT / "data" / "processed"

PUBLIC = ["00_staging/00", "10_onchain"]
SIM = ["00_staging/01", "20_funnel", "30_campaigns", "40_cohorts", "50_attribution"]
# aggregated tables written to data/processed/ (no address, no raw title, >= 20 addresses per cell)
EXPORT_PUBLIC = ["stg_por_snapshots", "onchain_daily", "onchain_daily_hkt", "onchain_hourly_profile",
                 "onchain_coverage_daily", "onchain_exclusions_daily", "onchain_address_cohorts",
                 "onchain_quality_daily"]
EXPORT_SIM = ["funnel_weekly", "kyc_daily_region", "cac_weekly", "campaign_kpis", "region_daily_panel",
              "campaign_day1_utc_vs_hkt", "cohort_matrix_weekly", "retention_by_channel_month",
              "attribution_rules", "partner_claims", "referral_abuse_indicators", "crm_experiment",
              "calendar_by_type_month", "calendar_overlap_daily", "funnel_by_region_channel"]


def connect():
    con = duckdb.connect(str(DB))
    (ROOT / "data" / "raw" / "duckdb_tmp").mkdir(parents=True, exist_ok=True)
    con.sql("SET memory_limit='10GB'; SET preserve_insertion_order=false; SET enable_progress_bar=false;")
    con.sql(f"SET file_search_path='{ROOT.as_posix()}';")
    con.sql(f"SET temp_directory='{(ROOT / 'data' / 'raw' / 'duckdb_tmp').as_posix()}';")
    return con


def files_for(prefixes):
    out = []
    for p in prefixes:
        folder, _, start = p.partition("/")
        out += sorted(f for f in (SQL / folder).glob("*.sql") if f.name.startswith(start))
    return out


def run_files(con, files, only=None):
    for f in files:
        if only and not f.relative_to(SQL).as_posix().startswith(tuple(only.split(","))):
            continue
        t0 = time.time()
        con.execute(f.read_text(encoding="utf-8"))
        print(f"[sql] {f.relative_to(SQL).as_posix():55s} {time.time() - t0:6.1f}s", flush=True)


def run_tests(con, part):
    fails = 0
    for f in sorted((SQL / "tests").glob("*.sql")):
        scope = "public" if "_onchain" in f.name or "_calendar" in f.name else "sim"
        if part != "all" and scope != part:
            continue
        n = len(con.execute(f.read_text(encoding="utf-8")).fetchall())
        if f.name.startswith("t_"):
            status = "PASS" if n == 0 else "FAIL"
            fails += n > 0
        else:
            status = "FOUND" if n else "none"
        print(f"[test] {f.name:50s} {status} ({n} rows)")
    return fails


def export(con, tables):
    PROC.mkdir(parents=True, exist_ok=True)
    for t in tables:
        con.sql(f"COPY {t} TO '{(PROC / (t + '.csv')).as_posix()}' (HEADER)")


def main(part="all", tests=True, only=None):
    con = connect()
    os_ok = (ROOT / "data" / "sim" / "campaigns.parquet").exists()
    if part in ("all", "public"):
        run_files(con, files_for(PUBLIC), only)
        if not only:
            export(con, EXPORT_PUBLIC)       # onchain_hourly_profile.csv also anchors the simulation
    if part in ("all", "sim") and os_ok:
        run_files(con, files_for(SIM), only)
        if not only:
            export(con, EXPORT_SIM)
    fails = run_tests(con, part) if tests else 0
    con.close()
    if fails:
        sys.exit(f"[test] {fails} test(s) failed")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", default="all", choices=["all", "public", "sim"])
    ap.add_argument("--no-tests", action="store_true")
    ap.add_argument("--only", help="comma-separated path prefixes, e.g. 50_attribution/504 (debugging)")
    a = ap.parse_args()
    main(a.part, not a.no_tests, a.only)
