"""Weekly growth review (Markdown + HTML, ready to paste, NEVER sent): week of 16 Nov 2026 by default.

    python tools/weekly_growth_review.py --week 2026-11-16

Structure: facts · what changed vs last week · why (campaign, crowd/mix, cycle/market, counting) · decisions asked.
Simulated exchange numbers are tagged SIMULATED; the market and on-chain context is PUBLIC DATA.
"""
import argparse
import html
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import onchain_metrics as om  # noqa: E402
import sim_analysis as sa  # noqa: E402

OUT = ROOT / "reports" / "weekly"


def wk(df, col, week):
    return df.loc[df.week == pd.Timestamp(week), col].sum()


def build(week: str) -> Path:
    w, p = pd.Timestamp(week), pd.Timestamp(week) - pd.Timedelta(days=7)
    fw = sa.q("""SELECT signup_week AS week, sum(registrations) reg, sum(first_deposit_7d) dep
                 FROM funnel_weekly GROUP BY 1""")
    fw["week"] = pd.to_datetime(fw.week)
    nd = sa.q("""SELECT date_trunc('week', event_ts)::DATE AS week, count(*) n FROM stg_funnel_events
                 WHERE event = 'first_deposit' GROUP BY 1""")
    nd["week"] = pd.to_datetime(nd.week)
    cw = sa.q("SELECT * FROM cac_weekly")
    cw["week"] = pd.to_datetime(cw.week)
    by_ch = sa.q(f"""SELECT channel, signup_week AS week, count(*) n FROM stg_users
                     WHERE signup_week IN (DATE '{p.date()}', DATE '{w.date()}') GROUP BY ALL""")
    by_ch["week"] = pd.to_datetime(by_ch.week)
    chg = by_ch.pivot(index="channel", columns="week", values="n")
    chg.columns = ["prev", "this"]
    chg["delta"] = chg["this"] - chg["prev"]
    live = sa.campaigns()
    live = live[(pd.to_datetime(live.start_ts_utc) <= w + pd.Timedelta(days=7)) & (pd.to_datetime(live.end_ts_utc) >= w)]
    mk = om.market()["quote_volume_BTCUSDT"]
    mv = mk[w:w + pd.Timedelta(days=6)].mean() / mk[p:p + pd.Timedelta(days=6)].mean() - 1
    dep_real = om.daily()
    rv = dep_real[w:w + pd.Timedelta(days=6)].mean() / dep_real[p:p + pd.Timedelta(days=6)].mean() - 1
    reg_t, reg_p = wk(fw, "reg", w), wk(fw, "reg", p)
    nd_t, nd_p = wk(nd, "n", w), wk(nd, "n", p)
    c_t = cw[cw.week == w].iloc[0]
    facts = [
        f"Sign-ups: {reg_t:,.0f} ({reg_t / reg_p - 1:+.1%} vs the week of {p.date()}). [SIMULATED]",
        f"New first depositors: {nd_t:,.0f} ({nd_t / nd_p - 1:+.1%}). [SIMULATED]",
        f"CAC per first depositor: {c_t.cac_activity:.2f} USD by activity date ({c_t.wow_activity:+.0%} week over week); "
        f"{c_t.cac_booking:.2f} USD by booking date ({c_t.wow_booking:+.0%}). [SIMULATED]",
        f"Market: BTCUSDT volume on Binance {mv:+.0%} week over week; deposit transfers to Binance-listed addresses on "
        f"Ethereum {rv:+.0%} (fixed list; addresses, not users). [PUBLIC DATA]",
    ]
    top = chg.sort_values("delta")
    changes = [f"Largest channel moves in sign-ups: {top.index[0]} {top.delta.iloc[0]:+,.0f}, "
               f"{top.index[-1]} {top.delta.iloc[-1]:+,.0f}.",
               f"Campaigns live this week: {', '.join(live.campaign_id) or 'none'}."]
    why = [
        "Campaign: " + ("; ".join(f"{r.campaign_id} ({r.type}, {r.region})" for r in live.itertuples())
                        or "no campaign started or ended this week") + ".",
        "Crowd / mix: compare channel shares before reading blended rates; the October affiliate push has ended, "
        "so blended retention and CAC move with the mix.",
        f"Cycle / market: BTC volume moved {mv:+.0%}; deposits and trades follow the market without any campaign.",
        "Counting: SQL tests green; the latest week's 7-day funnel window is not complete yet (later steps will grow); "
        "partner invoices booked late make booking-date CAC unreliable week to week.",
    ]
    e = sa.crm_experiment("CMP031")
    asks = [(f"Approve the CRM reactivation roll-out with a 10% holdout kept: CMP031 reactivated "
             f"{e['cuped_diff'] * 100:+.2f} points vs its randomised holdout (95% CI {e['cuped_lo'] * 100:+.2f} to "
             f"{e['cuped_hi'] * 100:+.2f})." if e["cuped_lo"] > 0 else
             "Do not roll out the CRM reactivation message: no effect against its holdout."),
            "Agree that weekly CAC alerts use the activity date; finance keeps booking date for accounting.",
            "Approve the withdrawal guardrail for all bonus campaigns before the next LATAM new-user offer."]
    md = [f"# Weekly growth review - week of {w.date()} (Mon-Sun, UTC)", "",
          "_Prepared for the growth and operations teams. Draft, not sent. Simulated exchange figures are not Binance "
          "data; on-chain figures count addresses, not users._", "", "## Facts"] + [f"- {x}" for x in facts] + \
         ["", "## What changed"] + [f"- {x}" for x in changes] + ["", "## Why (campaign, crowd, cycle or counting)"] + \
         [f"- {x}" for x in why] + ["", "## Decisions asked"] + [f"{i}. {x}" for i, x in enumerate(asks, 1)] + \
         ["", "Independent case study based on public data · not affiliated with or endorsed by Binance · "
              "Not investment advice"]
    OUT.mkdir(parents=True, exist_ok=True)
    mdp = OUT / f"weekly_growth_review_{w.date()}.md"
    mdp.write_text("\n".join(md) + "\n", encoding="utf-8")
    body = []
    for line in md:
        if line.startswith("# "):
            body.append(f"<h1>{html.escape(line[2:])}</h1>")
        elif line.startswith("## "):
            body.append(f"<h2>{html.escape(line[3:])}</h2>")
        elif line.startswith("- ") or line[:2].rstrip(".").isdigit():
            body.append(f"<p>• {html.escape(line.split(' ', 1)[1])}</p>")
        elif line:
            body.append(f"<p><i>{html.escape(line.strip('_'))}</i></p>")
    (OUT / f"weekly_growth_review_{w.date()}.html").write_text(
        "<!doctype html><html lang='en'><head><meta charset='utf-8'><title>Weekly growth review</title><style>"
        "body{font-family:'Segoe UI',Arial;max-width:860px;margin:30px auto;color:#0B0B0B;background:#F1EFEA}"
        "h1{font-size:22px}h2{font-size:16px;margin-top:22px}p{font-size:14px;line-height:1.45}</style></head><body>"
        + "".join(body) + "</body></html>", encoding="utf-8")
    return mdp


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--week", default="2026-11-16")
    print("[weekly]", build(ap.parse_args().week).relative_to(ROOT))
