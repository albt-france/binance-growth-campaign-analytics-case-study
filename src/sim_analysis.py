"""Analysis of the SIMULATED exchange (used by the notebook, findings.py and the tools).

Every function reads the DuckDB warehouse built by src/run_sql.py. Nothing here reads the hidden truth,
except `truth()` which is ONLY called by the final verification step (methods vs truth, event check).

  incrementality(cid)      naive before/after, difference-in-differences, synthetic control, placebo in time
  crm_experiment(cid)      randomised holdout: SRM, difference with CI, CUPED, minimum detectable effect
  methods_vs_truth()       bias and interval coverage of each method against the planted effects
  events()                 the 8 planted events, recovered one by one from the data
  monitoring_backtest()    control charts + CUSUM on CAC, KYC pass rate, deposits, sign-ups
"""
from functools import lru_cache
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

import stats

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "warehouse.duckdb"
START, END = pd.Timestamp("2026-08-24"), pd.Timestamp("2026-11-22")


@lru_cache(maxsize=1)
def con():
    c = duckdb.connect(str(DB), read_only=True)
    c.sql("SET enable_progress_bar=false")
    c.sql(f"SET file_search_path='{ROOT.as_posix()}'")       # relative paths in views resolve from the repo root
    return c


def q(sql: str) -> pd.DataFrame:
    return con().sql(sql).df()


# ------------------------------------------------------------------ panels
@lru_cache(maxsize=1)
def campaigns() -> pd.DataFrame:
    return q("SELECT * FROM stg_campaigns ORDER BY campaign_id")


@lru_cache(maxsize=None)
def outcome_panel(kind: str, channel: str | None = None) -> pd.DataFrame:
    """region x day matrix of the outcome a campaign is meant to move.
    signups (optionally one channel), repeat deposits (not first ones), trades."""
    if kind == "signups":
        flt = f"AND channel = '{channel}'" if channel else ""
        df = q(f"SELECT region, signup_date_utc AS d, count(*) AS y FROM stg_users WHERE TRUE {flt} GROUP BY ALL")
    elif kind == "repeat_deposits":
        df = q("SELECT region, date_utc AS d, count(*) AS y FROM stg_deposits WHERE NOT is_first GROUP BY ALL")
    elif kind == "trades":
        df = q("SELECT region, date_utc AS d, sum(n_trades) AS y FROM stg_trades_daily GROUP BY ALL")
    else:
        raise ValueError(kind)
    p = df.pivot(index="d", columns="region", values="y").reindex(pd.date_range(START, END)).fillna(0)
    return p


def outcome_for(c) -> tuple[str, str | None]:
    """Which series measures the campaign's objective (documented in docs/incrementality_methods.md)."""
    if c["objective"] in ("registrations", "first_deposits"):
        return ("signups", None) if c["campaign_id"] == "CMP014" else ("signups", c["channel"])
    if c["objective"] == "deposits":
        return "repeat_deposits", None
    if c["objective"] == "trades":
        return "trades", None
    return None, None


def windows(c, pre_days=14):
    s = pd.Timestamp(c["start_ts_utc"]).normalize()
    e = min(pd.Timestamp(c["end_ts_utc"]).normalize(), END)
    return s - pd.Timedelta(days=pre_days), s, e


# ------------------------------------------------------------------ incrementality
def naive_before_after(y: pd.Series, s, e, pre_start):
    """Relative change of the daily mean, campaign days vs the 14 days before (Welch t on log values)."""
    pre = np.log1p(y[pre_start:s - pd.Timedelta(days=1)].values)
    post = np.log1p(y[s:e].values)
    d = post.mean() - pre.mean()
    se = np.sqrt(pre.var(ddof=1) / len(pre) + post.var(ddof=1) / len(post))
    t = stats.stats.t.ppf(0.975, min(len(pre), len(post)) - 1)
    return {"effect": np.expm1(d), "lo": np.expm1(d - t * se), "hi": np.expm1(d + t * se)}


def did(panel: pd.DataFrame, region: str, s, e, pre_start):
    """Two-way fixed effects on log(1 + y), all other regions as controls, errors clustered by region."""
    sub = panel[pre_start:e]
    long = sub.stack().rename("y").reset_index()
    long.columns = ["d", "region", "y"]
    long["ly"] = np.log1p(long["y"])
    long["treated_post"] = ((long.region == region) & (long.d >= s)).astype(float)
    r = stats.did_clustered(long, "ly", "region", "d", "treated_post")
    return {"effect": np.expm1(r["effect"]), "lo": np.expm1(r["lo"]), "hi": np.expm1(r["hi"]), "p": r["p"]}


def synthetic(panel: pd.DataFrame, region: str, s, e, pre_start):
    """Synthetic control on log(1 + y): donor weights fitted on the pre-period; effect = mean post gap.
    Placebo in space: the same estimate for every donor region (as if it were treated)."""
    lp = np.log1p(panel[pre_start:e])

    def est(treated):
        donors = [r for r in lp.columns if r != treated]
        pre, post = lp[:s - pd.Timedelta(days=1)], lp[s:]
        w = stats.synthetic_control(pre[treated].values, pre[donors].values)
        # demeaned version (intercept): match levels in the pre-period, then compare changes
        gap_pre = (pre[treated].values - pre[donors].values @ w).mean()
        gap_post = (post[treated].values - post[donors].values @ w).mean()
        return gap_post - gap_pre, dict(zip(donors, np.round(w, 3)))
    eff, w = est(region)
    plac = np.array([est(r)[0] for r in lp.columns if r != region])
    band = np.quantile(np.abs(plac), 0.9)
    p = (np.sum(np.abs(plac) >= abs(eff)) + 1) / (len(plac) + 1)
    return {"effect": np.expm1(eff), "lo": np.expm1(eff - band), "hi": np.expm1(eff + band), "p": p, "weights": w}


def incrementality(cid: str) -> dict:
    c = campaigns().set_index("campaign_id").loc[cid].to_dict()
    c["campaign_id"] = cid
    kind, ch = outcome_for(c)
    if kind is None:
        return {"campaign_id": cid, "note": "CRM campaign: measured with its randomised holdout"}
    panel = outcome_panel(kind, ch)
    pre_start, s, e = windows(c)
    out = {"campaign_id": cid, "outcome": kind + (f" ({ch})" if ch else ""), "region": c["region"],
           "start": s.date(), "end": e.date()}
    if pre_start < START:
        out["note"] = "pre-period shorter than 14 days"
    if c["region"] == "ALL":
        y = panel.sum(axis=1)
        out["naive"] = naive_before_after(y, s, e, pre_start)
        out["note"] = "runs in every region: no untreated control (DiD and synthetic control impossible)"
        return out
    y = panel[c["region"]]
    out["naive"] = naive_before_after(y, s, e, pre_start)
    out["did"] = did(panel, c["region"], s, e, pre_start)
    out["synthetic"] = synthetic(panel, c["region"], s, e, pre_start)
    # placebo in time: pretend the campaign started 14 days earlier (no effect expected)
    ps, pe = s - pd.Timedelta(days=14), s - pd.Timedelta(days=1)
    if ps - pd.Timedelta(days=14) >= START:
        out["placebo_time"] = did(panel, c["region"], ps, pe, ps - pd.Timedelta(days=14))
    return out


def crm_experiment(cid: str) -> dict:
    """Randomised holdout readout: SRM check, difference in reactivation (z-test CI), CUPED, MDE."""
    d = q(f"SELECT arm, reactivated_14d::INT AS y, pre_active_days_90 AS x FROM crm_experiment_users "
          f"WHERE campaign_id = '{cid}'")
    t, h = d[d.arm == "treatment"], d[d.arm == "holdout"]
    srm = stats.srm_test(len(t), len(h), expected_t=0.9)          # 90/10 split expected
    pt = stats.prop_test(t.y.sum(), len(t), h.y.sum(), len(h))
    cu = stats.cuped(d.y.values, d.x.values, (d.arm == "treatment").values)
    adj = cu["adjusted"]
    se_raw = np.sqrt(pt["rate_t"] * (1 - pt["rate_t"]) / len(t) + pt["rate_c"] * (1 - pt["rate_c"]) / len(h))
    mde = (1.96 + 0.84) * se_raw                                  # 80% power, two-sided 5%
    return {"campaign_id": cid, "n_treatment": len(t), "n_holdout": len(h), "srm_p": srm["p"],
            "rate_treatment": pt["rate_t"], "rate_holdout": pt["rate_c"], "diff": pt["diff"],
            "diff_lo": pt["ci_low"], "diff_hi": pt["ci_high"], "p": pt["p"],
            "cuped_diff": adj["diff"], "cuped_lo": adj["ci_low"], "cuped_hi": adj["ci_high"],
            "variance_reduction": cu["var_reduction"], "mde_pts": mde}


# ------------------------------------------------------------------ verification only
def truth() -> pd.DataFrame:
    """The hidden truth. ONLY used by the final verification (methods vs truth, events check)."""
    return pd.read_csv(ROOT / "data" / "_hidden_truth.csv")


def methods_vs_truth() -> tuple[pd.DataFrame, pd.DataFrame]:
    tr = truth()
    tr = tr[tr.kind == "campaign"].drop_duplicates("key").set_index("key")
    rows = []
    for cid in campaigns().campaign_id:
        r = incrementality(cid)
        if "naive" not in r:
            continue
        true = float(tr.loc[cid, "true_lift"])
        for m in ("naive", "did", "synthetic"):
            if m in r:
                e = r[m]
                rows.append({"campaign_id": cid, "method": m, "true_lift": true, "estimate": e["effect"],
                             "lo": e["lo"], "hi": e["hi"], "error": e["effect"] - true,
                             "covered": e["lo"] <= true <= e["hi"]})
    for cid in campaigns().query("has_holdout").campaign_id:
        r = crm_experiment(cid)
        true = float(tr.loc[cid, "true_lift"])
        lo, hi = r["cuped_lo"], r["cuped_hi"]
        rows.append({"campaign_id": cid, "method": "randomised_holdout", "true_lift": true,
                     "estimate": r["cuped_diff"], "lo": lo, "hi": hi, "error": r["cuped_diff"] - true,
                     "covered": lo <= true <= hi})
    det = pd.DataFrame(rows)
    summ = det.groupby("method").agg(campaigns=("campaign_id", "count"),
                                     mean_abs_error=("error", lambda x: np.mean(np.abs(x))),
                                     mean_error=("error", "mean"), coverage=("covered", "mean")).reset_index()
    return det, summ


# ------------------------------------------------------------------ the 8 events, from the data
def events() -> dict:
    ev = {}
    k = q("SELECT * FROM campaign_kpis")
    k14 = k[k.campaign_id == "CMP014"].iloc[0]
    br = outcome_panel("signups")["LATAM-BR"]
    c14 = campaigns().set_index("campaign_id").loc["CMP014"]
    pre_start, s, e = windows(c14.to_dict() | {"campaign_id": "CMP014"})
    ev["E1"] = {"cac": float(k14.cac_first_deposit), "cac_rank": int((k.cac_first_deposit < k14.cac_first_deposit).sum()) + 1,
                "roi_30d": float(k14.roi_30d), "withdrew_90pct": float(k14.share_withdrew_90pct_30d),
                "retention_d30": float(k14.retention_d30),
                "signup_lift_naive": float(br[s:e].mean() / br[pre_start:s - pd.Timedelta(days=1)].mean() - 1),
                "median_roi_others": float(k[k.campaign_id != "CMP014"].roi_30d.median()), "n_kpi_campaigns": int(len(k))}
    # E2 referral farm: indicators
    ab = q("SELECT * FROM referral_abuse_indicators")
    flagged = ab[ab["flags"] >= 3]
    wk = q("""SELECT count(*) AS referral_signups FROM stg_users
              WHERE channel = 'referral' AND signup_week = DATE '2026-09-14'""").iloc[0, 0]
    flagged_ids = "','".join(flagged.referrer_id)
    farm_w = q(f"""SELECT count(*) FROM stg_users WHERE referrer_id IN ('{flagged_ids}')
                   AND signup_week = DATE '2026-09-14'""").iloc[0, 0] if len(flagged) else 0
    ev["E2"] = {"flagged_referrers": int(len(flagged)), "flagged_referees": int(flagged.referees.sum()),
                "referral_signups_week": int(wk), "flagged_in_week": int(farm_w),
                "inflation": float(farm_w / (wk - farm_w)) if wk > farm_w else None,
                "median_flags_others": float(ab[ab["flags"] < 3]["flags"].median()) if (ab["flags"] < 3).any() else None}
    pc = q("SELECT * FROM partner_claims").set_index("region_group")
    ev["E3"] = {"latam_claimed_over_real": float(pc.loc["LATAM", "claimed_over_real"]),
                "other_claimed_over_real": float(pc.loc["other", "claimed_over_real"])}
    kyc = q("SELECT * FROM kyc_daily_region WHERE region = 'TR'")
    kyc["date_utc"] = pd.to_datetime(kyc.date_utc)
    out = kyc[kyc.date_utc.between("2026-10-06", "2026-10-08")]
    base = kyc[kyc.date_utc < "2026-10-06"]
    ev["E4"] = {"pass_rate_outage": float(out.passed.sum() / out.submissions.sum()),
                "pass_rate_before": float(base.passed.sum() / base.submissions.sum())}
    k17 = k[k.campaign_id == "CMP017"]
    if len(k17):
        ev["E4"]["cmp017_first_depositors"] = int(k17.iloc[0].attributed_first_depositors)
    dup = q("""SELECT count(*) AS raw, count(DISTINCT event_id) AS clean
               FROM read_parquet('data/sim/deposits/*/*.parquet', hive_partitioning = true)
               WHERE CAST(ts AS DATE) = DATE '2026-10-27'""").iloc[0]
    d1 = q("SELECT * FROM campaign_day1_utc_vs_hkt WHERE launch_hour_utc >= 16").iloc[0]
    ev["E5"] = {"raw_rows_27oct": int(dup.raw), "clean_rows_27oct": int(dup.clean),
                "ratio": float(dup.raw / dup.clean), "late_launch_campaign": d1.campaign_id,
                "launch_ts_utc": str(d1.start_ts_utc), "day1_deposits_utc": int(d1.day1_deposits_utc),
                "day1_deposits_hkt": int(d1.day1_deposits_hkt)}
    r22 = incrementality("CMP022")
    ev["E6"] = {"naive": r22["naive"]["effect"], "did": r22["did"]["effect"], "did_lo": r22["did"]["lo"],
                "did_hi": r22["did"]["hi"], "start": str(r22["start"])}
    # naive definition used by the handoff: 3 competition days vs the 7 days before, EU trades
    tr_eu = outcome_panel("trades")["EU"]
    s22 = pd.Timestamp(r22["start"])
    ev["E6"]["naive_3d_vs_7d"] = float(tr_eu[s22:s22 + pd.Timedelta(days=2)].mean()
                                       / tr_eu[s22 - pd.Timedelta(days=7):s22 - pd.Timedelta(days=1)].mean() - 1)
    rb = q("SELECT * FROM retention_by_channel_month WHERE dep_month IN ('2026-09-01', '2026-10-01')")
    piv = rb.pivot(index="channel", columns="dep_month", values="retention_d30")
    piv.columns = ["sep", "oct"]
    w = rb[rb.channel != "ALL"].pivot(index="channel", columns="dep_month", values="depositors_full_30d")
    w.columns = ["sep", "oct"]
    std = stats.direct_standardization(
        rb[rb.channel != "ALL"].rename(columns={"retention_d30": "rate", "depositors_full_30d": "n"}),
        "channel", "dep_month", "rate", "n")
    ev["E7"] = {"overall_sep": float(piv.loc["ALL", "sep"]), "overall_oct": float(piv.loc["ALL", "oct"]),
                "channels_up": int((piv.drop("ALL").oct > piv.drop("ALL").sep).sum()),
                "channels": int(len(piv) - 1),
                "affiliate_share_sep": float(w.loc["affiliate_kol", "sep"] / w.sep.sum()),
                "affiliate_share_oct": float(w.loc["affiliate_kol", "oct"] / w.oct.sum()),
                "standardised_sep": float(std.standardised.iloc[0]), "standardised_oct": float(std.standardised.iloc[1])}
    cw = q("SELECT * FROM cac_weekly")
    r = cw[cw.week.astype(str) == "2026-11-02"].iloc[0]
    ev["E8"] = {"wow_booking": float(r.wow_booking), "wow_activity": float(r.wow_activity),
                "cac_booking": float(r.cac_booking), "cac_activity": float(r.cac_activity)}
    return ev


# ------------------------------------------------------------------ monitoring
def monitoring_backtest(baseline_days=28) -> pd.DataFrame:
    """Alert rules run over the 13 weeks, as an operations team would run them every morning:
      1. weekly CAC (booking date = finance view, activity date = growth view): week over week > +25%
      2. KYC pass rate, region x day (complete days only): below the 3-sigma limit of the first 28 days
      3. raw deposit rows per day (before deduplication): above 1.5 x the median of the 7 previous days
      4. sign-ups, region x day: above 1.5 x the median of the 28 previous days on 3 days in a row
         (then 7 quiet days before the same series can alert again)
    Rolling baselines are used because a growing business makes fixed limits fire every day."""
    alerts = []
    cw = q("SELECT * FROM cac_weekly ORDER BY week")
    for r in cw.itertuples():
        if pd.notna(r.wow_booking) and r.wow_booking > 0.25:
            alerts.append(("cac_booking_weekly", str(r.week)[:10], f"WoW {r.wow_booking:+.0%}"))
        if pd.notna(r.wow_activity) and r.wow_activity > 0.25:
            alerts.append(("cac_activity_weekly", str(r.week)[:10], f"WoW {r.wow_activity:+.0%}"))
    kyc = q("SELECT * FROM kyc_daily_region WHERE date_utc < DATE '2026-11-22' ORDER BY date_utc")
    for reg, g in kyc.groupby("region"):
        g = g[pd.to_datetime(g.date_utc) >= START]
        mu, lo, hi = stats.control_limits(g.pass_rate.values, baseline_days)
        for r in g.itertuples():
            if r.pass_rate < lo:
                alerts.append((f"kyc_pass_rate_{reg}", str(r.date_utc)[:10], f"{r.pass_rate:.0%} < {lo:.0%}"))
    dep = q("""SELECT CAST(ts AS DATE) AS d, count(*) AS n FROM read_parquet('data/sim/deposits/*/*.parquet',
               hive_partitioning = true) GROUP BY 1 ORDER BY 1""")
    dep = dep[pd.to_datetime(dep.d) >= START].reset_index(drop=True)
    med7 = dep.n.shift(1).rolling(7).median()
    for r, m in zip(dep.itertuples(), med7):
        if pd.notna(m) and r.n > 1.5 * m:
            alerts.append(("deposits_raw_daily", str(r.d)[:10], f"{r.n:,} > 1.5 x {m:,.0f}"))
    p = outcome_panel("signups")
    for reg in p.columns:
        y = p[reg]
        med = y.shift(1).rolling(28).median()
        hot = (y > 1.5 * med).astype(int)
        run = hot.groupby((hot != hot.shift()).cumsum()).cumsum()
        quiet_until = None
        for d, k in run.items():
            if k == 3 and (quiet_until is None or d > quiet_until):
                alerts.append((f"signups_{reg}", str(d.date()), f"3 days > 1.5 x 28-day median"))
                quiet_until = d + pd.Timedelta(days=7)
    return pd.DataFrame(alerts, columns=["series", "date", "detail"])


KNOWN = [  # planted anomalies these series should catch; used ONLY to score the backtest (verification step)
    ("kyc_pass_rate_TR", "2026-10-06", "2026-10-08", "KYC vendor outage (TR)"),
    ("deposits_raw_daily", "2026-10-27", "2026-10-27", "pipeline replay of 27 Oct"),
    ("signups_LATAM-BR", "2026-10-05", "2026-10-31", "CMP014 boosted-rate campaign"),
    ("signups_SEA-VN", "2026-09-14", "2026-09-27", "referral farm (week of 14 Sep)"),
    ("cac_booking_weekly", "2026-11-02", "2026-11-02", "invoices booked late (false signal to dismiss)"),
]


def score_backtest(alerts: pd.DataFrame) -> pd.DataFrame:
    """Label every alert with written rules:
    - an alert on a planted anomaly's series and dates: true alert (or 'explained false alert' for the late invoices);
    - a CAC alert that also shows on the ACTIVITY date: true alert (real spend per depositor changed);
    - anything else: false alert.  Planted anomalies with no alert: missed."""
    cw = q("SELECT week, wow_activity FROM cac_weekly")
    act = {str(w)[:10]: x for w, x in zip(cw.week, cw.wow_activity)}
    rows = []
    for a in alerts.itertuples():
        lab = "false alert"
        for s_, d0, d1, why in KNOWN:
            if a.series == s_ and d0 <= a.date <= d1:
                lab = "explained false alert" if "false signal" in why else "true alert"
        if lab == "false alert" and a.series.startswith("cac_") and (act.get(a.date) or 0) > 0.25:
            lab = "true alert"
        rows.append(lab)
    out = alerts.assign(label=rows)
    out.attrs["missed"] = [why for s_, d0, d1, why in KNOWN
                           if not ((out.series == s_) & (out.date >= d0) & (out.date <= d1)).any()]
    return out
