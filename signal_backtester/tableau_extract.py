"""
Layer: Queries & analysis — the daily series as a Tableau-ready CSV.
Extracto listo para Tableau: la serie diaria con precio, señal y equity.

Otra vez, sin mentir: esto no es integración con Tableau, es un CSV
ordenado que se importa en Tableau con dos clics, más la idea del
tablero en el README. La serie lleva el precio ajustado, las dos
medias móviles, la señal, la posición que realmente se tuvo (la señal
con un día de retraso, como ejecuta el backtester) y las dos curvas de
equity. Con eso el tablero se arma solo: precio con las medias encima,
equity de la estrategia contra buy-and-hold, y la señal como fondo.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

__all__ = ["write_equity_csv"]


def write_equity_csv(path, prices, signal, result, fast=50, slow=200,
                     column="Adj Close"):
    """Escribe la serie diaria para Tableau. Devuelve el número de filas."""
    close = prices[column]
    frame = pd.DataFrame({
        "date": prices.index.date.astype(str),
        "adj_close": close.values,
        "sma_fast": close.rolling(window=fast, min_periods=fast).mean().values,
        "sma_slow": close.rolling(window=slow, min_periods=slow).mean().values,
        "signal": signal.reindex(prices.index).values,
        "position": result["position"].reindex(prices.index).values,
        "equity": result["equity"].reindex(prices.index).values,
        "benchmark": result["benchmark"].reindex(prices.index).values,
    })
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
    return len(frame)
