"""
Layer: Queries & analysis — the saved backtest as an Excel workbook.
Exportar un backtest guardado a Excel (openpyxl).

Tres hojas: las métricas (estrategia contra buy-and-hold, por
periodo), las operaciones una por una y la curva de equity día a día.
Es el formato que se le puede mandar a alguien que no programa: abre
el archivo y ve el resultado sin tener que correr nada.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font

from .persistence import METRIC_FIELDS, get_backtest, get_equity, list_backtests
from .pivot_table import add_pivot_table

__all__ = ["export_workbook"]


def _write_sheet(wb, title, headers, rows):
    ws = wb.create_sheet(title)
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True)
    for row in rows:
        ws.append(row)
    for column in ws.columns:
        width = max(len(str(cell.value)) if cell.value is not None else 0
                    for cell in column)
        ws.column_dimensions[column[0].column_letter].width = min(width + 2, 28)
    return ws


def export_workbook(db_path, xlsx_path, backtest_id=None):
    """Escribe el libro de Excel de un backtest (el último, si no se dice cuál)."""
    db_path = Path(db_path)
    xlsx_path = Path(xlsx_path)
    xlsx_path.parent.mkdir(parents=True, exist_ok=True)
    if backtest_id is None:
        backtests = list_backtests(db_path)
        if not backtests:
            raise ValueError("la base no tiene backtests guardados")
        backtest_id = backtests[0]["id"]
    backtest = get_backtest(db_path, backtest_id)
    if backtest is None:
        raise ValueError(f"no existe el backtest {backtest_id}")
    equity = get_equity(db_path, backtest_id)

    wb = Workbook()
    wb.remove(wb.active)

    metric_rows = []
    for m in backtest["metrics"]:
        metric_rows.append(
            [m["scope"], m["side"]] + [m[f] for f in METRIC_FIELDS]
        )
    _write_sheet(
        wb, "Métricas",
        ["Periodo", "Lado"] + METRIC_FIELDS,
        metric_rows,
    )

    trade_rows = [
        [t["trade_no"], t["entry_date"], t["exit_date"], t["return_"],
         bool(t["open"])]
        for t in backtest["trades"]
    ]
    trades_ws = _write_sheet(
        wb, "Trades",
        ["#", "Entrada", "Salida", "Rendimiento", "Abierta"],
        trade_rows,
    )

    equity_rows = [
        [e["date"], e["equity"], e["benchmark"], e["position"],
         e["signal"], e["daily_return"]]
        for e in equity
    ]
    equity_ws = _write_sheet(
        wb, "Equity",
        ["Fecha", "Equity estrategia", "Equity buy-and-hold", "Posición",
         "Señal", "Retorno diario"],
        equity_rows,
    )

    # Tablas dinámicas NATIVAS de Excel (objeto pivotTable, no valores
    # pegados): Excel las recalcula al abrir. La primera agrupa las
    # operaciones por si quedaron abiertas o cerradas — una operación
    # abierta todavía no realizó su rendimiento, así que mezclarla con
    # las cerradas distorsiona el promedio — y cuenta cuántas hay de
    # cada tipo. La segunda agrupa los días por la señal que regía
    # (0 = fuera del mercado, 1 = dentro): si el retorno diario
    # promedio dentro es mayor que fuera, la señal está capturando
    # tendencia; si es al revés, la señal no aporta nada. La señal
    # puede ser None (días sin media lenta aún) y "Abierta" es
    # booleana: el helper las agrupa como faltante y como sí/no.
    # Si una hoja de origen no tiene filas, ese pivote se salta sin
    # romper la exportación.
    try:
        add_pivot_table(
            wb,
            source_sheet=trades_ws,
            pivot_sheet_title="Dinámica por resultado",
            pivot_name="PivotResultado",
            row_fields=["Abierta"],
            data_fields=[
                ("Rendimiento", "Rendimiento promedio", "average"),
                ("Rendimiento", "Número de operaciones", "count"),
            ],
        )
    except ValueError:
        pass
    try:
        add_pivot_table(
            wb,
            source_sheet=equity_ws,
            pivot_sheet_title="Dinámica por señal",
            pivot_name="PivotSenal",
            row_fields=["Señal"],
            data_fields=[
                ("Retorno diario", "Retorno diario promedio", "average"),
                ("Retorno diario", "Días", "count"),
            ],
        )
    except ValueError:
        pass

    wb.save(xlsx_path)
    return xlsx_path
