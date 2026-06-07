"""Live tests for the finmind skill, exercised against real companies.

These hit the FinMind API and are skipped automatically when FINMIND_TOKEN is unset.

    export FINMIND_TOKEN="your_token"
    pytest skills/finmind/tests -q
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

import pandas as pd
import pytest

SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
sys.path.insert(0, SCRIPTS)

pytestmark = pytest.mark.skipif(
    not os.environ.get("FINMIND_TOKEN"), reason="FINMIND_TOKEN not set"
)

import finmind_client as fm  # noqa: E402

TSMC = "2330"


def run(script, *args, outdir=None):
    cmd = [sys.executable, os.path.join(SCRIPTS, script), *args]
    if outdir:
        cmd += ["--outdir", outdir]
    return subprocess.run(cmd, capture_output=True, text=True)


@pytest.fixture
def tmp_outdir():
    d = tempfile.mkdtemp(prefix="finmind_test_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


# --- client-level ---------------------------------------------------------

def test_stock_info_loads():
    df = fm.fetch_df("TaiwanStockInfo")
    assert len(df) > 1000
    assert TSMC in set(df["stock_id"].astype(str))


def test_market_cap_is_positive_and_large():
    price = fm.fetch_df("TaiwanStockPrice", data_id=TSMC, start_date="2024-06-01", end_date="2024-06-30")
    shares = fm.fetch_df("TaiwanStockShareholding", data_id=TSMC, start_date="2024-06-01", end_date="2024-06-30")
    mc = fm.compute_market_cap(price, shares)
    assert not mc.empty
    assert (mc["market_cap"] > 0).all()
    # TSMC is a multi-trillion-TWD company; sanity-check the magnitude.
    assert mc["market_cap"].iloc[-1] > 1e12


# --- find_company ---------------------------------------------------------

def test_find_by_chinese_name():
    r = run("find_company.py", "台積電")
    assert r.returncode == 0, r.stderr
    assert TSMC in r.stdout


def test_find_by_id():
    r = run("find_company.py", TSMC)
    assert r.returncode == 0, r.stderr
    assert f"data_id={TSMC}" in r.stdout


# --- download + update (end to end) --------------------------------------

def test_download_then_idempotent_update(tmp_outdir):
    r = run("download_company.py", TSMC, "--start", "2024-01-01", outdir=tmp_outdir)
    assert r.returncode == 0, r.stderr
    cdir = os.path.join(tmp_outdir, TSMC)

    assert os.path.exists(os.path.join(cdir, "TaiwanStockPrice.csv"))
    assert os.path.exists(os.path.join(cdir, "TaiwanStockMonthRevenue.csv"))
    assert os.path.exists(os.path.join(cdir, "market_cap.csv"))

    meta = json.load(open(os.path.join(cdir, "metadata.json"), encoding="utf-8"))
    assert meta["datasets"]["TaiwanStockPrice"]["rows"] > 0
    assert meta["datasets"]["TaiwanStockShareholding"]["rows"] > 0

    price_path = os.path.join(cdir, "TaiwanStockPrice.csv")
    n_before = len(pd.read_csv(price_path))

    r2 = run("update_company.py", TSMC, outdir=tmp_outdir)
    assert r2.returncode == 0, r2.stderr
    n_after_first = len(pd.read_csv(price_path))

    r3 = run("update_company.py", TSMC, outdir=tmp_outdir)
    assert r3.returncode == 0, r3.stderr
    n_after_second = len(pd.read_csv(price_path))

    # Updating must never duplicate rows already present.
    assert n_after_first >= n_before
    assert n_after_second == n_after_first
