"""Statistics used by the notebook, the tools and the report. Plain NumPy/SciPy/pandas, one function per
idea, so every number can be re-derived by hand. Sections:

  A. Experiments (copied from an earlier A/B-testing study): sample_size_prop, sample_size_mean, mde_mean,
     prop_test, mean_test, srm_test, adjust_pvalues, cuped, obf_boundary, peeking_fpr
  B. Attribution (copied from an earlier marketing study): transition_counts, removal_effects,
     markov_with_bootstrap, last_click_with_bootstrap, n_per_arm, geo_mde, adstock
  C. Added for this study: wilson, bootstrap_ci, did_clustered, synthetic_control, placebo_in_time,
     kaplan_meier, cusum, control_limits, direct_standardization, benjamini_hochberg, event_study_placebo
"""
import numpy as np
import pandas as pd
from scipy import optimize, signal, stats

Z = stats.norm.ppf

# ============================================================== A. Experiments
def sample_size_prop(p_base, rel_mde, alpha=0.05, power=0.80):
    """n per arm for a two-sided z-test on proportions: n = (z_a/2 + z_b)^2 * (p1 q1 + p2 q2) / (p2 - p1)^2."""
    p2 = p_base * (1 + rel_mde)
    num = (Z(1 - alpha / 2) + Z(power)) ** 2 * (p_base * (1 - p_base) + p2 * (1 - p2))
    return int(np.ceil(num / (p2 - p_base) ** 2))


def sample_size_mean(mean_base, sd, rel_mde, alpha=0.05, power=0.80):
    """n per arm for a two-sided test on means with equal variance: n = 2 (z_a/2 + z_b)^2 sd^2 / delta^2."""
    delta = mean_base * rel_mde
    return int(np.ceil(2 * (Z(1 - alpha / 2) + Z(power)) ** 2 * sd ** 2 / delta ** 2))


def mde_mean(mean_base, sd, n_per_arm, alpha=0.05, power=0.80):
    """Smallest relative lift detectable with n users per arm."""
    return (Z(1 - alpha / 2) + Z(power)) * sd * np.sqrt(2 / n_per_arm) / mean_base


def prop_test(x_t, n_t, x_c, n_c, alpha=0.05):
    p_t, p_c = x_t / n_t, x_c / n_c
    se = np.sqrt(p_t * (1 - p_t) / n_t + p_c * (1 - p_c) / n_c)          # unpooled SE for the CI
    p_pool = (x_t + x_c) / (n_t + n_c)
    se0 = np.sqrt(p_pool * (1 - p_pool) * (1 / n_t + 1 / n_c))            # pooled SE for the test
    z = (p_t - p_c) / se0
    d = p_t - p_c
    zc = Z(1 - alpha / 2)
    rel_se = np.sqrt((p_t * (1 - p_t) / n_t) / p_c ** 2 + (p_t ** 2) * (p_c * (1 - p_c) / n_c) / p_c ** 4)
    return dict(n_t=int(n_t), n_c=int(n_c), rate_t=p_t, rate_c=p_c, diff=d, ci_low=d - zc * se, ci_high=d + zc * se,
                rel=d / p_c, rel_low=d / p_c - zc * rel_se, rel_high=d / p_c + zc * rel_se, z=z, p=2 * stats.norm.sf(abs(z)))


def mean_test(y_t, y_c, alpha=0.05):
    y_t, y_c = np.asarray(y_t, float), np.asarray(y_c, float)
    m_t, m_c = y_t.mean(), y_c.mean()
    v_t, v_c = y_t.var(ddof=1) / len(y_t), y_c.var(ddof=1) / len(y_c)
    se = np.sqrt(v_t + v_c)
    dof = (v_t + v_c) ** 2 / (v_t ** 2 / (len(y_t) - 1) + v_c ** 2 / (len(y_c) - 1))
    t = (m_t - m_c) / se
    tc = stats.t.ppf(1 - alpha / 2, dof)
    d = m_t - m_c
    rel_se = np.sqrt(v_t / m_c ** 2 + m_t ** 2 * v_c / m_c ** 4)             # delta method for (m_t / m_c - 1)
    return dict(n_t=len(y_t), n_c=len(y_c), mean_t=m_t, mean_c=m_c, diff=d, ci_low=d - tc * se, ci_high=d + tc * se,
                rel=d / m_c, rel_low=d / m_c - tc * rel_se, rel_high=d / m_c + tc * rel_se, se=se, t=t,
                p=2 * stats.t.sf(abs(t), dof))


def srm_test(n_t, n_c, expected_t=0.5):
    n = n_t + n_c
    chi2 = (n_t - n * expected_t) ** 2 / (n * expected_t) + (n_c - n * (1 - expected_t)) ** 2 / (n * (1 - expected_t))
    return dict(n_t=int(n_t), n_c=int(n_c), share_t=n_t / n, chi2=chi2, p=stats.chi2.sf(chi2, 1))


def adjust_pvalues(p):
    p = np.asarray(p, float)
    m = len(p)
    order = np.argsort(p)
    bonf = np.minimum(p * m, 1)
    holm = np.empty(m)
    holm[order] = np.minimum(1, np.maximum.accumulate((m - np.arange(m)) * p[order]))
    bh = np.empty(m)
    ranked = p[order] * m / (np.arange(m) + 1)
    bh[order] = np.minimum(1, np.minimum.accumulate(ranked[::-1])[::-1])
    return dict(bonferroni=bonf, holm=holm, bh=bh)


def cuped(y, x, treat):
    """theta = cov(x, y) / var(x) on the pooled sample; y_adj = y - theta (x - mean x). Same mean, smaller variance."""
    y, x, treat = np.asarray(y, float), np.asarray(x, float), np.asarray(treat, bool)
    theta = np.cov(x, y, ddof=1)[0, 1] / x.var(ddof=1)
    y_adj = y - theta * (x - x.mean())
    rho = np.corrcoef(x, y)[0, 1]
    return dict(theta=theta, rho=rho, var_reduction=1 - y_adj.var(ddof=1) / y.var(ddof=1),
                raw=mean_test(y[treat], y[~treat]), adjusted=mean_test(y_adj[treat], y_adj[~treat]), y_adj=y_adj)


def obf_constant(n_looks, alpha=0.05, n_sims=200_000, seed=11):
    """O'Brien-Fleming boundary z_k = C / sqrt(t_k) for n_looks equally spaced looks. C is calibrated by
    simulating the cumulative z-statistic under the null (a scaled random walk) so that the chance of ever
    crossing is alpha. For one look C = 1.96; it grows with the number of looks."""
    rng = np.random.default_rng(seed)
    k = np.arange(1, n_looks + 1)
    z = np.cumsum(rng.standard_normal((n_sims, n_looks)), axis=1) / np.sqrt(k)
    stat = np.max(np.abs(z) * np.sqrt(k / n_looks), axis=1)      # crossing |z_k| > C / sqrt(t_k)  <=>  |z_k| sqrt(t_k) > C
    return float(np.quantile(stat, 1 - alpha))


def obf_boundary(info_frac, alpha=0.05):
    """z boundary at each look (information fractions t_k, equally spaced): C / sqrt(t_k)."""
    t = np.asarray(info_frac, float)
    return obf_constant(len(t), alpha) / np.sqrt(t)


def peeking_fpr(n_per_day, days, p_base, n_sims=2000, alpha=0.05, seed=7):
    """A/A simulations: share of tests that ever show p < alpha when read every day (naive) vs once at the end,
    and with the O'Brien-Fleming boundary."""
    rng = np.random.default_rng(seed)
    zc = Z(1 - alpha / 2)
    frac = np.arange(1, days + 1) / days
    bound = obf_boundary(frac, alpha)
    ever = end = obf = 0
    for _ in range(n_sims):
        xt = rng.binomial(n_per_day, p_base, days).cumsum()
        xc = rng.binomial(n_per_day, p_base, days).cumsum()
        n = n_per_day * np.arange(1, days + 1)
        pp = (xt + xc) / (2 * n)
        z = (xt / n - xc / n) / np.sqrt(pp * (1 - pp) * 2 / n)
        ever += np.any(np.abs(z) > zc)
        end += abs(z[-1]) > zc
        obf += np.any(np.abs(z) > bound)
    return dict(naive_daily=ever / n_sims, single_look=end / n_sims, obf_daily=obf / n_sims, n_sims=n_sims)

# ============================================================== B. Attribution
def transition_counts(paths: pd.DataFrame):
    """For every path, count its transitions Start -> c1 -> ... -> Conversion/Null.
    Returns (states, pair_index, unit_matrix, unit_weights):
    one 'unit' = one path that converted, or the same path that did not convert;
    unit_matrix[u, j] = how many times unit u makes transition j (pair_index[j] = (from, to))."""
    pairs, rows, weights = {}, [], []
    for path, conv, null in paths[["path", "conversions", "non_conversions"]].itertuples(index=False):
        steps = ["Start"] + path.split(" > ")
        for outcome, n in (("Conversion", conv), ("Null", null)):
            if n <= 0:
                continue
            seq = steps + [outcome]
            row = {}
            for a, b in zip(seq[:-1], seq[1:]):
                j = pairs.setdefault((a, b), len(pairs))
                row[j] = row.get(j, 0) + 1
            rows.append(row)
            weights.append(n)
    M = np.zeros((len(rows), len(pairs)))
    for u, row in enumerate(rows):
        for j, k in row.items():
            M[u, j] = k
    states = sorted({s for p in pairs for s in p} - {"Start", "Conversion", "Null"})
    return states, list(pairs), M, np.array(weights, dtype=float)


def removal_effects(channels, pair_index, pair_counts):
    """Markov chain from transition counts -> conversion probability, then the removal effect of each
    channel = share of conversions lost if the channel disappears (whoever reaches it is lost)."""
    states = ["Start"] + list(channels) + ["Conversion", "Null"]
    idx = {s: i for i, s in enumerate(states)}
    P = np.zeros((len(states), len(states)))
    for (a, b), n in zip(pair_index, pair_counts):
        P[idx[a], idx[b]] += n
    P[idx["Conversion"], idx["Conversion"]] = P[idx["Null"], idx["Null"]] = 1   # absorbing states
    P = P / P.sum(axis=1, keepdims=True)
    transient = [idx["Start"]] + [idx[c] for c in channels]

    def p_conv(Pm):
        # absorbing chain: B = (I - Q)^-1 R gives the probability of ending in Conversion
        Q = Pm[np.ix_(transient, transient)]
        R = Pm[np.ix_(transient, [idx["Conversion"]])]
        return np.linalg.solve(np.eye(len(transient)) - Q, R)[0, 0]

    base = p_conv(P)
    eff = {}
    for c in channels:
        Pr = P.copy()
        Pr[idx[c], :] = 0
        Pr[idx[c], idx["Null"]] = 1
        eff[c] = 1 - p_conv(Pr) / base
    eff = pd.Series(eff)
    return base, eff, eff / eff.sum()


def markov_with_bootstrap(paths: pd.DataFrame, n_boot=500, seed=42):
    """Markov shares on the observed paths + n_boot bootstrap replicates.
    Bootstrap = draw the same number of users again, with replacement (multinomial on the units),
    rebuild the transition counts and the Markov shares. The spread of the replicates = sampling error."""
    channels, pair_index, M, w = transition_counts(paths)
    base, eff, share = removal_effects(channels, pair_index, w @ M)
    rng = np.random.default_rng(seed)
    n, p = int(w.sum()), w / w.sum()
    boot = []
    for _ in range(n_boot):
        wb = rng.multinomial(n, p).astype(float)
        boot.append(removal_effects(channels, pair_index, wb @ M)[2])
    return base, eff, share, pd.DataFrame(boot)


def last_click_with_bootstrap(last_click: pd.Series, n_boot=500, seed=42):
    """Last-click share of conversions per channel and its bootstrap replicates (multinomial)."""
    share = last_click / last_click.sum()
    rng = np.random.default_rng(seed)
    boot = rng.multinomial(int(last_click.sum()), share.values, size=n_boot) / last_click.sum()
    return share, pd.DataFrame(boot, columns=share.index)


# ============================================================== 2. Power


def n_per_arm(p0, rel_mde, alpha=0.05, power=0.8):
    """Users per arm to detect a relative lift `rel_mde` on a conversion rate p0
    (two-sided z-test for two proportions)."""
    p1 = p0 * (1 + rel_mde)
    z_a, z_b = stats.norm.ppf(1 - alpha / 2), stats.norm.ppf(power)
    pbar = (p0 + p1) / 2
    num = (z_a * np.sqrt(2 * pbar * (1 - pbar)) + z_b * np.sqrt(p0 * (1 - p0) + p1 * (1 - p1))) ** 2
    return int(np.ceil(num / (p1 - p0) ** 2))


def ar1(x):
    """Lag-1 autocorrelation (weekly series are not independent: it inflates the variance)."""
    x = np.asarray(x) - np.mean(x)
    return float(np.sum(x[1:] * x[:-1]) / np.sum(x * x))


def geo_mde(sd_weekly, n_pre, n_test, rho=0.0, alpha=0.05, power=0.8):
    """Minimum detectable effect (relative) of a pre/post test-vs-control geo test.
    sd_weekly = std of the weekly log-ratio test/control (noise), rho = its autocorrelation.
    SE of (mean test period - mean pre period) = sd * sqrt(1/n_pre + 1/n_test), inflated by the
    autocorrelation factor sqrt((1+rho)/(1-rho))."""
    infl = np.sqrt((1 + max(rho, 0)) / (1 - max(rho, 0)))
    se = sd_weekly * np.sqrt(1 / n_pre + 1 / n_test) * infl
    return (stats.norm.ppf(1 - alpha / 2) + stats.norm.ppf(power)) * se


# ============================================================== 3. Media-mix model


def adstock(x, lam):
    """Geometric carry-over, normalised: a constant spend x gives an adstocked value of x.
    carry[t] = x[t] + lam * carry[t-1]; adstock = (1 - lam) * carry. lfilter runs this recursion in C."""
    return (1 - lam) * signal.lfilter([1.0], [1.0, -lam], np.asarray(x, dtype=float))


def hill(x, K, S):
    """Saturation: 0 at no spend, 0.5 at spend K (half-saturation), towards 1 at high spend; S = shape."""
    x = np.maximum(x, 0)
    return x ** S / (x ** S + K ** S)


# ============================================================== C. Added for this study


def wilson(x, n, alpha=0.05):
    """Wilson score interval for a proportion x/n (better than p +/- 1.96 se when p is small or n is small)."""
    if n == 0:
        return np.nan, np.nan, np.nan
    z = Z(1 - alpha / 2)
    p = x / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return p, centre - half, centre + half


def bootstrap_ci(values, stat=np.mean, n_boot=1000, alpha=0.05, seed=42):
    """Percentile bootstrap: resample the units with replacement, recompute the statistic each time."""
    v = np.asarray(values)
    rng = np.random.default_rng(seed)
    reps = np.array([stat(v[rng.integers(0, len(v), len(v))]) for _ in range(n_boot)])
    return stat(v), np.quantile(reps, alpha / 2), np.quantile(reps, 1 - alpha / 2)


def ols_cluster(y, X, clusters):
    """OLS coefficients with cluster-robust (CR1) standard errors.
    V = (X'X)^-1 [sum_g X_g' u_g u_g' X_g] (X'X)^-1 * G/(G-1) * (N-1)/(N-K). With few clusters the
    t distribution with G-1 degrees of freedom is used for p-values and intervals."""
    y = np.asarray(y, float)
    X = np.asarray(X, float)
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    u = y - X @ beta
    XtX_inv = np.linalg.pinv(X.T @ X)
    meat = np.zeros((X.shape[1], X.shape[1]))
    groups = pd.Series(clusters).astype("category").cat.codes.values
    G = groups.max() + 1
    for g in range(G):
        s = X[groups == g].T @ u[groups == g]
        meat += np.outer(s, s)
    N, K = X.shape
    V = XtX_inv @ meat @ XtX_inv * G / (G - 1) * (N - 1) / (N - K)
    return beta, np.sqrt(np.diag(V)), G


def did_clustered(df, y, unit, time, treated_post, alpha=0.05):
    """Difference-in-differences with unit and time fixed effects (two-way FE), errors clustered by unit.
    y_ut = a_u + b_t + delta * treated_post_ut + e_ut ; delta = the incremental effect."""
    d = df[[y, unit, time, treated_post]].dropna()
    X = pd.concat([d[[treated_post]].astype(float),
                   pd.get_dummies(d[unit], prefix="u", drop_first=False, dtype=float),
                   pd.get_dummies(d[time], prefix="t", drop_first=True, dtype=float)], axis=1)
    beta, se, G = ols_cluster(d[y].values, X.values, d[unit].values)
    t = stats.t.ppf(1 - alpha / 2, G - 1)
    est, s = beta[0], se[0]
    p = 2 * (1 - stats.t.cdf(abs(est / s), G - 1)) if s > 0 else np.nan
    return {"effect": est, "se": s, "lo": est - t * s, "hi": est + t * s, "p": p, "clusters": int(G)}


def synthetic_control(treated_pre, donors_pre):
    """Weights w >= 0, sum(w) = 1 that make the donors' weighted pre-period series closest to the treated
    series (least squares). treated_pre: (T,), donors_pre: (T, J). Returns w (J,)."""
    J = donors_pre.shape[1]
    loss = lambda w: np.sum((treated_pre - donors_pre @ w) ** 2)
    res = optimize.minimize(loss, np.full(J, 1 / J), method="SLSQP", bounds=[(0, 1)] * J,
                            constraints=[{"type": "eq", "fun": lambda w: w.sum() - 1}])
    return res.x


def kaplan_meier(durations, observed):
    """Kaplan-Meier survival curve. durations: time to event or to censoring; observed: 1 if the event
    happened, 0 if censored (still waiting at the end of the data). S(t) = prod (1 - d_i / n_i)."""
    d = pd.DataFrame({"t": np.asarray(durations, float), "e": np.asarray(observed, int)})
    tab = d.groupby("t")["e"].agg(["sum", "count"]).rename(columns={"sum": "events", "count": "leaving"})
    tab["at_risk"] = len(d) - tab["leaving"].cumsum().shift(fill_value=0)
    tab["survival"] = (1 - tab["events"] / tab["at_risk"]).cumprod()
    return tab.reset_index()


def control_limits(x, baseline_n):
    """Shewhart limits from the first baseline_n points: mean +/- 3 standard deviations."""
    b = np.asarray(x[:baseline_n], float)
    return b.mean(), b.mean() - 3 * b.std(ddof=1), b.mean() + 3 * b.std(ddof=1)


def cusum(x, baseline_n, k=0.5, h=5.0):
    """Two-sided tabular CUSUM on standardised values (z = (x - mean) / sd of the baseline).
    S+ = max(0, S+ + z - k), S- = max(0, S- - z - k); alarm when S+ or S- > h. k=0.5, h=5 are the
    textbook defaults (detect a 1-sd shift quickly, few false alarms)."""
    x = np.asarray(x, float)
    mu, sd = x[:baseline_n].mean(), x[:baseline_n].std(ddof=1)
    z = (x - mu) / sd
    sp = sn = 0.0
    up, down, alarm = [], [], []
    for zi in z:
        sp, sn = max(0.0, sp + zi - k), max(0.0, sn - zi - k)
        up.append(sp)
        down.append(sn)
        alarm.append(sp > h or sn > h)
        if sp > h or sn > h:
            sp = sn = 0.0          # restart after an alarm
    return pd.DataFrame({"z": z, "s_plus": up, "s_minus": down, "alarm": alarm})


def direct_standardization(rates: pd.DataFrame, group, period, rate, weight):
    """Remove a mix effect: re-weight each period's group rates with ONE reference mix
    (the average mix over all periods). Returns crude and standardised rate per period."""
    ref = rates.groupby(group)[weight].sum()
    ref = ref / ref.sum()
    out = []
    for p, g in rates.groupby(period):
        crude = np.average(g[rate], weights=g[weight])
        std = (g.set_index(group)[rate] * ref).sum() / ref[g[group]].sum()
        out.append({period: p, "crude": crude, "standardised": std})
    return pd.DataFrame(out)


def benjamini_hochberg(p):
    """Benjamini-Hochberg q-values (false discovery rate)."""
    p = np.asarray(p, float)
    n = len(p)
    order = np.argsort(p)
    q = p[order] * n / np.arange(1, n + 1)
    q = np.minimum.accumulate(q[::-1])[::-1]
    out = np.empty(n)
    out[order] = np.minimum(q, 1)
    return out


def event_study_placebo(series: pd.Series, event_dates, pre=14, post=7, n_placebo=1000, seed=42,
                        exclude_days=None):
    """Log ratio of the mean of `post` days after a date to the mean of `pre` days before it.
    Observed: one value per real event date. Placebo: the same statistic on n_placebo random dates
    (drawn from dates with a full window). p-value = share of placebo values at least as large (two-sided
    on |value|). MDE = 97.5th percentile of |placebo| (the smallest effect that would stand out)."""
    s = series.sort_index()
    idx = s.index

    def stat(d):
        i = idx.searchsorted(pd.Timestamp(d))
        if i - pre < 0 or i + post > len(idx):
            return np.nan
        return np.log(s.iloc[i:i + post].mean() / s.iloc[i - pre:i].mean())

    obs = np.array([stat(d) for d in event_dates])
    rng = np.random.default_rng(seed)
    pool = idx[pre:len(idx) - post]
    if exclude_days is not None:
        pool = pool[~pool.isin(exclude_days)]
    plac = np.array([stat(d) for d in rng.choice(pool, n_placebo, replace=True)])
    plac = plac[~np.isnan(plac)]
    p = np.array([np.mean(np.abs(plac) >= abs(o)) if not np.isnan(o) else np.nan for o in obs])
    return obs, plac, p, float(np.quantile(np.abs(plac), 0.975))
