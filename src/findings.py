"""Compute EVERY number used in the report, the README, the dashboard and the readouts, and write
data/processed/findings.json (plus the tables the dashboard, the workbook and Power BI read).

Rule: no figure is typed by hand in a deliverable; build_pdf.py, build_dashboard.py, build_readme.py and the
tools read this file. Inputs: the DuckDB warehouse (src/run_sql.py), data/processed, the raw caches for
public facts. No network access. The hidden truth is read only in the "verification" block at the end.

    python src/findings.py
"""
import datetime as dt
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

import onchain_metrics as om
import sim_analysis as sa
import stats

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
RAW = ROOT / "data" / "raw"


def clean(x):
    """JSON-friendly: numpy -> python, NaN -> None, floats rounded to 6 digits."""
    if isinstance(x, dict):
        return {str(k): clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [clean(v) for v in x]
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating, float)):
        return None if math.isnan(float(x)) else round(float(x), 6)
    if isinstance(x, (np.bool_,)):
        return bool(x)
    if isinstance(x, (pd.Timestamp, dt.date)):
        return str(x)[:19]
    return x


# ------------------------------------------------------------------ public facts (as stated by Binance)
def facts():
    job = json.loads((RAW / "job" / "facts.json").read_text())
    ex = json.loads((RAW / "exchangeinfo" / "summary.json").read_text())
    nc = pd.read_csv(RAW / "por" / "network_counts.csv")
    nov = nc[nc.snapshot == 20261111]
    return {
        "job": job, "exchange_info": ex,
        "por_audit": {"audit_date_utc": "2026-11-12 00:00", "method": "zk-SNARKs",
                      "ratios": {"BTC": 1.0005, "ETH": 1.0002, "USDT": 1.0434, "USDC": 1.0007},
                      "source": "https://www.binance.com/en/proof-of-reserves", "read_on": "2026-11-23"},
        "company_claims": {"text": "world's largest cryptocurrency exchange by trading volume and registered users; "
                                   "trusted by 300+ million people in 100+ countries",
                           "source": "Binance job post JR100294 (Greenhouse)", "read_on": "2026-11-23"},
        "por_nov_files": {"deposit_rows": int(nov[nov.file == "deposit"].n.sum()),
                          "deposit_rows_eth": int(nov[(nov.file == "deposit") & (nov.network == "ETH")].n.sum()),
                          "deposit_rows_tron": int(nov[(nov.file == "deposit") & (nov.network == "TRX")].n.sum()),
                          "hotcold_rows": int(nov[nov.file == "hotcold"].n.sum())},
        "collected_on": "2026-11-23",
    }


# ------------------------------------------------------------------ simulated part
def sim_part():
    out = {}
    q = sa.q
    meta = json.loads((ROOT / "data" / "sim" / "_meta.json").read_text())
    out["meta"] = {k: meta[k] for k in ("seed", "signups", "rows_total", "competition_day")}
    f = q("SELECT * FROM funnel_by_region_channel")
    tot = f[["registrations", "kyc_submitted", "kyc_passed", "first_deposit_7d", "first_trade_7d"]].sum()
    out["funnel"] = {k: int(v) for k, v in tot.items()}
    out["funnel"]["reg_to_deposit_7d"] = float(tot.first_deposit_7d / tot.registrations)
    out["funnel"]["kyc_pass_of_submitted"] = float(tot.kyc_passed / tot.kyc_submitted)
    by_ch = f.groupby("channel")[["registrations", "first_deposit_7d"]].sum()
    out["funnel"]["reg_to_deposit_by_channel"] = (by_ch.first_deposit_7d / by_ch.registrations).round(4).to_dict()
    # Kaplan-Meier: days from KYC approval to first deposit
    t = q("SELECT channel, days, observed FROM time_to_first_deposit")
    km = stats.kaplan_meier(t.days.values, t.observed.values)
    out["km_median_days"] = float(km.loc[km.survival <= 0.5, "t"].iloc[0]) if (km.survival <= 0.5).any() else None
    out["km_share_deposit_by_7d"] = float(1 - km.loc[km.t <= 7, "survival"].iloc[-1])
    km_rows = []
    for ch, g in t.groupby("channel"):
        k = stats.kaplan_meier(g.days.values, g.observed.values)
        grid = np.arange(0, 31)
        s = np.interp(grid, k.t.values, k.survival.values, left=1.0)
        km_rows += [{"channel": ch, "day": int(d), "share_deposited": float(1 - v)} for d, v in zip(grid, s)]
    pd.DataFrame(km_rows).to_csv(PROC / "km_first_deposit.csv", index=False)
    # campaigns: reported KPIs + incrementality + status
    k = q("SELECT * FROM campaign_kpis")
    inc_rows = []
    for cid in sa.campaigns().campaign_id:
        r = sa.incrementality(cid)
        row = {"campaign_id": cid}
        for m in ("naive", "did", "synthetic"):
            if m in r:
                row[f"{m}_lift"], row[f"{m}_lo"], row[f"{m}_hi"] = r[m]["effect"], r[m]["lo"], r[m]["hi"]
        row["placebo_time_lift"] = r.get("placebo_time", {}).get("effect")
        row["inc_note"] = r.get("note", "")
        row["outcome"] = r.get("outcome", "reactivation (holdout)")
        inc_rows.append(row)
    inc = pd.DataFrame(inc_rows)
    camp = sa.campaigns()[["campaign_id", "name", "type", "region", "channel", "objective", "start_ts_utc",
                           "end_ts_utc", "budget_usd", "has_holdout"]]
    sc = camp.merge(k.drop(columns=["name", "type", "region", "channel", "objective"]), on="campaign_id", how="left")
    sc = sc.merge(inc, on="campaign_id", how="left")
    crm = {cid: sa.crm_experiment(cid) for cid in camp[camp.has_holdout].campaign_id}
    abuse = q("SELECT * FROM referral_abuse_indicators")
    farm_share = {}
    if len(abuse):
        flagged = "','".join(abuse[abuse["flags"] >= 3].referrer_id)
        fs = q(f"""SELECT attributed_campaign AS campaign_id, avg((referrer_id IN ('{flagged}'))::INT) AS s
                   FROM stg_users WHERE attributed_campaign IS NOT NULL GROUP BY 1""")
        farm_share = dict(zip(fs.campaign_id, fs.s))

    def status(r):
        if r.has_holdout:
            e = crm[r.campaign_id]
            return "scale" if e["cuped_lo"] > 0 else "stop (no measurable effect)"
        if farm_share.get(r.campaign_id, 0) > 0.05:
            return "pause (abuse flags)"
        if r.region == "ALL":
            return "not measurable (no untreated region)"
        if r.objective in ("deposits", "trades"):            # no attributed users: judged on the region outcome
            if pd.notna(r.get("did_lo")) and r.did_lo > 0:
                return "scale" if r.did_lift >= 0.10 else "keep (small effect: check cost)"
            return "stop (no incremental effect)"
        if pd.isna(r.get("roi_30d")):
            return "too early (no 30-day data)"
        lift = r.get("did_lift") if pd.notna(r.get("did_lift")) else None
        if lift is not None and pd.notna(r.get("did_lo")) and r.did_lo <= 0:
            return "stop (no incremental effect)"
        if r.get("share_withdrew_90pct_30d", 0) > 0.30:
            return "stop (guardrail: withdrawals)"
        return "scale" if r.roi_30d > 0 else "fix (ROI < 0)"
    sc["status"] = sc.apply(status, axis=1)
    sc["farm_share"] = sc.campaign_id.map(farm_share).fillna(0)
    sc.to_csv(PROC / "campaign_scorecard.csv", index=False)
    out["scorecard_status"] = sc.status.value_counts().to_dict()
    out["campaigns"] = int(len(sc))
    out["campaigns_attributed_roi_positive"] = int((sc.roi_30d > 0).sum())
    out["campaigns_with_roi"] = int(sc.roi_30d.notna().sum())
    out["crm"] = {cid: {kk: vv for kk, vv in e.items()} for cid, e in crm.items()}
    out["events"] = sa.events()
    # attribution: Markov on LATAM paths vs last touch
    pcnt = q("SELECT * FROM path_counts WHERE region_group = 'LATAM' ORDER BY path")   # fixed order: reproducible bootstrap
    base, eff, share, boot = stats.markov_with_bootstrap(pcnt.rename(columns={"path": "path"}), n_boot=200)
    att = q("SELECT * FROM attribution_rules WHERE region_group = 'LATAM'").set_index("channel")
    lt = att.last_touch / att.last_touch.sum()
    out["attribution_latam"] = {"markov_share": share.round(4).to_dict(),
                                "markov_lo": boot.quantile(0.025).round(4).to_dict(),
                                "markov_hi": boot.quantile(0.975).round(4).to_dict(),
                                "last_touch_share": lt.round(4).to_dict(),
                                "first_touch_share": (att.first_touch / att.first_touch.sum()).round(4).to_dict()}
    pd.DataFrame({"markov": share, "last_touch": lt, "first_touch": att.first_touch / att.first_touch.sum(),
                  "position_based": att.position_based / att.position_based.sum()}).to_csv(
        PROC / "attribution_latam_shares.csv")
    cw = q("SELECT * FROM cac_weekly")
    out["cac_weekly"] = {"mean_activity": float(cw.cac_activity.mean()), "mean_booking": float(cw.cac_booking.mean())}
    al = sa.monitoring_backtest()
    out["monitoring_alerts"] = int(len(al))
    al.to_csv(PROC / "monitoring_alerts.csv", index=False)
    return out, sc


# ------------------------------------------------------------------ verification against the hidden truth
def verification(sc):
    det, summ = sa.methods_vs_truth()
    det.to_csv(PROC / "methods_vs_truth_detail.csv", index=False)
    summ.to_csv(PROC / "methods_vs_truth.csv", index=False)
    al = sa.score_backtest(pd.read_csv(PROC / "monitoring_alerts.csv"))
    al.to_csv(PROC / "monitoring_backtest.csv", index=False)
    tr = sa.truth()
    ev = tr[tr.kind == "event"].set_index("key")
    return {"methods": summ.set_index("method").to_dict(orient="index"),
            "backtest": {"true": int((al.label == "true alert").sum()),
                         "false": int((al.label == "false alert").sum()),
                         "explained_false": int((al.label == "explained false alert").sum()),
                         "missed": al.attrs["missed"]},
            "truth_events": {"E1_hunters": int(ev.loc["E1_brazil_bonus_hunters", "true_incremental"]),
                             "E2_farm_accounts": int(ev.loc["E2_referral_farm", "true_incremental"]),
                             "E2_inflation_true": float(ev.loc["E2_referral_farm", "true_lift"]),
                             "E3_claims_ratio_true": float(ev.loc["E3_latam_double_counting", "true_lift"]),
                             "E6_true_lift": float(ev.loc["E6_market_false_success", "true_lift"]),
                             "E7_channel_uplift": float(ev.loc["E7_simpson_retention", "true_lift"])},
            "cmp014_true_lift": float(tr[(tr.key == "CMP014")].true_lift.iloc[0]),
            "cmp031_true_lift": float(tr[(tr.key == "CMP031")].true_lift.iloc[0])}


def main():
    t0 = dt.datetime.now()
    out = {"generated": "from data/processed and the DuckDB warehouse; no hand-typed figure",
           "facts": facts()}
    out["real"] = om.run_all()
    out["sim"], sc = sim_part()
    out["verification"] = verification(sc)
    pipe = ROOT / "data" / "processed" / "pipeline_runs.csv"
    if pipe.exists():
        p = pd.read_csv(pipe)
        out["pipeline"] = {"runs": int(len(p)), "last_seconds": float(p.seconds.iloc[-1]),
                           "median_seconds": float(p.seconds.median())}
    (PROC / "findings.json").write_text(json.dumps(clean(out), indent=1), encoding="utf-8")
    print(f"[findings] written in {(dt.datetime.now() - t0).seconds}s")


if __name__ == "__main__":
    main()
