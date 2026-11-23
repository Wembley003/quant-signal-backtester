"""Price data: download from Yahoo Finance with a local CSV cache.

The cache is the source of truth for reproducibility: once downloaded,
every run uses the same file unless ``force_refresh=True``. If the
download fails (no network, Yahoo down), a clearly-flagged synthetic
GBM series is generated instead so the pipeline still runs — but any
result computed on synthetic data is labelled as such and must not be
presented as a market result.
"""

import os

import numpy as np
import pandas as pd

COLUMNS = ["Open", "High", "Low", "Close", "Adj Close", "Volume"]


def download_prices(ticker, start, end, cache_path, force_refresh=False):
    """Download daily prices for ``ticker`` and save them to ``cache_path``.

    Returns the DataFrame (DatetimeIndex, OHLCV + Adj Close). Reuses the
    cache when it exists and ``force_refresh`` is False.
    """
    if os.path.exists(cache_path) and not force_refresh:
        return load_prices(cache_path)
    import yfinance as yf

    df = yf.download(ticker, start=start, end=end, auto_adjust=False,
                     progress=False)
    if df.empty:
        raise RuntimeError(f"yfinance returned no data for {ticker}")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df[COLUMNS].copy()
    df.index.name = "Date"
    os.makedirs(os.path.dirname(cache_path) or ".", exist_ok=True)
    df.to_csv(cache_path)
    return df


def load_prices(cache_path):
    """Load a cached price CSV into a DataFrame with a DatetimeIndex."""
    df = pd.read_csv(cache_path, index_col="Date", parse_dates=True)
    df.index.name = "Date"
    return df


def synthetic_prices(n_days=2520, start="2015-01-01", s0=100.0, mu=0.08,
                     sigma=0.20, seed=42):
    """Synthetic GBM prices, for offline use only.

    The returned DataFrame carries ``attrs["synthetic"] = True`` so that
    no result computed on it can be mistaken for a market result.
    """
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(start=start, periods=n_days)
    dt = 1.0 / 252.0
    shocks = rng.standard_normal(n_days)
    log_returns = (mu - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * shocks
    close = s0 * np.exp(np.cumsum(log_returns))
    close[0] = s0
    df = pd.DataFrame(
        {
            "Open": close,
            "High": close,
            "Low": close,
            "Close": close,
            "Adj Close": close,
            "Volume": np.full(n_days, 1_000_000),
        },
        index=dates,
    )
    df.index.name = "Date"
    df.attrs["synthetic"] = True
    return df


def get_prices(ticker="SPY", start="2005-01-01", end="2025-11-21",
               cache_path="data/spy_daily.csv"):
    """Best-effort price retrieval: cache, else download, else synthetic.

    Returns ``(df, source)`` where ``source`` is ``"cache"``,
    ``"download"`` or ``"synthetic"``.
    """
    if os.path.exists(cache_path):
        return load_prices(cache_path), "cache"
    try:
        return download_prices(ticker, start, end, cache_path), "download"
    except Exception as exc:  # noqa: BLE001 - fall back loudly, not silently
        print(f"WARNING: download failed ({exc}); using synthetic data.")
        return synthetic_prices(), "synthetic"
