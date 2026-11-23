"""Write README.md and the documents that contain numbers (all read from data/processed/findings.json):
docs/executive_memo.md, docs/data_issues_log.md, docs/campaign_taxonomy.md, docs/onchain_method.md and the
measured performance block of sql/README.md.

    python src/build_readme.py
"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
DOCS = ROOT / "docs"


def ai_note():
    """The AI-use sentence lives in ONE place: the Methods section of README.md (the PDF reuses it)."""
    for line in (ROOT / "README.md").read_text(encoding="utf-8").splitlines():
        if line.startswith("> AI-assisted workflow:"):
            return line[2:].strip()
    raise ValueError("AI note missing from README.md")


FOOT = "Independent case study based on public data · not affiliated with or endorsed by Binance · Not investment advice"


def p(x, d=1, signed=False):
    return "n/a" if x is None else (f"{x * 100:+.{d}f}%" if signed else f"{x * 100:.{d}f}%")


def n0(x):
    return f"{x:,.0f}"


def main():
    AI = ai_note()
    F = json.loads((PROC / "findings.json").read_text(encoding="utf-8"))
    r, s, v = F["real"], F["sim"], F["verification"]
    r1, r2, r3, r4, r5, cal, es = r["r1"], r["r2"], r["r3"], r["r4"], r["r5"], r["calendar"], r["event_study"]
    ev = s["events"]
    e1, e2, e3, e4, e5, e6, e7, e8 = (ev[k] for k in ["E1", "E2", "E3", "E4", "E5", "E6", "E7", "E8"])
    crm = s["crm"]["CMP031"]
    meth = v["methods"]
    pipe = F.get("pipeline", {})

    pages = "https://albt-france.github.io/binance-growth-campaign-analytics-case-study"
    readme = f"""# Campaign, crowd, cycle or counting? Growth-campaign analytics for Binance

### 📄 [Read the PDF report (10 pages)]({pages}/report/Binance_growth_campaign_analytics.pdf) · 📊 [Open the interactive dashboard (6 tabs)]({pages}/dashboard/index.html)

Independent case study for the **Data Analyst (12 months contract)** role at Binance (Central Data Analytics).
When a growth number moves, four causes have to be separated before recommending anything: the **campaign**
(incremental effect), the **crowd** (who was acquired), the **cycle** (the market) and the **counting** (the
measurement). The study does it on **real public data about Binance** and on a **simulated exchange** with planted,
known effects.

**Links:** [PDF report (10 pages)](report/Binance_growth_campaign_analytics.pdf) ·
[dashboard (6 tabs)](dashboard/index.html) · [campaign readouts](reports/readouts/) ·
[weekly review](reports/weekly/) · [ROI workbook](excel/campaign_roi_workbook.xlsx) · [SQL](sql/README.md) ·
[playbooks](docs/playbooks/) · [metrics dictionary](METRICS.md) · [executive memo](docs/executive_memo.md)

![Report overview](report/img/c05_definitions.png)

## Key results
1. **Counting (PUBLIC DATA).** Over {r1['days']} days of Ethereum flows to and from the addresses Binance published in its
   Proof of Reserves, deposit transfers changed **{p(r2['deposits_change_A_asof'], 0, True)}** (last 4 weeks vs first 4) when
   counted with the list in force each day, but **{p(r2['deposits_change_B_union'], 0, True)}** on a fixed list: the published list
   grew from {n0(r2['list_deposit_first'])} to {n0(r2['list_deposit_last'])} deposit addresses, and only
   {p(r2['coverage_20nov_raw'], 1)} of the addresses sending tokens to Binance wallets on 20 Nov are in it
   ({n0(r2['coverage_20nov_raw_listed'])} of {n0(r2['coverage_20nov_raw_senders'])}).
2. **Calendar (PUBLIC DATA).** {n0(cal['announcements'])} real "Latest Activities" announcements; about
   {es['mean_active_promotions']:.0f} promotions live on an average day. Of {es['events']} USDT/USDC deposit or Earn
   campaigns tested against 1,000 placebo dates, {es['significant_bh_q10']} stand(s) out after Benjamini-Hochberg; the
   smallest detectable change is {p(es['mde_usdt'], 0)} on active USDT deposit addresses, so single campaigns are
   mostly invisible in public data.
3. **Crowd (SIMULATED).** The campaign with the lowest CAC of the quarter ({e1['cac']:.2f} USD per first depositor) has a
   30-day ROI of **{p(e1['roi_30d'], 0, True)}**: {p(e1['withdrew_90pct'], 0)} of its depositors withdrew at least 90% within
   30 days (bonus hunters).
4. **Cycle (SIMULATED).** A trading competition launched on the real most volatile BTC day of the window shows
   **{p(e6['naive_3d_vs_7d'], 0, True)}** trades naive, but **{p(e6['did'], 1, True)}** against untreated regions (95% CI
   {p(e6['did_lo'], 1, True)} to {p(e6['did_hi'], 1, True)}). Across all campaigns, naive before/after misses the planted
   effect by {meth['naive']['mean_abs_error'] * 100:.0f} points on average, difference-in-differences by
   {meth['did']['mean_abs_error'] * 100:.0f}, the randomised holdout by {meth['randomised_holdout']['mean_abs_error'] * 100:.1f}.

## What a growth data analyst delivers here
| Mission in the job post | Deliverable |
|---|---|
| Support growth and marketing campaigns end to end: extract, validate and structure funnel data | `sql/` (28 query files, 13 tests, 4 detectors), launch QA checklist, dedup and time-zone rules |
| Measure conversion, CAC, ROI, retention of acquired users; actionable recommendations | campaign scorecard, cohorts, Kaplan-Meier, incrementality (holdout, DiD, synthetic control), readouts |
| Build and maintain campaign and growth dashboards; automate recurring extracts | `dashboard/index.html`, `powerbi/`, `bi/datawind_mapping.md`, `pipelines/daily_refresh.py` |
| Large behavioural and transaction data in SQL; cohort analyses | {r1['days']} days of Ethereum (about {r5['tx_total_mean'] / 1e6:.1f} M transactions and {r5['tt_total_mean'] / 1e6:.1f} M token transfers per day read), {s['meta']['rows_total'] / 1e6:.1f} M simulated rows |
| Simple visuals and clear stories for operations and leadership | 10-page PDF, one-page readouts, weekly review, executive memo |
| Fast time to market | `tools/growth_cli.py`, readout generator, daily refresh{f" ({pipe['last_seconds'] / 60:.0f} min end to end)" if pipe else ""} |

## Methods
- **Real data**: Binance Proof-of-Reserves address files (8 snapshots), AWS Public Blockchain Data (Ethereum, read
  anonymously, only the needed columns), official Binance market data (checksums verified), Binance announcements.
  Three list definitions are compared; failed, zero-value and internal transfers are measured and excluded; address
  cohorts use an 8-week burn-in. The 15 reference figures of 20 Nov 2026 are reproduced exactly (SQL test).
- **Simulated exchange**: 13 weeks, {n0(s['meta']['signups'])} sign-ups, 40 campaigns, 8 hidden events, anchored on real
  market data, the real hourly deposit profile and the real campaign mix (`docs/assumptions.md`). The events are found
  without reading the truth, then checked against it.
- **Statistics** (`src/stats.py`, `docs/statistics_notes.md`): difference-in-differences with clustered errors,
  synthetic control, placebo tests, holdout with SRM and CUPED, Kaplan-Meier, Markov attribution with bootstrap,
  Benjamini-Hochberg, direct standardisation, control charts and CUSUM with a 13-week backtest.
- Every number in the report and this README is read from `data/processed/findings.json`.

> {AI}

## How to re-run
```
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
python src/fetch_public.py all            # uses the cache in data/raw if present
python src/extract_onchain.py --start 2026-05-25 --end 2026-11-22
python src/campaigns_calendar.py
python src/run_sql.py --part public       # on-chain layer (also builds the hourly profile)
python src/simulate_exchange.py
python src/run_sql.py                      # every query + SQL tests
pytest
python src/findings.py
python src/crosscheck.py                  # second method (pandas) for 11 report figures
python src/charts.py
python src/build_dashboard.py
python tools/campaign_readout.py --campaign CMP014
jupyter nbconvert --to notebook --execute --inplace notebooks/binance_growth_campaign_analytics.ipynb
python src/build_pdf.py
```
`python src/run_all.py` runs the offline steps in order. The extraction reads about {r5['mb_read_total_gb']:.0f} GB from
AWS (column pruning) and took about {r5['extract_hours_total']:.1f} hours of process time.

## Sources and conditions
See [data/README.md](data/README.md). No raw data is redistributed; only aggregates (at least 20 addresses per cell)
and a 10,000-row simulated sample are published. No blockchain address, no announcement title and no personal data
appear in this repository.

## Limits
Ethereum only (not Tron, BNB Chain, Solana or Bitcoin); the published list changes every month and covers part of
the active deposit addresses; an address is not a user and a new address is not a new customer; market relations are
associations; the simulated exchange is fictional and says nothing about Binance's users, revenue, CAC, channels or
campaign results. Rules on crypto promotions differ by jurisdiction.

**Not investment advice.**

{FOOT}
"""
    (ROOT / "README.md").write_text(readme, encoding="utf-8")

    memo = f"""# Executive memo - growth measurement (one page)

**Decision asked:** adopt three measurement rules for every growth campaign from the next planning cycle.

**Why now.** In the simulated quarter (fictional exchange, not Binance data):
- the cheapest acquisition campaign ({e1['cac']:.0f} USD per first depositor) **lost {p(-e1['roi_30d'], 0)}** of its cost over
  30 days, because {p(e1['withdrew_90pct'], 0)} of the customers it brought left with the bonus;
- a trading competition looked like **{p(e6['naive_3d_vs_7d'], 0, True)}** trades; against regions without it, the real effect was
  about **{p(e6['did'], 0, True)}** - the market did the rest;
- a weekly alert "CAC {p(e8['wow_booking'], 0, True)}" was an invoicing delay: on the day the money was actually spent, CAC fell
  {p(-e8['wow_activity'], 0)}.

On real public data, counting with Binance's published address list as it grows would show deposits at
{p(r2['deposits_change_A_asof'], 0, True)} instead of {p(r2['deposits_change_B_union'], 0, True)} on a fixed list: a
{r2['fake_growth_pts'] * 100:.0f}-point illusion created by the measurement alone.

**The three rules**
1. **Judge on incremental 30-day value**, with a holdout (CRM) or untreated regions (regional campaigns), plus two
   guardrails: full withdrawals and abuse flags. A low CAC alone is not a success.
2. **Fix the counting first**: one event = one row, the day cut stated (UTC+8 for operations), CAC on the activity
   date, frozen definitions.
3. **Read every move against the market and the mix** before crediting a campaign.

**Cost:** a 10% holdout delays the effect on 10% of the audience. The CRM test kept that way measured
{crm['cuped_diff'] * 100:+.2f} points of reactivation (95% CI {crm['cuped_lo'] * 100:+.2f} to {crm['cuped_hi'] * 100:+.2f}),
an answer no other method gives as reliably.

**Next step:** one pilot market, one quarter, the readout template of `reports/readouts/`.

{FOOT}
"""
    (DOCS / "executive_memo.md").write_text(memo, encoding="utf-8")

    issues = f"""# Data issues log

| # | Date found | Source | Issue | Impact | Detection | Fix | Status |
|---|---|---|---|---|---|---|---|
| 1 | 2026-11-23 | Binance announcements API | HTTP 429 on the article detail endpoint after about 110 calls at 1 request/s | detail of 317 articles delayed | HTTP status | stopped, waited, resumed at 1 request / 6 s honouring Retry-After; no workaround | closed: {cal['detail_read']} / {cal['detail_in_scope']} read |
| 2 | 2026-11-23 | AWS Public Blockchain Data | token-transfer addresses padded to 32 bytes | zero matches with the address lists | reference check | normalise to the last 20 bytes | closed (pytest) |
| 3 | 2026-11-23 | AWS Public Blockchain Data | {r5['days_late_over_6h']} daily partitions landed more than 6 h after the end of the day (latest {r5['latest_day']}, {r5['max_hours_late']:.0f} h) | a daily job reading too early sees an incomplete day | watermark on `last_modified` | refresh waits for the partition; alert after 06:00 UTC | monitored |
| 4 | 2026-11-23 | AWS Public Blockchain Data | zero-value token transfers ({p(r5['zero_value_share_all_transfers'], 1)} of all transfers; address poisoning) | inflated counts | `value = 0` flag | excluded from clean counts, counted apart | closed |
| 5 | 2026-11-23 | Binance Proof of Reserves | the ETH list grows from {n0(r2['list_deposit_first'])} to {n0(r2['list_deposit_last'])} deposit addresses (max {n0(r2['list_deposit_max'])}) | fake growth with the list in force | three definitions compared | fixed list (all snapshots) as default | documented |
| 5b | 2026-11-23 | Binance address lists vs Ethereum | on {', '.join(r5['wallet_gap_days'])} transfers into listed wallets fell to {p(r5['wallet_gap_min_ratio'], 1)}-{p(r5['wallet_gap_max_ratio'], 0)} of their usual level while deposits to listed deposit addresses continued (about {p(r5['wallet_gap_deposit_ratio_mean'], 0)} of usual); partitions complete, address formats checked | wallet-based metrics (sweeps, coverage, withdrawals) unreliable on those days | daily ratio to the 14-day median (`onchain_wallet_inflows_daily.csv`) | consistent with wallets absent from all 8 published lists (rotation); days flagged, not imputed | documented |
| 6 | 2026-11-23 | Kline files | timestamps in milliseconds (2024) and microseconds (2026) | wrong dates | length test | convert by magnitude | closed (pytest) |
| 7 | sim | deposits feed | pipeline replay on 27 Oct: same `event_id`, later `ingested_at` (raw rows x{e5['ratio']:.1f}) | deposits doubled that day | `dq_duplicate_event_ids_raw.sql`, monitoring | dedup in staging (QUALIFY) | closed (test T06) |
| 8 | sim | campaign tracker | {e5['late_launch_campaign']} launched {e5['launch_ts_utc']} UTC = midnight UTC+8 | two different "day 1" readouts | `dq_launch_day_differs_utc_hkt.sql` | readouts use the UTC+8 day, stated on the page | closed (test T07) |
| 9 | sim | KYC vendor | TR pass rate {p(e4['pass_rate_before'], 0)} -> {p(e4['pass_rate_outage'], 0)} on 6-8 Oct | TR campaign looks failed | `dq_kyc_pass_rate_drop.sql`, control chart | re-contact affected users; KYC guardrail in readouts | closed |
| 10 | sim | finance | partner invoices of two weeks booked with a third on 2 Nov | booking-date CAC {p(e8['wow_booking'], 0, True)} WoW | CAC by activity vs booking date | CAC decisions on the activity date | closed |
"""
    (DOCS / "data_issues_log.md").write_text(issues, encoding="utf-8")

    prec = pd.read_csv(PROC / "campaign_taxonomy_precision_by_type.csv")
    tax = ["# Campaign taxonomy (rules for the real Binance calendar)", "",
           "Types are assigned by written rules on the announcement title, in priority order; the first match wins "
           "(code: `src/campaigns_calendar.py`). Region = a country, currency or region named in the title, else "
           "'not stated'. Asset = the first of USDC, USDT, FDUSD, BTC, ETH, BNB, SOL, XRP, DOGE named; tokenized-stock "
           "campaigns are written 'tokenized stock' or 'tokenized-stock voucher', never with a company name or ticker.", "",
           "| Priority | Type | Pattern idea |", "|---|---|---|",
           "| 1 | tokenized_stock | tokenized stocks, shares, equities, securities |",
           "| 2 | new_user | new users, newcomers, first-time, welcome, sign-up |", "| 3 | p2p | P2P |",
           "| 4 | trading_competition | trading competition / tournament / challenge / sprint / cup, traders league, trade to win/share |",
           "| 5 | referral | refer, referral, invite, friends |", "| 6 | alpha | Alpha, booster, pre-TGE, Binance Wallet |",
           "| 7 | learn_quiz | learn, quiz, academy, course, test your knowledge |",
           "| 8 | pay | Binance Pay, payment, merchant, card, cashback |",
           "| 9 | earn_apr | Earn, APR, APY, staking, savings, launchpool, hold, subscribe |",
           "| 10 | deposit | deposit, top-up, buy, convert |", "| - | other | anything else |", "",
           "## Hand check", f"- Rules v1 on a random development sample of 50 titles (seed 7): **{p(cal['taxonomy_dev_v1'], 0)}** correct.",
           f"- Rules refined on that sample (v2): {p(cal['taxonomy_dev_v2'], 0)} on the same sample (optimistic: tuned on it).",
           f"- Rules v2 on a **fresh** sample of 50 other titles (seed 8), checked once: **{p(cal['taxonomy_fresh_v2'], 0)}** correct.",
           "", "Precision by predicted type on the fresh sample:", "", "| type | correct | predicted | precision |", "|---|---|---|---|"]
    tax += [f"| {x.type} | {x.correct} | {x.predicted_n} | {x.precision:.0%} |" for x in prec.itertuples()]
    tax += ["", "Labels and titles stay in `data/raw/` (Binance's text is never published)."]
    (DOCS / "campaign_taxonomy.md").write_text("\n".join(tax) + "\n", encoding="utf-8")

    cc = r["crosscheck"]
    ax = r["approx_vs_exact"]
    onm = f"""# On-chain method

## Sources
- **Address lists**: Binance Proof-of-Reserves files of 1 May, 1 Jun, 1 Jul, 1 Aug, 1 Sep, 1 Oct, 31 Oct and 11 Nov 2026
  (public zip files); ETH network rows only; deposit addresses and hot/cold wallets.
- **Ethereum**: AWS Public Blockchain Data, `transactions` and `token_transfers`, 25 May - 22 Nov 2026 ({r1['days']} UTC days),
  read anonymously one day at a time, only the needed columns, keeping rows that touch any listed address plus the
  day's totals. About {r5['mb_read_total_gb']:.0f} GB read in total.

## Definitions
See `METRICS.md` (deposit, sweep, unlisted sender to a wallet, swept address, withdrawal, coverage, exclusions).

## Three list definitions
| Definition | Deposit transfers per day | Change, last 4 weeks vs first 4 |
|---|---|---|
| A - list in force on the day | {n0(r2['deposits_per_day_A_asof'])} | {p(r2['deposits_change_A_asof'], 0, True)} |
| B - all 8 lists (fixed, default) | {n0(r2['deposits_per_day_B_union'])} | {p(r2['deposits_change_B_union'], 0, True)} |
| C - November list only (fixed) | {n0(r2['deposits_per_day_C_nov'])} | {p(r2['deposits_change_C_nov'], 0, True)} |

Coverage of active senders by the November list: {p(r2['coverage_first4w_C_nov'], 0)} in the first 4 weeks,
{p(r2['coverage_last4w_C_nov'], 0)} in the last 4; with the list in force each day: {p(r2['coverage_first4w_A_asof'], 0)} and
{p(r2['coverage_last4w_A_asof'], 0)}.

## Checks
- The 15 reference figures of 20 Nov 2026 are reproduced exactly with their raw definitions
  (`sql/tests/t_onchain_reference_20nov.sql`).
- Second method: clean USDT deposits and distinct USDT senders to wallets recomputed with pandas for
  {len(cc)} days: {'all match' if all(x['match'] for x in cc) else 'MISMATCH'} ({', '.join(x['date'] for x in cc)}).
- `approx_count_distinct` vs exact distinct senders per day: mean error {p(ax['mean_abs_error'], 2)}, max
  {p(ax['max_abs_error'], 2)}; {ax['seconds_approx']} s vs {ax['seconds_exact']} s. Exact counts are kept.

## Limits
Ethereum only; the lists hold addresses with a balance at audit time; an address is not a user; senders to wallets
that are not listed can be other services. No address is published; cells under 20 addresses are suppressed.
"""
    (DOCS / "onchain_method.md").write_text(onm, encoding="utf-8")

    sr = (ROOT / "sql" / "README.md").read_text(encoding="utf-8")
    perf = (f"- **Distinct counts**: `approx_count_distinct` (HyperLogLog) vs exact `count(DISTINCT)` on daily wallet "
            f"senders: mean error {p(ax['mean_abs_error'], 2)}, max {p(ax['max_abs_error'], 2)}, {ax['seconds_approx']} s vs "
            f"{ax['seconds_exact']} s on this machine; exact counts are kept (the error matters for small cells).")
    start, end = "<!-- PERF -->", "<!-- /PERF -->"
    if end in sr:
        sr = sr[:sr.index(start)] + f"{start}\n{perf}\n{end}" + sr[sr.index(end) + len(end):]
    else:
        sr = sr.replace(start, f"{start}\n{perf}\n{end}")
    (ROOT / "sql" / "README.md").write_text(sr, encoding="utf-8")
    print("[readme] README.md + 4 generated docs")


if __name__ == "__main__":
    main()
