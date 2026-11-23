"""Tests for the SMA crossover signal."""

import numpy as np
import pandas as pd
import pytest

from signal_backtester.signals import sma_crossover_signal


def _prices(values):
    dates = pd.bdate_range(start="2020-01-01", periods=len(values))
    return pd.DataFrame({"Adj Close": values}, index=dates)


def test_signal_is_one_on_a_rising_market():
    prices = _prices(100.0 * 1.001 ** np.arange(250))
    signal = sma_crossover_signal(prices, fast=50, slow=200)
    assert signal.iloc[:199].isna().all()
    assert (signal.iloc[199:] == 1).all()


def test_signal_is_zero_on_a_falling_market():
    prices = _prices(100.0 * 0.999 ** np.arange(250))
    signal = sma_crossover_signal(prices, fast=50, slow=200)
    assert signal.iloc[:199].isna().all()
    assert (signal.iloc[199:] == 0).all()


def test_signal_is_nan_during_warmup():
    prices = _prices(np.full(250, 100.0))
    signal = sma_crossover_signal(prices, fast=50, slow=200)
    assert signal.iloc[:199].isna().all()
    assert signal.iloc[199:].notna().all()


def test_signal_has_no_look_ahead():
    # Changing only the last price must not change any earlier signal.
    values = 100.0 * 1.001 ** np.arange(250)
    base = sma_crossover_signal(_prices(values), fast=50, slow=200)
    changed = values.copy()
    changed[-1] = 200.0
    new = sma_crossover_signal(_prices(changed), fast=50, slow=200)
    pd.testing.assert_series_equal(base.iloc[:-1], new.iloc[:-1])


def test_fast_must_be_smaller_than_slow():
    prices = _prices(np.full(250, 100.0))
    with pytest.raises(ValueError):
        sma_crossover_signal(prices, fast=200, slow=50)
