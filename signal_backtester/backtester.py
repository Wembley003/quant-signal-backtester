"""
Layer: Business rules — the backtest itself, costs included.
Long-only backtester with transaction costs and slippage.

Execution convention (no look-ahead)
-------------------------------------
The signal is computed from closing prices. A position change is
executed at the close of the day the signal changes, so the position
held during day ``i`` is the signal as of the close of day ``i - 1``:

    position = signal.shift(1)

Daily strategy return on day ``i``:

    r_strategy[i] = position[i] * r_market[i]
                    - |position[i] - position[i-1]| * cost_rate

where ``r_market`` is the adjusted-close return and ``cost_rate`` is the
commission plus slippage charged on every trade (per side). Costs are
charged on the day the position changes, so a round trip pays twice:
once on entry, once on exit.

Trade returns are measured exactly from the equity curve: a trade
entered on day ``e`` (first day with position 1) and exited on day
``x`` (first day back to position 0) returns

    equity[x] / equity[e - 1] - 1

which includes both the entry and the exit cost and no market return
outside the holding period (the position is 0 on day ``x``).
"""

import numpy as np
import pandas as pd

__all__ = ["backtest"]


def backtest(prices, signal, commission_bps=5.0, slippage_bps=5.0,
             column="Adj Close"):
    """Run the backtest.

    Parameters
    ----------
    prices : DataFrame
        OHLCV data with a DatetimeIndex.
    signal : Series
        Raw 0/1 signal aligned with ``prices`` (NaN where undefined).
    commission_bps, slippage_bps : float
        Cost per trade (per side), in basis points.
    column : str
        Price column for returns.

    Returns
    -------
    dict with keys:
        ``equity`` (Series, starts at 1), ``benchmark`` (buy-and-hold
        equity, starts at 1), ``position`` (Series), ``returns``
        (daily strategy returns), ``trades`` (list of dicts with
        ``entry``, ``exit``, ``return`` and ``open``), ``cost_rate``.
    """
    data = prices[[column]].copy()
    data["signal"] = signal
    data = data.dropna(subset=["signal"])
    if data.empty:
        raise ValueError("no overlapping data between prices and signal")

    market_returns = data[column].pct_change().fillna(0.0)
    position = data["signal"].shift(1).fillna(0.0)
    turnover = position.diff().abs().fillna(position.abs())
    cost_rate = (commission_bps + slippage_bps) / 10_000.0
    strategy_returns = position * market_returns - turnover * cost_rate

    equity = (1.0 + strategy_returns).cumprod()
    benchmark = (1.0 + market_returns).cumprod()
    equity.name = "equity"
    benchmark.name = "benchmark"
    position.name = "position"
    strategy_returns.name = "returns"

    trades = _extract_trades(position, equity)
    return {
        "equity": equity,
        "benchmark": benchmark,
        "position": position,
        "returns": strategy_returns,
        "trades": trades,
        "cost_rate": cost_rate,
    }


def _extract_trades(position, equity):
    """Round-trip trades from the position series and the equity curve."""
    trades = []
    pos = position.to_numpy()
    dates = position.index
    equity_values = equity.to_numpy()
    entry_idx = None
    for i, p in enumerate(pos):
        if entry_idx is None and p == 1:
            entry_idx = i
        elif entry_idx is not None and p == 0:
            start_equity = equity_values[entry_idx - 1] if entry_idx > 0 else 1.0
            trades.append({
                "entry": dates[entry_idx],
                "exit": dates[i],
                "return": float(equity_values[i] / start_equity - 1.0),
                "open": False,
            })
            entry_idx = None
    if entry_idx is not None:
        start_equity = equity_values[entry_idx - 1] if entry_idx > 0 else 1.0
        trades.append({
            "entry": dates[entry_idx],
            "exit": dates[-1],
            "return": float(equity_values[-1] / start_equity - 1.0),
            "open": True,
        })
    return trades
