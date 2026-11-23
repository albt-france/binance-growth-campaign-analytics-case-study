"""Single-file HTML dashboard (Plotly, 6 tabs): dashboard/index.html (data inlined, plotly.js from its pinned CDN).

Tabs: Campaign scorecard · Funnel · Cohorts & retention · Spend & attribution ·
      Real data: Binance on Ethereum · Real data: campaign calendar
Every figure title carries PUBLIC DATA or SIMULATED. Every number comes from data/processed/ or the warehouse.

    python src/build_dashboard.py
"""
import html
import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import plotly.offline

import sim_analysis as sa

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
OUT = ROOT / "dashboard" / "index.html"
BLUE, ORANGE, GREEN, RED, MUTED, SAND = "#1C5CAB", "#C2541B", "#1E7B4F", "#B42F2F", "#6B6A65", "#B8A27A"
PUB, SIM = "PUBLIC DATA", "SIMULATED"
FOOT = "Independent case study based on public data · not affiliated with or endorsed by Binance · Not investment advice"


def lay(f, title, tag, h=360):
    f.update_layout(title=dict(text=f"{title} <span style='font-size:11px;color:{BLUE if tag == PUB else ORANGE}'>"
                                    f"[{tag}]</span>", font=dict(size=14)),
                    height=h, margin=dict(l=50, r=20, t=50, b=40), template="plotly_white",
                    font=dict(family="Segoe UI, Arial", size=11), legend=dict(orientation="h", y=-0.2))
    return f.to_html(full_html=False, include_plotlyjs=False)


def table_html(df, tag):
    head = "".join(f"<th>{html.escape(str(c))}</th>" for c in df.columns)
    rows = "".join("<tr>" + "".join(f"<td>{html.escape(str(v))}</td>" for v in r) + "</tr>"
                   for r in df.itertuples(index=False))
    return f'<div class="tbl"><div class="tag">[{tag}]</div><table><tr>{head}</tr>{rows}</table></div>'


def pct(x):
    return "" if pd.isna(x) else f"{x:+.0%}" if abs(x) < 10 else f"{x:+.0f}x"


# ------------------------------------------------------------------ tabs
def tab_scorecard():
    s = pd.read_csv(PROC / "campaign_scorecard.csv")
    t = pd.DataFrame({
        "campaign": s.campaign_id, "type": s.type, "region": s.region, "channel": s.channel,
        "first depositors (attrib.)": s.attributed_first_depositors.map(lambda v: "" if pd.isna(v) or v == 0
                                                                        else f"{int(v):,}"),
        "CAC $": s.cac_first_deposit.map(lambda v: "" if pd.isna(v) else f"{v:.1f}"), "30-day ROI": s.roi_30d.map(lambda v: "" if pd.isna(v) else f"{v:+.0%}"),
        "D30 retention": s.retention_d30.map(lambda v: "" if pd.isna(v) else f"{v:.0%}"),
        "withdrew >=90%": s.share_withdrew_90pct_30d.map(lambda v: "" if pd.isna(v) else f"{v:.0%}"),
        "incremental (DiD)": s.did_lift.map(pct), "naive": s.naive_lift.map(pct), "status": s.status})
    d = s.dropna(subset=["roi_30d"])
    f = go.Figure(go.Scatter(x=d.cac_first_deposit, y=d.roi_30d * 100, mode="markers+text", text=d.campaign_id,
                             textposition="top center", marker=dict(size=10, color=[RED if c == "CMP014" else BLUE
                                                                                    for c in d.campaign_id])))
    f.add_hline(y=0, line_color=MUTED)
    f.update_xaxes(title="CAC per first depositor (USD)")
    f.update_yaxes(title="30-day ROI (%)")
    return lay(f, "Cheapest is not best: CAC vs 30-day ROI per campaign", SIM) + table_html(t, SIM)


def tab_funnel():
    fr = pd.read_csv(PROC / "funnel_by_region_channel.csv")
    steps = ["registrations", "kyc_submitted", "kyc_passed", "first_deposit_7d", "first_trade_7d"]
    f = go.Figure()
    regions = ["ALL"] + sorted(fr.region.unique())
    for i, r in enumerate(regions):
        g = fr if r == "ALL" else fr[fr.region == r]
        v = g[steps].sum()
        f.add_trace(go.Funnel(y=steps, x=v.values, visible=(i == 0), name=r, textinfo="value+percent initial"))
    f.update_layout(updatemenus=[dict(buttons=[dict(label=r, method="update",
                                                    args=[{"visible": [j == i for j in range(len(regions))]}])
                                               for i, r in enumerate(regions)], x=1, y=1.15)])
    a = lay(f, "Funnel with time windows (KYC and first deposit within 7 days of sign-up)", SIM, 420)
    d = sa.q("""SELECT signup_date_utc d, 'UTC' tz, count(*) n FROM stg_users GROUP BY 1 UNION ALL
                SELECT signup_date_hkt, 'UTC+8', count(*) FROM stg_users GROUP BY 1""")
    d["d"] = pd.to_datetime(d.d)
    d = d[(d.d >= "2026-08-25") & (d.d <= "2026-11-22")].sort_values("d")
    g = go.Figure([go.Scatter(x=x.d, y=x.n, name=tz, line=dict(color=BLUE if tz == "UTC" else ORANGE))
                   for tz, x in d.groupby("tz")])
    b = lay(g, "Same sign-ups, two day cuts: UTC (data) vs UTC+8 (operations)", SIM)
    k = sa.q("SELECT * FROM kyc_daily_region")
    h = go.Figure([go.Scatter(x=x.date_utc, y=x.pass_rate * 100, name=r,
                              line=dict(width=3 if r == "TR" else 1, color=RED if r == "TR" else None))
                   for r, x in k.groupby("region")])
    h.update_yaxes(title="KYC pass rate (%)")
    return a + b + lay(h, "KYC pass rate by region: the TR vendor outage (6-8 Oct)", SIM)


def tab_cohorts():
    c = pd.read_csv(PROC / "cohort_matrix_weekly.csv")
    p = c.pivot(index="cohort_week", columns="weeks_since", values="retention")
    f = go.Figure(go.Heatmap(z=p.values * 100, x=[f"W+{w}" for w in p.columns], y=p.index.astype(str),
                             colorscale="Blues", colorbar=dict(title="%")))
    a = lay(f, "Weekly cohorts of new depositors: % active (traded) in week W+k", SIM, 440)
    r = pd.read_csv(PROC / "retention_by_channel_month.csv")
    g = go.Figure([go.Bar(x=x.dep_month.astype(str), y=x.retention_d30 * 100, name=ch) for ch, x in r.groupby("channel")])
    g.update_yaxes(title="30-day retention (%)")
    b = lay(g, "30-day retention by channel and month: falls overall, rises in every channel (mix)", SIM)
    km = pd.read_csv(PROC / "km_first_deposit.csv")
    h = go.Figure([go.Scatter(x=x.day, y=x.share_deposited * 100, name=ch) for ch, x in km.groupby("channel")])
    h.update_xaxes(title="days after KYC approval")
    h.update_yaxes(title="% with a first deposit (Kaplan-Meier)")
    return a + b + lay(h, "Time to first deposit, censoring handled (Kaplan-Meier)", SIM)


def tab_spend():
    c = pd.read_csv(PROC / "cac_weekly.csv")
    f = go.Figure([go.Scatter(x=c.week, y=c.cac_booking, name="booking date", line=dict(color=RED)),
                   go.Scatter(x=c.week, y=c.cac_activity, name="activity date", line=dict(color=BLUE))])
    f.update_yaxes(title="CAC per first depositor (USD)")
    a = lay(f, "Weekly CAC: booking date vs activity date (the 2 Nov alert is an invoicing artefact)", SIM)
    s = pd.read_csv(PROC / "attribution_latam_shares.csv", index_col=0)
    g = go.Figure([go.Bar(x=s.index, y=s[col] * 100, name=col.replace("_", " ")) for col in s.columns])
    g.update_yaxes(title="% of LATAM sign-ups credited")
    b = lay(g, "One credit per sign-up: attribution rules compared (LATAM)", SIM)
    pc = sa.q("SELECT * FROM partner_claims")
    t = pc.assign(claimed_over_real=pc.claimed_over_real.map(lambda v: f"{v:.0%}"))
    return a + b + table_html(t, SIM)


def tab_onchain():
    d = pd.read_csv(PROC / "onchain_r2_definitions.csv", parse_dates=[0], index_col=0)
    lab = {"A_asof": "list in force on the day", "B_union": "all 8 lists (fixed)", "C_nov": "November list (fixed)"}
    f = go.Figure([go.Scatter(x=d.index, y=d[c].rolling(7).mean(), name=lab[c]) for c in d.columns])
    f.update_yaxes(title="deposit transfers per day (7-day mean)")
    a = lay(f, "Choose the list definition: the 'in force' list manufactures growth", PUB)
    r1 = pd.read_csv(PROC / "onchain_r1_daily.csv", parse_dates=["date_utc"])
    g = go.Figure([go.Scatter(x=r1.date_utc, y=r1[c].rolling(7).mean(), name=c.replace("_", " "))
                   for c in ["deposits", "withdrawals", "active_deposit_addresses", "swept_addresses"]])
    b = lay(g, "26 weeks of Binance flows on Ethereum (fixed list, 7-day means)", PUB)
    cov = pd.read_csv(PROC / "onchain_coverage_daily.csv")
    h = go.Figure([go.Scatter(x=x.date_utc, y=x.coverage * 100, name=lab[k]) for k, x in cov.groupby("definition")])
    h.update_yaxes(title="% of senders to Binance wallets that are listed")
    c = lay(h, "Coverage of the published deposit list", PUB)
    rc = pd.read_csv(PROC / "onchain_r3_retention_curve.csv")
    k = go.Figure(go.Scatter(x=rc.weeks_since, y=rc.retention * 100, error_y=dict(
        type="data", array=(rc.hi - rc.retention) * 100, arrayminus=(rc.retention - rc.lo) * 100)))
    k.update_xaxes(title="weeks after first seen")
    k.update_yaxes(title="% of addresses seen again (an address is not a user)")
    return a + b + c + lay(k, "Address cohorts (8-week burn-in against left censoring)", PUB)


def tab_calendar():
    c = pd.read_csv(PROC / "calendar_by_type_month.csv")
    f = go.Figure([go.Bar(x=x.month, y=x.announcements, name=t) for t, x in c.groupby("type")])
    f.update_layout(barmode="stack")
    a = lay(f, "750 'Latest Activities' announcements by type (rules, 88% correct on a fresh sample)", PUB, 400)
    o = pd.read_csv(PROC / "calendar_overlap_daily.csv")
    g = go.Figure([go.Scatter(x=o.date_utc, y=o.active_promotions, name="all promotions", fill="tozeroy"),
                   go.Scatter(x=o.date_utc, y=o.active_usd_stable_deposit_earn, name="USDT/USDC deposit or Earn")])
    b = lay(g, "Promotions running on the same day (UTC)", PUB)
    e = pd.read_csv(PROC / "event_study_real_campaigns.csv")
    h = go.Figure(go.Scatter(x=e.start, y=e.effect * 100, mode="markers", marker=dict(
        color=[BLUE if a == "USDT" else GREEN for a in e.asset], size=9), text=e.asset))
    h.add_hline(y=0, line_color=MUTED)
    h.update_yaxes(title="market-adjusted change in active senders (%)")
    t = e.assign(effect=e.effect.map(lambda v: f"{v:+.1%}"), p_placebo=e.p_placebo.round(3),
                 q_bh=e.q_bh.round(3), mde=e.mde.map(lambda v: f"{v:.0%}"))[
        ["article_code", "asset", "start", "start_from_period", "effect", "p_placebo", "q_bh", "mde"]]
    return a + b + lay(h, "Event study: USDT/USDC deposit and Earn campaigns vs placebo dates", PUB) + table_html(t, PUB)


def main():
    F = json.loads((PROC / "findings.json").read_text(encoding="utf-8"))
    tabs = [("Campaign scorecard", tab_scorecard()), ("Funnel", tab_funnel()), ("Cohorts & retention", tab_cohorts()),
            ("Spend & attribution", tab_spend()), ("Real data: Binance on Ethereum", tab_onchain()),
            ("Real data: campaign calendar", tab_calendar())]
    # plotly.js from its official CDN, pinned to the version bundled with the plotly package (smaller file;
    # the page needs an internet connection the first time it is opened)
    js_src = f"https://cdn.plot.ly/plotly-{plotly.offline.get_plotlyjs_version()}.min.js"
    buttons = "".join(f'<button onclick="show({i})" id="b{i}">{html.escape(n)}</button>' for i, (n, _) in enumerate(tabs))
    panes = "".join(f'<div class="pane" id="p{i}" style="display:{"block" if i == 0 else "none"}">{c}</div>'
                    for i, (_, c) in enumerate(tabs))
    sub = (f"Real data: {F['real']['r1']['days']} days of Ethereum flows, {F['real']['calendar']['announcements']} "
           f"announcements · Simulated exchange: {F['sim']['meta']['signups']:,} sign-ups, 40 campaigns")
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Growth campaign dashboard</title>
<script src="{js_src}"></script><style>
body{{margin:0;font-family:'Segoe UI',Arial,sans-serif;background:#F1EFEA;color:#0B0B0B}}
header{{padding:16px 24px 6px}} h1{{font-size:20px;margin:0}} .sub{{color:#52514E;font-size:13px;margin:4px 0}}
nav{{padding:0 24px;display:flex;flex-wrap:wrap;gap:6px}} nav button{{border:1px solid #D8D6CE;background:#fff;
padding:7px 12px;border-radius:6px;cursor:pointer;font-size:13px}} nav button.on{{background:#0B0B0B;color:#fff}}
.pane{{margin:12px 24px;background:#fff;border:1px solid #E1E0D9;border-radius:8px;padding:10px}}
.tbl{{overflow-x:auto;margin:10px 0}} table{{border-collapse:collapse;font-size:12px;width:100%}}
th{{text-align:left;color:#52514E;border-bottom:1px solid #E1E0D9;padding:4px}} td{{border-bottom:1px solid #EFEEE9;padding:3px 4px}}
.tag{{font-size:11px;color:#9A3B12;font-weight:700}} footer{{font-size:11px;color:#898781;padding:10px 24px 20px}}
</style></head><body><header><h1>Campaign, crowd, cycle or counting? Growth-campaign analytics</h1>
<p class="sub">{html.escape(sub)}</p></header><nav>{buttons}</nav>{panes}
<footer>{FOOT}. Simulated data describe a fictional exchange, never Binance. On-chain figures count addresses, not users.</footer>
<script>function show(i){{document.querySelectorAll('.pane').forEach((p,j)=>p.style.display=j==i?'block':'none');
document.querySelectorAll('nav button').forEach((b,j)=>b.className=j==i?'on':'');window.dispatchEvent(new Event('resize'));}}
show(0);</script></body></html>""", encoding="utf-8")
    print(f"[dashboard] {OUT.relative_to(ROOT)} ({OUT.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
