"""Pruebas de la exportación a Excel."""

import zipfile
from pathlib import Path

import pytest
from openpyxl import load_workbook

from signal_backtester.backtester import backtest
from signal_backtester.data import load_prices
from signal_backtester import excel_export, persistence
from signal_backtester.metrics import compute_metrics
from signal_backtester.signals import sma_crossover_signal

DATA = Path(__file__).resolve().parent.parent / "data" / "spy_daily.csv"


@pytest.fixture(scope="module")
def stored(tmp_path_factory):
    prices = load_prices(DATA)
    signal = sma_crossover_signal(prices, fast=50, slow=200)
    result = backtest(prices, signal, commission_bps=5.0, slippage_bps=5.0)
    metrics = compute_metrics(result["equity"], result["returns"], result["trades"])
    bench = compute_metrics(
        result["benchmark"],
        result["benchmark"].pct_change().fillna(0.0),
        trades=[],
    )
    db = tmp_path_factory.mktemp("db") / "backtests.db"
    backtest_id = persistence.store_backtest(
        db, ticker="SPY", strategy="sma_crossover_50_200", fast=50, slow=200,
        commission_bps=5.0, slippage_bps=5.0, result=result,
        metrics_by_scope={"full_period": (metrics, bench)}, signal=signal,
    )
    return {"db": db, "id": backtest_id, "result": result,
            "prices": prices, "signal": signal}


def test_export_crea_tres_hojas(stored, tmp_path):
    xlsx = tmp_path / "backtest.xlsx"
    excel_export.export_workbook(stored["db"], xlsx)
    wb = load_workbook(xlsx)
    assert wb.sheetnames == ["Métricas", "Trades", "Equity",
                             "Dinámica por resultado", "Dinámica por señal"]
    assert wb["Trades"].max_row == 12  # encabezado + 11 operaciones
    equity = wb["Equity"]
    assert equity.max_row == len(stored["result"]["equity"]) + 1
    metricas = wb["Métricas"]
    # Las filas van ordenadas por lado: buy_and_hold antes que strategy.
    filas = {
        (metricas.cell(row=r, column=1).value,
         metricas.cell(row=r, column=2).value): r
        for r in range(2, metricas.max_row + 1)
    }
    fila_strat = filas[("full_period", "strategy")]
    assert metricas.cell(row=fila_strat, column=4).value == pytest.approx(
        0.0878, abs=1e-3)  # columna D = CAGR


def test_export_sin_backtests_falla_claro(tmp_path):
    db = tmp_path / "vacia.db"
    persistence.init_db(db)
    with pytest.raises(ValueError, match="no tiene backtests"):
        excel_export.export_workbook(db, tmp_path / "vacia.xlsx")


def test_export_incluye_tablas_dinamicas_nativas(stored, tmp_path):
    # Una tabla dinámica nativa no es una hoja más: son tres piezas
    # dentro del zip (definición, caché y registros) por tabla. Si
    # falta una, Excel dice que el archivo está dañado, así que el
    # test abre el .xlsx como zip y exige las seis piezas, dos por
    # pivote, además de las hojas donde Excel las dibuja.
    xlsx = tmp_path / "backtest.xlsx"
    excel_export.export_workbook(stored["db"], xlsx)
    with zipfile.ZipFile(xlsx) as zf:
        partes = set(zf.namelist())
    for i in (1, 2):
        assert f"xl/pivotTables/pivotTable{i}.xml" in partes
        assert f"xl/pivotCache/pivotCacheDefinition{i}.xml" in partes
        assert f"xl/pivotCache/pivotCacheRecords{i}.xml" in partes
    wb = load_workbook(xlsx)
    assert "Dinámica por resultado" in wb.sheetnames
    assert "Dinámica por señal" in wb.sheetnames