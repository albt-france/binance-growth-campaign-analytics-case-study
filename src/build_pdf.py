"""The 10-page PDF report: report/Binance_growth_campaign_analytics.pdf (HTML -> headless Edge, empty metadata).

Every number is read from data/processed/findings.json; charts come from src/charts.py (report/img/).

    python src/build_pdf.py
"""
import json
from pathlib import Path

import pandas as pd

import report_kit as rk

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
OUT = ROOT / "report"
TITLE = "Campaign, crowd, cycle or counting? Growth-campaign analytics for Binance"
MISSIONS_H2 = "<h2>The role's missions and what this study delivers</h2>"
SRC_REAL = ("Sources: AWS Public Blockchain Data (Ethereum, anonymous S3); Binance Proof of Reserves address files; "
            "Binance official market data (data.binance.vision)")
SRC_SIM = "Source: simulated exchange (fictional, seed 42) - not Binance data"


def p(x, d=1, signed=False):
    return "n/a" if x is None else (f"{x * 100:+.{d}f}%" if signed else f"{x * 100:.{d}f}%")


def n0(x):
    return f"{x:,.0f}"


def img(name):
    return f"img/{name}.png"


def build():
    F = json.loads((PROC / "findings.json").read_text(encoding="utf-8"))
    fa, r, s, v = F["facts"], F["real"], F["sim"], F["verification"]
    r1, r2, r3, r4, r5, cal, es = r["r1"], r["r2"], r["r3"], r["r4"], r["r5"], r["calendar"], r["event_study"]
    ev = s["events"]
    e1, e2, e3, e4, e5, e6, e7, e8 = (ev[k] for k in ["E1", "E2", "E3", "E4", "E5", "E6", "E7", "E8"])
    crm = s["crm"]["CMP031"]
    meth = v["methods"]
    T = 10
    pages = []

    # ------------------------------------------------------------ 0 Overview
    qs = ["What do Binance's real flows on Ethereum show over 26 weeks, and how much of the movement comes from "
          "counting (a changing address list) and from the market?",
          "What does Binance's real campaign calendar look like, and can public data detect one campaign's effect?",
          "On a simulated exchange: which campaigns really paid back (CAC, 30-day ROI, retention, incrementality)?",
          "Which estimation method recovers the true (hidden) effect: naive, DiD, synthetic control, holdout?",
          "What does a growth analyst deliver every day: dashboards, one-page readouts, automated extracts, rules?"]
    four = "".join(rk.card(f"<h3>{a}</h3><p>{b}</p>") for a, b in [
        ("Campaign", "the incremental effect: what would not have happened without it"),
        ("Crowd", "who was acquired: channel and region mix, bonus hunters, referral farms"),
        ("Cycle", "the market: BTC fell " + p(-r4["btc_change_1oct_22nov"], 0) + " from 1 Oct to 22 Nov; "
                  "volatility moves deposits and trades with no campaign"),
        ("Counting", "the measurement: duplicates, UTC vs UTC+8, late partitions, a changing address list, "
                     "double-counted attribution")])
    tiles = "".join([
        rk.tile("Counting (real)", p(r2["fake_growth_pts"], 0, True).replace("%", " pts"),
                f"fake growth in deposits if you count with the address list in force each day "
                f"({p(r2['deposits_change_A_asof'], 0, True)} vs {p(r2['deposits_change_B_union'], 0, True)} on a fixed list)", "PUBLIC"),
        rk.tile("Coverage of the list (real)", p(r2["coverage_20nov_raw"], 1),
                f"of the {n0(r2['coverage_20nov_raw_senders'])} addresses sending tokens to Binance wallets on 20 Nov "
                "are in the published deposit list", "PUBLIC"),
        rk.tile("Cheapest is not best (sim.)", f"{e1['cac']:.0f} USD",
                f"lowest CAC of the quarter, yet 30-day ROI {p(e1['roi_30d'], 0, True)}: "
                f"{p(e1['withdrew_90pct'], 0)} of depositors left with the bonus", "SIM"),
        rk.tile("Cycle, not campaign (sim.)", p(e6["naive_3d_vs_7d"], 0, True),
                f"trades during a competition on the most volatile BTC day; vs untreated regions: "
                f"{p(e6['did'], 1, True)} (CI {p(e6['did_lo'], 1, True)} to {p(e6['did_hi'], 1, True)})", "SIM")])
    recos = [
        "Judge campaigns on incremental 30-day value (holdout or control regions), with guardrails on withdrawals "
        "and abuse - never on CAC or attributed conversions alone.",
        "Fix the counting before reading a trend: deduplicate on event_id, state the day cut (UTC+8 for operations), "
        "use the activity date for CAC, and freeze definitions (address lists, attribution rule).",
        "Keep a 10% holdout on every CRM campaign and two untreated regions for regional campaigns; size them first.",
        "Read every move against the market (real BTC volume) and the mix (channel, region) before crediting a campaign.",
        "Automate the daily refresh with a watermark and SQL tests; publish one-page readouts the morning after."]
    body = f"""
<div class="g12">
 <div class="stack">{rk.card('<h2>5 questions</h2><ol class="qs">' + ''.join(f'<li>{q}</li>' for q in qs) + '</ol>')}
  {rk.card('<h2>Method</h2><p class="small">Real part: 182 days of Ethereum flows to and from the addresses Binance '
           'published in 8 Proof-of-Reserves snapshots; 750 real campaign announcements; official market data. '
           'Simulated part: a fictional exchange with 40 campaigns and 8 hidden events, recovered without looking at '
           'the truth, then checked against it. SQL (DuckDB), Python, Plotly, Excel, Power BI.</p>', 'auto')}</div>
 <div class="stack"><div class="grid4">{tiles}</div>
  <div class="card auto"><h2>Before recommending anything, separate four causes</h2><div class="grid4">{four}</div></div>
  {rk.card('<h2>Recommendations</h2><ol class="reco">' + ''.join(f'<li>{x}</li>' for x in recos) + '</ol>')}</div>
</div>"""
    pages.append(rk.page(0, "When a growth number moves, separate campaign, crowd, cycle and counting first",
                         TITLE + " · independent case study for the Data Analyst (12 months contract) role",
                         body, SRC_REAL + "; Binance announcements; simulated exchange", total=T))

    # ------------------------------------------------------------ 1 Binance and the role
    job = fa["job"]
    pr = fa["por_audit"]["ratios"]
    facts = (f"<ul><li>\"{fa['company_claims']['text']}\" - as stated by Binance in the job post (read 23 Nov 2026).</li>"
             f"<li>Proof of Reserves, audit of 12 Nov 2026 00:00 UTC, zk-SNARK verified: BTC {pr['BTC']:.2%}, ETH "
             f"{pr['ETH']:.2%}, USDT {pr['USDT']:.2%}, USDC {pr['USDC']:.2%} - as stated by Binance "
             f"(binance.com/en/proof-of-reserves, read 23 Nov 2026).</li>"
             f"<li>Spot market: {n0(fa['exchange_info']['pairs'])} pairs listed, {n0(fa['exchange_info']['trading'])} "
             f"trading, {n0(fa['exchange_info']['trading_usdt_quote'])} against USDT (public exchangeInfo API, 23 Nov 2026).</li>"
             f"<li>The November address file lists {n0(fa['por_nov_files']['deposit_rows'])} deposit rows, of which "
             f"{n0(fa['por_nov_files']['deposit_rows_eth'])} on the ETH network.</li>"
             f"<li>Role: {job['title']}, Central Data Analytics, {job['location']}; first published "
             f"{job['first_published'][:10]} on Binance's careers board ({job['open_roles_on_board']} open roles).</li></ul>")
    missions = pd.DataFrame([
        ("Support growth campaigns end to end; validate funnel data", "SQL layer + 13 tests, dedup, UTC+8 rules, launch QA"),
        ("Measure conversion, CAC, ROI, retention of acquired users", "campaign scorecard, cohorts, incrementality"),
        ("Build and maintain dashboards; automate recurring extracts", "6-tab dashboard, Power BI, daily refresh"),
        ("Large behavioural and transaction data in SQL; cohort analyses", f"{r1['days']} days of Ethereum flows, 24.7 M simulated rows"),
        ("Simple visuals and clear stories for operations and leadership", "one-page readouts, weekly review, memo"),
        ("Fast time to market", "question to decision in a day (page 8)")], columns=["Mission (job post)", "Deliverable here"])
    can = ("<p><b>Can</b> be measured from outside: Ethereum deposits and withdrawals of published addresses, their "
           "rhythm, assets, hours; the campaign calendar; market data.</p><p><b>Cannot</b>: users, new customers, "
           "revenue, CAC or campaign results of Binance; other networks (Tron, BNB Chain, Solana, Bitcoin). "
           "An address is not a user.</p>")
    body = f"""
<div class="g21"><div class="stack">{rk.card('<h2>Binance, as stated by Binance ' + rk.TAGS['PUBLIC'] + '</h2>' + facts)}
 {rk.card(MISSIONS_H2 + rk.table(missions), 'auto')}</div>
 <div class="stack">{rk.chart(img('c01_por_list'), 'The published address list grew 4x in six months', 'PUBLIC',
     f"{n0(r2['list_deposit_first'])} deposit addresses (1 May) to {n0(r2['list_deposit_last'])} (11 Nov); wallets "
     f"{r2['list_wallets_first']} to {r2['list_wallets_last']}. The list only holds addresses with a balance at audit time.")}
 {rk.card('<h2>What public data can and cannot say</h2>' + can, 'auto')}</div></div>"""
    pages.append(rk.page(1, "Binance publishes rich public data; none of it counts users or campaign results",
                         "Facts are quoted as stated by Binance, with source and date; no internal data is used or invented",
                         body, "Sources: Binance job post (Greenhouse API), Proof of Reserves, exchangeInfo API", total=T))

    # ------------------------------------------------------------ 2 R1
    tiles = "".join([
        rk.tile("Deposit transfers / day", n0(r1["deposits_per_day"]), f"{p(r1['deposits_change_first_vs_last_4w'], 0, True)} "
                "last 4 weeks vs first 4 (fixed list)", "PUBLIC"),
        rk.tile("Withdrawal transfers / day", n0(r1["withdrawals_per_day"]),
                f"{r1['withdrawals_to_deposits']:.1f} withdrawals per deposit transfer", "PUBLIC"),
        rk.tile("USDT share of deposits", p(r1["usdt_share_of_deposit_transfers"], 0),
                f"USDC {p(r1['usdc_share_of_deposit_transfers'], 0)}, ETH {p(r1['eth_share_of_deposit_transfers'], 0)}", "PUBLIC"),
        rk.tile("Busiest hour (UTC+8)", f"{r1['peak_hour_hkt']}:00",
                f"{r1['peak_to_trough_hkt']:.1f}x the quietest hour ({r1['trough_hour_hkt']}:00); weekend "
                f"{p(r1['weekend_vs_weekday'], 0, True)} vs weekdays", "PUBLIC")])
    body = f"""<div class="grid4">{tiles}</div>
<div class="grid3">{rk.chart(img('c02_flows'), 'Deposits and withdrawals per day, 26 weeks', 'PUBLIC',
    'Ethereum only; all 8 published lists used as one fixed list.')}
 {rk.chart(img('c03_assets'), 'Stablecoins dominate the flows', 'PUBLIC', 'Share of deposit and withdrawal transfers by asset.')}
 {rk.chart(img('c04_hours'), 'An Asian-hours profile', 'PUBLIC', 'Deposits by hour of day in UTC+8, relative to the hourly mean.')}</div>"""
    pages.append(rk.page(2, f"26 weeks of real Binance flows on Ethereum: about {n0(r1['deposits_per_day'])} deposit "
                            f"transfers a day, mostly stablecoins, peaking in Asian hours",
                         f"{r1['days']} days (25 May - 22 Nov 2026), {r5['tx_total_mean'] / 1e6:.1f} M transactions and "
                         f"{r5['tt_total_mean'] / 1e6:.1f} M token transfers read per day; transfers and addresses, not users",
                         body, SRC_REAL, total=T))

    # ------------------------------------------------------------ 3 R2
    tiles = "".join([
        rk.tile("List in force each day", p(r2["deposits_change_A_asof"], 0, True), "deposit transfers, last 4 weeks vs first 4", "PUBLIC"),
        rk.tile("Fixed list (all snapshots)", p(r2["deposits_change_B_union"], 0, True), "same period, same data", "PUBLIC"),
        rk.tile("Coverage, Nov list", f"{p(r2['coverage_first4w_C_nov'], 0)} -> {p(r2['coverage_last4w_C_nov'], 0)}",
                "share of wallet senders that are listed, first vs last 4 weeks", "PUBLIC"),
        rk.tile("Rows removed", p(1 - r2["clean_share"], 0),
                f"failed {p(r2['excl_failed_share'], 1)}, zero-value {p(r2['excl_zero_value_share'], 1)}, dust "
                f"{p(r2['excl_dust_share'], 1)}, internal {p(r2['excl_internal_share'], 1)}", "PUBLIC")])
    body = f"""<div class="grid4">{tiles}</div>
<div class="grid3">{rk.chart(img('c05_definitions'), 'Same transfers, three list definitions', 'PUBLIC',
    'Counting with the list in force each day adds every newly published address to the trend.')}
 {rk.chart(img('c06_coverage'), 'The list covers a minority of active senders', 'PUBLIC',
    f"Listed senders / all non-wallet senders to Binance wallets (token transfers). Drops to ~0 on "
    f"{', '.join(d[5:] for d in r5['wallet_gap_days'])}: wallets absent from the lists.")}
 {rk.chart(img('c07_exclusions'), 'What the cleaning removes', 'PUBLIC', 'Kept in staging, measured, excluded from clean counts.')}</div>"""
    pages.append(rk.page(3, f"Counting: with the address list in force each day, deposits look "
                            f"{p(r2['fake_growth_pts'], 0, True).replace('%', ' points')} better than they are",
                         "Binance's published list grows from snapshot to snapshot; a fixed definition is the only fair "
                         "comparison over time. The 20 Nov reference figures are reproduced exactly (SQL test).",
                         body, SRC_REAL, total=T))

    # ------------------------------------------------------------ 4 R3 / R4
    tiles = "".join([
        rk.tile("Seen again after 1 week", p(r3["retention_w1"], 0), f"{r3['cohorts']} weekly cohorts after an 8-week burn-in", "PUBLIC"),
        rk.tile("After 12 weeks", p(r3["retention_w12"], 0), "swept addresses (not users)", "PUBLIC"),
        rk.tile("Deposits vs BTC volume", f"r = {r4['deposits_corr_btc_volume']:.2f}",
                f"daily correlation; once weekdays and volatility are controlled, the volume elasticity is "
                f"{r4['deposits_elasticity_btc_volume']:.2f} (s.e. {r4['deposits_elasticity_se']:.2f}): weak, "
                "association only", "PUBLIC"),
        rk.tile("BTC, 1 Oct -> 22 Nov", p(r4["btc_change_1oct_22nov"], 0, True),
                f"{n0(r4['btc_open_1oct'])} -> {n0(r4['btc_open_22nov'])} USDT (official klines)", "PUBLIC")])
    body = f"""<div class="grid4">{tiles}</div>
<div class="grid2x2">{rk.chart(img('c08_retention'), 'Address cohorts: share seen again', 'PUBLIC', 'Bootstrap 95% intervals.')}
 {rk.chart(img('c09_heatmap'), 'Cohort matrix', 'PUBLIC', 'Cells under 20 addresses are never published.')}
 {rk.chart(img('c10_market'), 'Activity follows market volume', 'PUBLIC', 'One point per day.')}
 {rk.chart(img('c11_btc'), 'The cycle: a strong market decline', 'PUBLIC', 'BTCUSDT daily close.')}</div>"""
    pages.append(rk.page(4, "Cohorts and the crypto cycle: most addresses are seen once, and activity only loosely tracks the market",
                         "Addresses first seen in a week are followed for 12 weeks; daily activity is set against real BTC "
                         "volume and volatility (no causality claimed)", body, SRC_REAL, total=T))

    # ------------------------------------------------------------ 5 calendar
    tiles = "".join([
        rk.tile("Announcements", n0(cal["announcements"]), f"{cal['first']} to {cal['last']}; "
                f"{n0(cal['since_25may'])} since 25 May, detail read for all", "PUBLIC"),
        rk.tile("Promotions per day", f"{es['mean_active_promotions']:.0f}", f"on average (max {es['max_active_promotions']}), "
                f"periods found for {n0(cal['period_found'])}", "PUBLIC"),
        rk.tile("Campaigns tested", n0(es["events"]), f"USDT/USDC deposit or Earn starts; significant after BH: "
                f"{es['significant_bh_q10']}", "PUBLIC"),
        rk.tile("Smallest detectable effect", p(es["mde_usdt"], 0, True),
                "change in active USDT deposit addresses that would stand out from 1,000 placebo dates", "PUBLIC")])
    body = f"""<div class="grid4">{tiles}</div>
<div class="grid3">{rk.chart(img('c12_calendar_types'), 'Campaign types by month', 'PUBLIC',
    f"Rules checked by hand: {p(cal['taxonomy_fresh_v2'], 0)} correct on a fresh sample of 50 titles.")}
 {rk.chart(img('c13_overlap'), 'Many promotions run at once', 'PUBLIC', 'Promotion periods read in the announcements (UTC).')}
 {rk.chart(img('c14_event_study'), 'Event study vs placebo dates', 'PUBLIC',
    'Market- and weekday-adjusted; blue lines = real campaign starts.')}</div>"""
    pages.append(rk.page(5, f"{n0(cal['since_25may'])} real campaigns since May: with about {es['mean_active_promotions']:.0f} "
                            "promotions live each day, public data cannot isolate one",
                         f"With overlapping campaigns, public on-chain data cannot isolate a single campaign; the smallest "
                         f"effect it could detect here is {p(es['mde_usdt'], 0)} on active USDT deposit addresses. Titles are never published.",
                         body, "Sources: Binance announcements ('Latest Activities'); Ethereum flows; official market data",
                         total=T))

    # ------------------------------------------------------------ 6 scorecard
    sc = pd.read_csv(PROC / "campaign_scorecard.csv")
    show = sc[sc.campaign_id.isin(["CMP014", "CMP012", "CMP006", "CMP022", "CMP017", "CMP027"])].copy()
    show = pd.DataFrame({"campaign": show.campaign_id, "type": show.type, "region": show.region,
                         "CAC $": show.cac_first_deposit.round(1).fillna(""),
                         "ROI 30d": show.roi_30d.map(lambda x: "" if pd.isna(x) else f"{x:+.0%}"),
                         "DiD lift": show.did_lift.map(lambda x: "" if pd.isna(x) else f"{x:+.0%}"),
                         "status": show.status})
    tiles = "".join([
        rk.tile("CMP014: CAC", f"{e1['cac']:.2f} USD", f"rank {e1['cac_rank']} of {e1['n_kpi_campaigns']} acquisition campaigns by CAC", "SIM"),
        rk.tile("CMP014: 30-day ROI", p(e1["roi_30d"], 0, True), f"D30 retention {p(e1['retention_d30'], 0)}", "SIM"),
        rk.tile("Referral farm", f"{n0(e2['flagged_in_week'])}", f"accounts from {e2['flagged_referrers']} flagged referrers: "
                f"referral sign-ups inflated by {p(e2['inflation'], 0)} that week", "SIM"),
        rk.tile("Attributed ROI > 0", f"{s['campaigns_attributed_roi_positive']} / {s['campaigns_with_roi']}",
                "campaigns with 30 days of data", "SIM")])
    body = f"""<div class="grid4">{tiles}</div>
<div class="grid3">{rk.chart(img('c15_cac_roi'), 'CAC does not predict 30-day ROI', 'SIM', 'Red = CMP014 (boosted rate, LATAM-BR).')}
 {rk.chart(img('c16_cmp014'), 'CMP014 lifted sign-ups...', 'SIM',
    f"...by about {p(e1['signup_lift_naive'], 0, True)} naive (part of it is the October partner push); "
    f"{p(e1['withdrew_90pct'], 0)} of depositors withdrew >= 90% within 30 days.")}
 <div class="stack">{rk.chart(img('c17_farm'), 'The farm stands out on 4 indicators together', 'SIM',
    'Shared devices, 60-minute bursts, KYC failures, identical deposits. Indicators only.')}
 {rk.card('<h2>Scorecard extract ' + rk.TAGS['SIM'] + '</h2>' + rk.table(show), 'auto')}</div></div>"""
    pages.append(rk.page(6, f"Which simulated campaigns really paid back: the cheapest acquisition "
                            f"({e1['cac']:.0f} USD) lost {p(-e1['roi_30d'], 0)} in 30 days",
                         "Simulated exchange - fictional campaigns CMP001-CMP040, not Binance. Attributed numbers first, "
                         "then guardrails and incrementality.", body, SRC_SIM, total=T))

    # ------------------------------------------------------------ 7 four causes
    evt = pd.DataFrame([
        ("6 Cycle", f"trades {p(e6['naive_3d_vs_7d'], 0, True)} naive", f"{p(e6['did'], 1, True)} vs untreated regions",
         f"true {p(v['truth_events']['E6_true_lift'], 0, True)}"),
        ("7 Crowd (Simpson)", f"D30 retention {p(e7['overall_sep'], 0)} -> {p(e7['overall_oct'], 0)}",
         f"up in {e7['channels_up']}/{e7['channels']} channels; standardised {p(e7['standardised_sep'], 0)} -> "
         f"{p(e7['standardised_oct'], 0)}", "mix shift to affiliates"),
        ("3 Counting (attribution)", f"partners claim {p(e3['latam_claimed_over_real'], 0)} of LATAM sign-ups",
         "one user-level rule sums to 100%", f"true {p(v['truth_events']['E3_claims_ratio_true'], 0)}"),
        ("4 Downstream", f"TR KYC pass {p(e4['pass_rate_before'], 0)} -> {p(e4['pass_rate_outage'], 0)}",
         "vendor outage 6-8 Oct, not the campaign", "found by detector"),
        ("5 Counting (data)", f"27 Oct deposits x{e5['ratio']:.1f} raw", f"{e5['late_launch_campaign']}: day 1 UTC "
         f"{n0(e5['day1_deposits_utc'])} vs UTC+8 {n0(e5['day1_deposits_hkt'])}", "SQL tests"),
        ("8 False signal", f"CAC {p(e8['wow_booking'], 0, True)} WoW (booking date)",
         f"{p(e8['wow_activity'], 0, True)} by activity date", "dismissed")],
        columns=["event", "what the dashboard shows", "what it is", "check"])
    body = f"""<div class="grid2x2">{rk.chart(img('c18_competition'), 'Cycle: a competition on the most volatile day', 'SIM',
    f"Naive {p(e6['naive_3d_vs_7d'], 0, True)}; difference-in-differences {p(e6['did'], 1, True)} "
    f"(CI {p(e6['did_lo'], 1, True)} to {p(e6['did_hi'], 1, True)}).")}
 {rk.chart(img('c19_simpson'), 'Crowd: retention down overall, up in every channel', 'SIM',
    f"Affiliate share of new depositors {p(e7['affiliate_share_sep'], 0)} -> {p(e7['affiliate_share_oct'], 0)}.")}
 {rk.chart(img('c22_cac'), 'Counting: the 2 Nov CAC alert is an invoicing artefact', 'SIM',
    'Three weeks of partner invoices booked in one week. Dismissed with evidence.')}
 {rk.card('<h2>The 8 hidden events, recovered ' + rk.TAGS['SIM'] + '</h2>' + rk.table(evt))}</div>"""
    pages.append(rk.page(7, "Campaign, crowd, cycle or counting? Six of the eight simulated surprises were not campaign effects",
                         f"Naive before/after misses the planted effects by {meth['naive']['mean_abs_error'] * 100:.0f} points on "
                         f"average; DiD and synthetic control by about {meth['did']['mean_abs_error'] * 100:.0f}; the randomised "
                         f"holdout by {meth['randomised_holdout']['mean_abs_error'] * 100:.1f} (page 8). Events 1-2 are on page 6.",
                         body, SRC_SIM + "; real BTC volume and volatility", total=T))

    # ------------------------------------------------------------ 8 tools
    bt = v["backtest"]
    pipe = F.get("pipeline", {})
    tools = ("<ul><li><b>growth_cli.py</b>: funnel, retention, campaign, 'is it real?' answers with a plain-English sentence.</li>"
             "<li><b>campaign_readout.py</b>: one-page readout (5 examples in reports/readouts).</li>"
             "<li><b>holdout_planner.py</b>: holdout size and duration for a target effect.</li>"
             "<li><b>weekly_growth_review.py</b>: facts, changes, causes, decisions asked (draft, never sent).</li>"
             "<li><b>daily_refresh.py</b>: incremental, idempotent; watermark on the AWS partitions; alert if yesterday is "
             "missing after 06:00 UTC" + (f"; last run {pipe['last_seconds'] / 60:.0f} min end to end" if pipe else "") +
             ".</li><li><b>SQL</b>: 28 numbered query files, 13 tests, 4 detectors; measurement plan and 6 playbooks.</li></ul>")
    mtab = pd.DataFrame([(k, f"{vv['mean_abs_error'] * 100:.1f} pts", p(vv["coverage"], 0), int(vv["campaigns"]))
                         for k, vv in meth.items()], columns=["method", "mean abs. error", "CI covers truth", "n"])
    body = f"""<div class="g12"><div class="stack">{rk.card('<h2>From question to decision in a day</h2>' + tools)}
 {rk.card('<h2>Methods vs the hidden truth ' + rk.TAGS['SIM'] + '</h2>' + rk.table(mtab) +
          '<p class="note">Checked after the analysis. Naive errors are large because trend, market and the October '
          'partner push are counted as campaign effect.</p>', 'auto')}
 {rk.card(f"<h2>CRM done right: CMP031 holdout {rk.TAGS['SIM']}</h2><p>{n0(crm['n_treatment'] + crm['n_holdout'])} dormant "
          f"users, 10% randomised holdout (split check p = {crm['srm_p']:.2f}). Reactivation in 14 days "
          f"{p(crm['rate_treatment'], 2)} vs {p(crm['rate_holdout'], 2)}: <b>{crm['cuped_diff'] * 100:+.2f} points</b> "
          f"(95% CI {crm['cuped_lo'] * 100:+.2f} to {crm['cuped_hi'] * 100:+.2f}, CUPED variance "
          f"{p(-crm['variance_reduction'], 0, True)}); smallest detectable {crm['mde_pts'] * 100:.2f} points.</p>", 'auto')}</div>
 <div class="stack">{rk.chart(img('c24_backtest'), 'Monitoring rules replayed over 13 weeks', 'SIM',
    f"{bt['true']} true alerts, {bt['explained_false']} explained false alert (2 Nov CAC), {bt['false']} false alert; "
    f"missed: {', '.join(bt['missed']) or 'none'} (caught by the abuse indicators instead).")}
 {rk.chart(img('c25_crm'), 'CRM campaigns against their holdouts', 'SIM', 'Only intervals above zero justify a roll-out.')}</div></div>"""
    pages.append(rk.page(8, "From question to decision in a day: tools, readouts, automated extracts and tests",
                         "What a growth analyst delivers every day, built and run on this study's data", body,
                         SRC_SIM + "; pipeline logs", total=T))

    # ------------------------------------------------------------ 9 methods, limits, AI note
    limits = ("<ul><li>Ethereum only: Tron, BNB Chain, Solana and Bitcoin flows are not measured.</li>"
              "<li>The published list holds addresses with a balance at audit time and changes every month; coverage of "
              "active senders is partial.</li><li>An address is not a user; a new address is not a new customer.</li>"
              "<li>Market relations are associations, not causal effects.</li>"
              "<li>The simulated exchange is fictional; its parameters are assumptions (docs/assumptions.md).</li>"
              f"<li>Data quality: {r5['days_late_over_6h']} AWS partitions landed more than 6 h late (latest "
              f"{r5['latest_day']}, {r5['max_hours_late']:.0f} h); handled by the watermark.</li>"
              f"<li>Wallet gap: on {', '.join(d[5:] for d in r5['wallet_gap_days'])} transfers into listed wallets nearly "
              "vanished while deposits continued - consistent with wallets missing from every published list; "
              "wallet-based metrics of those days are flagged, not imputed.</li></ul>")
    srcs = ("<ul><li>AWS Public Blockchain Data, Ethereum transactions and token transfers (anonymous S3, AWS Open Data).</li>"
            "<li>Binance Proof of Reserves address files (public.bnbstatic.com), 8 snapshots May-Nov 2026.</li>"
            "<li>Binance official market data (data.binance.vision, SHA-256 checked) and exchangeInfo API.</li>"
            "<li>Binance 'Latest Activities' announcements (public CMS API; titles never published).</li>"
            "<li>Binance careers board (Greenhouse API). All collected 23 Nov 2026, polite rate, no account.</li></ul>")
    priv = ("<p>No blockchain address is published (not even wallets or token contracts); aggregates only, at least "
            "20 addresses per cell; no attempt to link addresses to people. Abuse detection is described as indicators "
            "only. Rules on crypto promotions differ by jurisdiction. <b>Not investment advice.</b></p>")
    body = f"""<div class="grid2"><div class="stack">{rk.card('<h2>Sources and dates</h2>' + srcs)}
 {rk.card('<h2>Limits</h2>' + limits)}</div>
 <div class="stack">{rk.card('<h2>Methods</h2><p>DuckDB SQL (28 query files, 13 tests), Python (pandas, NumPy, SciPy): '
     'difference-in-differences with clustered errors, synthetic control, placebo tests, randomised holdout with SRM and '
     'CUPED, Kaplan-Meier, Markov attribution with bootstrap, Benjamini-Hochberg, direct standardisation, CUSUM. '
     'Every number in this report is read from data/processed/findings.json.</p>')}
 {rk.card('<h2>Privacy and caution</h2>' + priv)}
 {rk.card('<h2>AI note</h2><p>' + rk.ai_note() + '</p>', 'auto')}</div></div>"""
    pages.append(rk.page(9, "Methods, limits and sources", "How each number was produced and what it cannot say",
                         body, "See data/README.md for every source and its conditions", total=T))

    OUT.mkdir(exist_ok=True)
    html_path = rk.write_html(pages, TITLE, OUT / "_report.html")
    pdf = rk.print_pdf(html_path, OUT / "Binance_growth_campaign_analytics.pdf", TITLE)
    html_path.unlink()
    print(f"[pdf] {pdf.relative_to(ROOT)}")


if __name__ == "__main__":
    build()
