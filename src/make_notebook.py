"""Write notebooks/binance_growth_campaign_analytics.ipynb (the single notebook of the study). Execute it with:
    jupyter nbconvert --to notebook --execute --inplace notebooks/binance_growth_campaign_analytics.ipynb
It makes no network call: it reads the DuckDB warehouse and data/processed.
"""
from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
MD, CODE = nbf.v4.new_markdown_cell, nbf.v4.new_code_cell

cells = [
    MD("# Campaign, crowd, cycle or counting? Growth-campaign analytics for Binance\n\n"
       "Independent case study based on public data · not affiliated with or endorsed by Binance · Not investment advice.\n\n"
       "Order: **real data** (Ethereum flows, campaign calendar, market) → **simulated exchange** (funnel, CAC, ROI, "
       "cohorts) → **incrementality** and methods table → **the 8 hidden events, one by one** → **monitoring and "
       "backtest** → **verification against the hidden truth** (last, and only there).\n\n"
       "No network call: everything is read from the DuckDB warehouse (`src/run_sql.py`) and `data/processed/`."),
    CODE("import sys, json\nfrom pathlib import Path\nROOT = Path.cwd().parent if Path.cwd().name == 'notebooks' else Path.cwd()\n"
         "sys.path.insert(0, str(ROOT / 'src'))\nimport os; os.chdir(ROOT)\n"
         "import pandas as pd, numpy as np\nimport matplotlib.pyplot as plt\n"
         "import onchain_metrics as om, sim_analysis as sa, stats\npd.set_option('display.width', 160)\n"
         "pd.set_option('display.max_columns', 20)"),
    MD("## Part A - Real data: Binance flows on Ethereum (PUBLIC DATA)\n"
       "Deposits and withdrawals **on Ethereum only**, to and from the addresses Binance published in its Proof of "
       "Reserves. An address is not a user; a new address is not a new customer."),
    CODE("r1 = om.r1(); pd.Series(r1).round(4)"),
    CODE("d = pd.read_csv('data/processed/onchain_r1_daily.csv', parse_dates=['date_utc']).set_index('date_utc')\n"
         "d[['deposits', 'withdrawals']].rolling(7).mean().plot(figsize=(9, 3), title='7-day mean transfers [PUBLIC DATA]');"),
    MD("### R2 - Counting: three list definitions\nThe list grows from snapshot to snapshot. Counting with the list in "
       "force each day adds every newly published address to the trend."),
    CODE("r2 = om.r2(); pd.Series(r2).round(4)"),
    CODE("pd.read_csv('data/processed/stg_por_snapshots.csv')"),
    MD("### R3 - Address cohorts (8-week burn-in) and R4 - market"),
    CODE("r3 = om.r3(); print(r3)\npd.read_csv('data/processed/onchain_r3_retention_curve.csv').round(4)"),
    CODE("r4 = om.r4(); pd.Series(r4)"),
    MD("### R5 - data quality of the public source"),
    CODE("r5 = om.r5(); {k: v for k, v in r5.items()}"),
    MD("### Second method and approximate counts"),
    CODE("print(om.crosscheck_pandas())\nprint(om.approx_vs_exact())"),
    MD("## Part B - Real campaign calendar (PUBLIC DATA)\nTitles are never shown: code, dates, period and derived "
       "categories only."),
    CODE("cal = om.calendar_summary(); cal"),
    CODE("es = om.event_study(); print(es)\n"
         "pd.read_csv('data/processed/event_study_real_campaigns.csv').round(3).head(20)"),
    MD("**Reading.** With many promotions live every day, public on-chain data cannot isolate a single campaign; the "
       "minimum detectable effect above is the honest answer."),
    MD("## Part C - Simulated exchange (SIMULATED, fictional, not Binance)"),
    CODE("json.loads((ROOT / 'data/sim/_meta.json').read_text())"),
    CODE("sa.q('SELECT * FROM funnel_by_region_channel').groupby('region')"
         "[['registrations','kyc_passed','first_deposit_7d']].sum().assign("
         "conv=lambda x: x.first_deposit_7d / x.registrations).round(3)"),
    CODE("sa.q('SELECT campaign_id, type, region, attributed_first_depositors, cac_first_deposit, roi_30d, "
         "retention_d30, share_withdrew_90pct_30d FROM campaign_kpis ORDER BY cac_first_deposit')"),
    CODE("t = sa.q('SELECT channel, days, observed FROM time_to_first_deposit')\n"
         "km = stats.kaplan_meier(t.days.values, t.observed.values)\n"
         "print('median days from KYC to first deposit:', km.loc[km.survival <= 0.5, 't'].iloc[0])"),
    MD("## Part D - Incrementality: four methods per campaign"),
    CODE("rows = []\nfor cid in sa.campaigns().campaign_id:\n    r = sa.incrementality(cid)\n"
         "    rows.append({'campaign': cid, 'outcome': r.get('outcome', 'holdout'),\n"
         "                 **{m: round(r[m]['effect'], 3) for m in ('naive', 'did', 'synthetic') if m in r},\n"
         "                 'placebo_time': round(r['placebo_time']['effect'], 3) if 'placebo_time' in r else None,\n"
         "                 'note': r.get('note', '')})\ninc = pd.DataFrame(rows); inc"),
    CODE("pd.DataFrame([sa.crm_experiment(c) for c in sa.campaigns().query('has_holdout').campaign_id]).round(4)"),
    MD("## Part E - The 8 hidden events, recovered from the data (no truth read here)"),
    CODE("ev = sa.events()"),
    MD("### 1. LATAM-BR boosted-rate campaign (CMP014): best CAC, negative ROI\nRead CAC, then the costs it leaves "
       "out (promo bonus), then the crowd: retention and full withdrawals."),
    CODE("ev['E1']"),
    MD("### 2. Referral farm (week of 14 Sep): indicators only"),
    CODE("print(ev['E2'])\nsa.q('SELECT * FROM referral_abuse_indicators ORDER BY flags DESC LIMIT 5')"),
    MD("### 3. Double-counted attribution (LATAM)"),
    CODE("print(ev['E3'])\nsa.q('SELECT * FROM partner_claims')"),
    MD("### 4. KYC vendor outage in TR (6-8 Oct): the campaign was not the problem"),
    CODE("ev['E4']"),
    MD("### 5. Data quality: duplicated deposits (27 Oct) and the UTC vs UTC+8 launch day"),
    CODE("ev['E5']"),
    MD("### 6. A market-made success: the trading competition on the most volatile BTC day"),
    CODE("ev['E6']"),
    MD("### 7. Simpson: retention down overall, up in every channel"),
    CODE("print(ev['E7'])\nsa.q(\"SELECT * FROM retention_by_channel_month WHERE dep_month IN ('2026-09-01','2026-10-01')\")"),
    MD("### 8. False signal: CAC +40% week over week (2 Nov) - dismissed with evidence"),
    CODE("print(ev['E8'])\nsa.q('SELECT week, cac_activity, cac_booking, wow_activity, wow_booking FROM cac_weekly')"),
    MD("## Part F - Monitoring: control charts, CUSUM and a 13-week backtest"),
    CODE("alerts = sa.monitoring_backtest(); alerts"),
    MD("## Part G - Verification against the hidden truth (only here)"),
    CODE("det, summ = sa.methods_vs_truth(); summ.round(3)"),
    CODE("scored = sa.score_backtest(alerts); print(scored.label.value_counts().to_dict(), 'missed:', scored.attrs['missed'])"),
    CODE("sa.truth().query(\"kind == 'event'\")"),
]
nb = nbf.v4.new_notebook(cells=cells, metadata={"kernelspec": {"name": "python3", "display_name": "Python 3",
                                                                "language": "python"}})
out = ROOT / "notebooks" / "binance_growth_campaign_analytics.ipynb"
out.parent.mkdir(exist_ok=True)
nbf.write(nb, out)
print("[notebook]", out.relative_to(ROOT))
