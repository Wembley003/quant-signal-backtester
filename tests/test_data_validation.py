"""Tests for data loading and walk-forward validation."""

import os

import numpy as np
import pandas as pd
import pytest

from signal_backtester.backtester import backtest
from signal_backtester.data import (
    get_prices,
    load_prices,
    synthetic_prices,
)
from signal_backtester.signals import sma_crossover_signal
from signal_backtester.validation import in_sample_out_of_sample, walk_forward

DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "data", "spy_daily.csv")


def test_cached_spy_data_loads():
    df = load_prices(DATA_PATH)
    assert df.shape == (5256, 6)
    assert list(df.columns) == ["Open", "High", "Low", "Close", "Adj Close", "Volume"]
    assert df.index[0] == pd.Timestamp("2005-01-03")
    assert df.index[-1] == pd.Timestamp("2025-11-20")
    assert int(df.isna().sum().sum()) == 0


def test_get_prices_uses_cache():
    df, source = get_prices(cache_path=DATA_PATH)
    assert source == "cache"
    assert len(df) == 5256


def test_synthetic_prices_are_flagged():
    df = synthetic_prices(n_days=500, seed=1)
    assert df.attrs.get("synthetic") is True
    assert df.shape == (500, 6)
    assert int(df.isna().sum().sum()) == 0
    assert df["Close"].iloc[0] == pytest.approx(100.0)


def test_in_sample_out_of_sample_split():
    df = synthetic_prices(n_days=500, seed=1)
    is_df, oos_df = in_sample_out_of_sample(df, "2016-06-01")
    assert is_df.index.max() < pd.Timestamp("2016-06-01")
    assert oos_df.index.min() >= pd.Timestamp("2016-06-01")
    assert len(is_df) + len(oos_df) == len(df)


def test_walk_forward_windows_do_not_overlap_in_test():
    df = synthetic_prices(n_days=1500, seed=1)
    windows = [
        ("2015-01-01", "2016-12-31", "2017-01-01", "2017-12-31"),
        ("2015-01-01", "2017-12-31", "2018-01-01", "2018-12-31"),
        ("2015-01-01", "2018-12-31", "2019-01-01", "2019-12-31"),
    ]
    results = walk_forward(
        df,
        lambda prices: sma_crossover_signal(prices, fast=20, slow=50),
        lambda prices, signal: backtest(prices, signal),
        windows,
    )
    assert len(results) == 3
    test_ranges = [(r["test_start"], r["test_end"]) for r in results]
    for (s1, e1), (s2, e2) in zip(test_ranges, test_ranges[1:]):
        assert pd.Timestamp(e1) < pd.Timestamp(s2)
    for r in results:
        assert "equity" in r["result"]
