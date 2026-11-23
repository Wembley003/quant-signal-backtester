"""Signal research and backtesting on real market data.

Modules
-------
data
    Download (Yahoo Finance, cached locally) and load price data.
signals
    The signal under study: a dual moving-average crossover (trend/momentum).
backtester
    A long-only backtester with transaction costs and slippage, executed
    at the next open to avoid look-ahead bias.
metrics
    Performance metrics: CAGR, Sharpe, max drawdown, hit rate.
validation
    Walk-forward / out-of-sample validation against overfitting.
plots
    Equity curve, drawdown and signal charts.
"""

from .backtester import backtest
from .metrics import compute_metrics
from .signals import sma_crossover_signal

__all__ = ["backtest", "compute_metrics", "sma_crossover_signal"]
