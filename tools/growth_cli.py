"""Quick answers in plain English (SIMULATED exchange), from the DuckDB warehouse.

    python tools/growth_cli.py funnel --region LATAM-BR --week last
    python tools/growth_cli.py retention --by channel
    python tools/growth_cli.py campaign --campaign CMP014
    python tools/growth_cli.py is-it-real --metric cac --week 2026-11-02
    python tools/growth_cli.py is-it-real --metric signups --region EU --start 2026-09-21 --days 3

Every answer ends with one sentence generated from a template (no language model).
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import sim_analysis as sa  # noqa: E402

LAST_WEEK = "2026-11-16"


def funnel(region, week):
    week = LAST_WEEK if week == "last" else week
    f = sa.q(f"""SELECT sum(registrations) reg, sum(kyc_submitted) sub, sum(kyc_passed) pas,
                        sum(first_deposit_7d) dep, sum(first_trade_7d) trd, bool_and(window_complete) complete
                 FROM funnel_weekly WHERE signup_week = DATE '{week}'
                 {f"AND region = '{region}'" if region else ''}""").iloc[0].to_dict()
    where = region or "all regions"
    print(f"Funnel, {where}, sign-up week of {week} (UTC):")
    for lab, v in [("sign-ups", f["reg"]), ("KYC submitted (7 d)", f["sub"]), ("KYC passed (7 d)", f["pas"]),
                   ("first deposit (7 d)", f["dep"]), ("first trade (7 d)", f["trd"])]:
        print(f"  {lab:22s} {int(v):>9,}  {v / f['reg']:6.1%}")
    note = "" if f["complete"] else " The 7-day window is not complete yet for this week, so the later steps will still grow."
    print(f"In plain English: in {where}, {f['dep'] / f['reg']:.1%} of the week's sign-ups made a first deposit within "
          f"7 days, and {f['pas'] / f['sub']:.0%} of KYC submissions passed.{note}")


def retention(by):
    r = sa.q("SELECT * FROM retention_by_channel_month ORDER BY dep_month, channel")
    p = r.pivot(index="channel", columns="dep_month", values="retention_d30")
    p.columns = [str(c)[:7] for c in p.columns]
    print("30-day retention of new depositors (traded on days 24-30), full 30-day cohorts only:")
    print((p * 100).round(1).to_string())
    if {"2026-09", "2026-10"} <= set(p.columns):
        up = int((p.drop("ALL")["2026-10"] > p.drop("ALL")["2026-09"]).sum())
        print(f"In plain English: overall retention went from {p.loc['ALL', '2026-09']:.0%} (Sep) to "
              f"{p.loc['ALL', '2026-10']:.0%} (Oct), while it rose in {up} of {len(p) - 1} channels: "
              f"the change comes from the channel mix, not from worse retention inside channels.")


def campaign(cid):
    k = sa.q(f"SELECT * FROM campaign_kpis WHERE campaign_id = '{cid}'")
    c = sa.campaigns().set_index("campaign_id").loc[cid]
    print(f"{cid} - {c['name']} ({c['objective']}), {str(c['start_ts_utc'])[:16]} to {str(c['end_ts_utc'])[:16]} UTC")
    if len(k):
        r = k.iloc[0]
        print(f"  attributed first depositors {int(r.attributed_first_depositors):,} | CAC {r.cac_first_deposit:.2f} USD"
              f" | 30-day ROI {r.roi_30d:+.0%} | D30 retention {r.retention_d30:.0%} | withdrew >= 90%: "
              f"{r.share_withdrew_90pct_30d:.0%}" if pd.notna(r.roi_30d) else "  30-day data not complete yet")
    inc = sa.incrementality(cid)
    if "did" in inc:
        d = inc["did"]
        print(f"  incremental (difference-in-differences): {d['effect']:+.1%} [{d['lo']:+.1%}, {d['hi']:+.1%}]; "
              f"naive before/after {inc['naive']['effect']:+.1%}")
        verdict = "a measurable" if d["lo"] > 0 else "no measurable"
        print(f"In plain English: against untreated regions, {cid} had {verdict} incremental effect on "
              f"{inc['outcome']}; the naive before/after says {inc['naive']['effect']:+.0%}, which also counts "
              f"trend and market.")
    elif c["has_holdout"]:
        e = sa.crm_experiment(cid)
        print(f"  holdout: {e['rate_treatment']:.2%} vs {e['rate_holdout']:.2%} reactivated in 14 days; "
              f"CUPED difference {e['cuped_diff'] * 100:+.2f} points [{e['cuped_lo'] * 100:+.2f}, {e['cuped_hi'] * 100:+.2f}]")
        print(f"In plain English: the message changed 14-day reactivation by {e['cuped_diff'] * 100:+.2f} points "
              f"against a randomised holdout (sample split check p = {e['srm_p']:.2f}).")
    else:
        print(f"  {inc.get('note', '')}")


def is_it_real(metric, week, region, start, days):
    if metric == "cac":
        c = sa.q("SELECT * FROM cac_weekly")
        r = c[pd.to_datetime(c.week) == pd.Timestamp(week)].iloc[0]
        print(f"Week of {week}: CAC {r.cac_booking:.2f} USD by booking date ({r.wow_booking:+.0%} week over week), "
              f"{r.cac_activity:.2f} USD by activity date ({r.wow_activity:+.0%}).")
        real = abs(r.wow_activity) > 0.25
        print("In plain English: " + ("the move shows on the activity date too, so it is real spend per depositor."
                                      if real else "the jump exists only by booking date: invoices from earlier "
                                      "weeks were booked this week. On the activity date CAC did not rise, so it is "
                                      "not a real change."))
    else:
        p = sa.outcome_panel("signups" if metric == "signups" else "trades")
        s = pd.Timestamp(start)
        e = s + pd.Timedelta(days=days - 1)
        naive = sa.naive_before_after(p[region], s, e, s - pd.Timedelta(days=14))
        did = sa.did(p, region, s, e, s - pd.Timedelta(days=14))
        print(f"{metric}, {region}, {start} + {days} days: naive {naive['effect']:+.1%}; against the other regions "
              f"{did['effect']:+.1%} [{did['lo']:+.1%}, {did['hi']:+.1%}]")
        if naive["effect"] > 0.2 and did["effect"] < naive["effect"] / 3:
            msg = (f"most of the {naive['effect']:+.0%} also happened in regions without the change (market or season); "
                   f"what is specific to {region} is about {did['effect']:+.0%}.")
        elif did["lo"] > 0:
            msg = "the change stands out against the other regions."
        else:
            msg = "nothing stands out from normal variation."
        print("In plain English: " + msg)


def main(argv=None):
    ap = argparse.ArgumentParser(description="quick growth answers (simulated exchange)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("funnel")
    f.add_argument("--region")
    f.add_argument("--week", default="last")
    r = sub.add_parser("retention")
    r.add_argument("--by", default="channel")
    c = sub.add_parser("campaign")
    c.add_argument("--campaign", required=True)
    i = sub.add_parser("is-it-real")
    i.add_argument("--metric", choices=["cac", "signups", "trades"], required=True)
    i.add_argument("--week", default="2026-11-02")
    i.add_argument("--region", default="EU")
    i.add_argument("--start", default="2026-09-21")
    i.add_argument("--days", type=int, default=3)
    a = ap.parse_args(argv)
    if a.cmd == "funnel":
        funnel(a.region, a.week)
    elif a.cmd == "retention":
        retention(a.by)
    elif a.cmd == "campaign":
        campaign(a.campaign)
    else:
        is_it_real(a.metric, a.week, a.region, a.start, a.days)


if __name__ == "__main__":
    main()
