"""Holdout planner: how many users and how long for a CRM test to detect a target effect.

    python tools/holdout_planner.py --baseline 0.06 --lift 0.005 --holdout 0.10 --daily-users 40000

Two-sided 5% test, 80% power by default. Unequal split (holdout share h):
    n_total = (z_a/2 + z_b)^2 x [p0(1-p0)/h + p1(1-p1)/(1-h)] / d^2
Also prints the minimum detectable effect for a given audience (the reverse question).
"""
import argparse
import math
import sys
from pathlib import Path

from scipy.stats import norm

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def n_total(p0, d, h=0.10, alpha=0.05, power=0.80):
    z = norm.ppf(1 - alpha / 2) + norm.ppf(power)
    p1 = p0 + d
    return math.ceil(z ** 2 * (p0 * (1 - p0) / h + p1 * (1 - p1) / (1 - h)) / d ** 2)


def mde(p0, n, h=0.10, alpha=0.05, power=0.80):
    """Smallest absolute lift detectable with n targeted users (same variance approximation at p0)."""
    z = norm.ppf(1 - alpha / 2) + norm.ppf(power)
    return z * math.sqrt(p0 * (1 - p0) * (1 / (h * n) + 1 / ((1 - h) * n)))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--baseline", type=float, required=True, help="baseline rate in the holdout, e.g. 0.06")
    ap.add_argument("--lift", type=float, required=True, help="target ABSOLUTE lift, e.g. 0.005 = +0.5 point")
    ap.add_argument("--holdout", type=float, default=0.10)
    ap.add_argument("--alpha", type=float, default=0.05)
    ap.add_argument("--power", type=float, default=0.80)
    ap.add_argument("--daily-users", type=int, default=0, help="eligible users entering per day (for duration)")
    a = ap.parse_args(argv)
    n = n_total(a.baseline, a.lift, a.holdout, a.alpha, a.power)
    out = {"total_users": n, "holdout_users": math.ceil(n * a.holdout), "treatment_users": n - math.ceil(n * a.holdout)}
    print(f"To detect +{a.lift * 100:.2f} points on a {a.baseline:.1%} baseline "
          f"(alpha {a.alpha:.0%}, power {a.power:.0%}, holdout {a.holdout:.0%}):")
    print(f"  target {n:,} users: {out['holdout_users']:,} in the holdout, {out['treatment_users']:,} treated")
    if a.daily_users:
        days = math.ceil(n / a.daily_users)
        out["days"] = days
        print(f"  at {a.daily_users:,} eligible users per day: {days} days of enrolment")
    for size in (50_000, 200_000, 600_000):
        print(f"  with {size:,} users the smallest detectable lift is +{mde(a.baseline, size, a.holdout) * 100:.2f} points")
    return out


if __name__ == "__main__":
    main()
