"""Collect every PUBLIC source used by the study (cached in data/raw/, never published raw).

Sub-commands (all idempotent: cached files are reused):
  por            8 Proof-of-Reserves address snapshots (public zip files) -> ETH address tables
  market         official Binance daily klines (data.binance.vision) + SHA-256 checksum check
  exchangeinfo   one call to the public exchangeInfo endpoint (pair counts only)
  job            the public Greenhouse job post (facts about the role)
  announcements  "Latest Activities" list (15 pages x 50) + detail of the articles since 2026-05-25
  all            everything above, in that order

Usage:  python src/fetch_public.py all
"""
import argparse
import hashlib
import html
import io
import json
import re
import sys
import zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import duckdb
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import polite  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"

# ---------------------------------------------------------------- Proof of Reserves
POR_SNAPSHOTS = ["20260501", "20260601", "20260701", "20260801",
                 "20260901", "20261001", "20261031", "20261111"]
POR_URL = "https://public.bnbstatic.com/static/proof-of-reserve/wallet_address_{d}.zip"


def fetch_por():
    """Download each snapshot into its own folder, keep only the ETH-network rows.

    Output (raw, never published):
      data/raw/por/eth_membership.parquet  snapshot, kind (deposit|hotcold), coin, address, custodian
      data/raw/por/network_counts.csv      rows per snapshot x file x network (aggregate, publishable)
    """
    out = RAW / "por" / "eth_membership.parquet"
    if out.exists():
        print("[por] cached", out.name)
        return
    con = duckdb.connect()
    parts, counts = [], []
    for d in POR_SNAPSHOTS:
        folder = RAW / "por" / d
        z = polite.cached(POR_URL.format(d=d), folder / f"wallet_address_{d}.zip")
        if z is None:
            raise SystemExit(f"[por] missing snapshot {d}")
        with zipfile.ZipFile(z) as zf:
            for name in zf.namelist():
                if name.startswith("__MACOSX") or not name.endswith(".csv"):
                    continue  # macOS resource forks are not data
                kind = "deposit" if name.endswith("_Deposit.csv") else "hotcold"
                csv_path = folder / Path(name).name
                if not csv_path.exists():
                    zf.extract(name, folder)
                    extracted = folder / name
                    if extracted != csv_path:
                        extracted.replace(csv_path)
                rel = csv_path.as_posix()
                # rows per network (aggregate only)
                c = con.sql(f"""SELECT network, count(*) n FROM read_csv('{rel}', header=true, all_varchar=true)
                                GROUP BY 1""").df()
                c["snapshot"], c["file"] = d, kind
                counts.append(c)
                # ETH network only, addresses in lower case
                p = folder / f"eth_{kind}.parquet"
                con.sql(f"""COPY (SELECT '{d}' AS snapshot, '{kind}' AS kind, coin,
                                lower(trim(address)) AS address,
                                "Third party custodian name" AS custodian
                           FROM read_csv('{rel}', header=true, all_varchar=true)
                           WHERE network = 'ETH') TO '{p.as_posix()}' (FORMAT parquet)""")
                parts.append(p.as_posix())
                csv_path.unlink()  # the CSV is large; the zip stays as the cache
        print("[por]", d, "done")
    con.sql(f"COPY (SELECT * FROM read_parquet({parts})) TO '{out.as_posix()}' (FORMAT parquet)")
    pd.concat(counts).to_csv(RAW / "por" / "network_counts.csv", index=False)


# ---------------------------------------------------------------- market data
SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "USDCUSDT",
           "USDTBRL", "USDTTRY", "USDTMXN", "USDTARS", "EURUSDT"]
KLINE_COLS = ["open_time", "open", "high", "low", "close", "volume", "close_time",
              "quote_volume", "trades", "taker_buy_base", "taker_buy_quote", "ignore"]
VISION = "https://data.binance.vision/data/spot"


def to_utc(ts: int) -> datetime:
    """Kline timestamps: milliseconds in older files (13 digits), microseconds in 2025+ files (16 digits)."""
    ts = int(ts)
    if ts >= 10**15:          # microseconds
        return datetime.fromtimestamp(ts / 1_000_000, tz=timezone.utc)
    return datetime.fromtimestamp(ts / 1_000, tz=timezone.utc)   # milliseconds


def _checked_zip(url: str, path: Path) -> bytes | None:
    """Download a kline zip and its .CHECKSUM file; refuse the file if SHA-256 differs."""
    z = polite.cached(url, path)
    c = polite.cached(url + ".CHECKSUM", path.with_suffix(".zip.CHECKSUM"))
    if z is None or c is None:
        return None
    expected = c.read_text().split()[0].strip().lower()
    got = hashlib.sha256(z.read_bytes()).hexdigest()
    if got != expected:
        path.unlink()
        raise SystemExit(f"[market] checksum mismatch {path.name}")
    return z.read_bytes()


def read_kline_zip(blob: bytes) -> pd.DataFrame:
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        df = pd.read_csv(zf.open(zf.namelist()[0]), header=None, names=KLINE_COLS)
    df["date"] = [to_utc(t).date() for t in df["open_time"]]
    return df


def fetch_market(last_day: date = date(2026, 11, 22)):
    """Daily klines from 2026-04 to last_day (monthly files, then daily files for the current month)."""
    rows = []
    months = pd.period_range("2026-04", last_day.strftime("%Y-%m"), freq="M")
    for sym in SYMBOLS:
        for m in months:
            if m.end_time.date() <= last_day and m.strftime("%Y-%m") != last_day.strftime("%Y-%m"):
                name = f"{sym}-1d-{m.strftime('%Y-%m')}.zip"
                blob = _checked_zip(f"{VISION}/monthly/klines/{sym}/1d/{name}", RAW / "market" / sym / name)
                if blob:
                    rows.append(read_kline_zip(blob).assign(symbol=sym))
            else:  # current month: daily files
                d = m.start_time.date()
                while d <= min(m.end_time.date(), last_day):
                    name = f"{sym}-1d-{d.isoformat()}.zip"
                    blob = _checked_zip(f"{VISION}/daily/klines/{sym}/1d/{name}", RAW / "market" / sym / name)
                    if blob:
                        rows.append(read_kline_zip(blob).assign(symbol=sym))
                    d += timedelta(days=1)
    # one 2024 file to prove the millisecond/microsecond handling on real data
    _checked_zip(f"{VISION}/monthly/klines/BTCUSDT/1d/BTCUSDT-1d-2024-12.zip",
                 RAW / "market" / "BTCUSDT" / "BTCUSDT-1d-2024-12.zip")
    df = pd.concat(rows)[["symbol", "date", "open", "high", "low", "close", "volume", "quote_volume", "trades"]]
    df = df.drop_duplicates(["symbol", "date"]).sort_values(["symbol", "date"])
    PROCESSED.mkdir(parents=True, exist_ok=True)
    df.to_csv(PROCESSED / "market_daily.csv", index=False)   # official public market data, aggregated daily
    print("[market]", len(df), "rows")


# ---------------------------------------------------------------- exchangeInfo
def fetch_exchangeinfo():
    d = polite.cached_json("https://api.binance.com/api/v3/exchangeInfo?permissions=SPOT",
                           RAW / "exchangeinfo" / "exchangeInfo_spot.json")
    s = pd.DataFrame(d["symbols"])
    summary = {"pairs": int(len(s)), "trading": int((s["status"] == "TRADING").sum()),
               "trading_usdt_quote": int(((s["status"] == "TRADING") & (s["quoteAsset"] == "USDT")).sum())}
    (RAW / "exchangeinfo" / "summary.json").write_text(json.dumps(summary, indent=1))
    print("[exchangeinfo]", summary)


# ---------------------------------------------------------------- job post
def fetch_job():
    d = polite.cached_json("https://boards-api.greenhouse.io/v1/boards/binance/jobs/5004445101?questions=true",
                           RAW / "job" / "job_5004445101.json")
    body = html.unescape(html.unescape(d.get("content", "")))      # escaped twice by the API
    (RAW / "job" / "job_body.html").write_text(body, encoding="utf-8")
    allj = polite.cached_json("https://boards-api.greenhouse.io/v1/boards/binance/jobs",
                              RAW / "job" / "all_jobs.json")
    facts = {"title": d.get("title"), "first_published": d.get("first_published"),
             "updated_at": d.get("updated_at"), "location": (d.get("location") or {}).get("name"),
             "open_roles_on_board": len(allj.get("jobs", []))}
    (RAW / "job" / "facts.json").write_text(json.dumps(facts, indent=1))
    print("[job]", facts)


# ---------------------------------------------------------------- announcements
LIST_URL = ("https://www.binance.com/bapi/composite/v1/public/cms/article/list/query"
            "?type=1&catalogId=93&pageNo={n}&pageSize=50")       # 50 is the maximum (100 -> HTTP 400)
DETAIL_URL = "https://www.binance.com/bapi/composite/v1/public/cms/article/detail/query?articleCode={c}"
PERIOD_RE = re.compile(
    r"(20\d\d-\d\d-\d\d \d\d:\d\d(?::\d\d)?)\s*\(UTC\)\s*(?:to|-|–|~)\s*(20\d\d-\d\d-\d\d \d\d:\d\d(?::\d\d)?)\s*\(UTC\)")


def _body_text(body) -> str:
    """The article body is a JSON tree of nodes; collect every text leaf."""
    try:
        tree = json.loads(body) if isinstance(body, str) else body
    except (TypeError, ValueError):
        return str(body or "")
    out = []

    def walk(n):
        if isinstance(n, dict):
            if isinstance(n.get("text"), str):
                out.append(n["text"])
            for v in n.values():
                walk(v)
        elif isinstance(n, list):
            for v in n:
                walk(v)
    walk(tree)
    return " ".join(out)


def fetch_announcements(pages: int = 15, detail_since: date = date(2026, 5, 25)):
    """List + detail. Raw titles stay in data/raw/ (they are Binance's text: never published)."""
    arts = []
    for n in range(1, pages + 1):
        d = polite.cached_json(LIST_URL.format(n=n), RAW / "announcements" / "list" / f"page_{n:02d}.json")
        arts += d["data"]["catalogs"][0]["articles"]
    df = pd.DataFrame(arts).drop_duplicates("id")
    df["release_utc"] = pd.to_datetime(df["releaseDate"], unit="ms", utc=True)
    periods, stopped = [], False
    for code, rel in zip(df["code"], df["release_utc"]):
        start = end = None
        if rel.date() >= detail_since and not stopped:
            # slower pace for the detail endpoint (it answered 429 at 1 request/s after ~110 calls)
            try:
                d = polite.cached_json(DETAIL_URL.format(c=code), RAW / "announcements" / "detail" / f"{code}.json",
                                       min_delay=6.0)
            except polite.RateLimited:
                stopped, d = True, None       # stop politely; the next run resumes from the cache
                print("[announcements] rate limited twice: stopping, rerun later to resume", flush=True)
            text = _body_text(((d or {}).get("data") or {}).get("body"))
            m = PERIOD_RE.search(text)
            if m:
                start, end = m.group(1), m.group(2)
        periods.append((start, end))
    df["period_start_utc"] = [p[0] for p in periods]
    df["period_end_utc"] = [p[1] for p in periods]
    df.to_parquet(RAW / "announcements" / "announcements_raw.parquet", index=False)   # contains titles: raw only
    print("[announcements]", len(df), "articles;", int((df["release_utc"].dt.date >= detail_since).sum()),
          "with detail;", int(df["period_start_utc"].notna().sum()), "periods found")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["por", "market", "exchangeinfo", "job", "announcements", "all"])
    a = ap.parse_args()
    steps = {"por": fetch_por, "market": fetch_market, "exchangeinfo": fetch_exchangeinfo,
             "job": fetch_job, "announcements": fetch_announcements}
    for k, f in steps.items():
        if a.what in (k, "all"):
            f()
