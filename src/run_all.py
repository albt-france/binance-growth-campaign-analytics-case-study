"""Run every OFFLINE step in order (the network steps fetch_public.py and extract_onchain.py use their cache).

    python src/run_all.py            # calendar -> SQL public -> simulation -> SQL all + tests -> findings -> outputs
"""
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STEPS = [
    ["src/campaigns_calendar.py"],
    ["src/run_sql.py", "--part", "public", "--no-tests"],
    ["src/simulate_exchange.py"],
    ["src/run_sql.py"],
    ["-m", "pytest", "-q", "-p", "no:cacheprovider"],
    ["src/findings.py"],
    ["src/crosscheck.py"],
    ["src/charts.py"],
    ["src/build_dashboard.py"],
    ["src/build_excel.py"],
    ["src/build_pbip.py"],
    ["tools/campaign_readout.py", "--all-examples", "--pdf"],
    ["tools/weekly_growth_review.py"],
    ["src/export_sample.py"],
    ["src/build_readme.py"],
    ["src/make_notebook.py"],
    ["-m", "jupyter", "nbconvert", "--to", "notebook", "--execute", "--inplace",
     "notebooks/binance_growth_campaign_analytics.ipynb"],
    ["src/build_pdf.py"],
]

if __name__ == "__main__":
    t0 = time.time()
    start = int(sys.argv[sys.argv.index("--from") + 1]) if "--from" in sys.argv else 0   # resume at step N
    for s in STEPS[start:]:
        t = time.time()
        subprocess.run([sys.executable] + s, cwd=ROOT, check=True)
        print(f"[run_all] {' '.join(s)}: {time.time() - t:.0f}s", flush=True)
    print(f"[run_all] done in {(time.time() - t0) / 60:.1f} min")
