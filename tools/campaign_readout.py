"""One-page campaign readout (SIMULATED exchange): HTML, printed to PDF with headless Edge.

    python tools/campaign_readout.py --campaign CMP014
    python tools/campaign_readout.py --all-examples        # the 5 readouts of reports/readouts/

Sections: objective · key numbers with intervals · incremental vs control/holdout · guardrails ·
3 recommendations · "for operations" box · 3 lines "for executives". Text is generated from rules (templates).
"""
import argparse
import html
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import report_kit as rk  # noqa: E402
import sim_analysis as sa  # noqa: E402

OUT = ROOT / "reports" / "readouts"
EXAMPLES = ["CMP014", "CMP006", "CMP022", "CMP031", "CMP017"]

HOW_I_APPROACHED_CMP014 = [
    "Started from the decision: 'relaunch?' means 'did it create customers worth more than they cost?', not 'was the CAC low?'.",
    "Checked the counting first: deduplicated events, UTC vs UTC+8 day, complete 30-day windows only.",
    "Read the reported numbers (attributed first depositors, CAC) and then the cost the CAC leaves out: promo bonuses.",
    "Looked at the crowd: 30-day retention and the share of depositors who withdrew >= 90% within 30 days.",
    "Measured the incremental sign-ups against untreated regions (difference-in-differences, synthetic control) and "
    "set them against the October partner push and the market.",
    "Wrote the decision with its condition: what would have to change for a relaunch to pay back.",
]


def fmt_pct(x, signed=True):
    return "n/a" if x is None or pd.isna(x) else (f"{x:+.1%}" if signed else f"{x:.1%}")


def build(cid: str) -> Path:
    c = sa.campaigns().set_index("campaign_id").loc[cid]
    k = sa.q(f"SELECT * FROM campaign_kpis WHERE campaign_id = '{cid}'")
    k = k.iloc[0] if len(k) else None
    s0, s1 = str(c.start_ts_utc)[:16], str(c.end_ts_utc)[:16]
    hk = (pd.Timestamp(c.start_ts_utc) + pd.Timedelta(hours=8)).strftime("%Y-%m-%d %H:%M")
    tiles, rows, recos, ops, execs = [], [], [], [], []
    kyc = sa.q(f"""SELECT min(date_utc) d0, max(date_utc) d1, round(avg(pass_rate), 3) pr FROM kyc_daily_region
                   WHERE region = '{c.region}' AND pass_rate < 0.5 AND submissions >= 200
                   AND date_utc BETWEEN CAST('{s0}' AS DATE) AND CAST('{s1}' AS DATE)""").iloc[0]
    if c.has_holdout:
        e = sa.crm_experiment(cid)
        tiles = [("Targeted users", f"{e['n_treatment'] + e['n_holdout']:,}", f"holdout {e['n_holdout']:,} (10%)"),
                 ("14-day reactivation", f"{e['rate_treatment']:.2%}", f"holdout {e['rate_holdout']:.2%}"),
                 ("Incremental (CUPED)", f"{e['cuped_diff'] * 100:+.2f} pts",
                  f"95% CI {e['cuped_lo'] * 100:+.2f} to {e['cuped_hi'] * 100:+.2f}"),
                 ("Smallest detectable", f"{e['mde_pts'] * 100:.2f} pts", f"split check p = {e['srm_p']:.2f}")]
        real = e["cuped_lo"] > 0
        rows = [("Sample split (SRM, expected 90/10)", f"p = {e['srm_p']:.2f}", "OK" if e["srm_p"] > 0.01 else "BROKEN"),
                ("Raw difference", f"{e['diff'] * 100:+.2f} pts [{e['diff_lo'] * 100:+.2f}, {e['diff_hi'] * 100:+.2f}]", ""),
                ("CUPED variance reduction", f"{e['variance_reduction']:.0%}", "same estimate, narrower interval")]
        recos = ([f"Scale: send to the remaining dormant users, keeping a 10% holdout to keep measuring.",
                  "Test the message (timing, offer) as an A/B inside the treated group; keep the holdout fixed.",
                  "Report reactivation as incremental users per 1,000 messages, the number finance can budget."]
                 if real else
                 ["Stop sending this message as is: no reactivation effect is measurable against the holdout.",
                  f"Before re-testing, size the test for a realistic effect (current MDE {e['mde_pts'] * 100:.2f} pts).",
                  "Keep the holdout design: it is what makes this conclusion trustworthy."])
        ops = ["Holdout users must stay excluded from all overlapping CRM sends during the 14 days.",
               "Read reactivation from assignment day, in both arms; 'opened the e-mail' is not a comparison."]
        execs = [f"Reactivation {('rose' if real else 'did not move')}: {e['cuped_diff'] * 100:+.2f} points vs a randomised holdout.",
                 f"That is about {e['cuped_diff'] * 1000:.0f} extra active users per 1,000 messages." if real else
                 "No budget should be attached to it until a redesigned test shows an effect.",
                 "Measured with a randomised holdout: the most reliable method we have."]
    else:
        inc = sa.incrementality(cid)
        if k is not None:
            tiles = [("First depositors (attributed)", f"{int(k.attributed_first_depositors):,}",
                      f"{int(k.attributed_signups):,} attributed sign-ups"),
                     ("CAC per first depositor", f"{k.cac_first_deposit:.2f} USD", "media / attributed depositors"),
                     ("30-day ROI", fmt_pct(k.roi_30d), "incl. promo bonuses" if k.promo_usd > 0 else "media only"),
                     ("Withdrew >= 90% (30 d)", fmt_pct(k.share_withdrew_90pct_30d, False),
                      f"D30 retention {fmt_pct(k.retention_d30, False)}")]
        n, d, s = inc.get("naive"), inc.get("did"), inc.get("synthetic")
        rows = [("Outcome measured", inc.get("outcome", ""), f"campaign days vs 14 days before")]
        if n:
            rows.append(("Naive before/after", f"{n['effect']:+.1%} [{n['lo']:+.1%}, {n['hi']:+.1%}]",
                         "counts trend and market as campaign"))
        if d:
            rows.append(("Difference-in-differences vs 8 regions", f"{d['effect']:+.1%} [{d['lo']:+.1%}, {d['hi']:+.1%}]",
                         "region and day fixed effects, clustered by region"))
        if s:
            rows.append(("Synthetic control", f"{s['effect']:+.1%} [{s['lo']:+.1%}, {s['hi']:+.1%}]",
                         f"placebo-in-space p = {s['p']:.2f}"))
        if "placebo_time" in inc:
            p = inc["placebo_time"]
            rows.append(("Placebo in time (fake start 14 days earlier)", f"{p['effect']:+.1%}", "should be about 0"))
        if inc.get("note"):
            rows.append(("Note", inc["note"], ""))
        abuse = sa.q("SELECT * FROM referral_abuse_indicators")
        flagged = abuse[abuse["flags"] >= 3]
        farm = 0
        if len(flagged):
            ids = "','".join(flagged.referrer_id)
            farm = int(sa.q(f"""SELECT count(*) FROM stg_users WHERE attributed_campaign = '{cid}'
                                AND referrer_id IN ('{ids}')""").iloc[0, 0])
        if farm:
            rows.append(("Accounts from flagged referrers", f"{farm:,}", f"{len(flagged)} referrers, >= 3 of 4 indicators"))
        if pd.notna(kyc.d0):
            rows.append(("KYC pass rate in the region", f"{kyc.pr:.0%} on {str(kyc.d0)[:10]} to {str(kyc.d1)[:10]}",
                         "downstream incident during the campaign"))
        no_effect = d is not None and d["lo"] <= 0
        ci_txt = "interval includes zero" if no_effect else (f"95% CI {d['lo']:+.0%} to {d['hi']:+.0%}" if d else "")
        withdrawals = k is not None and pd.notna(k.share_withdrew_90pct_30d) and k.share_withdrew_90pct_30d > 0.30
        roi_neg = k is not None and pd.notna(k.roi_30d) and k.roi_30d < 0
        if withdrawals and roi_neg:
            recos = [f"Do not relaunch as is: the CAC is the lowest of the window, but the 30-day ROI is "
                     f"{k.roi_30d:+.0%} once promo cost is counted and {k.share_withdrew_90pct_30d:.0%} of depositors "
                     f"took >= 90% back out within 30 days.",
                     "If relaunched: pay the boosted rate only after a holding period, cap it per user, and judge it on "
                     "30-day net deposits and retention, with a withdrawal guardrail written in the plan.",
                     "Keep the acquisition partners (the sign-up lift is real); change the offer, not the channel."]
            ops = ["Add the full-withdrawal share and promo cost per depositor to the daily campaign view.",
                   "Flag depositors who withdraw >= 90% within 8 days of the bonus end for risk review (indicators only)."]
            execs = [f"Cheapest customers of the quarter ({k.cac_first_deposit:.0f} USD each), but the campaign lost money "
                     f"over 30 days ({k.roi_30d:+.0%}).",
                     f"{k.share_withdrew_90pct_30d:.0%} of its depositors left with the bonus.",
                     "Decision: no relaunch as is; a redesigned offer with a holding period can be tested."]
        elif farm:
            recos = [f"Pause the referral rewards of the {len(flagged)} flagged referrers and report the campaign without "
                     f"their {farm:,} accounts.",
                     "Re-measure the campaign on qualified referrals (KYC passed, deposit above the minimum, active after 30 days).",
                     "Add the four abuse indicators as automatic guardrails for every referral campaign."]
            ops = ["Hold rewards of flagged referrers until risk review; no account action on indicators alone.",
                   "Watch shared devices and 60-minute sign-up bursts per referrer daily."]
            execs = [f"Referral sign-ups were inflated by {farm:,} low-quality accounts from {len(flagged)} referrers.",
                     "The real effect of the campaign is smaller than reported; rewards for those accounts are on hold.",
                     "Guardrails now catch this pattern automatically."]
        elif d is not None and n and n["effect"] > 0.2 and d["effect"] < n["effect"] / 3:   # market-dominated
            recos = [f"Credit the campaign with {d['effect']:+.0%} at most, not {n['effect']:+.0%}: regions without "
                     "the campaign rose almost as much (market volume on the most volatile BTC day of the window).",
                     "Judge trading competitions against untreated regions or a holdout of eligible users.",
                     "If repeated, randomise eligibility (e.g. 10% holdout) so the effect can be read in days."]
            ops = ["Show the control regions next to the treated region in the campaign view.",
                   "Annotate the dashboard with the market context (BTC volume, volatility) of each campaign day."]
            execs = [f"Trades rose {n['effect']:+.0%} during the competition, but {d['effect']:+.0%} once the market is "
                     f"taken out ({ci_txt}).",
                     "Most of the rise came from the market, not the campaign.",
                     "Next competitions will keep a holdout so their effect can be measured."]
        elif pd.notna(kyc.d0):
            recos = ["Do not judge the campaign on first deposits of the outage days: KYC approvals collapsed in the region "
                     "(downstream incident), not demand.",
                     "Re-contact users who failed KYC during the outage; measure the campaign on sign-ups and on "
                     "deposits after the incident.",
                     "Add KYC pass rate by region and day as a guardrail on every acquisition campaign view."]
            ops = ["Escalate vendor outages to growth the same day; pause paid acquisition in the region while KYC is down.",
                   "Track resubmissions after the outage."]
            execs = ["The campaign brought sign-ups; the drop in first deposits came from the KYC vendor outage.",
                     "Users blocked by the outage are being re-contacted.",
                     "No budget decision should be taken on the outage days."]
        else:
            ok = d is not None and d["lo"] > 0
            recos = ["Scale gradually: the effect stands out against untreated regions." if ok else
                     "Do not scale yet: the effect does not stand out against untreated regions.",
                     "Keep two untreated regions as controls for the next wave.",
                     "Read the 30-day ROI again once every depositor has 30 days of history."]
            ops = ["Keep tagging consistent across partners.", "State the day cut (UTC+8) on the daily view."]
            execs = ["Incremental effect: " + (fmt_pct(d["effect"]) if d else "not measurable"),
                     "30-day ROI (attributed): " + (fmt_pct(k.roi_30d) if k is not None else "n/a"),
                     "Decision follows the incremental number, not the attributed one."]
    tile_html = "".join(rk.tile(a, b, t, "SIM") for a, b, t in tiles)
    tbl = "".join(f"<tr><td>{html.escape(a)}</td><td><b>{html.escape(b)}</b></td><td>{html.escape(t)}</td></tr>"
                  for a, b, t in rows)
    extra = ""
    if cid == "CMP014":
        extra = rk.card("<h2>How I approached it (6 steps)</h2><ol>" +
                        "".join(f"<li>{html.escape(x)}</li>" for x in HOW_I_APPROACHED_CMP014) + "</ol>", "auto")
    body = f"""
<div class="grid4">{tile_html}</div>
<div class="g21">
  <div class="stack">{rk.card(f'<h2>Incremental vs control {rk.TAGS["SIM"]}</h2><table>{tbl}</table>')}{extra}</div>
  <div class="stack">
    {rk.card('<h2>3 recommendations</h2><ol>' + ''.join(f'<li>{html.escape(r)}</li>' for r in recos) + '</ol>')}
    {rk.card('<h2>For operations</h2><ul>' + ''.join(f'<li>{html.escape(r)}</li>' for r in ops) + '</ul>', 'auto')}
    {rk.card('<h2>For executives</h2><ul>' + ''.join(f'<li>{html.escape(r)}</li>' for r in execs) + '</ul>', 'auto')}
  </div>
</div>"""
    title = f"{cid} readout - {c['name']}"
    sub = (f"Objective: {c['objective']} · {s0} to {s1} UTC (launch {hk} UTC+8) · budget "
           f"{c['budget_usd']:,.0f} USD · SIMULATED exchange, not Binance data")
    pg = rk.page(0, html.escape(title), html.escape(sub), body, "Source: simulated exchange (seed 42)", total=1)
    OUT.mkdir(parents=True, exist_ok=True)
    out = rk.write_html([pg], title, OUT / f"{cid}.html")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--campaign")
    ap.add_argument("--all-examples", action="store_true")
    ap.add_argument("--pdf", action="store_true", help="also print to PDF (headless Edge)")
    a = ap.parse_args(argv)
    ids = EXAMPLES if a.all_examples else [a.campaign]
    for cid in ids:
        h = build(cid)
        if a.pdf:
            rk.print_pdf(h, h.with_suffix(".pdf"), f"{cid} readout")
        print(f"[readout] {h.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
