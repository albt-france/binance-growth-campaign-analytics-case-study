"""SIMULATED data: a fictional crypto exchange ("the simulated exchange"), 13 weeks (2026-08-24 to 2026-11-22).

Nothing here is Binance data. The simulation is only ANCHORED on public facts (docs/assumptions.md):
  - market factor   = real daily |return| of BTCUSDT (official Binance klines, data/processed/market_daily.csv)
  - hourly profile  = real hourly profile of deposits to Binance-listed addresses on Ethereum
  - campaign types  = real mix of the "Latest Activities" announcements; start dates drawn in their real rhythm
  - local currency  = real USDTBRL, USDTTRY, USDTMXN, USDTARS, EURUSDT closes

Eight hidden events are planted (truth in data/_hidden_truth.csv, never published, never read by the analysis):
  1 LATAM-BR boosted-rate new-user campaign (CMP014): +80% sign-ups, best CAC, 55% of depositors withdraw >=90%
  2 referral farm, week of 14 Sep: 6,200 accounts from 41 referrers (shared devices, bursts, identical deposits)
  3 LATAM double counting: affiliate_kol + paid_social partner reports claim ~128% of the real sign-ups
  4 KYC vendor outage in TR, 6-8 Oct: KYC pass rate 78% -> 22%
  5 data quality: (a) deposits replayed on 27 Oct (same event_id, new ingested_at); (b) a campaign launched at
    16:00 UTC (= midnight in UTC+8), so its "day 1" differs by time zone
  6 trading competition starting on the real most volatile BTC day: naive +45% trades, true effect +3%
  7 Simpson: October 30-day retention falls overall while it rises in every channel (affiliate push)
  8 false signal: week of 2 Nov, three weeks of partner invoices booked at once -> CAC +40% by booking date

Seed 42. Output: Parquet in data/sim/ (partitioned by week for the large tables).
Usage:  python src/simulate_exchange.py [--scale 1.0]
"""
import argparse
import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
SIM = ROOT / "data" / "sim"
TRUTH = ROOT / "data" / "_hidden_truth.csv"

START, END = pd.Timestamp("2026-08-24"), pd.Timestamp("2026-11-22")
DAYS = pd.date_range(START, END, freq="D")
ND = len(DAYS)                                     # 91 days = 13 weeks
END_TS = END + pd.Timedelta(hours=23, minutes=59, seconds=59)

REGIONS = ["LATAM-BR", "LATAM-AR", "LATAM-MX", "TR", "SEA-VN", "SEA-PH", "CIS-KZ", "MENA", "EU"]
BASE_REG = np.array([1680, 840, 1050, 1680, 1890, 1260, 630, 1365, 2205], float)   # sign-ups / day
CURRENCY = {"LATAM-BR": "BRL", "LATAM-AR": "ARS", "LATAM-MX": "MXN", "TR": "TRY", "EU": "EUR"}
LATAM = [0, 1, 2]
CHANNELS = ["organic", "paid_search", "paid_social", "affiliate_kol", "referral", "app_store_ads"]
MIX = np.array([0.285, 0.13, 0.14, 0.08, 0.215, 0.15])
PAID = ["paid_search", "paid_social", "affiliate_kol", "app_store_ads"]
CPR = {"paid_search": 9.0, "paid_social": 6.0, "affiliate_kol": 7.0, "app_store_ads": 8.0}   # USD per sign-up
P_KYC_SUB = 0.74
P_KYC_PASS = 0.78
P_DEP = dict(zip(CHANNELS, [0.62, 0.58, 0.50, 0.52, 0.60, 0.55]))       # first deposit | KYC passed
# 30-day retention target per channel (Sep), +3.5 pts in Oct for every channel (event 7)
RET = dict(zip(CHANNELS, [0.43, 0.39, 0.335, 0.08, 0.40, 0.335]))
RET_OCT_UPLIFT = 0.04
AFF_PUSH_OCT = 6.5                                  # affiliate partner push in October (event 7)
Q_ACTIVE = 0.28                                     # daily activity probability of a retained user
DOW = np.array([1.02, 1.03, 1.03, 1.02, 1.00, 0.94, 0.96])               # Mon..Sun
FEE = 0.0025                                        # net revenue take rate on volume (fees + spread), assumption

rng = np.random.default_rng(42)


def day_index(ts) -> np.ndarray:
    return np.asarray((pd.to_datetime(ts) - START) // pd.Timedelta(days=1)).astype(int)


# ------------------------------------------------------------------ real anchors
def load_anchors():
    mk = pd.read_csv(PROC / "market_daily.csv", parse_dates=["date"])
    btc = mk[mk.symbol == "BTCUSDT"].set_index("date")["close"].sort_index()
    ret = np.log(btc).diff().abs()
    vol = ret.reindex(DAYS).values
    m = vol / np.nanmean(vol)                                   # 1 = average volatility day of the window
    qv = mk[mk.symbol == "BTCUSDT"].set_index("date")["quote_volume"].reindex(DAYS).values
    v = qv / np.nanmean(qv)                                     # 1 = average BTC volume day of the window
    fx = {}
    for cur, sym, inv in [("BRL", "USDTBRL", False), ("TRY", "USDTTRY", False), ("MXN", "USDTMXN", False),
                          ("ARS", "USDTARS", False), ("EUR", "EURUSDT", True)]:
        s = mk[mk.symbol == sym].set_index("date")["close"].reindex(DAYS).ffill().bfill().values
        fx[cur] = 1 / s if inv else s                           # local currency per 1 USD(T)
    prof = pd.read_csv(PROC / "onchain_hourly_profile.csv").sort_values("hour_utc")["share"].values
    prof = prof / prof.sum()
    cal = pd.read_csv(PROC / "campaign_calendar.csv", parse_dates=["release_date_utc", "period_start_utc",
                                                                    "period_end_utc"])
    return m, v, fx, prof, cal


# ------------------------------------------------------------------ campaigns
SIM_TYPES = {"new_user": "registrations", "referral": "registrations", "learn_quiz": "registrations",
             "deposit": "deposits", "earn_apr": "deposits", "p2p": "deposits",
             "trading_competition": "trades", "alpha": "trades", "tokenized_stock": "trades",
             "pay": "trades", "other": "trades"}


def build_campaigns(m, cal):
    """40 campaigns. 7 are fixed by the hidden events / experiment; 33 are drawn from the real type mix,
    with start dates and durations drawn from the real promotion periods of the same window."""
    real = cal[(cal.release_date_utc >= START) & (cal.release_date_utc <= END_TS)]
    mix = real["type"].value_counts(normalize=True)
    starts = real["period_start_utc"].dropna()
    starts = starts[(starts >= START) & (starts <= END - pd.Timedelta(days=10))]
    dur = (real["period_end_utc"] - real["period_start_utc"]).dt.days.dropna().clip(3, 28)
    # most volatile real BTC day with 14 days before and 7 days after inside the window (event 6)
    elig = np.arange(14, ND - 7)
    comp_day = int(elig[np.nanargmax(m[elig])])
    fixed = {
        "CMP006": dict(type="referral", region="SEA-VN", channel="referral", start="2026-09-07", days=21,
                       lift=0.15, objective="registrations"),
        "CMP009": dict(type="deposit", region="ALL", channel="crm_lifecycle", start="2026-09-21", days=14,
                       lift=0.006, objective="reactivation", holdout=True, n_target=200_000),
        "CMP014": dict(type="new_user", region="LATAM-BR", channel="affiliate_kol", start="2026-10-05", days=21,
                       lift=0.80, objective="first_deposits"),
        "CMP017": dict(type="new_user", region="TR", channel="paid_social", start="2026-10-01", days=14,
                       lift=0.25, objective="first_deposits"),
        "CMP020": dict(type="earn_apr", region="ALL", channel="crm_lifecycle", start="2026-10-05", days=14,
                       lift=0.0, objective="reactivation", holdout=True, n_target=200_000),
        "CMP022": dict(type="trading_competition", region="EU", channel="paid_social",
                       start=str(DAYS[comp_day].date()), days=3, lift=0.03, objective="trades"),
        "CMP027": dict(type="earn_apr", region="SEA-PH", channel="paid_search", start="2026-11-02 16:00", days=14,
                       lift=0.20, objective="deposits"),
        "CMP031": dict(type="deposit", region="ALL", channel="crm_lifecycle", start="2026-10-19", days=14,
                       lift=0.018, objective="reactivation", holdout=True, n_target=600_000),
        "CMP035": dict(type="learn_quiz", region="ALL", channel="crm_lifecycle", start="2026-11-02", days=14,
                       lift=0.010, objective="reactivation", holdout=True, n_target=200_000),
    }
    rows = []
    free_types = [t for t in mix.index if t in SIM_TYPES]
    p = mix[free_types] / mix[free_types].sum()
    for i in range(1, 41):
        cid = f"CMP{i:03d}"
        if cid in fixed:
            f = fixed[cid]
            s = pd.Timestamp(f["start"])
            rows.append(dict(campaign_id=cid, type=f["type"], region=f["region"], channel=f["channel"],
                             start_ts_utc=s, end_ts_utc=s + pd.Timedelta(days=f["days"]) - pd.Timedelta(seconds=1),
                             objective=f["objective"], true_lift=f["lift"], has_holdout=f.get("holdout", False),
                             n_target=f.get("n_target", 0)))
            continue
        t = rng.choice(p.index, p=p.values)
        obj = SIM_TYPES[t]
        region = "ALL" if rng.random() < 0.10 else rng.choice(REGIONS)
        s = pd.Timestamp(rng.choice(starts.values)).normalize() if len(starts) else START + pd.Timedelta(
            days=int(rng.integers(14, ND - 10)))
        s = max(s, START + pd.Timedelta(days=14))                 # keep a 14-day pre-period in the window
        d = int(rng.choice(dur.values)) if len(dur) else 14
        ch = {"registrations": rng.choice(["paid_social", "paid_search", "app_store_ads"]),
              "deposits": "paid_search", "trades": "paid_social"}[obj]
        if t == "referral":
            ch = "referral"
        if t == "learn_quiz":
            ch = "organic"
        # true effect: some campaigns do nothing (realistic), most do a little
        lift = max(0.0, rng.normal({"registrations": 0.10, "deposits": 0.08, "trades": 0.05}[obj], 0.06))
        if rng.random() < 0.25:
            lift = 0.0
        rows.append(dict(campaign_id=cid, type=t, region=region, channel=ch, start_ts_utc=s,
                         end_ts_utc=s + pd.Timedelta(days=d) - pd.Timedelta(seconds=1), objective=obj,
                         true_lift=round(lift, 3), has_holdout=False, n_target=0))
    c = pd.DataFrame(rows)
    c["end_ts_utc"] = c["end_ts_utc"].clip(upper=END_TS)
    # what marketing typed in its tracker: the launch date in UTC+8 (Hong Kong office), event 5b
    c["start_date_hkt_entered"] = (c["start_ts_utc"] + pd.Timedelta(hours=8)).dt.date
    c["holdout_share"] = np.where(c["has_holdout"], 0.10, 0.0)
    return c, comp_day


def active_matrix(c: pd.DataFrame, obj: str) -> np.ndarray:
    """Multiplier (1 + lift) per region x day for campaigns with this objective (ALL = every region)."""
    M = np.ones((len(REGIONS), ND))
    for r in c[c.objective == obj].itertuples():
        d0 = max(0, int((r.start_ts_utc.normalize() - START).days))
        d1 = min(ND - 1, int((r.end_ts_utc.normalize() - START).days))
        rows = range(len(REGIONS)) if r.region == "ALL" else [REGIONS.index(r.region)]
        for ri in rows:
            M[ri, d0:d1 + 1] *= 1 + r.true_lift
    return M


# ------------------------------------------------------------------ helpers
def ts_in_day(day_idx: np.ndarray, prof: np.ndarray) -> np.ndarray:
    """Timestamp inside each day following the real hourly profile."""
    h = rng.choice(24, size=len(day_idx), p=prof)
    sec = rng.integers(0, 3600, size=len(day_idx))
    return (START.value + day_idx.astype(np.int64) * 86_400_000_000_000
            + (h * 3600 + sec).astype(np.int64) * 1_000_000_000).astype("datetime64[ns]")


def write_partitioned(df: pd.DataFrame, name: str, ts_col: str):
    out = SIM / name
    if out.exists():
        shutil.rmtree(out)
    df = df.copy()
    wk = pd.to_datetime(df[ts_col]).dt.normalize()
    df["week"] = (wk - pd.to_timedelta(wk.dt.dayofweek, unit="D")).dt.strftime("%Y-%m-%d")
    df.loc[pd.to_datetime(df[ts_col]) < START, "week"] = "pre-window"
    pq.write_to_dataset(pa.Table.from_pandas(df, preserve_index=False), out, partition_cols=["week"])


def write_single(df: pd.DataFrame, name: str):
    df.to_parquet(SIM / f"{name}.parquet", index=False)


# ------------------------------------------------------------------ main generator
def main(scale: float = 1.0):
    SIM.mkdir(parents=True, exist_ok=True)
    m, v_btc, fx, prof, cal = load_anchors()
    camps, comp_day = build_campaigns(m, cal)
    dates = DAYS.values
    dow = DOW[DAYS.dayofweek.values]
    oct_mask = (DAYS.month == 10)

    # ---------- 1. sign-ups: region x channel x day intensities
    noise = np.exp(rng.normal(0, 0.05, size=(len(REGIONS), ND)))           # region-day shocks
    m_reg = np.clip(1 + 0.10 * (m - 1), 0.7, 1.6)
    lam = (BASE_REG[:, None, None] * scale * MIX[None, :, None] * dow[None, None, :]
           * m_reg[None, None, :] * noise[:, None, :])
    ai = CHANNELS.index("affiliate_kol")
    lam[:, ai, oct_mask] *= AFF_PUSH_OCT
    base_counts = rng.poisson(lam)
    users = []
    for (ri, ci, di), n in np.ndenumerate(base_counts):
        if n:
            users.append((ri, ci, di, n, ""))
    # incremental sign-ups from acquisition campaigns (who would NOT have signed up without the campaign)
    truth_rows = []
    for r in camps[camps.objective.isin(["registrations", "first_deposits"])].itertuples():
        ci = CHANNELS.index(r.channel) if r.channel in CHANNELS else 0
        rows = range(len(REGIONS)) if r.region == "ALL" else [REGIONS.index(r.region)]
        d0 = int((r.start_ts_utc.normalize() - START).days)
        d1 = int((r.end_ts_utc.normalize() - START).days)
        inc_total, base_total = 0, 0.0
        for ri in rows:
            for di in range(d0, d1 + 1):
                if r.campaign_id == "CMP014":            # +80% of ALL Brazilian sign-ups, all via KOL codes
                    lam_inc = r.true_lift * lam[ri, :, di].sum()
                    base_total += lam[ri, :, di].sum()
                else:
                    lam_inc = r.true_lift * lam[ri, ci, di]
                    base_total += lam[ri, ci, di]
                n = rng.poisson(lam_inc)
                inc_total += n
                if n:
                    users.append((ri, ci, di, n, r.campaign_id))
        truth_rows.append(dict(kind="campaign", key=r.campaign_id, metric="registrations",
                               true_lift=r.true_lift, true_incremental=inc_total,
                               counterfactual=round(base_total, 1)))
    u = pd.DataFrame(users, columns=["ri", "ci", "di", "n", "inc_campaign"])
    u = u.loc[u.index.repeat(u["n"])].drop(columns="n").reset_index(drop=True)

    # ---------- 2. referral farm (event 2): 6,200 accounts, 41 referrers, week of 14 Sep
    n_farm, n_ref = 6200, 41
    farm_days = rng.integers(21, 28, size=n_farm)                      # 14-20 Sep
    farm = pd.DataFrame({"ri": REGIONS.index("SEA-VN"), "ci": CHANNELS.index("referral"), "di": farm_days,
                         "inc_campaign": ""})
    u["is_farm"] = False
    farm["is_farm"] = True
    u = pd.concat([u, farm], ignore_index=True)
    N = len(u)
    u["user_id"] = [f"U{4_000_001 + i:07d}" for i in range(N)]
    u["region"] = np.array(REGIONS)[u.ri]
    u["channel"] = np.array(CHANNELS)[u.ci]
    ts = ts_in_day(u.di.values, prof)
    # farm bursts: each referrer's accounts arrive in 3 bursts of ~40 minutes
    fm = u.is_farm.values
    farm_ref = rng.integers(0, n_ref, size=fm.sum())
    burst_start = rng.integers(0, 86_400 - 2_400, size=(n_ref, 3))
    burst_day = rng.integers(21, 28, size=(n_ref, 3))
    b = rng.integers(0, 3, size=fm.sum())
    bd = burst_day[farm_ref, b]
    sec = burst_start[farm_ref, b] + rng.integers(0, 2_400, size=fm.sum())
    ts[fm] = (START.value + bd.astype(np.int64) * 86_400_000_000_000 + sec.astype(np.int64) * 1_000_000_000
              ).astype("datetime64[ns]")
    u.loc[fm, "di"] = bd
    u["signup_ts"] = ts
    print(f"[sim] sign-ups: {N:,}", flush=True)

    # ---------- 3. funnel
    reg_ts = u.signup_ts.values
    sub = rng.random(N) < np.where(fm, 0.50, P_KYC_SUB)
    sub_ts = reg_ts + (rng.exponential(6 * 3600, N) * 1e9).astype("timedelta64[ns]")
    sub_day = day_index(sub_ts)
    tr = (u.region.values == "TR")
    outage = tr & (sub_day >= 43) & (sub_day <= 45)                     # 6-8 Oct (event 4)
    p_pass = np.where(outage, 0.22, P_KYC_PASS)
    p_pass = np.where(fm, 0.30, p_pass)
    passed1 = sub & (rng.random(N) < p_pass)
    # some users who failed during the outage try again 2-8 days later
    retry = sub & ~passed1 & outage & (rng.random(N) < 0.45)
    retry_ts = sub_ts + (rng.uniform(2, 8, N) * 86_400 * 1e9).astype("timedelta64[ns]")
    passed2 = retry & (rng.random(N) < P_KYC_PASS)
    passed = passed1 | passed2
    pass_ts = np.where(passed1, sub_ts, retry_ts) + (rng.exponential(2 * 3600, N) * 1e9).astype("timedelta64[ns]")
    # first deposit
    p_dep = np.array([P_DEP[c] for c in u.channel.values])
    br14 = (u.inc_campaign.values == "CMP014")
    p_dep = np.where(br14, 0.85, p_dep)                               # the boosted rate pulls deposits
    p_dep = np.where(fm, 0.90, p_dep)
    dep = passed & (rng.random(N) < p_dep)
    dep_ts = pass_ts + (rng.exponential(2.5 * 86_400, N) * 1e9).astype("timedelta64[ns]")
    trade = dep & (rng.random(N) < np.where(fm, 0.05, 0.85))
    trade_ts = dep_ts + (rng.exponential(12 * 3600, N) * 1e9).astype("timedelta64[ns]")
    end = np.datetime64(END_TS)
    sub &= sub_ts <= end
    passed &= pass_ts <= end
    dep &= dep_ts <= end
    trade &= trade_ts <= end
    retry &= retry_ts <= end

    # campaign exposure of NON-incremental users (they would have signed up anyway, but click the campaign)
    u["attributed_campaign"] = u.inc_campaign.values
    for r in camps[camps.objective.isin(["registrations", "first_deposits"])].itertuples():
        d0 = int((r.start_ts_utc.normalize() - START).days)
        d1 = int((r.end_ts_utc.normalize() - START).days)
        inreg = (u.region.values == r.region) if r.region != "ALL" else np.ones(N, bool)
        ch = u.channel.values == r.channel
        if r.campaign_id == "CMP014":
            ch = np.isin(u.channel.values, ["affiliate_kol", "paid_social", "organic"])
        cand = inreg & ch & (u.di.values >= d0) & (u.di.values <= d1) & (u.attributed_campaign.values == "") & ~fm
        p_cap = 0.55 if r.campaign_id == "CMP014" else 0.45
        hit = cand & (rng.random(N) < p_cap)
        u.loc[hit, "attributed_campaign"] = r.campaign_id
    u.loc[fm, "attributed_campaign"] = "CMP006"
    # bonus hunters (event 1): among CMP014-attributed depositors
    att14 = (u.attributed_campaign.values == "CMP014") & dep
    hunter = att14 & (rng.random(N) < 0.52)
    print(f"[sim] funnel: kyc_sub {sub.sum():,} passed {passed.sum():,} dep {dep.sum():,} trade {trade.sum():,}",
          flush=True)

    # ---------- 4. first deposit amounts, retention and activity
    med = {"LATAM-BR": 110, "LATAM-AR": 90, "LATAM-MX": 120, "TR": 100, "SEA-VN": 80, "SEA-PH": 70,
           "CIS-KZ": 90, "MENA": 160, "EU": 220}
    dep_amt = np.round(np.exp(np.log([med[r] for r in u.region.values]) + rng.normal(0, 1.1, N)), 2)
    dep_amt = np.where(hunter, np.round(np.exp(np.log(1500) + rng.normal(0, 0.4, N)), 2), dep_amt)
    dep_amt = np.where(fm, 10.0, dep_amt)                              # identical minimal deposits
    month = pd.DatetimeIndex(reg_ts).month
    p_ret = np.array([RET[c] for c in u.channel.values]) + np.where(month == 10, RET_OCT_UPLIFT, 0)
    p_ret = p_ret / 0.9                                                 # measured D30 = 0.9 x retained share
    p_ret = np.where(hunter | fm, 0.0, p_ret)
    retained = dep & (rng.random(N) < p_ret)

    idx = np.where(trade)[0]
    t_day = day_index(trade_ts[idx])
    offs = np.arange(1, ND)
    rows_u, rows_d = [idx], [t_day]                                   # the first-trade day is active
    for chunk in np.array_split(np.arange(len(idx)), 20):
        ii, td = idx[chunk], t_day[chunk]
        ret = retained[ii][:, None]
        p = np.where(ret, Q_ACTIVE, 0.30 * np.exp(-offs[None, :] / 4.0))
        p = np.where(hunter[ii][:, None], np.where(offs[None, :] <= 14, 0.12, 0.0), p)
        act = rng.random((len(ii), len(offs))) < p
        dd = td[:, None] + offs[None, :]
        act &= dd < ND
        r_, c_ = np.nonzero(act)
        rows_u.append(ii[r_])
        rows_d.append(dd[r_, c_])
    au, ad = np.concatenate(rows_u), np.concatenate(rows_d)
    act = pd.DataFrame({"u": au, "d": ad}).drop_duplicates()
    print(f"[sim] active user-days (new users): {len(act):,}", flush=True)

    # ---------- 5. CRM base (existing accounts) and CRM experiments with randomised holdouts
    n_base = int(4_000_000 * scale)
    base_reg = rng.choice(len(REGIONS), size=n_base, p=BASE_REG / BASE_REG.sum())
    pre_active = rng.negative_binomial(0.6, 0.6 / (0.6 + 6), size=n_base).clip(0, 90)   # active days, last 90 d
    days_since = np.where(pre_active > 0, rng.integers(1, 90, n_base), rng.integers(90, 900, n_base))
    base = pd.DataFrame({"user_id": [f"U{i + 1:07d}" for i in range(n_base)], "region": np.array(REGIONS)[base_reg],
                         "account_age_days": rng.integers(120, 2500, n_base), "pre_active_days_90": pre_active,
                         "days_since_last_active": days_since})
    dormant = np.where(days_since >= 30)[0]
    crm_rows, exp_rows, crm_act = [], [], []
    used = np.zeros(n_base, bool)
    for r in camps[camps.has_holdout].itertuples():
        pool = dormant[~used[dormant]]
        tgt = rng.choice(pool, size=min(int(r.n_target * scale), len(pool)), replace=False)
        used[tgt] = True
        arm = np.where(rng.random(len(tgt)) < 0.10, "holdout", "treatment")
        send = r.start_ts_utc + pd.Timedelta(hours=9)
        # baseline 14-day reactivation depends on past activity (this is what CUPED exploits)
        p0 = 1 / (1 + np.exp(-(-3.3 + 0.12 * base.pre_active_days_90.values[tgt]
                               - 0.002 * base.days_since_last_active.values[tgt])))
        p1 = np.clip(p0 + np.where(arm == "treatment", r.true_lift, 0.0), 0, 1)
        react = rng.random(len(tgt)) < p1
        rday = int((send.normalize() - START).days) + rng.integers(0, 14, len(tgt))
        crm_rows.append(pd.DataFrame({"campaign_id": r.campaign_id, "user_id": base.user_id.values[tgt],
                                      "arm": arm, "assigned_at": send - pd.Timedelta(days=1)}))
        tr_ = arm == "treatment"
        exp_rows.append(pd.DataFrame({"campaign_id": r.campaign_id, "user_id": base.user_id.values[tgt][tr_],
                                      "exposed_ts": send, "message": "push+email",
                                      "delivered": rng.random(tr_.sum()) < 0.93}))
        ok = react & (rday < ND)
        crm_act.append(pd.DataFrame({"bu": tgt[ok], "d": rday[ok]}))
        truth_rows.append(dict(kind="campaign", key=r.campaign_id, metric="reactivation_14d_pts",
                               true_lift=r.true_lift, true_incremental=round(r.true_lift * tr_.sum()),
                               counterfactual=round(float(p0[tr_].sum()), 1)))
    holdouts = pd.concat(crm_rows, ignore_index=True)
    exposure_crm = pd.concat(exp_rows, ignore_index=True)
    crm_act = pd.concat(crm_act, ignore_index=True)
    print(f"[sim] CRM targeted: {len(holdouts):,}", flush=True)

    # ---------- 6. trades_daily (new users + reactivated base users); market factor + campaign lifts
    trade_lift = active_matrix(camps, "trades")
    dep_lift = active_matrix(camps, "deposits")
    # trade intensity follows the REAL BTC volume of the day: multiplier = (volume / mean volume) ** k.
    # k is calibrated so that the naive "3 competition days vs 7 days before" in the region is +45%
    eu = REGIONS.index("EU")
    eu_users = set(np.where(u.ri.values == eu)[0])
    a_new = act[act.u.isin(eu_users)].groupby("d").size().reindex(range(ND), fill_value=0).values
    a_crm = crm_act[base.region.values[crm_act.bu.values] == "EU"].groupby("d").size().reindex(
        range(ND), fill_value=0).values
    A = (a_new + a_crm).astype(float)
    pre, post = slice(comp_day - 7, comp_day), slice(comp_day, comp_day + 3)

    def naive_ratio(k):
        mt = v_btc ** k
        return (A[post] * mt[post]).mean() * 1.03 / (A[pre] * mt[pre]).mean()
    lo, hi = 0.0, 4.0
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if naive_ratio(mid) < 1.45 else (lo, mid)
    k_mkt = round((lo + hi) / 2, 4)
    m_trd = v_btc ** k_mkt
    print(f"[sim] market sensitivity k = {k_mkt} (expected naive ratio {naive_ratio(k_mkt):.3f})", flush=True)

    uid_new = u.user_id.values
    t_new = pd.DataFrame({"user_id": uid_new[act.u.values], "ri": u.ri.values[act.u.values], "d": act.d.values})
    t_crm = pd.DataFrame({"user_id": base.user_id.values[crm_act.bu.values],
                          "ri": base_reg[crm_act.bu.values], "d": crm_act.d.values})
    td = pd.concat([t_new, t_crm], ignore_index=True).drop_duplicates(["user_id", "d"])
    mu = 3.0 * m_trd[td.d.values] * trade_lift[td.ri.values, td.d.values]
    td["n_trades"] = rng.poisson(mu)
    size_med = 500 * np.exp(rng.normal(0, 0.5, len(td)))
    vol = td.n_trades.values * np.exp(np.log(size_med) + rng.normal(0, 1.2, len(td)))
    td["volume_usd"] = np.round(vol, 2)
    td["fee_usd"] = np.round(vol * FEE, 4)
    td["date"] = dates[td.d.values]
    td["region"] = np.array(REGIONS)[td.ri.values]
    trades_daily = td[["user_id", "date", "region", "n_trades", "volume_usd", "fee_usd"]]
    print(f"[sim] trades_daily rows: {len(trades_daily):,}", flush=True)

    # ---------- 7. deposits (first + repeat) and withdrawals
    di_ = np.where(dep)[0]
    first = pd.DataFrame({"user_id": uid_new[di_], "ts": dep_ts[di_], "amount_usd": dep_amt[di_],
                          "region": u.region.values[di_], "is_first": True})
    a_dep = act[act.u.isin(set(di_)) & ~hunter[act.u.values]]       # hunters never top up
    p_rep = 0.12 * np.clip(1 + 0.25 * (m[a_dep.d.values] - 1), 0.5, 2) * dep_lift[u.ri.values[a_dep.u.values],
                                                                                a_dep.d.values]
    rep = a_dep[rng.random(len(a_dep)) < p_rep]
    rep_amt = np.round(np.exp(np.log(dep_amt[rep.u.values] * 0.6 + 5) + rng.normal(0, 0.8, len(rep))), 2)
    repeat = pd.DataFrame({"user_id": uid_new[rep.u.values], "ts": ts_in_day(rep.d.values, prof),
                           "amount_usd": rep_amt, "region": u.region.values[rep.u.values], "is_first": False})
    deposits = pd.concat([first, repeat], ignore_index=True).sort_values("ts").reset_index(drop=True)
    deposits["asset"] = rng.choice(["USDT", "USDC", "BTC", "ETH", "fiat"], len(deposits),
                                   p=[0.55, 0.12, 0.10, 0.08, 0.15])
    deposits["currency"] = [CURRENCY.get(r, "USD") for r in deposits.region.values]
    dd_ = day_index(deposits.ts.values).clip(0, ND - 1)
    rate = np.ones(len(deposits))
    for cur, arr in fx.items():
        mk = deposits.currency.values == cur
        rate[mk] = arr[dd_[mk]]
    deposits["amount_local"] = np.round(deposits.amount_usd.values * rate, 2)
    deposits["event_id"] = [f"E{i + 1:09d}" for i in range(len(deposits))]
    deposits["deposit_id"] = [f"DEP{i + 1:09d}" for i in range(len(deposits))]
    deposits["ingested_at"] = deposits.ts + pd.to_timedelta(rng.exponential(300, len(deposits)), unit="s")
    # event 5a: pipeline replay of 27 Oct -> every row of the day again (+10% twice), same event_id
    day27 = deposits[deposits.ts.dt.normalize() == pd.Timestamp("2026-10-27")]
    dup1 = day27.assign(ingested_at=pd.Timestamp("2026-10-28 02:10:00"))
    dup2 = day27.sample(frac=0.10, random_state=42).assign(ingested_at=pd.Timestamp("2026-10-28 02:40:00"))
    deposits_raw = pd.concat([deposits, dup1, dup2], ignore_index=True)

    # withdrawals: hunters take >=90% out within 8 days after the bonus period; 8% of others do too
    wd = []
    hunt_idx = np.where(hunter)[0]
    bonus_end = dep_ts[hunt_idx] + np.timedelta64(14, "D")
    w_ts = bonus_end + (rng.uniform(0, 8, len(hunt_idx)) * 86_400 * 1e9).astype("timedelta64[ns]")
    wd.append(pd.DataFrame({"user_id": uid_new[hunt_idx], "ts": w_ts,
                            "amount_usd": np.round(dep_amt[hunt_idx] * rng.uniform(0.92, 1.0, len(hunt_idx)), 2)}))
    norm_idx = np.where(dep & ~hunter & ~fm)[0]
    full = norm_idx[rng.random(len(norm_idx)) < 0.08]
    w2 = dep_ts[full] + (rng.uniform(0.2, 8, len(full)) * 86_400 * 1e9).astype("timedelta64[ns]")
    wd.append(pd.DataFrame({"user_id": uid_new[full], "ts": w2,
                            "amount_usd": np.round(dep_amt[full] * rng.uniform(0.9, 1.0, len(full)), 2)}))
    part = a_dep[rng.random(len(a_dep)) < 0.04]
    wd.append(pd.DataFrame({"user_id": uid_new[part.u.values], "ts": ts_in_day(part.d.values, prof),
                            "amount_usd": np.round(dep_amt[part.u.values] * rng.uniform(0.2, 0.6, len(part)), 2)}))
    withdrawals = pd.concat(wd, ignore_index=True)
    withdrawals = withdrawals[withdrawals.ts <= END_TS].sort_values("ts").reset_index(drop=True)
    withdrawals["withdrawal_id"] = [f"WDR{i + 1:09d}" for i in range(len(withdrawals))]
    withdrawals = withdrawals.merge(u[["user_id", "region"]], on="user_id", how="left")
    withdrawals["currency"] = [CURRENCY.get(r, "USD") for r in withdrawals.region.values]

    # ---------- 8. funnel_events table (event_id + ingested_at)
    fe = []

    def add(mask, ts_arr, name):
        ii = np.where(mask)[0]
        fe.append(pd.DataFrame({"user_id": uid_new[ii], "event": name, "event_ts": ts_arr[ii]}))
    add(np.ones(N, bool), reg_ts, "register")
    add(sub, sub_ts, "kyc_submitted")
    add(retry, retry_ts, "kyc_submitted")
    add(passed, pass_ts, "kyc_passed")
    add(dep, dep_ts, "first_deposit")
    add(trade, trade_ts, "first_trade")
    funnel = pd.concat(fe, ignore_index=True).sort_values("event_ts").reset_index(drop=True)
    funnel["event_id"] = [f"F{i + 1:09d}" for i in range(len(funnel))]
    funnel["ingested_at"] = funnel.event_ts + pd.to_timedelta(rng.exponential(300, len(funnel)), unit="s")
    fd27 = funnel[(funnel.event == "first_deposit") & (funnel.event_ts.dt.normalize() == pd.Timestamp("2026-10-27"))]
    funnel = pd.concat([funnel, fd27.assign(ingested_at=pd.Timestamp("2026-10-28 02:10:00"))], ignore_index=True)

    # ---------- 9. touchpoints: converting paths + non-converting visitors (event 3: LATAM overlap)
    n_touch = rng.integers(1, 4, N)                                    # extra touches before the last one
    tp_u = np.repeat(np.arange(N), n_touch)
    other_p = np.array([0.30, 0.20, 0.20, 0.10, 0.05, 0.15])
    tp_ch = rng.choice(len(CHANNELS), size=len(tp_u), p=other_p)
    tp_ts = reg_ts[tp_u] - (rng.uniform(0.1, 7, len(tp_u)) * 86_400 * 1e9).astype("timedelta64[ns]")
    last = pd.DataFrame({"u": np.arange(N), "ci": u.ci.values, "ts": reg_ts - np.timedelta64(90, "s"),
                         "campaign_id": u.attributed_campaign.values})
    extra = pd.DataFrame({"u": tp_u, "ci": tp_ch, "ts": tp_ts, "campaign_id": ""})
    # LATAM: KOL and paid-social partners touch the same users (overlap -> double counting in their reports)
    lat = np.isin(u.ri.values, LATAM)
    ps, ak = CHANNELS.index("paid_social"), CHANNELS.index("affiliate_kol")
    has = {c: np.zeros(N, bool) for c in (ps, ak)}
    for c in (ps, ak):
        has[c][u.ci.values == c] = True
        has[c][tp_u[tp_ch == c]] = True
    only_one = lat & (has[ps] ^ has[ak])
    add_both = only_one & (rng.random(N) < 0.095)
    miss = np.where(add_both)[0]
    add_ch = np.where(has[ps][miss], ak, ps)
    extra = pd.concat([extra, pd.DataFrame({"u": miss, "ci": add_ch,
                                            "ts": reg_ts[miss] - (rng.uniform(0.2, 6, len(miss)) * 86_400 * 1e9
                                                                  ).astype("timedelta64[ns]"),
                                            "campaign_id": ""})], ignore_index=True)
    for c, mask in ((ak, add_both & has[ps]), (ps, add_both & has[ak])):
        has[c] = has[c] | mask                 # keep the truth flags in line with the added touches
    tp = pd.concat([last, extra], ignore_index=True)
    tp["visitor_id"] = ["V" + uid_new[i][1:] for i in tp.u.values]
    tp["user_id"] = uid_new[tp.u.values]
    tp["region"] = u.region.values[tp.u.values]
    # non-converting visitors (needed by the Markov model): 1.5 per sign-up, 1-3 touches
    nv = int(1.5 * N)
    v_n = rng.integers(1, 4, nv)
    v_id = np.repeat(np.arange(nv), v_n)
    v_reg = rng.choice(len(REGIONS), nv, p=BASE_REG / BASE_REG.sum())[v_id]
    v_ch = rng.choice(len(CHANNELS), len(v_id), p=np.array([0.18, 0.20, 0.26, 0.12, 0.08, 0.16]))
    v_day = rng.integers(0, ND, nv)[v_id]
    nonconv = pd.DataFrame({"ci": v_ch, "ts": ts_in_day(v_day, prof) - (rng.uniform(0, 3, len(v_id)) * 86_400 * 1e9
                                                                         ).astype("timedelta64[ns]"),
                            "campaign_id": "", "visitor_id": [f"V9{i:08d}" for i in v_id], "user_id": None,
                            "region": np.array(REGIONS)[v_reg]})
    tp = pd.concat([tp.drop(columns="u"), nonconv], ignore_index=True)
    tp["channel"] = np.array(CHANNELS)[tp.ci.values]
    tp = tp.drop(columns="ci").sort_values("ts").reset_index(drop=True)
    tp["touch_id"] = [f"T{i + 1:010d}" for i in range(len(tp))]
    tp = tp.rename(columns={"ts": "touch_ts"})
    print(f"[sim] touchpoints: {len(tp):,}", flush=True)

    # partner reports: each partner claims every sign-up it touched in the 7 days before (event 3)
    conv = tp[tp.user_id.notna() & tp.channel.isin(["paid_social", "affiliate_kol"])][["user_id", "channel"]]
    conv = conv.drop_duplicates().merge(u[["user_id", "region", "signup_ts"]], on="user_id")
    conv["week"] = (conv.signup_ts.dt.normalize() - pd.to_timedelta(conv.signup_ts.dt.dayofweek, unit="D"))
    partner_reports = conv.groupby(["channel", "region", "week"]).size().rename("claimed_signups").reset_index()

    # ---------- 10. referrals and devices
    ref_users = np.where((u.channel.values == "referral"))[0]
    genuine_ref = rng.choice(n_base, size=len(ref_users))
    ref_ids = base.user_id.values[genuine_ref].astype(object)
    farm_parent = np.array([f"U{3_000_001 + i:07d}" for i in range(n_ref)])   # 41 referrers (existing accounts)
    is_f = fm[ref_users]
    fr = rng.integers(0, n_ref, is_f.sum())
    ref_ids[is_f] = farm_parent[fr]
    qualified = dep[ref_users] & (dep_amt[ref_users] >= 10)
    referrals = pd.DataFrame({"referral_id": [f"R{i + 1:08d}" for i in range(len(ref_users))],
                              "referrer_id": ref_ids, "referee_id": uid_new[ref_users],
                              "referral_ts": reg_ts[ref_users], "qualified": qualified,
                              "reward_usd": np.where(qualified, 5.0, 0.0)})
    dev = rng.integers(0, int(N * 1.1), N)
    dev_ids = np.array([f"D{d:08d}" for d in dev])
    fdev = rng.integers(0, 90, fm.sum())                               # ~90 phones for 6,200 accounts
    dev_ids[fm] = np.array([f"D9{d:07d}" for d in fdev])
    devices = pd.DataFrame({"device_id": dev_ids, "user_id": uid_new, "first_seen_ts": reg_ts,
                            "os": rng.choice(["android", "ios", "web"], N, p=[0.55, 0.25, 0.20])})

    # ---------- 11. spend (activity date and booking date), campaigns' budgets, bonuses
    reg_cnt = u.groupby(["ri", "ci", "di"]).size()
    sp = []
    for (ri, ci, di), n in reg_cnt.items():
        ch = CHANNELS[ci]
        if ch in CPR:
            amt = n * CPR[ch] * (1.25 if REGIONS[ri] in ("EU", "MENA") else 1.0) * rng.lognormal(0, 0.08)
            sp.append((ch, REGIONS[ri], DAYS[di], "media" if ch != "affiliate_kol" else "partner_fee", amt, ""))
    # referral rewards (paid to the referrer when the referee qualifies)
    rw = referrals[referrals.qualified].assign(d=lambda x: x.referral_ts.dt.normalize())
    rw = rw.merge(u[["user_id", "region"]], left_on="referee_id", right_on="user_id")
    for (reg, d), n in rw.groupby(["region", "d"]).size().items():
        sp.append(("referral", reg, d, "referral_reward", 5.0 * n, ""))
    # campaign budgets: media on top of baseline, sized so that CAC differs across campaigns (CMP014 lowest)
    first_dep_att = pd.Series(u.attributed_campaign.values[dep]).value_counts()
    for r in camps.itertuples():
        if r.has_holdout:
            budget = 0.002 * r.n_target * scale * 3                     # 3 messages per targeted user
        else:
            target_cac = 9.0 if r.campaign_id == "CMP014" else float(rng.uniform(22, 70))
            budget = target_cac * max(int(first_dep_att.get(r.campaign_id, 0)), 50)
        d0 = int((r.start_ts_utc.normalize() - START).days)
        d1 = int((r.end_ts_utc.normalize() - START).days)
        regions = [r.region] if r.region != "ALL" else REGIONS
        for reg in regions:
            for di in range(d0, d1 + 1):
                sp.append((r.channel, reg, DAYS[di], "media", budget / (d1 - d0 + 1) / len(regions), r.campaign_id))
        camps.loc[camps.campaign_id == r.campaign_id, "budget_usd"] = round(budget, 2)
    # CMP014 boosted rate: promo cost = boosted APR paid on up to 3,000 USDT for 14 days (120% APR)
    p14 = np.where(att14)[0]
    bonus = np.minimum(dep_amt[p14], 3000) * 1.20 * 14 / 365
    bdf = pd.DataFrame({"d": pd.DatetimeIndex(dep_ts[p14]).normalize(), "b": bonus}).groupby("d")["b"].sum()
    for d, b in bdf.items():
        sp.append(("affiliate_kol", "LATAM-BR", d, "promo_bonus", b, "CMP014"))
    spend = pd.DataFrame(sp, columns=["channel", "region", "activity_date", "cost_type", "amount_usd", "campaign_id"])
    spend = spend[spend.activity_date <= END].reset_index(drop=True)
    # booking date: partner invoices are booked the Monday after the activity week; other costs same day
    wk = spend.activity_date - pd.to_timedelta(spend.activity_date.dt.dayofweek, unit="D")
    spend["booking_date"] = np.where(spend.cost_type == "partner_fee", wk + pd.Timedelta(days=7), spend.activity_date)
    spend["booking_date"] = pd.to_datetime(spend["booking_date"])

    # event 8: a share f of partner invoices for activity weeks 12 Oct and 19 Oct is booked on 2 Nov
    # with the invoice of week 26 Oct; f is calibrated so the booking-date CAC jumps +40% week over week
    nd_week = pd.Series(1, index=pd.DatetimeIndex(dep_ts[dep]).normalize()).groupby(level=0).sum()
    nd_week.index = nd_week.index - pd.to_timedelta(nd_week.index.dayofweek, unit="D")
    nd_week = nd_week.groupby(level=0).sum()
    acq = spend.cost_type.isin(["media", "partner_fee"]) & (spend.channel != "crm_lifecycle")
    held_rows = acq & (spend.cost_type == "partner_fee") & \
        spend.activity_date.between(pd.Timestamp("2026-10-12"), pd.Timestamp("2026-10-25"))

    def booked_ratio(f):
        s = spend[acq].copy()
        h = held_rows[acq].values
        s_h = s[h].assign(amount_usd=s[h].amount_usd * f, booking_date=pd.Timestamp("2026-11-02"))
        s.loc[h, "amount_usd"] *= (1 - f)
        s = pd.concat([s, s_h])
        b = s.groupby(s.booking_date - pd.to_timedelta(s.booking_date.dt.dayofweek, unit="D"))["amount_usd"].sum()
        cac = b / nd_week
        return cac[pd.Timestamp("2026-11-02")] / cac[pd.Timestamp("2026-10-26")]
    lo, hi = 0.0, 1.0
    for _ in range(50):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if booked_ratio(mid) < 1.40 else (lo, mid)
    f_held = (lo + hi) / 2
    ratio_held = booked_ratio(f_held)
    h = spend[held_rows].assign(amount_usd=spend[held_rows].amount_usd * f_held,
                                booking_date=pd.Timestamp("2026-11-02"))
    spend.loc[held_rows, "amount_usd"] *= (1 - f_held)
    spend = pd.concat([spend, h], ignore_index=True)
    spend["currency"] = [CURRENCY.get(r, "USD") for r in spend.region.values]
    rate = np.ones(len(spend))
    sdi = day_index(spend.activity_date.values).clip(0, ND - 1)
    for cur, arr in fx.items():
        mk = spend.currency.values == cur
        rate[mk] = arr[sdi[mk]]
    spend["amount_local"] = np.round(spend.amount_usd.values * rate, 2)
    spend["amount_usd"] = spend.amount_usd.round(2)
    spend["invoice_id"] = [f"INV{i + 1:07d}" for i in range(len(spend))]
    print(f"[sim] held invoice share f = {f_held:.3f}; booked CAC ratio {ratio_held:.3f}", flush=True)

    # ---------- 12. write everything
    users_out = u[["user_id", "signup_ts", "region", "channel"]].copy()
    users_out["device_id"] = dev_ids
    users_out["referrer_id"] = None
    users_out.loc[ref_users, "referrer_id"] = ref_ids
    users_out["first_touch_campaign"] = u.attributed_campaign.replace("", None)
    camp_out = camps.drop(columns=["true_lift", "n_target"]).copy()
    camp_out["name"] = [f"{r.region} {r.type.replace('_', ' ')} ({r.channel})" for r in camps.itertuples()]
    write_partitioned(users_out, "users", "signup_ts")
    write_partitioned(funnel, "funnel_events", "event_ts")
    write_partitioned(deposits_raw.drop(columns=["is_first"]).assign(is_first=deposits_raw.is_first),
                      "deposits", "ts")
    write_partitioned(withdrawals, "withdrawals", "ts")
    write_partitioned(trades_daily, "trades_daily", "date")
    write_partitioned(tp, "touchpoints", "touch_ts")
    write_single(spend, "spend_daily")
    write_single(camp_out, "campaigns")
    write_single(pd.concat([exposure_crm], ignore_index=True), "campaign_exposure")
    write_single(holdouts, "holdout_assignments")
    write_single(referrals, "referrals")
    write_single(devices, "devices")
    write_single(base, "crm_base")
    write_single(partner_reports, "partner_reports")

    # ---------- 13. hidden truth (never published; the analysis never reads it before the final check)
    lat_users = u[np.isin(u.ri.values, LATAM)]
    touched = has[ps] | has[ak]
    claims = (has[ps] & lat).sum() + (has[ak] & lat).sum()
    for k, v in [(ps, None)]:
        pass
    ref_week = (u.channel.values == "referral") & (u.di.values >= 21) & (u.di.values <= 27)
    truth_rows += [
        dict(kind="event", key="E1_brazil_bonus_hunters", metric="hunter_share_of_cmp014_depositors",
             true_lift=0.80, true_incremental=int(hunter.sum()), counterfactual=int(att14.sum())),
        dict(kind="event", key="E2_referral_farm", metric="farm_accounts_vs_genuine_referral_signups_week",
             true_lift=round(n_farm / (ref_week & ~fm).sum(), 4), true_incremental=n_farm,
             counterfactual=int((ref_week & ~fm).sum())),
        dict(kind="event", key="E3_latam_double_counting", metric="claims_over_touched_signups",
             true_lift=round(claims / (touched & lat).sum(), 4), true_incremental=int(claims),
             counterfactual=int((touched & lat).sum())),
        dict(kind="event", key="E4_tr_kyc_outage", metric="kyc_pass_rate_outage", true_lift=0.22,
             true_incremental=int(outage.sum()), counterfactual=0.78),
        dict(kind="event", key="E5a_duplicate_deposits", metric="duplicate_rows_2026-10-27",
             true_lift=round((len(day27) * 2.1) / len(day27), 3), true_incremental=len(dup1) + len(dup2),
             counterfactual=len(day27)),
        dict(kind="event", key="E5b_utc_vs_utc8_launch", metric="campaign", true_lift=0,
             true_incremental=0, counterfactual="CMP027"),
        dict(kind="event", key="E6_market_false_success", metric="true_trade_lift_CMP022", true_lift=0.03,
             true_incremental=comp_day, counterfactual=k_mkt),
        dict(kind="event", key="E7_simpson_retention", metric="channel_uplift_oct", true_lift=RET_OCT_UPLIFT,
             true_incremental=0, counterfactual=AFF_PUSH_OCT),
        dict(kind="event", key="E8_booking_vs_activity", metric="held_invoice_share", true_lift=round(f_held, 4),
             true_incremental=0, counterfactual="2026-11-02"),
    ]
    for r in camps[camps.objective.isin(["deposits", "trades"])].itertuples():
        truth_rows.append(dict(kind="campaign", key=r.campaign_id, metric=r.objective, true_lift=r.true_lift,
                               true_incremental=None, counterfactual=None))
    pd.DataFrame(truth_rows).to_csv(TRUTH, index=False)
    ut = pd.DataFrame({"user_id": uid_new, "inc_campaign": u.inc_campaign.values, "is_farm": fm,
                       "is_hunter": hunter, "retained": retained})
    (SIM / "_truth").mkdir(exist_ok=True)
    ut.to_parquet(SIM / "_truth" / "users_truth.parquet", index=False)
    n_rows = sum(len(x) for x in [users_out, funnel, deposits_raw, withdrawals, trades_daily, tp, spend, camp_out,
                                  exposure_crm, holdouts, referrals, devices, base, partner_reports])
    meta = {"seed": 42, "scale": scale, "signups": int(N), "rows_total": int(n_rows),
            "competition_day": str(DAYS[comp_day].date()), "market_k": k_mkt, "held_invoice_share": round(f_held, 4)}
    (SIM / "_meta.json").write_text(json.dumps(meta, indent=1))
    print("[sim] done", meta, flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", type=float, default=1.0)
    main(ap.parse_args().scale)
