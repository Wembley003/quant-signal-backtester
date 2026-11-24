"""
Layer: Queries & analysis — the numbers that summarize a backtest.
Performance metrics for a backtest.

All annualized figures use 252 trading days per year. The Sharpe ratio
uses a zero risk-free rate (cash earns nothing in this backtest), which
is stated explicitly so the number is not misread.
"""

import numpy as np

TRADING_DAYS = 252

__all__ = ["max_drawdown", "compute_metrics"]


def max_drawdown(equity):
    """Return (max_drawdown, peak_date, trough_date).

    Max drawdown is the largest peak-to-trough decline of the equity
    curve, as a positive fraction.
    """
    running_max = equity.cummax()
    drawdown = equity / running_max - 1.0
    trough_idx = drawdown.idxmin()
    trough = drawdown.loc[trough_idx]
    peak_idx = equity.loc[:trough_idx].idxmax()
    return float(-trough), peak_idx, trough_idx


def compute_metrics(equity, strategy_returns, trades, risk_free=0.0):
    """Compute the standard metric set from an equity curve and trades.

    Returns a dict with total_return, cagr, ann_volatility,
    sharpe_ratio, max_drawdown, num_trades, closed_trades, hit_rate
    (fraction of closed trades with a positive return), avg_win,
    avg_loss and profit_factor.
    """
    returns = strategy_returns.dropna()
    n = len(returns)
    if n == 0:
        raise ValueError("empty return series")
    total_return = float(equity.iloc[-1] / equity.iloc[0] - 1.0)
    years = n / TRADING_DAYS
    cagr = float((equity.iloc[-1] / equity.iloc[0]) ** (1.0 / years) - 1.0)
    ann_vol = float(returns.std(ddof=1) * np.sqrt(TRADING_DAYS))
    std = float(returns.std(ddof=1))
    # A constant return series has a floating-point std around 1e-19, not
    # exactly zero; treat anything below 1e-12 as zero volatility.
    sharpe = float(
        (returns.mean() - risk_free / TRADING_DAYS)
        / std
        * np.sqrt(TRADING_DAYS)
    ) if std > 1e-12 else 0.0
    mdd, _, _ = max_drawdown(equity)

    closed = [t for t in trades if not t["open"]]
    wins = [t["return"] for t in closed if t["return"] > 0]
    losses = [t["return"] for t in closed if t["return"] <= 0]
    hit_rate = len(wins) / len(closed) if closed else float("nan")
    avg_win = float(np.mean(wins)) if wins else float("nan")
    avg_loss = float(np.mean(losses)) if losses else float("nan")
    profit_factor = (
        float(-sum(wins) / sum(losses)) if losses and sum(losses) != 0
        else float("inf") if wins else float("nan")
    )

    return {
        "total_return": total_return,
        "cagr": cagr,
        "ann_volatility": ann_vol,
        "sharpe_ratio": sharpe,
        "max_drawdown": mdd,
        "num_trades": len(trades),
        "closed_trades": len(closed),
        "hit_rate": hit_rate,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "profit_factor": profit_factor,
        "n_days": n,
        "years": years,
    }
