"""
Layer: Client (presentation) — the charts of a backtest.
Charts for the backtest report."""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def plot_equity(equity, benchmark, title, path):
    """Equity curve of the strategy vs buy-and-hold (log scale)."""
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(equity.index, equity.values, label="Strategy (50/200 crossover)")
    ax.plot(benchmark.index, benchmark.values, label="Buy and hold SPY",
            alpha=0.7)
    ax.set_yscale("log")
    ax.set_xlabel("Date")
    ax.set_ylabel("Equity (log scale, starts at 1)")
    ax.set_title(title)
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_drawdown(equity, title, path):
    """Drawdown of the strategy equity curve."""
    drawdown = equity / equity.cummax() - 1.0
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.fill_between(drawdown.index, drawdown.values, 0, alpha=0.4)
    ax.plot(drawdown.index, drawdown.values, linewidth=0.8)
    ax.set_xlabel("Date")
    ax.set_ylabel("Drawdown")
    ax.set_title(title)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_price_and_signal(prices, signal, fast=50, slow=200, path=None):
    """Adjusted close with fast/slow SMAs and shaded in-market periods."""
    close = prices["Adj Close"]
    fast_sma = close.rolling(window=fast).mean()
    slow_sma = close.rolling(window=slow).mean()
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(close.index, close.values, label="SPY Adj Close", linewidth=0.8)
    ax.plot(fast_sma.index, fast_sma.values, label=f"SMA {fast}", linewidth=1.0)
    ax.plot(slow_sma.index, slow_sma.values, label=f"SMA {slow}", linewidth=1.0)
    in_market = signal.fillna(0).to_numpy() > 0
    ax.fill_between(close.index, close.min(), close.max(),
                    where=in_market, alpha=0.08, label="In market")
    ax.set_xlabel("Date")
    ax.set_ylabel("Price (USD)")
    ax.set_title("SPY with 50/200-day SMA crossover signal")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
