"""Signal research and backtesting on real market data.

Layers
------
Business rules (the rule and the execution engine):
signals
    The signal under study: a dual moving-average crossover (trend/momentum).
backtester
    A long-only backtester with transaction costs and slippage, executed
    at the next open to avoid look-ahead bias.

Queries & analysis (the strategy metrics and validation, in Python,
plus data access and storage):
data
    Download (Yahoo Finance, cached locally) and load price data.
metrics
    Performance metrics: CAGR, Sharpe, max drawdown, hit rate.
validation
    Walk-forward / out-of-sample validation against overfitting.
persistence
    Guarda backtests en SQLite (operaciones, equity diaria, métricas).
excel_export
    Exporta un backtest guardado a Excel.
tableau_extract
    Serie diaria en CSV, lista para importar en Tableau.

Client (presentation): plots (the charts) and examples/run_backtest.py
(the full run the user launches).
Bronze/Silver/Gold does not apply here: prices are used as
downloaded, with no cleaning stage producing a different dataset and
no Gold aggregates; the data -> signals -> results flow is a pipeline,
not a lakehouse.
"""

from .backtester import backtest
from .metrics import compute_metrics
from .signals import sma_crossover_signal

__all__ = ["backtest", "compute_metrics", "sma_crossover_signal"]
