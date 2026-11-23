"""Tests for the performance metrics."""

import numpy as np
import pandas as pd
import pytest

from signal_backtester.metrics import compute_metrics, max_drawdown


def _equity(values, dates=None):
    dates = dates or pd.bdate_range(start="2020-01-01", periods=len(values))
    return pd.Series(values, index=dates)


def test_max_drawdown_known_series():
    equity = _equity([1.0, 1.2, 1.1, 0.9, 1.0])
    mdd, peak, trough = max_drawdown(equity)
    assert mdd == pytest.approx(0.25)
    assert peak == equity.index[1]
    assert trough == equity.index[3]


def test_max_drawdown_zero_for_monotonic_series():
    equity = _equity([1.0, 1.1, 1.2, 1.3])
    mdd, _, _ = max_drawdown(equity)
    assert mdd == pytest.approx(0.0)


def test_metrics_constant_daily_return():
    # +0.1% every day for one trading year; equity starts at 1.0.
    returns = pd.Series(np.full(252, 0.001))
    equity = pd.Series(np.concatenate([[1.0], (1.0 + returns).cumprod().to_numpy()]))
    m = compute_metrics(equity, returns, trades=[])
    assert m["total_return"] == pytest.approx(1.001**252 - 1, rel=1e-6)
    assert m["cagr"] == pytest.approx(1.001**252 - 1, rel=1e-6)
    assert m["ann_volatility"] == pytest.approx(0.0)
    assert m["sharpe_ratio"] == pytest.approx(0.0)
    assert m["max_drawdown"] == pytest.approx(0.0)
    assert m["num_trades"] == 0


def test_sharpe_known_series():
    # Alternating +2% / -1%: mean 0.5%, sample std 1.503% (252 values).
    returns = pd.Series([0.02, -0.01] * 126)
    equity = (1.0 + returns).cumprod()
    m = compute_metrics(equity, returns, trades=[])
    expected_sharpe = 0.005 / 0.0150298 * np.sqrt(252)
    assert m["sharpe_ratio"] == pytest.approx(expected_sharpe, rel=1e-4)


def test_hit_rate_and_profit_factor():
    returns = pd.Series(np.zeros(10))
    equity = pd.Series(np.ones(10))
    trades = [
        {"return": 0.05, "open": False},
        {"return": -0.02, "open": False},
        {"return": 0.03, "open": False},
        {"return": 0.10, "open": True},  # open trade: excluded
    ]
    m = compute_metrics(equity, returns, trades)
    assert m["closed_trades"] == 3
    assert m["hit_rate"] == pytest.approx(2 / 3)
    assert m["avg_win"] == pytest.approx(0.04)
    assert m["avg_loss"] == pytest.approx(-0.02)
    assert m["profit_factor"] == pytest.approx(0.08 / 0.02)


def test_metrics_empty_returns_raises():
    with pytest.raises(ValueError):
        compute_metrics(pd.Series([], dtype=float), pd.Series([], dtype=float), [])
