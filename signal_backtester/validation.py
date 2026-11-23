"""Walk-forward / out-of-sample validation.

The honest way to read these results: the crossover rule has no fitted
parameters (50 and 200 are the standard windows, chosen before looking
at the data, not tuned on it), so there is nothing to overfit in the
usual sense. What walk-forward does here is measure *stability*: does
the same fixed rule behave similarly in different market regimes, or
does the full-period result depend on one lucky stretch?

The procedure uses expanding training windows and non-overlapping test
windows. Metrics are computed on each test window only; the training
window is reported for context, not used for tuning.
"""

import pandas as pd

__all__ = ["walk_forward", "in_sample_out_of_sample"]


def in_sample_out_of_sample(prices, split_date):
    """Split prices into in-sample (before split) and out-of-sample (after)."""
    split = pd.Timestamp(split_date)
    return prices.loc[prices.index < split], prices.loc[prices.index >= split]


def walk_forward(prices, signal_fn, backtest_fn, windows):
    """Run the backtest on each (train_start, train_end, test_start, test_end).

    ``signal_fn`` and ``backtest_fn`` take a price DataFrame and return
    respectively the signal Series and the backtest result dict. Each
    window returns a dict with the window bounds and the test-period
    backtest result.
    """
    results = []
    for train_start, train_end, test_start, test_end in windows:
        test_prices = prices.loc[test_start:test_end]
        signal = signal_fn(test_prices)
        result = backtest_fn(test_prices, signal)
        results.append({
            "train_start": train_start,
            "train_end": train_end,
            "test_start": test_start,
            "test_end": test_end,
            "result": result,
        })
    return results
