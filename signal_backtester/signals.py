"""
Layer: Business rules — the 50/200 rule computed on the prices.
The signal under study: dual moving-average crossover (trend/momentum).

Hypothesis
----------
Prices trend: once a fast average rises above a slow average, the
uptrend tends to persist for weeks to months, so being long while the
fast average is above the slow one should capture the bulk of uptrends
and sit out the bulk of downtrends. This is the classic trend-following
rule (the "golden cross" / "death cross" at 50/200 days) and the
simplest momentum signal that survives across decades of literature.

Why this signal and not mean reversion: mean reversion works on
stationary spreads (pairs, ranges), not on a broad equity index that
drifts upward over time. On SPY, buying every dip is close to
buy-and-hold with extra turnover; the crossover rule at least changes
exposure when the trend breaks.

Definition
----------
Let F_t be the fast simple moving average (default 50 days) and S_t the
slow one (default 200 days) of the adjusted close. The raw signal is

    signal_t = 1  if F_t > S_t
               0  otherwise

The backtester holds ``signal`` shifted by one day (the trade is
entered at the next open), so no information from day t is used before
the close of day t.
"""

import pandas as pd

__all__ = ["sma_crossover_signal"]


def sma_crossover_signal(prices, fast=50, slow=200, column="Adj Close"):
    """Return a Series of 0/1 positions from the fast/slow SMA crossover.

    Parameters
    ----------
    prices : DataFrame
        OHLCV data with a DatetimeIndex; ``column`` holds the price series.
    fast, slow : int
        Fast and slow moving-average windows in days.
    column : str
        Price column to average (adjusted close by default).

    Returns
    -------
    Series
        1 when the fast SMA is above the slow SMA, else 0. NaN for the
        first ``slow - 1`` days (the slow average does not exist yet).
    """
    if fast >= slow:
        raise ValueError("fast must be smaller than slow")
    close = prices[column]
    fast_sma = close.rolling(window=fast, min_periods=fast).mean()
    slow_sma = close.rolling(window=slow, min_periods=slow).mean()
    signal = (fast_sma > slow_sma).astype("float")
    signal[slow_sma.isna()] = float("nan")
    return signal
