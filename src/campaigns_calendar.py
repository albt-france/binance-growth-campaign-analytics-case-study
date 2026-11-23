"""PUBLIC DATA: Binance "Latest Activities" announcements -> a campaign calendar WITHOUT titles.

Input  (raw, never published): data/raw/announcements/announcements_raw.parquet (titles + promotion periods)
Output (publishable):
  data/processed/campaign_calendar.csv      article_code, release date, promotion period, type, region, asset
  data/processed/campaigns_active_daily.csv number of campaigns whose promotion period covers each UTC day
  data/processed/campaign_taxonomy_check.csv precision per type on 50 hand-checked titles (labels only)

Classification = written rules (docs/campaign_taxonomy.md): the first matching rule wins.
No title and no sentence of an announcement leaves data/raw/ (the text belongs to Binance).
"""
import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "announcements"
PROC = ROOT / "data" / "processed"

# (type, pattern) in priority order: the first match wins.
# v1 = first draft (70% correct on a 50-title development sample);
# v2 = refined on that sample, then measured on a FRESH sample of 50 titles (see main()).
TYPE_RULES = [
    ("tokenized_stock", r"tokeni[sz]ed\s+(stock|share|equit|securit)|\bstock(s)?\b|\bequit(y|ies)\b|pre-ipo"),
    ("new_user", r"new\s*users?|newcomer|first[- ]time|welcome|new to binance|sign[- ]?up"),
    ("p2p", r"\bp2p\b"),
    ("trading_competition", r"trading\s+(competition|tournament|challenge|sprint|cup|frenzy)|\bcompetition\b|"
                            r"\btournament\b|trade\s+to\s+(win|share|earn)|\bleaderboard\b|traders\s+league|"
                            r"futures\s+frenzy"),
    ("referral", r"\brefer|referral|invite|friends"),
    ("alpha", r"\balpha\b|booster|pre-tge|\btge\b|binance\s+wallet"),
    ("learn_quiz", r"\blearn\b|\bquiz\b|academy|\bcourse\b|test your knowledge|word of the day"),
    ("pay", r"binance\s+pay|\bpay\b|payment|merchant|binance\s+card|cashback"),
    ("earn_apr", r"\bearn\b|\bapr\b|\bapy\b|staking|savings|launchpool|hodler|yield|subscribe|subscription|"
                 r"\bvault\b|\bstake\b|\bhold\b"),
    ("deposit", r"deposit|top[- ]?up|\bbuy\b|convert"),
]
REGION_RULES = [
    ("LATAM", r"brazil|brasil|\bbrl\b|argentin|\bars\b|mexic|\bmxn\b|colombia|\bcop\b|peru|chile|latam|latin"),
    ("TR", r"t[uü]rk|turkey|\btry\b"),
    ("SEA", r"vietnam|\bvnd\b|philippin|\bphp\b|indonesia|\bidr\b|thai|malaysia|\bmyr\b|\bsea\b"),
    ("CIS", r"kazakh|\bkzt\b|ukrain|\buah\b|uzbek|\bcis\b|russia|\brub\b"),
    ("MENA", r"\bmena\b|\buae\b|saudi|egypt|morocco|bahrain|\baed\b"),
    ("AFRICA", r"nigeria|\bngn\b|kenya|ghana|africa|\bzar\b"),
    ("EU", r"\beur\b|europe|balkan|poland|\bpln\b|france|spain|italy|germany"),
    ("SOUTH_ASIA", r"india|\binr\b|pakistan|\bpkr\b|bangladesh"),
]
ASSETS = ["USDC", "USDT", "FDUSD", "BTC", "ETH", "BNB", "SOL", "XRP", "DOGE"]


def classify(title: str) -> tuple[str, str, str]:
    t = title.lower()
    typ = next((k for k, p in TYPE_RULES if re.search(p, t)), "other")
    reg = next((k for k, p in REGION_RULES if re.search(p, t)), "not stated")
    if typ == "tokenized_stock":
        asset = "tokenized-stock voucher" if "voucher" in t else "tokenized stock"   # never a company or ticker
    else:
        asset = next((a for a in ASSETS if re.search(rf"\b{a}\b", title)), "other or none")
    return typ, reg, asset


def main():
    raw = pd.read_parquet(RAW / "announcements_raw.parquet")
    cls = raw["title"].map(classify)
    cal = pd.DataFrame({
        "article_code": raw["code"],
        "release_date_utc": raw["release_utc"].dt.tz_convert(None),
        "period_start_utc": pd.to_datetime(raw["period_start_utc"], format="mixed"),
        "period_end_utc": pd.to_datetime(raw["period_end_utc"], format="mixed"),
        "type": [c[0] for c in cls], "region": [c[1] for c in cls], "asset": [c[2] for c in cls],
    }).sort_values("release_date_utc")
    cal["detail_in_scope"] = cal.release_date_utc >= pd.Timestamp("2026-05-25")     # detail requested
    cached = {f.stem for f in (RAW / "detail").glob("*.json")}
    cal["detail_read"] = cal.article_code.isin(cached)                                 # detail actually read
    cal.to_csv(PROC / "campaign_calendar.csv", index=False)

    # campaigns active per day (only those whose promotion period was found)
    days = pd.date_range("2026-05-25", "2026-11-22", freq="D")
    p = cal.dropna(subset=["period_start_utc", "period_end_utc"])
    active = [((p.period_start_utc.dt.normalize() <= d) & (p.period_end_utc >= d)).sum() for d in days]
    pd.DataFrame({"date": days, "active_campaigns": active}).to_csv(PROC / "campaigns_active_daily.csv", index=False)

    # hand checks (labels typed by the analyst in raw-only files; only precision figures are published)
    #  dev sample (seed 7): rules v1 were checked on it, then refined -> v2
    #  fresh sample (seed 8, excluding the dev titles): rules v2 measured once, never tuned on it
    dev = pd.read_csv(RAW / "manual_check_dev_v1.csv")
    fresh_path = RAW / "manual_check_fresh_v2.csv"
    if not fresh_path.exists():
        f = raw[~raw["code"].isin(dev["code"])].sample(50, random_state=8)[["code", "title"]].copy()
        f["predicted_v2"] = f["title"].map(lambda x: classify(x)[0])
        f["manual"] = ""
        f.to_csv(fresh_path, index=False)
        print("[calendar] fill the 'manual' column of", fresh_path.name)
    else:
        f = pd.read_csv(fresh_path)
        dev["predicted_v2"] = dev["title"].map(lambda x: classify(x)[0])
        rows = [("dev sample, rules v1", (dev.predicted_v1 == dev.manual).mean()),
                ("dev sample, rules v2 (tuned on it)", (dev.predicted_v2 == dev.manual).mean()),
                ("fresh sample, rules v2", (f.predicted_v2 == f.manual).mean())]
        out = pd.DataFrame(rows, columns=["check", "accuracy"])
        per = f.assign(ok=f.predicted_v2 == f.manual).groupby("predicted_v2")["ok"].agg(["sum", "count"])
        per = per.reset_index().rename(columns={"predicted_v2": "type", "sum": "correct", "count": "predicted_n"})
        per["precision"] = (per.correct / per.predicted_n).round(3)
        out.to_csv(PROC / "campaign_taxonomy_check.csv", index=False)
        per.to_csv(PROC / "campaign_taxonomy_precision_by_type.csv", index=False)
    print(f"[calendar] {len(cal)} announcements, {int(cal.detail_in_scope.sum())} in detail scope, "
          f"{int(cal.detail_read.sum())} details read, "
          f"{int(cal.period_start_utc.notna().sum())} periods; types:",
          cal[cal.detail_in_scope].type.value_counts().to_dict())


if __name__ == "__main__":
    main()
