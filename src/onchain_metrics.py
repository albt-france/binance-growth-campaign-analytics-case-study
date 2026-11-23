"""PUBLIC DATA: Binance flows on Ethereum (R1-R5) and the event study of real campaigns (6.2).

Reads the DuckDB warehouse built by src/run_sql.py (tables of sql/10_onchain and sql/30_campaigns/305) and
the official market data. Writes aggregated CSVs to data/processed/ and returns a dict for findings.py.

What the data measure: deposits and withdrawals on ETHEREUM ONLY, to and from the addresses Binance
published in its Proof of Reserves. An address is not a user; a "new" address is not a new customer.
"""
import hashlib
import time
from functools import lru_cache
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

import stats

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "warehouse.duckdb"
PROC = ROOT / "data" / "processed"
USDT_SHA256 = "63cbd95b98536412d438ab18ed85c35e326b10e413d89033ba7143f1744abecf"   # SHA-256 of the USDT (ERC-20) contract address (no address in the repo)
FIRST4 = ("2026-05-25", "2026-06-21")       # first 4 weeks of the window
LAST4 = ("2026-10-26", "2026-11-22")        # last 4 weeks


@lru_cache(maxsize=1)
def con():
    c = duckdb.connect(str(DB), read_only=True)
    c.sql("SET enable_progress_bar=false")
    c.sql(f"SET file_search_path='{ROOT.as_posix()}'")
    return c


def q(sql):
    return con().sql(sql).df()


def daily(definition="B_union", flows=("deposit",), assets=None, col="n_transfers") -> pd.Series:
    f = "','".join(flows)
    a = ("AND asset IN ('" + "','".join(assets) + "')") if assets else ""
    s = q(f"""SELECT date_utc, sum({col}) AS v FROM onchain_daily
              WHERE definition = '{definition}' AND flow IN ('{f}') {a} GROUP BY 1 ORDER BY 1""")
    return s.set_index(pd.to_datetime(s.date_utc))["v"].asfreq("D")


def change(s: pd.Series) -> float:
    return float(s[FIRST4[0]:FIRST4[1]].mean() and s[LAST4[0]:LAST4[1]].mean() / s[FIRST4[0]:FIRST4[1]].mean() - 1)


# ------------------------------------------------------------------ R1 activity
def r1():
    dep = daily()
    wd = daily(flows=("withdrawal",))
    dep_addr = daily(col="n_receivers")
    swept = daily(flows=("sweep", "to_wallet_unlisted"), col="n_senders")   # disjoint sets -> exact sum
    tok = q("""SELECT asset, sum(n_transfers) AS n FROM onchain_daily
               WHERE definition = 'B_union' AND flow = 'deposit' GROUP BY 1""").set_index("asset")["n"]
    dow = dep.groupby(dep.index.dayofweek).mean()
    hp = q("SELECT * FROM onchain_hourly_profile ORDER BY hour_utc")
    hk = hp.set_index("hour_utc")["deposits_hkt"]          # deposits_hkt is indexed by the UTC+8 hour
    out = pd.DataFrame({"deposits": dep, "withdrawals": wd, "active_deposit_addresses": dep_addr,
                        "swept_addresses": swept})
    out.index.name = "date_utc"
    out.to_csv(PROC / "onchain_r1_daily.csv")
    return {
        "days": int(dep.notna().sum()),
        "deposits_per_day": float(dep.mean()), "withdrawals_per_day": float(wd.mean()),
        "active_deposit_addresses_per_day": float(dep_addr.mean()), "swept_addresses_per_day": float(swept.mean()),
        "deposits_change_first_vs_last_4w": change(dep), "withdrawals_change_first_vs_last_4w": change(wd),
        "usdt_share_of_deposit_transfers": float(tok.get("USDT", 0) / tok.sum()),
        "usdc_share_of_deposit_transfers": float(tok.get("USDC", 0) / tok.sum()),
        "eth_share_of_deposit_transfers": float(tok.get("ETH", 0) / tok.sum()),
        "weekend_vs_weekday": float(dow[[5, 6]].mean() / dow[[0, 1, 2, 3, 4]].mean() - 1),
        "peak_hour_hkt": int(hk.idxmax()), "trough_hour_hkt": int(hk.idxmin()),
        "peak_to_trough_hkt": float(hk.max() / hk.min()),
        "withdrawals_to_deposits": float(wd.sum() / dep.sum()),
    }


# ------------------------------------------------------------------ R2 counting
def r2():
    res = {}
    for d in ("A_asof", "B_union", "C_nov"):
        s = daily(d)
        res[f"deposits_change_{d}"] = change(s)
        res[f"deposits_per_day_{d}"] = float(s.mean())
    res["fake_growth_pts"] = res["deposits_change_A_asof"] - res["deposits_change_B_union"]
    cov = q("SELECT * FROM onchain_coverage_daily ORDER BY date_utc")
    cov["date_utc"] = pd.to_datetime(cov.date_utc)
    for d in ("A_asof", "C_nov"):
        c = cov[cov.definition == d].set_index("date_utc")["coverage"]
        res[f"coverage_first4w_{d}"] = float(c[FIRST4[0]:FIRST4[1]].mean())
        res[f"coverage_last4w_{d}"] = float(c[LAST4[0]:LAST4[1]].mean())
    c20 = cov[(cov.definition == "C_nov") & (cov.date_utc == "2026-11-20")]
    res["coverage_20nov_clean"] = float(c20.coverage.iloc[0]) if len(c20) else None
    raw = q("""SELECT count(DISTINCT from_address) FILTER (WHERE from_address IN (SELECT address FROM addr_nov
                                                                               WHERE kind = 'dep')) AS listed,
                      count(DISTINCT from_address) AS senders
               FROM stg_tt WHERE date_utc = DATE '2026-11-20'
                 AND to_address IN (SELECT address FROM addr_nov WHERE kind = 'hot')""").iloc[0]
    res["coverage_20nov_raw"] = float(raw.listed / raw.senders)        # reference definition (raw counts)
    res["coverage_20nov_raw_listed"], res["coverage_20nov_raw_senders"] = int(raw.listed), int(raw.senders)
    ex = q("""SELECT sum(rows_all) a, sum(rows_failed) f, sum(rows_zero_value) z, sum(rows_dust) du,
                     sum(rows_internal) i, sum(rows_clean) c FROM onchain_exclusions_daily
                     WHERE definition = 'B_union'""").iloc[0]
    res.update({"excl_failed_share": float(ex.f / ex.a), "excl_zero_value_share": float(ex.z / ex.a),
                "excl_dust_share": float(ex.du / ex.a),
                "excl_internal_share": float(ex.i / ex.a), "clean_share": float(ex.c / ex.a)})
    snaps = q("SELECT * FROM stg_por_snapshots ORDER BY snapshot_date")
    res["list_deposit_first"] = int(snaps.n_deposit_addresses.iloc[0])
    res["list_deposit_last"] = int(snaps.n_deposit_addresses.iloc[-1])
    res["list_wallets_first"] = int(snaps.n_hot_cold_wallets.iloc[0])
    res["list_wallets_last"] = int(snaps.n_hot_cold_wallets.iloc[-1])
    res["list_deposit_max"] = int(snaps.n_deposit_addresses.max())
    pd.DataFrame({d: daily(d) for d in ("A_asof", "B_union", "C_nov")}).to_csv(PROC / "onchain_r2_definitions.csv")
    return res


# ------------------------------------------------------------------ R3 cohorts
def r3(seed=42):
    c = q("SELECT * FROM onchain_address_cohorts")
    c["retention"] = c.active_addresses / c.cohort_size
    rng = np.random.default_rng(seed)
    rows = []
    for k in range(1, 13):
        g = c[c.weeks_since == k]
        if g.empty:
            continue
        n, x = g.cohort_size.sum(), g.active_addresses.sum()
        # bootstrap of addresses: resampling n addresses with replacement = binomial(n, p) per replicate
        reps = rng.binomial(n, x / n, 2000) / n
        rows.append({"weeks_since": k, "cohorts": len(g), "addresses": int(n), "retention": x / n,
                     "lo": np.quantile(reps, 0.025), "hi": np.quantile(reps, 0.975)})
    curve = pd.DataFrame(rows)
    curve.to_csv(PROC / "onchain_r3_retention_curve.csv", index=False)
    sizes = c[c.weeks_since == 0][["cohort_week", "cohort_size"]]
    return {"cohorts": int(len(sizes)), "median_cohort_size": float(sizes.cohort_size.median()),
            "retention_w1": float(curve.retention.iloc[0]) if len(curve) else None,
            "retention_w4": float(curve.set_index("weeks_since").retention.get(4, np.nan)),
            "retention_w8": float(curve.set_index("weeks_since").retention.get(8, np.nan)),
            "retention_w12": float(curve.set_index("weeks_since").retention.get(12, np.nan))}


# ------------------------------------------------------------------ R4 market
def market() -> pd.DataFrame:
    m = q("""SELECT date_utc, symbol, abs_log_return, quote_volume FROM stg_market
             WHERE symbol IN ('BTCUSDT', 'ETHUSDT')""")
    m = m.pivot(index="date_utc", columns="symbol", values=["abs_log_return", "quote_volume"])
    m.columns = [f"{a}_{b}" for a, b in m.columns]
    m.index = pd.to_datetime(m.index)
    return m


def r4():
    m = market()
    y = pd.DataFrame({"deposits": daily(), "withdrawals": daily(flows=("withdrawal",))}).join(m, how="inner").dropna()
    out = {}
    for target in ("deposits", "withdrawals"):
        d = y.copy()
        d["ly"] = np.log(d[target])
        d["lvol"] = np.log(d["quote_volume_BTCUSDT"])
        X = pd.concat([pd.Series(1.0, index=d.index, name="const"),
                       d[["abs_log_return_BTCUSDT", "lvol"]],
                       pd.get_dummies(d.index.dayofweek, prefix="dow", drop_first=True, dtype=float).set_index(d.index)],
                      axis=1)
        beta, se, _ = stats.ols_cluster(d["ly"].values, X.values, np.arange(len(d)))   # 1 obs per cluster = HC1
        r2 = 1 - np.sum((d.ly - X.values @ beta) ** 2) / np.sum((d.ly - d.ly.mean()) ** 2)
        i = list(X.columns).index("lvol")
        out[f"{target}_elasticity_btc_volume"] = float(beta[i])
        out[f"{target}_elasticity_se"] = float(se[i])
        out[f"{target}_r2"] = float(r2)
        out[f"{target}_corr_btc_abs_return"] = float(d[target].corr(d["abs_log_return_BTCUSDT"]))
        out[f"{target}_corr_btc_volume"] = float(d[target].corr(d["quote_volume_BTCUSDT"]))
    btc = q("SELECT date_utc, open, close FROM stg_market WHERE symbol = 'BTCUSDT'").set_index("date_utc")
    btc.index = pd.to_datetime(btc.index)
    out["btc_open_1oct"] = float(btc.loc["2026-10-01", "open"])
    out["btc_open_22nov"] = float(btc.loc["2026-11-22", "open"])
    out["btc_change_1oct_22nov"] = out["btc_open_22nov"] / out["btc_open_1oct"] - 1
    sim = m.loc["2026-08-24":"2026-11-22", "abs_log_return_BTCUSDT"]
    out["most_volatile_day_sim_window"] = str(sim.idxmax().date())
    out["most_volatile_day_abs_return"] = float(sim.max())
    return out


def residual_series(series: pd.Series) -> pd.Series:
    """Market- and weekday-adjusted series: exp(residual of log(series) on BTC volume, |return|, weekday)."""
    m = market()
    d = pd.DataFrame({"y": series}).join(m, how="inner").dropna()
    d = d[d.y > 0]
    X = pd.concat([pd.Series(1.0, index=d.index, name="c"), np.log(d["quote_volume_BTCUSDT"]),
                   d["abs_log_return_BTCUSDT"],
                   pd.get_dummies(d.index.dayofweek, prefix="dow", drop_first=True, dtype=float).set_index(d.index)],
                  axis=1).values
    beta, *_ = np.linalg.lstsq(X, np.log(d.y.values), rcond=None)
    return pd.Series(np.exp(np.log(d.y.values) - X @ beta), index=d.index).asfreq("D")


# ------------------------------------------------------------------ 6.2 event study
def event_study(n_placebo=1000):
    cal = q("SELECT * FROM stg_calendar")
    cal["release_ts_utc"] = pd.to_datetime(cal.release_ts_utc)
    cal["start"] = pd.to_datetime(cal.period_start_utc).fillna(cal.release_ts_utc).dt.normalize()
    cal["start_from_period"] = cal.period_start_utc.notna()
    ev = cal[cal.type.isin(["deposit", "earn_apr"]) & cal.asset.isin(["USDT", "USDC"])
             & (cal.start >= "2026-06-08") & (cal.start <= "2026-11-15")].copy()
    rows, placebo = [], {}
    for asset in ("USDT", "USDC"):
        # active deposit addresses of the asset (fixed list B): addresses receiving a clean deposit that day
        s = q(f"""SELECT date_utc, sum(n_receivers) AS v FROM onchain_daily WHERE definition = 'B_union'
                  AND flow = 'deposit' AND asset = '{asset}' GROUP BY 1 ORDER BY 1""")
        s = s.set_index(pd.to_datetime(s.date_utc))["v"].asfreq("D")
        res = residual_series(s)
        e = ev[ev.asset == asset]
        obs, plac, p, mde = stats.event_study_placebo(res.dropna(), e.start.values, pre=14, post=7,
                                                      n_placebo=n_placebo)
        placebo[asset] = plac
        for (code, st, fp), o, pv in zip(e[["article_code", "start", "start_from_period"]].values, obs, p):
            rows.append({"article_code": code, "asset": asset, "start": st.date(), "start_from_period": fp,
                         "log_effect": o, "effect": np.expm1(o), "p_placebo": pv, "mde": np.expm1(mde)})
    out = pd.DataFrame(rows).dropna(subset=["log_effect"])
    if len(out):
        out["q_bh"] = stats.benjamini_hochberg(out.p_placebo.values)
    out.to_csv(PROC / "event_study_real_campaigns.csv", index=False)
    pd.DataFrame({k: pd.Series(v) for k, v in placebo.items()}).to_csv(PROC / "event_study_placebo.csv", index=False)
    ov = q("SELECT * FROM calendar_overlap_daily")
    return {"events": int(len(out)), "events_usdt": int((out.asset == "USDT").sum()),
            "events_usdc": int((out.asset == "USDC").sum()),
            "share_start_from_period": float(out.start_from_period.mean()) if len(out) else None,
            "significant_raw_p05": int((out.p_placebo < 0.05).sum()), "significant_bh_q10": int((out.q_bh < 0.10).sum()),
            "mde_usdt": float(out[out.asset == "USDT"].mde.iloc[0]) if (out.asset == "USDT").any() else None,
            "mde_usdc": float(out[out.asset == "USDC"].mde.iloc[0]) if (out.asset == "USDC").any() else None,
            "median_abs_effect": float(out.effect.abs().median()) if len(out) else None,
            "mean_active_promotions": float(ov.active_promotions.mean()),
            "max_active_promotions": int(ov.active_promotions.max())}


def calendar_summary():
    c = q("SELECT * FROM stg_calendar")
    c["release_ts_utc"] = pd.to_datetime(c.release_ts_utc)
    since = c[c.release_ts_utc >= "2026-05-25"]
    window = c[(c.release_ts_utc >= "2026-08-24") & (c.release_ts_utc < "2026-11-23")]
    types = since.type.value_counts(normalize=True)
    chk = pd.read_csv(PROC / "campaign_taxonomy_check.csv").set_index("check")["accuracy"]
    return {"announcements": int(len(c)), "since_25may": int(len(since)), "in_sim_window": int(len(window)),
            "first": str(c.release_ts_utc.min().date()), "last": str(c.release_ts_utc.max().date()),
            "detail_in_scope": int(c.detail_in_scope.sum()), "detail_read": int(c.detail_read.sum()),
            "period_found": int(since.period_start_utc.notna().sum()),
            "type_shares_since_25may": {k: round(float(v), 4) for k, v in types.items()},
            "region_stated_share": float((since.region != "not stated").mean()),
            "taxonomy_dev_v1": float(chk.iloc[0]), "taxonomy_dev_v2": float(chk.iloc[1]),
            "taxonomy_fresh_v2": float(chk.iloc[2])}


# ------------------------------------------------------------------ R5 quality and performance notes
def r5():
    qd = q("SELECT * FROM onchain_quality_daily ORDER BY date_utc")
    late = qd[qd.hours_after_day_end > 6]
    # wallet gap: days when clean transfers INTO listed wallets fall under 30% of the previous 14-day median
    # while deposits to listed deposit addresses continue (consistent with wallets absent from every list)
    w = q("""SELECT date_utc, count(*) FILTER (WHERE kt = 'hot') AS into_w, count(*) FILTER (WHERE flow = 'deposit') AS dep
             FROM onchain_classified WHERE definition = 'B_union' AND succeeded AND NOT zero_value
             GROUP BY 1 ORDER BY 1""")
    w["ratio"] = w.into_w / w.into_w.rolling(14, min_periods=5).median().shift(1)
    w["dep_ratio"] = w.dep / w.dep.rolling(14, min_periods=5).median().shift(1)
    gap = w[w.ratio < 0.3]
    w.to_csv(PROC / "onchain_wallet_inflows_daily.csv", index=False)
    return {"days": int(len(qd)), "max_hours_late": float(qd.hours_after_day_end.max()),
            "latest_day": str(qd.loc[qd.hours_after_day_end.idxmax(), "date_utc"])[:10],
            "days_late_over_6h": int(len(late)), "late_days": [str(d)[:10] for d in late.date_utc],
            "duplicate_hash_days": int((qd.tx_duplicate_hash > 0).sum()),
            "duplicate_hash_rows": int(qd.tx_duplicate_hash.sum()),
            "tx_total_mean": float(qd.tx_total.mean()), "tt_total_mean": float(qd.tt_total.mean()),
            "zero_value_share_all_transfers": float(qd.tt_zero_value.sum() / qd.tt_total.sum()),
            "failed_share_all_tx": float(qd.tx_failed.sum() / qd.tx_total.sum()),
            "mb_read_total_gb": float(qd.mb_read.sum() / 1000), "extract_hours_total": float(qd.seconds.sum() / 3600),
            "outlier_days_z3": int((qd.tx_total_z.abs() > 3).sum()),
            "wallet_gap_days": [str(d)[:10] for d in gap.date_utc],
            "wallet_gap_min_ratio": float(gap.ratio.min()) if len(gap) else None,
            "wallet_gap_max_ratio": float(gap.ratio.max()) if len(gap) else None,
            "wallet_gap_deposit_ratio_mean": float(gap.dep_ratio.mean()) if len(gap) else None}


def approx_vs_exact():
    """Measured error and time of approx_count_distinct (HyperLogLog) vs count(DISTINCT)."""
    t0 = time.time()
    ex = q("""SELECT date_utc, count(DISTINCT from_id) AS n FROM onchain_classified
              WHERE definition = 'B_union' AND kt = 'hot' AND kf <> 'hot' GROUP BY 1""")
    t1 = time.time()
    ap = q("""SELECT date_utc, approx_count_distinct(from_id) AS n FROM onchain_classified
              WHERE definition = 'B_union' AND kt = 'hot' AND kf <> 'hot' GROUP BY 1""")
    t2 = time.time()
    m = ex.merge(ap, on="date_utc", suffixes=("_exact", "_approx"))
    err = (m.n_approx / m.n_exact - 1).abs()
    return {"mean_abs_error": float(err.mean()), "max_abs_error": float(err.max()),
            "seconds_exact": round(t1 - t0, 2), "seconds_approx": round(t2 - t1, 2)}


def crosscheck_pandas(days=("2026-06-15", "2026-09-21", "2026-11-20")):
    """Second method: recompute clean USDT deposits and distinct USDT wallet senders for 3 days, pandas only.
    Clean = value of at least 1 USDT (6 decimals: raw value >= 1e6), i.e. zero-value and dust excluded."""
    union = pd.read_parquet(ROOT / "data" / "raw" / "por" / "eth_addr_union.parquet")
    kind = pd.Series(np.where(union.is_hotcold, "hot", "dep"), index=union.address)
    rows = []
    for d in days:
        p = ROOT / "data" / "raw" / "onchain" / f"date={d}" / "tt.parquet"
        if not p.exists():
            continue
        tt = pd.read_parquet(p, columns=["token_address", "from_address", "to_address", "value"])
        tt = tt[(tt.value >= 1e6) & (tt.token_address.map(lambda a: hashlib.sha256(a.encode()).hexdigest()) == USDT_SHA256)]
        kf, kt = tt.from_address.map(kind).fillna("ext"), tt.to_address.map(kind).fillna("ext")
        dep_pd = int(((kf == "ext") & (kt == "dep")).sum())
        snd_pd = int(tt.from_address[(kt == "hot") & (kf != "hot")].nunique())
        sql = q(f"""SELECT sum(n_transfers) FILTER (WHERE flow = 'deposit') AS dep,
                           sum(n_senders) FILTER (WHERE flow IN ('sweep', 'to_wallet_unlisted')) AS snd
                    FROM onchain_daily WHERE definition = 'B_union' AND date_utc = DATE '{d}'
                    AND asset = 'USDT'""").iloc[0]
        rows.append({"date": d, "deposits_pandas": dep_pd, "deposits_sql": int(sql.dep),
                     "senders_pandas": snd_pd, "senders_sql": int(sql.snd),
                     "match": dep_pd == int(sql.dep) and snd_pd == int(sql.snd)})
    return rows


def run_all() -> dict:
    return {"r1": r1(), "r2": r2(), "r3": r3(), "r4": r4(), "r5": r5(), "calendar": calendar_summary(),
            "event_study": event_study(), "approx_vs_exact": approx_vs_exact(), "crosscheck": crosscheck_pandas()}


if __name__ == "__main__":
    import json
    print(json.dumps(run_all(), indent=1, default=str)[:4000])
