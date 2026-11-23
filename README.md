# Signal Research + Backtester: SMA Crossover on SPY

One signal, tested honestly on real market data: a dual moving-average
crossover (50/200-day) on the S&P 500 ETF (SPY), 2005–2025. The
backtester is built from scratch (no backtesting library), charges
transaction costs and slippage, executes without look-ahead bias, and
validates out-of-sample with walk-forward windows. The result is
reported as it is — including the parts where the signal loses to
buy-and-hold.

## The signal and the hypothesis

**Signal:** long SPY while the 50-day simple moving average of the
adjusted close is above the 200-day average; flat otherwise. This is
the classic trend-following rule ("golden cross" / "death cross").

**Hypothesis:** prices trend — once a fast average rises above a slow
one, the uptrend tends to persist, so being long during uptrends and
flat during downtrends should capture most of the upside while sitting
out the worst declines.

**Why momentum, not mean reversion:** mean reversion works on
stationary spreads (pairs, ranges), not on a broad equity index that
drifts upward for decades. On SPY, buying every dip is close to
buy-and-hold with extra turnover; the crossover rule at least changes
exposure when the trend breaks.

## Methodology

- **Data:** SPY daily OHLCV from Yahoo Finance, 2005-01-03 to
  2025-11-20 (5,256 rows), cached in `data/spy_daily.csv`. Re-run
  `examples/run_backtest.py` to reproduce everything from the cache;
  delete the CSV (or pass `force_refresh=True`) to re-download.
- **Execution:** the signal is computed from closing prices and the
  trade executes at the close of the day the signal changes, so the
  position held during day *t* is the signal as of the close of day
  *t − 1*. No look-ahead.
- **Costs:** 5 bps commission + 5 bps slippage per trade (per side),
  charged on the day the position changes. A round trip pays 10 bps
  on entry and 10 bps on exit.
- **Benchmark:** buy-and-hold SPY over the same dates.
- **Validation:** in-sample 2005–2014 vs out-of-sample 2015–2025, plus
  a 3-fold expanding walk-forward with non-overlapping test windows.
  The 50/200 windows are the standard values chosen before looking at
  the data — nothing was tuned on the sample, so there is no
  overfitting to hide. Walk-forward here measures stability across
  regimes, not parameter fitting.
- **Metrics:** CAGR, annualized volatility, Sharpe (risk-free rate 0,
  252 trading days/year), max drawdown, hit rate, average win/loss,
  profit factor.

## Results (run 23 Nov 2026, real data)

Full period, 2005-01-03 to 2025-11-20 (5,057 trading days):

| Metric | Strategy | Buy and hold |
|--------|----------|--------------|
| CAGR | 8.78% | 10.89% |
| Sharpe | 0.68 | 0.63 |
| Max drawdown | 33.72% | 55.19% |
| Ann. volatility | 13.85% | 19.35% |
| Trades | 11 (10 closed) | — |
| Hit rate | 80.0% | — |
| Avg win / avg loss | +26.14% / −7.40% | — |
| Profit factor | 14.12 | — |

In-sample (2005–2014) vs out-of-sample (2015–2025):

| Period | Strategy CAGR | B&H CAGR | Strategy Sharpe | B&H Sharpe | Strategy max DD | B&H max DD |
|--------|---------------|----------|-----------------|------------|-----------------|------------|
| 2005–2014 | 10.47% | 8.33% | 0.87 | 0.49 | 17.31% | 55.19% |
| 2015–2025 | 8.42% | 14.16% | 0.61 | 0.83 | 33.72% | 33.72% |

Walk-forward (expanding train, non-overlapping test windows):

| Test window | Strategy CAGR | B&H CAGR | Strategy Sharpe | B&H Sharpe |
|-------------|---------------|----------|-----------------|------------|
| 2013–2016 | 4.84% | 10.76% | 0.47 | 0.85 |
| 2017–2020 | 5.05% | 14.78% | 0.35 | 0.73 |
| 2021–2025 | 8.33% | 11.21% | 0.65 | 0.68 |

Largest drawdown: 33.72% (peak 2020-02-19, trough 2020-03-23) — the
strategy was long through the COVID crash, so it took the same
drawdown as buy-and-hold in that window.

## Honest conclusion

**The signal does not beat buy-and-hold on return.** Over the full
period it returns less (CAGR 8.78% vs 10.89%) and in every walk-forward
window buy-and-hold earned more. Out-of-sample the gap is wide
(8.42% vs 14.16%): the rule sat out long stretches of the bull market
and got whipsawed around crossings.

What the signal *does* deliver is risk reduction: volatility falls
from 19.35% to 13.85% and the worst drawdown from 55.19% to 33.72%,
which is why its full-period Sharpe is slightly better (0.68 vs 0.63)
despite the lower return. It behaves like a defensive overlay, not an
alpha source — on this asset, in this period.

That is a useful negative result, and it is reported as such. Next
steps worth testing: the same rule on other assets (it may behave
differently where trends are stronger), a volatility filter to avoid
whipsaws, and mean reversion on a stationary spread (pairs) instead of
on the index itself.

## Requirements

- Python 3.10 or higher.

## Installation

```bash
git clone https://github.com/Wembley003/quant-signal-backtester.git
cd quant-signal-backtester
python -m venv .venv
source .venv/bin/activate   # on Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Reproduce the results

```bash
python examples/run_backtest.py
```

Uses the cached data in `data/spy_daily.csv` (no download needed).
Prints the full-period, in-sample/out-of-sample and walk-forward
tables, saves `results/metrics.json` and three charts
(`equity_curve.png`, `drawdown.png`, `price_and_signal.png`).

To refresh the data from Yahoo Finance, delete `data/spy_daily.csv`
and run again. If the download fails, the pipeline falls back to a
clearly-flagged synthetic GBM series so the code still runs — results
on synthetic data are labelled as such and must not be presented as
market results.

## Tests

```bash
pytest
```

24 tests, all passing. They check the signal on rising/falling/flat
series, the no-look-ahead property, the backtester against
hand-computed equity curves and trade returns, the metrics against
known values, the cached data file, and the walk-forward split logic.

## Structure

```text
quant-signal-backtester/
├── signal_backtester/
│   ├── __init__.py
│   ├── data.py          # Yahoo Finance download (cached) + synthetic fallback
│   ├── signals.py       # the 50/200 SMA crossover signal
│   ├── backtester.py    # long-only backtest, costs + slippage, no look-ahead
│   ├── metrics.py       # CAGR, Sharpe, max drawdown, hit rate, profit factor
│   ├── validation.py    # in-sample/out-of-sample + walk-forward
│   └── plots.py         # equity, drawdown and signal charts
├── tests/
│   ├── test_signals.py
│   ├── test_backtester.py
│   ├── test_metrics.py
│   └── test_data_validation.py
├── examples/
│   └── run_backtest.py  # full run: backtest + validation + charts
├── data/
│   └── spy_daily.csv    # real SPY data, 2005-01-03 to 2025-11-20 (5,256 rows)
├── results/
│   ├── metrics.json     # generated by the example
│   ├── equity_curve.png
│   ├── drawdown.png
│   └── price_and_signal.png
├── requirements.txt
├── LICENSE
└── README.md
```

## Author

Wembley Emmanuel Ibarra Tepato — BSc in Physics (UAM Iztapalapa),
MSc in Physics candidate (UAM), BSc in Mathematics student (UNAM),
Balance Risk Specialist at Bancomext.

## License

MIT. See `LICENSE`.
