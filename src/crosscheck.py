"""Second method: recompute report figures with pandas only (no SQL, no DuckDB), from the Parquet files, and
compare them with findings.json. Writes data/processed/crosscheck.csv.

    python src/crosscheck.py
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SIM = ROOT / "data" / "sim"
PROC = ROOT / "data" / "processed"


def rd(name, cols=None):
    return pd.read_parquet(SIM / name, columns=cols)


def main():
    F = json.loads((PROC / "findings.json").read_text(encoding="utf-8"))
    ev, r = F["sim"]["events"], F["real"]
    rows = []

    def add(label, report, recomputed, tol=1e-6):
        rows.append({"figure": label, "report": report, "pandas": recomputed,
                     "match": bool(abs(report - recomputed) <= tol * max(1, abs(report)))})

    # deduplicated deposits (latest ingestion per event_id)
    dep = rd("deposits", ["event_id", "user_id", "ts", "amount_usd", "is_first", "ingested_at"])
    raw27 = (dep.ts.dt.normalize() == "2026-10-27").sum()
    dep = dep.sort_values("ingested_at").drop_duplicates("event_id", keep="last")
    add("E5 raw / clean deposit rows on 27 Oct", ev["E5"]["ratio"],
        raw27 / (dep.ts.dt.normalize() == "2026-10-27").sum(), 1e-4)

    fe = rd("funnel_events", ["user_id", "event", "event_ts", "event_id", "ingested_at"])
    fe = fe.sort_values("ingested_at").drop_duplicates("event_id", keep="last")
    users = rd("users", ["user_id", "region", "channel", "signup_ts", "first_touch_campaign"])
    first = fe[fe.event == "first_deposit"].groupby("user_id").event_ts.min()

    # E1 CAC of CMP014 = media / attributed first depositors
    sp = pd.read_parquet(SIM / "spend_daily.parquet")
    media14 = sp[(sp.campaign_id == "CMP014") & (sp.cost_type == "media")].amount_usd.sum()
    dep14 = users[users.first_touch_campaign == "CMP014"].user_id.isin(first.index).sum()
    add("E1 CMP014 CAC (USD)", ev["E1"]["cac"], round(media14 / dep14, 2), 1e-3)

    # E8 week-over-week CAC, booking and activity date
    acq = sp[sp.cost_type.isin(["media", "partner_fee"]) & (sp.channel != "crm_lifecycle")]
    wk = lambda s: (s - pd.to_timedelta(s.dt.dayofweek, unit="D")).dt.normalize()
    nd = first.groupby(wk(first.reset_index().set_index("user_id").event_ts).values).size()
    nd.index = pd.to_datetime(nd.index)
    for col, key in (("booking_date", "wow_booking"), ("activity_date", "wow_activity")):
        b = acq.groupby(wk(pd.to_datetime(acq[col])))["amount_usd"].sum()
        cac = b / nd
        add(f"E8 CAC week-over-week by {col.split('_')[0]} date (2 Nov)", ev["E8"][key],
            cac[pd.Timestamp("2026-11-02")] / cac[pd.Timestamp("2026-10-26")] - 1, 1e-3)

    # E4 TR KYC pass rate during the outage (submission cohort, retries counted separately)
    sub = fe[fe.event == "kyc_submitted"].merge(users[["user_id", "region"]], on="user_id")
    sub = sub[sub.region == "TR"].sort_values(["user_id", "event_ts"])
    sub["next_ts"] = sub.groupby("user_id").event_ts.shift(-1)
    pas = fe[fe.event == "kyc_passed"][["user_id", "event_ts"]].rename(columns={"event_ts": "pass_ts"})
    s2 = sub.merge(pas, on="user_id", how="left")
    s2["ok"] = (s2.pass_ts >= s2.event_ts) & (s2.next_ts.isna() | (s2.pass_ts < s2.next_ts))
    out = s2[s2.event_ts.dt.normalize().between("2026-10-06", "2026-10-08")]
    add("E4 TR KYC pass rate 6-8 Oct", ev["E4"]["pass_rate_outage"], out.ok.mean(), 1e-6)

    # E7 30-day retention Sep / Oct (traded on days 24-30 after the first deposit, full cohorts)
    tr = rd("trades_daily", ["user_id", "date"])
    tr["date"] = pd.to_datetime(tr.date)
    fd = first.dt.normalize().rename("d0").reset_index()
    fd = fd[fd.d0 + pd.Timedelta(days=30) <= pd.Timestamp("2026-11-22")]
    m = tr.merge(fd, on="user_id")
    k = (m.date - m.d0).dt.days
    act = set(m[(k >= 24) & (k <= 30)].user_id)
    fd["ret"] = fd.user_id.isin(act)
    for mon, key in (("2026-09", "overall_sep"), ("2026-10", "overall_oct")):
        add(f"E7 30-day retention, {mon} cohort", ev["E7"][key],
            round(fd[fd.d0.dt.strftime("%Y-%m") == mon].ret.mean(), 4), 1e-4)

    # E2 farm inflation: flagged referrers' referees / other referral sign-ups that week
    u = users.assign(week=wk(users.signup_ts))
    ab = pd.read_csv(PROC / "referral_abuse_indicators.csv")
    flagged = set(ab[ab["flags"] >= 3].referrer_id)
    ref = rd("referrals.parquet", ["referrer_id", "referee_id"])
    farm_ids = set(ref[ref.referrer_id.isin(flagged)].referee_id)
    wkref = u[(u.channel == "referral") & (u.week == "2026-09-14")]
    nf = wkref.user_id.isin(farm_ids).sum()
    add("E2 referral inflation, week of 14 Sep", ev["E2"]["inflation"], nf / (len(wkref) - nf), 1e-6)

    # real part: three days of USDT deposits and senders (pandas vs SQL, computed in onchain_metrics)
    for x in r["crosscheck"]:
        add(f"Real {x['date']}: USDT deposit transfers", x["deposits_sql"], x["deposits_pandas"])

    out = pd.DataFrame(rows)
    out.to_csv(PROC / "crosscheck.csv", index=False)
    print(out.to_string(index=False))
    print(f"[crosscheck] {int(out.match.sum())} / {len(out)} figures match")


if __name__ == "__main__":
    main()
