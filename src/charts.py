"""Static charts (PNG) for the PDF report and the campaign readouts. Matplotlib, one function per chart.
Every chart reads data/processed/ or the DuckDB warehouse; titles live in the report cards (with the
PUBLIC DATA / SIMULATED tag), so the images carry only axes, labels and a source line.

    python src/charts.py
"""
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import sim_analysis as sa  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
IMG = ROOT / "report" / "img"
INK, MUTED, GRID = "#0B0B0B", "#6B6A65", "#E6E4DE"
BLUE, ORANGE, GREEN, RED, SAND, PURPLE = "#1C5CAB", "#C2541B", "#1E7B4F", "#B42F2F", "#B8A27A", "#6B4FA0"
PALETTE = [BLUE, ORANGE, GREEN, PURPLE, SAND, RED, "#3F8FA6", MUTED]

plt.rcParams.update({"font.family": "Segoe UI", "font.size": 10, "axes.edgecolor": GRID, "axes.labelcolor": MUTED,
                     "xtick.color": MUTED, "ytick.color": MUTED, "axes.grid": True, "grid.color": GRID,
                     "grid.linewidth": 0.7, "axes.spines.top": False, "axes.spines.right": False,
                     "legend.frameon": False, "legend.fontsize": 9, "figure.dpi": 150, "savefig.dpi": 150})


def F():
    return json.loads((PROC / "findings.json").read_text(encoding="utf-8"))


def save(fig, name, source):
    fig.text(0.01, 0.005, source, fontsize=7.5, color=MUTED, ha="left", va="bottom")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    IMG.mkdir(parents=True, exist_ok=True)
    fig.savefig(IMG / f"{name}.png", metadata={"Software": None})
    plt.close(fig)


def fig(w=5.6, h=4.4):
    return plt.subplots(figsize=(w, h))


def datefmt(ax):
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))


SRC_CHAIN = "Source: AWS Public Blockchain Data (Ethereum) x Binance Proof-of-Reserves address lists; own extraction"
SRC_SIM = "Source: simulated exchange (seed 42) - not Binance data"


# ------------------------------------------------------------------ real data
def c01_por_list():
    s = pd.read_csv(PROC / "stg_por_snapshots.csv", parse_dates=["snapshot_date"])
    f, ax = fig()
    ax.bar(s.snapshot_date, s.n_deposit_addresses / 1e6, width=9, color=BLUE)
    ax.set_ylabel("deposit addresses listed (millions)")
    ax2 = ax.twinx()
    ax2.plot(s.snapshot_date, s.n_hot_cold_wallets, color=ORANGE, marker="o")
    ax2.set_ylabel("hot/cold wallets listed", color=ORANGE)
    ax2.grid(False)
    datefmt(ax)
    save(f, "c01_por_list", "Source: Binance Proof of Reserves, 8 public address files (ETH network)")


def c02_flows():
    d = pd.read_csv(PROC / "onchain_r1_daily.csv", parse_dates=["date_utc"]).set_index("date_utc")
    f, ax = fig()
    for col, c, lab in [("deposits", BLUE, "deposit transfers"), ("withdrawals", ORANGE, "withdrawal transfers")]:
        ax.plot(d.index, d[col], color=c, alpha=0.25, lw=0.8)
        ax.plot(d.index, d[col].rolling(7).mean(), color=c, lw=2, label=lab + " (7-day mean)")
    ax.set_ylabel("transfers per day")
    ax.legend(loc="upper left")
    datefmt(ax)
    save(f, "c02_flows", SRC_CHAIN + " - fixed list (all 8 snapshots)")


def c03_assets():
    q = sa.q("""SELECT asset, flow, sum(n_transfers) n FROM onchain_daily WHERE definition = 'B_union'
                AND flow IN ('deposit', 'withdrawal') GROUP BY ALL""")
    p = q.pivot(index="asset", columns="flow", values="n").fillna(0)
    p = p / p.sum()
    p = p.loc[["USDT", "USDC", "ETH", "other token"]]
    f, ax = fig()
    x = np.arange(len(p))
    ax.bar(x - 0.2, p.deposit * 100, 0.4, color=BLUE, label="deposits")
    ax.bar(x + 0.2, p.withdrawal * 100, 0.4, color=ORANGE, label="withdrawals")
    ax.set_xticks(x, ["USDT (ERC-20)", "USDC (ERC-20)", "ETH", "other tokens"])
    ax.set_ylabel("% of transfers")
    ax.legend()
    save(f, "c03_assets", SRC_CHAIN)


def c04_hours():
    h = pd.read_csv(PROC / "onchain_hourly_profile.csv")
    f, ax = fig()
    v = h.deposits_hkt / h.deposits_hkt.mean()
    ax.bar(h.hour_utc, v, color=[ORANGE if 9 <= i <= 18 else BLUE for i in h.hour_utc])
    ax.axhline(1, color=MUTED, lw=0.8)
    ax.set_xlabel("hour of day in UTC+8 (orange = Hong Kong office hours)")
    ax.set_ylabel("deposits vs hourly mean")
    ax.set_xticks(range(0, 24, 3))
    save(f, "c04_hours", SRC_CHAIN)


def c05_definitions():
    d = pd.read_csv(PROC / "onchain_r2_definitions.csv", parse_dates=[0], index_col=0)
    f, ax = fig()
    lab = {"A_asof": "list in force on the day", "B_union": "all 8 lists (fixed)", "C_nov": "November list only (fixed)"}
    for (col, c) in zip(["A_asof", "B_union", "C_nov"], [RED, BLUE, GREEN]):
        s = d[col].rolling(7).mean()
        ax.plot(d.index, s / s.dropna().iloc[:7].mean() * 100, color=c, lw=2, label=lab[col])
    ax.axhline(100, color=MUTED, lw=0.8)
    ax.set_ylabel("deposit transfers, index (first week = 100)")
    ax.legend(loc="upper left")
    datefmt(ax)
    save(f, "c05_definitions", SRC_CHAIN)


def c06_coverage():
    c = pd.read_csv(PROC / "onchain_coverage_daily.csv", parse_dates=["date_utc"])
    f, ax = fig()
    for d, col, lab in [("A_asof", RED, "list in force on the day"), ("C_nov", GREEN, "November list")]:
        s = c[c.definition == d].set_index("date_utc").coverage.sort_index()
        ax.plot(s.index, s * 100, color=col, lw=1.8, label=lab)
    ax.set_ylabel("% of wallet senders that are listed")
    ax.set_ylim(0, None)
    ax.legend()
    datefmt(ax)
    save(f, "c06_coverage", SRC_CHAIN + " - token transfers")


def c07_exclusions(Fd):
    r = Fd["real"]["r2"]
    lab = ["failed tx", "zero-value", "dust < 1 USDT/USDC\n(address poisoning)", "internal\nBinance-to-Binance",
           "kept (clean)"]
    v = [r["excl_failed_share"], r["excl_zero_value_share"], r["excl_dust_share"], r["excl_internal_share"],
         r["clean_share"]]
    f, ax = fig()
    ax.barh(lab[::-1], np.array(v[::-1]) * 100, color=[GREEN, SAND, SAND, SAND, SAND])
    for i, x in enumerate(v[::-1]):
        ax.text(x * 100 + 0.5, i, f"{x:.1%}", va="center", fontsize=9)
    ax.set_xlabel("% of rows touching a listed address")
    save(f, "c07_exclusions", SRC_CHAIN)


def c08_retention():
    c = pd.read_csv(PROC / "onchain_r3_retention_curve.csv")
    f, ax = fig(6.6, 2.9)
    ax.fill_between(c.weeks_since, c.lo * 100, c.hi * 100, color=BLUE, alpha=0.2)
    ax.plot(c.weeks_since, c.retention * 100, color=BLUE, marker="o")
    ax.set_xlabel("weeks after first seen")
    ax.set_ylabel("% of addresses seen again")
    ax.set_ylim(0, None)
    save(f, "c08_retention", SRC_CHAIN + " - cohorts from 20 Jul (8-week burn-in)")


def c09_heatmap():
    c = pd.read_csv(PROC / "onchain_address_cohorts.csv", parse_dates=["cohort_week"])
    c["r"] = c.active_addresses / c.cohort_size
    p = c[c.weeks_since > 0].pivot(index="cohort_week", columns="weeks_since", values="r")
    f, ax = fig(6.6, 2.9)
    im = ax.imshow(p.values * 100, aspect="auto", cmap="Blues", vmin=0)
    ax.set_yticks(range(len(p)), [d.strftime("%d %b") for d in p.index], fontsize=7)
    ax.set_xticks(range(len(p.columns)), p.columns)
    ax.set_xlabel("weeks after first seen")
    ax.grid(False)
    f.colorbar(im, ax=ax, label="% seen again")
    save(f, "c09_heatmap", SRC_CHAIN)


def c10_market():
    d = pd.read_csv(PROC / "onchain_r1_daily.csv", parse_dates=["date_utc"]).set_index("date_utc")
    m = pd.read_csv(PROC / "market_daily.csv", parse_dates=["date"])
    b = m[m.symbol == "BTCUSDT"].set_index("date")
    j = d.join(b[["close", "quote_volume"]], how="inner")
    f, ax = fig(6.6, 2.9)
    ax.scatter(j.quote_volume / 1e9, j.deposits, s=12, color=BLUE, alpha=0.6)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("BTCUSDT daily quote volume on Binance (USDT bn, log)")
    ax.set_ylabel("deposit transfers (log)")
    save(f, "c10_market", "Source: Binance official klines (data.binance.vision) x Ethereum deposits")


def c11_btc():
    m = pd.read_csv(PROC / "market_daily.csv", parse_dates=["date"])
    b = m[(m.symbol == "BTCUSDT") & (m.date >= "2026-05-25")].set_index("date")
    f, ax = fig(6.6, 2.9)
    ax.plot(b.index, b.close / 1e3, color=INK, lw=1.6)
    ax.axvspan(pd.Timestamp("2026-08-24"), pd.Timestamp("2026-11-22"), color=SAND, alpha=0.15)
    ax.text(pd.Timestamp("2026-08-27"), b.close.max() / 1e3 * 0.98, "simulated window", fontsize=8, color=MUTED)
    ax.set_ylabel("BTCUSDT close (thousand USDT)")
    datefmt(ax)
    save(f, "c11_btc", "Source: Binance official daily klines (data.binance.vision), SHA-256 checked")


def c12_calendar_types():
    c = pd.read_csv(PROC / "calendar_by_type_month.csv", parse_dates=["month"])
    p = c.pivot(index="month", columns="type", values="announcements").fillna(0)
    order = p.sum().sort_values(ascending=False).index
    p = p[order]
    f, ax = fig()
    bottom = np.zeros(len(p))
    cols = PALETTE + ["#9C9A94", "#C9C6BD", "#D8C9A8"]
    for i, t in enumerate(p.columns):
        ax.bar(p.index, p[t], width=20, bottom=bottom, color=cols[i % len(cols)], label=t.replace("_", " "))
        bottom += p[t].values
    ax.set_ylabel("announcements per month")
    ax.legend(ncol=2, fontsize=7.5, loc="upper left")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    save(f, "c12_calendar_types", "Source: Binance 'Latest Activities' announcements (750), classified by written rules")


def c13_overlap():
    o = pd.read_csv(PROC / "calendar_overlap_daily.csv", parse_dates=["date_utc"])
    f, ax = fig()
    ax.fill_between(o.date_utc, o.active_promotions, color=BLUE, alpha=0.35, step="mid")
    ax.plot(o.date_utc, o.active_usd_stable_deposit_earn, color=ORANGE, lw=1.4,
            label="of which USDT/USDC deposit or Earn")
    ax.set_ylabel("promotions running on the day")
    ax.legend(loc="upper left")
    datefmt(ax)
    save(f, "c13_overlap", "Source: promotion periods read in 372 Binance announcements (UTC)")


def c14_event_study():
    e = pd.read_csv(PROC / "event_study_real_campaigns.csv")
    pl = pd.read_csv(PROC / "event_study_placebo.csv")
    f, ax = fig()
    vals = pl["USDT"].dropna()
    ax.hist(np.expm1(vals) * 100, bins=40, color=SAND, alpha=0.8, label="1,000 random dates (placebo)")
    for v in e[e.asset == "USDT"].effect:
        ax.axvline(v * 100, color=BLUE, lw=1.2, alpha=0.8)
    ax.plot([], [], color=BLUE, label="real USDT deposit/Earn campaign starts")
    ax.set_xlabel("change in active USDT deposit addresses, 7 d after vs 14 d before (%, market-adjusted)")
    ax.legend(fontsize=8)
    save(f, "c14_event_study", SRC_CHAIN + " x Binance announcements")


# ------------------------------------------------------------------ simulated
def c15_cac_roi():
    s = pd.read_csv(PROC / "campaign_scorecard.csv").dropna(subset=["roi_30d", "cac_first_deposit"])
    f, ax = fig()
    col = [RED if c == "CMP014" else (GREEN if r > 0 else MUTED) for c, r in zip(s.campaign_id, s.roi_30d)]
    ax.scatter(s.cac_first_deposit, s.roi_30d * 100, s=np.clip(s.attributed_first_depositors / 30, 20, 300),
               color=col, alpha=0.8)
    for r in s.itertuples():
        if r.campaign_id in ("CMP014", "CMP006", "CMP012"):
            ax.annotate(r.campaign_id, (r.cac_first_deposit, r.roi_30d * 100), fontsize=8, xytext=(4, 4),
                        textcoords="offset points")
    ax.axhline(0, color=INK, lw=0.8)
    ax.set_xlabel("CAC per first depositor (USD, attributed)")
    ax.set_ylabel("30-day ROI (%)")
    save(f, "c15_cac_roi", SRC_SIM + " - bubble size = first depositors")


def c16_cmp014():
    d = sa.q("""SELECT signup_date_utc d, count(*) n FROM stg_users WHERE region = 'LATAM-BR' GROUP BY 1 ORDER BY 1""")
    f, ax = fig()
    ax.plot(pd.to_datetime(d.d), d.n, color=BLUE)
    ax.axvspan(pd.Timestamp("2026-10-05"), pd.Timestamp("2026-10-25"), color=ORANGE, alpha=0.15)
    ax.text(pd.Timestamp("2026-10-06"), d.n.max() * 0.95, "CMP014 boosted rate", fontsize=8, color=ORANGE)
    ax.set_ylabel("LATAM-BR sign-ups per day")
    datefmt(ax)
    save(f, "c16_cmp014", SRC_SIM)


def c17_farm():
    a = sa.q("SELECT * FROM referral_abuse_indicators")
    f, ax = fig()
    flagged = a["flags"] >= 3
    ax.scatter(a.share_shared_device[~flagged] * 100, a.kyc_pass_share[~flagged] * 100, s=14, color=MUTED,
               label="other referrers (>= 20 referees)")
    ax.scatter(a.share_shared_device[flagged] * 100, a.kyc_pass_share[flagged] * 100, s=22, color=RED,
               label="flagged: >= 3 of 4 indicators")
    ax.set_xlabel("% of referees on a shared device")
    ax.set_ylabel("% of referees passing KYC")
    ax.legend(fontsize=8)
    save(f, "c17_farm", SRC_SIM)


def c18_competition():
    p = sa.outcome_panel("trades")
    s = pd.Timestamp(F()["sim"]["events"]["E6"]["start"])
    w = p[s - pd.Timedelta(days=21):s + pd.Timedelta(days=13)]
    f, ax = fig(6.6, 2.9)
    ctrl = w.drop(columns="EU").sum(axis=1)
    ax.plot(w.index, w.EU / w.EU[:s - pd.Timedelta(days=1)].tail(7).mean() * 100, color=ORANGE, lw=2,
            label="EU (trading competition)")
    ax.plot(w.index, ctrl / ctrl[:s - pd.Timedelta(days=1)].tail(7).mean() * 100, color=BLUE, lw=2,
            label="8 other regions (no competition)")
    ax.axvspan(s, s + pd.Timedelta(days=2), color=SAND, alpha=0.3)
    ax.set_ylabel("trades, index (7 days before = 100)")
    ax.legend(fontsize=8)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    save(f, "c18_competition", SRC_SIM + " - competition starts on the real most volatile BTC day")


def c19_simpson():
    r = pd.read_csv(PROC / "retention_by_channel_month.csv", parse_dates=["dep_month"])
    r = r[r.dep_month.isin([pd.Timestamp("2026-09-01"), pd.Timestamp("2026-10-01")])]
    p = r.pivot(index="channel", columns="dep_month", values="retention_d30") * 100
    p.columns = ["Sep", "Oct"]
    p = p.loc[[c for c in p.index if c != "ALL"] + ["ALL"]]
    f, ax = fig(6.6, 2.9)
    for i, (ch, row) in enumerate(p.iterrows()):
        c = RED if ch == "ALL" else (GREEN if row.Oct > row.Sep else RED)
        ax.plot([0, 1], [row.Sep, row.Oct], color=c, lw=3 if ch == "ALL" else 1.5, marker="o")
        ax.text(1.03, row.Oct, ch.replace("_", " ") + (" (overall)" if ch == "ALL" else ""), va="center", fontsize=8)
    ax.set_xticks([0, 1], ["September cohort", "October cohort"])
    ax.set_xlim(-0.1, 1.6)
    ax.set_ylabel("30-day retention of new depositors (%)")
    save(f, "c19_simpson", SRC_SIM)


def c20_claims():
    c = sa.q("SELECT * FROM partner_claims WHERE region_group = 'LATAM'").iloc[0]
    f, ax = fig()
    vals = [c.claimed_affiliate_kol, c.claimed_paid_social, c.real_signups_touched]
    ax.bar([0], [vals[0] / 1e3], color=PURPLE, label="claimed by affiliate/KOL partners")
    ax.bar([0], [vals[1] / 1e3], bottom=[vals[0] / 1e3], color=ORANGE, label="claimed by paid-social partners")
    ax.bar([1], [vals[2] / 1e3], color=BLUE, label="real sign-ups they touched")
    ax.set_xticks([0, 1], ["partner reports", "user-level paths"])
    ax.set_ylabel("LATAM sign-ups (thousands)")
    ax.legend(fontsize=8)
    save(f, "c20_claims", SRC_SIM)


def c21_kyc():
    k = sa.q("SELECT * FROM kyc_daily_region WHERE date_utc BETWEEN DATE '2026-09-20' AND DATE '2026-10-25'")
    f, ax = fig()
    for reg, g in k.groupby("region"):
        ax.plot(pd.to_datetime(g.date_utc), g.pass_rate * 100, color=RED if reg == "TR" else GRID,
                lw=2 if reg == "TR" else 1, zorder=3 if reg == "TR" else 1)
    ax.set_ylabel("KYC pass rate (%) - TR in red")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    save(f, "c21_kyc", SRC_SIM)


def c22_cac():
    c = pd.read_csv(PROC / "cac_weekly.csv", parse_dates=["week"])
    f, ax = fig(6.6, 2.9)
    ax.plot(c.week, c.cac_booking, color=RED, marker="o", label="by booking date (finance)")
    ax.plot(c.week, c.cac_activity, color=BLUE, marker="o", label="by activity date (growth)")
    ax.set_ylabel("weekly CAC per first depositor (USD)")
    ax.legend(fontsize=8)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    save(f, "c22_cac", SRC_SIM)


def c23_methods():
    m = pd.read_csv(PROC / "methods_vs_truth.csv").set_index("method")
    m = m.loc[[x for x in ["naive", "did", "synthetic", "randomised_holdout"] if x in m.index]]
    f, ax = fig(6.6, 2.9)
    lab = {"naive": "naive before/after", "did": "difference-in-differences", "synthetic": "synthetic control",
           "randomised_holdout": "randomised holdout (CRM)"}
    y = np.arange(len(m))
    ax.barh(y, m.mean_abs_error * 100, color=[RED, BLUE, BLUE, GREEN][:len(m)])
    for i, (e, c, n) in enumerate(zip(m.mean_abs_error, m.coverage, m.campaigns)):
        ax.text(e * 100 + 0.5, i, f"{e * 100:.1f} pts | CI covers truth {c:.0%} | n={n}", va="center", fontsize=8)
    ax.set_yticks(y, [lab[i] for i in m.index])
    ax.invert_yaxis()
    ax.set_xlabel("mean absolute error vs the planted effect (percentage points)")
    ax.set_xlim(0, m.mean_abs_error.max() * 100 * 1.9)
    save(f, "c23_methods", SRC_SIM + " - checked against the hidden truth after the analysis")


def c24_backtest():
    a = pd.read_csv(PROC / "monitoring_backtest.csv", parse_dates=["date"])
    f, ax = fig(6.6, 2.9)
    series = sorted(a.series.unique())
    col = {"true alert": GREEN, "false alert": RED, "explained false alert": ORANGE}
    for lab, g in a.groupby("label"):
        ax.scatter(g.date, [series.index(s) for s in g.series], color=col[lab], s=40, label=lab)
    ax.set_yticks(range(len(series)), series, fontsize=8)
    ax.legend(fontsize=8, loc="lower left")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    save(f, "c24_backtest", SRC_SIM + " - alert rules replayed day by day over 13 weeks")


def c25_crm():
    e = F()["sim"]["crm"]
    ids = sorted(e)
    f, ax = fig(6.6, 2.9)
    for i, cid in enumerate(ids):
        r = e[cid]
        ax.errorbar(r["cuped_diff"] * 100, i, xerr=[[(r["cuped_diff"] - r["cuped_lo"]) * 100],
                                                     [(r["cuped_hi"] - r["cuped_diff"]) * 100]],
                    fmt="o", color=GREEN if r["cuped_lo"] > 0 else MUTED, capsize=3)
    ax.axvline(0, color=INK, lw=0.8)
    ax.set_yticks(range(len(ids)), ids)
    ax.set_xlabel("14-day reactivation, treatment minus holdout (points, CUPED, 95% CI)")
    save(f, "c25_crm", SRC_SIM)


ALL = [c01_por_list, c02_flows, c03_assets, c04_hours, c05_definitions, c06_coverage, c08_retention, c09_heatmap,
       c10_market, c11_btc, c12_calendar_types, c13_overlap, c14_event_study, c15_cac_roi, c16_cmp014, c17_farm,
       c18_competition, c19_simpson, c20_claims, c21_kyc, c22_cac, c23_methods, c24_backtest, c25_crm]

if __name__ == "__main__":
    Fd = F()
    for fn in ALL:
        fn()
    c07_exclusions(Fd)
    print(f"[charts] {len(ALL) + 1} charts in report/img")
