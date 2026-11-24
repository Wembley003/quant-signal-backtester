"""Pruebas del extracto listo para Tableau."""

import csv
from pathlib import Path

import pytest

from signal_backtester.backtester import backtest
from signal_backtester.data import load_prices
from signal_backtester import tableau_extract
from signal_backtester.signals import sma_crossover_signal

DATA = Path(__file__).resolve().parent.parent / "data" / "spy_daily.csv"


def test_extracto_tiene_la_serie_completa(tmp_path):
    prices = load_prices(DATA)
    signal = sma_crossover_signal(prices, fast=50, slow=200)
    result = backtest(prices, signal, commission_bps=5.0, slippage_bps=5.0)
    path = tmp_path / "equity.csv"
    n = tableau_extract.write_equity_csv(path, prices, signal, result)
    assert n == len(prices)
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == len(prices)
    assert list(rows[0].keys()) == [
        "date", "adj_close", "sma_fast", "sma_slow",
        "signal", "position", "equity", "benchmark",
    ]
    # La primera fila no tiene medias móviles todavía (ventana de 200).
    assert rows[0]["sma_slow"] == ""
    # La última fila tiene que empatar con el equity final conocido.
    assert float(rows[-1]["equity"]) == pytest.approx(
        float(result["equity"].iloc[-1])
    )
    # La señal solo vale 0 o 1 (o vacío donde aún no existe).
    assert {r["signal"] for r in rows} <= {"", "0.0", "1.0"}
