"""Full run: 50/200-day SMA crossover on SPY, 2005-2025.

Downloads (or loads the cached) SPY daily data, runs the full-period
backtest with transaction costs and slippage, splits in-sample /
out-of-sample at 2015-01-01, and runs a 3-fold expanding walk-forward.
Prints the metrics and saves charts plus ``results/metrics.json``.

Run from the repository root:

    python examples/run_backtest.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from signal_backtester.backtester import backtest
from signal_backtester.data import get_prices
from signal_backtester.metrics import compute_metrics, max_drawdown
from signal_backtester.plots import plot_drawdown, plot_equity, plot_price_and_signal
from signal_backtester.signals import sma_crossover_signal
from signal_backtester.validation import in_sample_out_of_sample, walk_forward

FAST, SLOW = 50, 200
COMMISSION_BPS, SLIPPAGE_BPS = 5.0, 5.0


def _fmt_pct(value):
    """Format a ratio as a percentage, or 'n/a' for NaN (e.g. no losing trades)."""
    if value is None:
        return "n/a"
    try:
        if value != value:  # NaN
            return "n/a"
    except TypeError:
        return "n/a"
    return f"{value:.2%}"


def _sanitize(obj):
    """Recursively replace non-finite floats with None for valid JSON."""
    if isinstance(obj, float):
        return obj if obj == obj and abs(obj) != float("inf") else None
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    return obj


def run(prices, label):
    signal = sma_crossover_signal(prices, fast=FAST, slow=SLOW)
    result = backtest(prices, signal, commission_bps=COMMISSION_BPS,
                      slippage_bps=SLIPPAGE_BPS)
    metrics = compute_metrics(result["equity"], result["returns"], result["trades"])
    bench_metrics = compute_metrics(result["benchmark"],
                                    result["benchmark"].pct_change().fillna(0.0),
                                    trades=[])
    print(f"\n--- {label} ---")
    print(f"Period: {prices.index[0].date()} to {prices.index[-1].date()} "
          f"({metrics['n_days']} trading days)")
    print(f"Strategy: CAGR {metrics['cagr']:.2%}, Sharpe {metrics['sharpe_ratio']:.2f}, "
          f"max DD {metrics['max_drawdown']:.2%}, vol {metrics['ann_volatility']:.2%}")
    print(f"Buy&Hold: CAGR {bench_metrics['cagr']:.2%}, "
          f"Sharpe {bench_metrics['sharpe_ratio']:.2f}, "
          f"max DD {bench_metrics['max_drawdown']:.2%}, "
          f"vol {bench_metrics['ann_volatility']:.2%}")
    pf = metrics['profit_factor']
    pf_str = f"{pf:.2f}" if pf == pf and abs(pf) != float('inf') else "∞ (no losing closed trades)"
    print(f"Trades: {metrics['num_trades']} ({metrics['closed_trades']} closed), "
          f"hit rate {_fmt_pct(metrics['hit_rate'])}, "
          f"avg win {_fmt_pct(metrics['avg_win'])}, "
          f"avg loss {_fmt_pct(metrics['avg_loss'])}, "
          f"profit factor {pf_str}")
    return result, metrics, bench_metrics


def main():
    prices, source = get_prices()
    print(f"Data source: {source} — {len(prices)} rows, "
          f"{prices.index[0].date()} to {prices.index[-1].date()}")
    if getattr(prices, "attrs", {}).get("synthetic"):
        print("WARNING: results below are on SYNTHETIC data, not market data.")

    os.makedirs("results", exist_ok=True)
    all_metrics = {}

    full_result, full_metrics, full_bench = run(prices, "Full period (2005-2025)")
    all_metrics["full_period"] = {"strategy": full_metrics, "buy_and_hold": full_bench}

    is_prices, oos_prices = in_sample_out_of_sample(prices, "2015-01-01")
    _, is_metrics, is_bench = run(is_prices, "In-sample (2005-2014)")
    _, oos_metrics, oos_bench = run(oos_prices, "Out-of-sample (2015-2025)")
    all_metrics["in_sample"] = {"strategy": is_metrics, "buy_and_hold": is_bench}
    all_metrics["out_of_sample"] = {"strategy": oos_metrics, "buy_and_hold": oos_bench}

    print("\n--- Walk-forward (expanding train, non-overlapping test) ---")
    windows = [
        ("2005-01-01", "2012-12-31", "2013-01-01", "2016-12-31"),
        ("2005-01-01", "2016-12-31", "2017-01-01", "2020-12-31"),
        ("2005-01-01", "2020-12-31", "2021-01-01", "2025-11-20"),
    ]
    wf = walk_forward(
        prices,
        lambda p: sma_crossover_signal(p, fast=FAST, slow=SLOW),
        lambda p, s: backtest(p, s, commission_bps=COMMISSION_BPS,
                              slippage_bps=SLIPPAGE_BPS),
        windows,
    )
    wf_metrics = []
    for fold in wf:
        res = fold["result"]
        m = compute_metrics(res["equity"], res["returns"], res["trades"])
        b = compute_metrics(res["benchmark"],
                            res["benchmark"].pct_change().fillna(0.0), trades=[])
        print(f"Test {fold['test_start']} to {fold['test_end']}: "
              f"strategy CAGR {m['cagr']:.2%}, Sharpe {m['sharpe_ratio']:.2f}, "
              f"max DD {m['max_drawdown']:.2%} | "
              f"buy&hold CAGR {b['cagr']:.2%}, Sharpe {b['sharpe_ratio']:.2f}, "
              f"max DD {b['max_drawdown']:.2%}")
        wf_metrics.append({"window": {k: v for k, v in fold.items() if k != "result"},
                           "strategy": m, "buy_and_hold": b})
    all_metrics["walk_forward"] = wf_metrics

    mdd, peak, trough = max_drawdown(full_result["equity"])
    print(f"\nFull-period max drawdown: {mdd:.2%} (peak {peak.date()}, trough {trough.date()})")

    with open("results/metrics.json", "w") as f:
        json.dump(_sanitize(all_metrics), f, indent=2, default=str)
    print("Metrics saved to results/metrics.json")

    plot_equity(full_result["equity"], full_result["benchmark"],
                "SMA 50/200 crossover on SPY vs buy and hold (2005-2025)",
                "results/equity_curve.png")
    plot_drawdown(full_result["equity"],
                  "Strategy drawdown — SMA 50/200 crossover on SPY",
                  "results/drawdown.png")
    plot_price_and_signal(prices, sma_crossover_signal(prices, fast=FAST, slow=SLOW),
                          fast=FAST, slow=SLOW,
                          path="results/price_and_signal.png")
    print("Charts saved to results/equity_curve.png, results/drawdown.png, "
          "results/price_and_signal.png")


if __name__ == "__main__":
    main()
