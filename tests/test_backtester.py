"""Tests for the backtester, with hand-computed expectations.

Hand-computed example
---------------------
Adj Close: [100, 110, 121, 115, 120]
Signal:    [0, 0, 1, 1, 0]
Position (signal shifted by 1): [0, 0, 0, 1, 1]
Market returns: [0, 0.10, 0.10, -0.04959, 0.04348]
Turnover: [0, 0, 0, 1, 0]; cost_rate = 10 bps = 0.001
Strategy returns with costs:
  day 3: 1 * (-0.04959) - 0.001 = -0.05059
  day 4: 1 * 0.04348 - 0 = 0.04348
Equity: [1, 1, 1, 0.94941, 0.99069]
One trade: entry day 3, exit day 4, return = 0.99069 / 1.0 - 1 = -0.00931.
"""

import numpy as np
import pandas as pd
import pytest

from signal_backtester.backtester import backtest

DATES = pd.bdate_range(start="2020-01-01", periods=5)


def _frame(closes, dates=None):
    dates = dates if dates is not None else DATES
    return pd.DataFrame({"Adj Close": closes}, index=dates)


def _signal(values, dates=None):
    dates = dates if dates is not None else DATES
    return pd.Series(values, index=dates, dtype=float)


def test_hand_computed_equity_with_costs():
    result = backtest(_frame([100, 110, 121, 115, 120]),
                      _signal([0, 0, 1, 1, 0]),
                      commission_bps=5.0, slippage_bps=5.0)
    equity = result["equity"].to_numpy()
    assert equity == pytest.approx([1, 1, 1, 0.94941, 0.99069], abs=1e-4)


def test_hand_computed_equity_without_costs():
    result = backtest(_frame([100, 110, 121, 115, 120]),
                      _signal([0, 0, 1, 1, 0]),
                      commission_bps=0.0, slippage_bps=0.0)
    equity = result["equity"].to_numpy()
    assert equity == pytest.approx([1, 1, 1, 0.95041, 0.99173], abs=1e-4)


def test_trade_extraction_and_return():
    # Closed trade: signal [0, 0, 1, 0, 0] -> position [0, 0, 0, 1, 0].
    # Day 3 (entry): 1 * (115/121 - 1) - 0.001 = -0.05059 -> equity 0.94941.
    # Day 4 (exit): 0 - 0.001 = -0.001 -> equity 0.94846.
    # Trade return = 0.94846 / 1.0 - 1 = -0.05154 (both costs included).
    result = backtest(_frame([100, 110, 121, 115, 120]),
                      _signal([0, 0, 1, 0, 0]),
                      commission_bps=5.0, slippage_bps=5.0)
    trades = result["trades"]
    assert len(trades) == 1
    assert trades[0]["entry"] == DATES[3]
    assert trades[0]["exit"] == DATES[4]
    assert trades[0]["return"] == pytest.approx(-0.05154, abs=1e-4)
    assert trades[0]["open"] is False


def test_trade_open_at_end_uses_last_equity():
    # Signal [0, 0, 1, 1, 0] -> position [0, 0, 0, 1, 1]: no exit, open trade.
    result = backtest(_frame([100, 110, 121, 115, 120]),
                      _signal([0, 0, 1, 1, 0]),
                      commission_bps=5.0, slippage_bps=5.0)
    trades = result["trades"]
    assert len(trades) == 1
    assert trades[0]["entry"] == DATES[3]
    assert trades[0]["exit"] == DATES[4]
    assert trades[0]["return"] == pytest.approx(-0.00931, abs=1e-4)
    assert trades[0]["open"] is True


def test_always_long_with_zero_costs_equals_buy_and_hold():
    dates = pd.bdate_range(start="2020-01-01", periods=100)
    closes = 100.0 * (1.001 ** np.arange(100))
    result = backtest(_frame(closes, dates), _signal(np.ones(100), dates),
                      commission_bps=0.0, slippage_bps=0.0)
    pd.testing.assert_series_equal(result["equity"], result["benchmark"],
                                   check_names=False)


def test_costs_only_reduce_equity():
    dates = pd.bdate_range(start="2020-01-01", periods=100)
    closes = 100.0 * (1.001 ** np.arange(100))
    signal = _signal([0] * 50 + [1] * 50, dates)
    free = backtest(_frame(closes, dates), signal,
                    commission_bps=0.0, slippage_bps=0.0)
    costly = backtest(_frame(closes, dates), signal,
                      commission_bps=5.0, slippage_bps=5.0)
    assert costly["equity"].iloc[-1] < free["equity"].iloc[-1]


def test_open_trade_at_end_is_flagged():
    result = backtest(_frame([100, 110, 121, 115, 120]),
                      _signal([0, 0, 1, 1, 1]),
                      commission_bps=0.0, slippage_bps=0.0)
    assert len(result["trades"]) == 1
    assert result["trades"][0]["open"] is True


def test_empty_overlap_raises():
    with pytest.raises(ValueError):
        backtest(_frame([100, 110, 121]),
                 _signal([np.nan, np.nan, np.nan]))
