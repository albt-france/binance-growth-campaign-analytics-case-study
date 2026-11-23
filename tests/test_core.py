"""pytest: timestamp conversion, address normalisation, statistics, taxonomy, tools.

    pytest -q
"""
import hashlib
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

import campaigns_calendar as cc  # noqa: E402
import extract_onchain as ex  # noqa: E402
import fetch_public as fp  # noqa: E402
import holdout_planner as hp  # noqa: E402
import stats  # noqa: E402


# ------------------------------------------------------------------ timestamps (ms in 2024 files, us in 2026 files)
def test_kline_timestamp_milliseconds_2024():
    assert fp.to_utc(1733011200000) == datetime(2024, 12, 1, tzinfo=timezone.utc)


def test_kline_timestamp_microseconds_2026():
    assert fp.to_utc(1790812800000000).date() == date(2026, 10, 1)


def test_real_2024_file_is_milliseconds():
    z = ROOT / "data" / "raw" / "market" / "BTCUSDT" / "BTCUSDT-1d-2024-12.zip"
    if not z.exists():
        pytest.skip("raw cache not present")
    df = fp.read_kline_zip(z.read_bytes())
    assert len(str(int(df.open_time.iloc[0]))) == 13 and df.date.iloc[0] == date(2024, 12, 1)


# ------------------------------------------------------------------ address normalisation
def test_padded_token_address_is_normalised():
    padded = "0x" + "0" * 24 + "ab" * 20
    got = duckdb.sql(f"SELECT {ex.norm(repr(padded))}").fetchone()[0]
    assert got == "0x" + "ab" * 20 and len(got) == 42


def test_normalisation_lowercases():
    got = duckdb.sql(f"SELECT {ex.norm(repr('0x' + '0' * 24 + 'AB' * 20))}").fetchone()[0]
    assert got == "0x" + "ab" * 20


def test_token_contracts_matched_by_hash_not_address():
    sql = (ROOT / "sql" / "00_staging" / "002_stg_onchain.sql").read_text(encoding="utf-8")
    assert "sha256(token_address)" in sql
    assert not any(len(w) == 42 and w.startswith("0x") for w in sql.replace("'", " ").split())
    h = duckdb.sql("SELECT sha256('abc')").fetchone()[0]
    assert h == hashlib.sha256(b"abc").hexdigest()


# ------------------------------------------------------------------ statistics
def test_wilson_contains_p_and_stays_in_bounds():
    p, lo, hi = stats.wilson(0, 20)
    assert lo >= 0 and hi > 0 and p == 0
    p, lo, hi = stats.wilson(30, 100)
    assert lo < 0.3 < hi


def test_kaplan_meier_simple_case():
    km = stats.kaplan_meier([1, 2, 3, 4], [1, 1, 0, 1])
    s = dict(zip(km.t, km.survival))
    assert s[1] == pytest.approx(0.75) and s[2] == pytest.approx(0.5) and s[4] == pytest.approx(0.0)


def test_benjamini_hochberg_known_values():
    q = stats.benjamini_hochberg([0.01, 0.04, 0.03, 0.5])
    assert q == pytest.approx([0.04, 0.0533333, 0.0533333, 0.5], rel=1e-4)


def test_did_recovers_planted_effect():
    rng = np.random.default_rng(1)
    rows = []
    for u in range(8):
        a = rng.normal(5, 1)
        for t in range(40):
            treat_post = float(u == 0 and t >= 20)
            rows.append({"u": u, "t": t, "y": a + 0.02 * t + 0.3 * treat_post + rng.normal(0, 0.05), "tp": treat_post})
    r = stats.did_clustered(pd.DataFrame(rows), "y", "u", "t", "tp")
    assert r["lo"] < 0.3 < r["hi"] and abs(r["effect"] - 0.3) < 0.05


def test_synthetic_control_weights_sum_to_one():
    rng = np.random.default_rng(2)
    donors = rng.normal(size=(30, 4)).cumsum(axis=0)
    w = stats.synthetic_control(donors @ np.array([0.5, 0.5, 0, 0]), donors)
    assert w.sum() == pytest.approx(1, abs=1e-6) and (w >= -1e-9).all() and w[:2].sum() > 0.9


def test_cuped_keeps_mean_difference_and_reduces_variance():
    rng = np.random.default_rng(3)
    x = rng.poisson(5, 20000).astype(float)
    t = rng.random(20000) < 0.5
    y = 0.1 * x + 0.2 * t + rng.normal(0, 0.3, 20000)
    r = stats.cuped(y, x, t)
    assert r["var_reduction"] > 0.2
    assert r["adjusted"]["diff"] == pytest.approx(r["raw"]["diff"], abs=0.01)


def test_srm_detects_broken_split():
    assert stats.srm_test(9000, 1000, 0.9)["p"] > 0.05
    assert stats.srm_test(8500, 1500, 0.9)["p"] < 0.001


def test_direct_standardisation_removes_mix_effect():
    df = pd.DataFrame({"g": ["a", "b", "a", "b"], "p": [1, 1, 2, 2], "rate": [0.4, 0.1, 0.42, 0.12],
                       "n": [900, 100, 300, 700]})
    s = stats.direct_standardization(df, "g", "p", "rate", "n")
    assert s.crude.iloc[1] < s.crude.iloc[0] and s.standardised.iloc[1] > s.standardised.iloc[0]


def test_cusum_alarms_on_shift_only():
    x = np.r_[np.zeros(40), np.full(20, 3.0)] + np.random.default_rng(4).normal(0, 1, 60)
    c = stats.cusum(x, 30)
    assert not c.alarm.iloc[:35].any() and c.alarm.iloc[40:].any()


# ------------------------------------------------------------------ taxonomy and tools
@pytest.mark.parametrize("title,typ", [
    ("XYZ Trading Tournament: Trade to Share Up to 1,000 XYZ Token Vouchers", "trading_competition"),
    ("Binance Earn: Enjoy Up to 8% APR with USDT Flexible Products", "earn_apr"),
    ("Limited-Time New User Gift: Deposit & Trade to Get Up to 10 USDT", "new_user"),
    ("Referral Rush: Refer a Friend and Get 9 USDT Each!", "referral"),
    ("Binance P2P: Zero Fees for a Limited Time", "p2p"),
])
def test_taxonomy_rules(title, typ):
    assert cc.classify(title)[0] == typ


def test_tokenized_stock_asset_never_names_a_company():
    typ, _, asset = cc.classify("Get vouchers of tokenized stocks of a listed company")
    assert typ == "tokenized_stock" and asset == "tokenized-stock voucher"


def test_holdout_planner_matches_formula():
    n = hp.n_total(0.06, 0.005, h=0.5)
    # equal split: n per arm = (1.96 + 0.84)^2 (p0 q0 + p1 q1) / d^2 ; total = 2 x per arm
    per_arm = (1.959964 + 0.841621) ** 2 * (0.06 * 0.94 + 0.065 * 0.935) / 0.005 ** 2
    assert abs(n - 2 * per_arm) / n < 0.01
    assert hp.mde(0.06, n, h=0.5) == pytest.approx(0.005, rel=0.05)


def test_growth_cli_answers(capsys):
    if not (ROOT / "data" / "warehouse.duckdb").exists():
        pytest.skip("warehouse not built")
    import growth_cli
    growth_cli.main(["is-it-real", "--metric", "cac", "--week", "2026-11-02"])
    out = capsys.readouterr().out
    assert "In plain English" in out and "booking date" in out
