"""Put skills/charting on the path and load the dummy financial records.

The dummy data in `tests/data/` is generic financial records (period + metric
fields) — the input the skill assumes is already available. Tests run offline.
"""
import json
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))   # tests/
ROOT = os.path.dirname(HERE)                          # skills/charting/
sys.path.insert(0, ROOT)
DATA = os.path.join(HERE, "data")


def _load(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def aapl_income():
    return _load("aapl_income_annual.json")


@pytest.fixture
def aapl_income_q():
    return _load("aapl_income_quarter.json")


@pytest.fixture
def aapl_segmentation():
    return _load("aapl_segmentation.json")


@pytest.fixture
def aapl_dividends():
    return _load("aapl_dividends.json")


@pytest.fixture
def aapl_earnings():
    return _load("aapl_earnings.json")


@pytest.fixture
def aapl_price():
    return _load("aapl_price.json")


@pytest.fixture
def msft_price():
    return _load("msft_price.json")


@pytest.fixture
def msft_income():
    return _load("msft_income_annual.json")
