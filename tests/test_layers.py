"""Pruebas de la estructura por capas del backtester.

Las tres capas del proyecto (Bronce/Plata/Oro NO aplica aquí: los
precios se usan tal como se descargan, sin una etapa de limpieza que
produzca un dataset distinto ni agregados Oro; el flujo
datos → señales → resultados es un pipeline, no un lakehouse):

    Client (presentation):  plots, examples/run_backtest.py
                            (las gráficas y la corrida que lanza el usuario)
    Business rules:         signals, backtester
                            (la regla 50/200 y el motor de ejecución)
    Queries & analysis:     data, metrics, validation, persistence,
                            excel_export, tableau_extract, pivot_table
                            (las métricas de la estrategia y la validación,
                            en Python; el acceso a datos y el guardado)

La cadena es: los Datos alimentan las Señales, y los Resultados solo
existen sobre la señal. Si una etapa se rompe, las de abajo no pueden
inventarse el resultado. Y las reglas no dependen del formato de
salida: el backtest corre igual sin Excel ni SQLite.
"""

import ast
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from signal_backtester import backtester, data, metrics, signals

_PROJECT = Path(__file__).resolve().parent.parent
_PACKAGE = _PROJECT / "signal_backtester"
_PAQUETE = "signal_backtester"

_CAPAS = {
    "cliente": {"plots", "run_backtest"},
    "reglas": {"signals", "backtester"},
    "consultas": {"data", "metrics", "validation", "persistence", "excel_export", "tableau_extract", "pivot_table"},
}
# Módulos de almacenamiento/salida que las reglas no deben conocer.
_SALIDA = {"persistence", "excel_export", "tableau_extract", "pivot_table"}
# Librerías de almacenamiento/salida que cliente y reglas no deben importar.
_LIBS_SALIDA = {"openpyxl", "sqlite3"}


def test_capas_en_orden_con_datos_sinteticos():
    # Capa Consultas (acceso a datos): precios sintéticos, marcados
    # como tales para que nadie confunda estos números con el mercado.
    prices = data.synthetic_prices(n_days=600, seed=7)
    assert prices.attrs.get("synthetic") is True

    # Capa Reglas (señal): la regla vive sobre los mismos días que los
    # precios; si un índice no coincide con el otro, el backtest
    # estaría mezclando fechas.
    signal = signals.sma_crossover_signal(prices, fast=50, slow=200)
    assert signal.index.equals(prices.index)

    # Capa Reglas (motor): el backtest corre sobre esa señal y nada más.
    result = backtester.backtest(prices, signal)
    assert len(result["equity"]) == len(result["position"])
    assert result["equity"].index.equals(result["position"].index)

    # Cada trade nace de un cambio de la señal: el número de entradas
    # es el número de veces que la posición pasa de 0 a 1.
    position = result["position"]
    entradas = int(((position.diff() == 1).sum()))
    assert len(result["trades"]) == entradas

    # Capa Consultas (análisis): las métricas se calculan sobre la
    # curva que salió del backtest, no releyendo los datos: el CAGR
    # que reportan es el de esa curva.
    m = metrics.compute_metrics(result["equity"], result["returns"], result["trades"])
    n = len(result["returns"].dropna())
    cagr_independiente = float(
        (result["equity"].iloc[-1] / result["equity"].iloc[0]) ** (252.0 / n) - 1.0
    )
    assert m["cagr"] == pytest.approx(cagr_independiente)
    assert m["num_trades"] == len(result["trades"])


def test_senal_en_cero_no_opera():
    # Si la señal nunca se enciende, el backtest no opera: la capa de
    # Reglas manda y la de Consultas obedece.
    prices = data.synthetic_prices(n_days=600, seed=7)
    signal = signals.sma_crossover_signal(prices, fast=50, slow=200) * 0.0
    result = backtester.backtest(prices, signal)
    assert result["trades"] == []
    assert float(result["equity"].iloc[-1]) == pytest.approx(1.0)


# --- Las capas no se mezclan (análisis estático de imports) -------------

def _modulos_importados(path: Path) -> set[str]:
    """Nombres de módulo que un archivo importa (resueltos a su raíz)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    nombres = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                partes = alias.name.split(".")
                nombres.add(partes[1] if partes[0] == _PAQUETE and len(partes) > 1 else partes[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                partes = node.module.split(".")
                nombres.add(partes[1] if partes[0] == _PAQUETE and len(partes) > 1 else partes[0])
            else:
                for alias in node.names:
                    nombres.add(alias.name.split(".")[0])
    return nombres


def _capa_de(stem: str) -> str:
    for capa, modulos in _CAPAS.items():
        if stem in modulos:
            return capa
    raise AssertionError(f"módulo sin capa asignada: {stem}")


def test_todos_los_modulos_tienen_capa():
    # Cada módulo del paquete pertenece a exactamente una capa; si
    # alguien agrega un archivo y se le olvida ubicarlo, esta prueba
    # lo delata. __init__.py es la fachada pública, no una capa.
    vistos = set()
    for path in sorted(_PACKAGE.glob("*.py")):
        if path.stem == "__init__":
            continue
        vistos.add(path.stem)
        _capa_de(path.stem)
    assert vistos == _CAPAS["reglas"] | _CAPAS["consultas"] | {"plots"}
    assert (_PROJECT / "examples" / "run_backtest.py").exists()


def test_capas_no_se_mezclan():
    # Reglas: pura lógica de mercado, sin almacenamiento ni salida.
    # Cliente (plots): gráficas, sin tocar el almacenamiento directo.
    # Consultas: sin llamar al cliente. La corrida (examples/) es
    # orquestadora: arma las capas, así que ahí solo se prohíbe tocar
    # las librerías de salida.
    for path in sorted(_PACKAGE.glob("*.py")):
        if path.stem == "__init__":
            continue
        capa = _capa_de(path.stem)
        importados = _modulos_importados(path)
        if capa == "reglas":
            assert not (importados & _CAPAS["consultas"]), (
                f"{path.stem} (reglas) importa de consultas: {importados & _CAPAS['consultas']}"
            )
            assert not (importados & _CAPAS["cliente"]), (
                f"{path.stem} (reglas) importa del cliente: {importados & _CAPAS['cliente']}"
            )
            assert not (importados & _LIBS_SALIDA), (
                f"{path.stem} (reglas) importa librerías de salida: {importados & _LIBS_SALIDA}"
            )
        elif capa == "cliente":
            assert not (importados & _CAPAS["consultas"]), (
                f"{path.stem} (cliente) importa de consultas: {importados & _CAPAS['consultas']}"
            )
            assert not (importados & _LIBS_SALIDA), (
                f"{path.stem} (cliente) importa librerías de salida: {importados & _LIBS_SALIDA}"
            )
        elif capa == "consultas":
            assert not (importados & _CAPAS["cliente"]), (
                f"{path.stem} (consultas) importa del cliente: {importados & _CAPAS['cliente']}"
            )
    corrida = _modulos_importados(_PROJECT / "examples" / "run_backtest.py")
    assert not (corrida & _LIBS_SALIDA), (
        f"run_backtest.py (cliente) toca librerías de salida: {corrida & _LIBS_SALIDA}"
    )


def test_reglas_no_dependen_del_formato_de_salida():
    # La prueba fuerte: con openpyxl y sqlite3 bloqueados, las reglas
    # (señal + motor) y el análisis (métricas) siguen funcionando con
    # datos sintéticos. Si dependieran de Excel o de la base, esto se cae.
    codigo = textwrap.dedent(
        """
        import importlib.abc
        import sys
        sys.path.insert(0, r"%s")

        class _Bloqueo(importlib.abc.MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if fullname.split(".")[0] in {"openpyxl", "sqlite3"}:
                    raise ImportError("bloqueado en esta prueba: " + fullname)
                return None

        sys.meta_path.insert(0, _Bloqueo())
        from signal_backtester import backtester, data, metrics, signals
        prices = data.synthetic_prices(n_days=600, seed=7)
        signal = signals.sma_crossover_signal(prices, fast=50, slow=200)
        result = backtester.backtest(prices, signal)
        m = metrics.compute_metrics(result["equity"], result["returns"], result["trades"])
        assert m["num_trades"] == len(result["trades"])
        assert len(result["equity"]) == len(result["position"])
        print("reglas OK sin openpyxl ni sqlite3")
        """
        % str(_PROJECT)
    )
    resultado = subprocess.run(
        [sys.executable, "-c", codigo],
        capture_output=True,
        text=True,
        cwd=str(_PROJECT),
    )
    assert resultado.returncode == 0, resultado.stderr
    assert "reglas OK sin openpyxl ni sqlite3" in resultado.stdout
