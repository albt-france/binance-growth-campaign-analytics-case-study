"""Daily incremental refresh (idempotent): run it every day at 04:30 UTC (see task_scheduler_daily_refresh.xml).

Steps, each skipped when there is nothing new:
  1. Ethereum: extract every day after the last extracted one whose AWS partition exists (watermark = the
     partition's last_modified, stored in totals.json). ALERT if yesterday's partition is still missing after
     06:00 UTC (it happened on 31 Aug 2026: landed on 1 Sep at 14:10 UTC).
  2. Announcements: re-read page 1 of "Latest Activities", read the detail of new articles only (cache).
  3. Market data: new daily klines, SHA-256 checksum verified.
  4. Calendar classification, SQL layer + tests, findings.json, dashboard.
Every run appends one line to data/processed/pipeline_runs.csv (end-to-end seconds: "time to market").

    python pipelines/daily_refresh.py [--today 2026-11-23] [--offline]
"""
import argparse
import datetime as dt
import json
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import extract_onchain  # noqa: E402
import fetch_public  # noqa: E402
import polite  # noqa: E402

LOG = ROOT / "data" / "processed" / "pipeline_runs.csv"
S3_LIST = "https://aws-public-blockchain.s3.us-east-2.amazonaws.com/?list-type=2&prefix=v1.0/eth/transactions/date={d}/"


def log(msg):
    print(f"[{dt.datetime.now(dt.timezone.utc):%Y-%m-%d %H:%M:%S} UTC] {msg}", flush=True)


def partition_ready(d: dt.date) -> bool:
    """Is the day's transactions partition published? (anonymous S3 listing, no account)"""
    r = requests.get(S3_LIST.format(d=d.isoformat()), headers={"User-Agent": polite.USER_AGENT}, timeout=60)
    return "<Key>" in r.text


def step_onchain(today: dt.date, offline: bool) -> tuple[int, list]:
    done = sorted(p.parent.name[5:] for p in (ROOT / "data" / "raw" / "onchain").glob("date=*/_done"))
    last = dt.date.fromisoformat(done[-1])
    alerts, new = [], 0
    d = last + dt.timedelta(days=1)
    con = None
    while d < today:
        if offline:
            break
        if not partition_ready(d):
            now = dt.datetime.now(dt.timezone.utc)
            if d == today - dt.timedelta(days=1) and now.hour >= 6:
                alerts.append(f"partition {d} still missing at {now:%H:%M} UTC")
            break                                   # later days cannot be complete either
        if con is None:
            con = extract_onchain.connect()
            extract_onchain.load_address_union(con)
        tot = extract_onchain.extract_day(con, d)
        log(f"on-chain {d}: {tot['tx_kept']:,} tx, {tot['tt_kept']:,} transfers, watermark {tot['tx_last_modified']}")
        new += 1
        d += dt.timedelta(days=1)
    return new, alerts


def step_announcements(offline: bool) -> int:
    if offline:
        return 0
    page1 = ROOT / "data" / "raw" / "announcements" / "list" / "page_01.json"
    before = {a["id"] for a in json.loads(page1.read_text(encoding="utf-8"))["data"]["catalogs"][0]["articles"]}
    page1.unlink()                                   # page 1 is the only page that changes
    fetch_public.fetch_announcements()
    after = {a["id"] for a in json.loads(page1.read_text(encoding="utf-8"))["data"]["catalogs"][0]["articles"]}
    return len(after - before)


def run(cmd):
    subprocess.run([sys.executable] + cmd, cwd=ROOT, check=True)


def main(today: dt.date, offline: bool):
    t0 = time.time()
    new_days, alerts = step_onchain(today, offline)
    new_ann = step_announcements(offline)
    if not offline:
        fetch_public.fetch_market(last_day=today - dt.timedelta(days=1))
    run(["src/campaigns_calendar.py"])
    run(["src/run_sql.py"])                          # exits with an error if a SQL test fails
    run(["src/findings.py"])
    run(["src/build_dashboard.py"])
    secs = round(time.time() - t0, 1)
    for a in alerts:
        log("ALERT " + a)
    row = pd.DataFrame([{"run_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M"), "today": today,
                         "new_onchain_days": new_days, "new_announcements": new_ann, "alerts": len(alerts),
                         "seconds": secs}])
    row.to_csv(LOG, mode="a", header=not LOG.exists(), index=False)
    log(f"refresh done in {secs:.0f} s: {new_days} new on-chain day(s), {new_ann} new announcement(s), "
        f"{len(alerts)} alert(s)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--today", default=dt.datetime.now(dt.timezone.utc).date().isoformat())
    ap.add_argument("--offline", action="store_true", help="no network: rebuild from the cache only")
    a = ap.parse_args()
    main(dt.date.fromisoformat(a.today), a.offline)
