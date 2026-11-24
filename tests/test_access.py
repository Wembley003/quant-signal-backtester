"""Pruebas del volcado a Access: CSV + esquema y .accdb real.

Access no se puede fabricar con Python en Linux, así que el camino
es en dos pasos: primero se vuelca la base SQLite a CSV + esquema
(``access/dump_access.py``) y después Java con Jackcess construye el
.accdb real (``access/build_access.sh``). El primer test cubre el
volcado; el segundo, la construcción completa, pero solo si el
toolchain está disponible (JDK, curl, mdbtools y los jars
descargables de Maven Central): en una máquina sin eso, el test se
salta en vez de fallar por algo que no es el código.
"""

import csv
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from signal_backtester.backtester import backtest
from signal_backtester.metrics import compute_metrics
from signal_backtester.signals import sma_crossover_signal
from signal_backtester import persistence

ACCESS_DIR = Path(__file__).resolve().parent.parent / "access"


def _cargar_dump_access():
    spec = importlib.util.spec_from_file_location(
        "dump_access", ACCESS_DIR / "dump_access.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def base_juguete(tmp_path_factory):
    """Un backtest chico sobre una serie sintética (300 días hábiles):
    lo justo para que haya backtests, metrics, trades y equity."""
    rng = np.random.default_rng(7)
    fechas = pd.date_range("2020-01-01", periods=300, freq="B")
    precios = pd.DataFrame(
        {"Adj Close": 100 * np.exp(np.cumsum(
            rng.normal(0.0005, 0.01, len(fechas))))},
        index=fechas,
    )
    signal = sma_crossover_signal(precios, fast=10, slow=50)
    result = backtest(precios, signal, commission_bps=5.0, slippage_bps=5.0)
    metrics = compute_metrics(result["equity"], result["returns"],
                              result["trades"])
    bench = compute_metrics(
        result["benchmark"],
        result["benchmark"].pct_change().fillna(0.0), trades=[],
    )
    db = tmp_path_factory.mktemp("db") / "backtests.db"
    persistence.store_backtest(
        db, ticker="SYN", strategy="sma_crossover_10_50", fast=10, slow=50,
        commission_bps=5.0, slippage_bps=5.0, result=result,
        metrics_by_scope={"full_period": (metrics, bench)}, signal=signal,
    )
    return db


def _filas_csv(ruta):
    with open(ruta, newline="", encoding="utf-8") as fh:
        return list(csv.reader(fh))


def test_volcado_produce_csvs_y_esquema(base_juguete, tmp_path):
    dump_access = _cargar_dump_access()
    out_dir = tmp_path / "access"
    resumen = dump_access.dump(base_juguete, out_dir)

    por_nombre = {t["name"]: t for t in resumen["tables"]}
    assert set(por_nombre) == {"backtests", "metrics", "trades",
                               "equity_daily"}
    assert por_nombre["backtests"]["rows"] == 1
    assert por_nombre["metrics"]["rows"] == 2
    assert por_nombre["trades"]["rows"] == 3
    assert por_nombre["equity_daily"]["rows"] == 251

    for tabla in por_nombre:
        filas = _filas_csv(out_dir / "csv" / f"{tabla}.csv")
        assert filas[0]  # encabezados
        assert len(filas) - 1 == por_nombre[tabla]["rows"]
    encabezados = _filas_csv(out_dir / "csv" / "backtests.csv")[0]
    primera = _filas_csv(out_dir / "csv" / "backtests.csv")[1]
    fila = dict(zip(encabezados, primera))
    assert fila["ticker"] == "SYN"
    assert fila["strategy"] == "sma_crossover_10_50"

    esquema = (out_dir / "schema.txt").read_text(encoding="utf-8")
    for tabla in ("backtests", "metrics", "trades", "equity_daily"):
        assert f"TABLE|{tabla}" in esquema
    assert "COL|daily_return|DOUBLE|" in esquema
    resumen_json = json.loads((out_dir / "schema.json").read_text())
    assert [t["name"] for t in resumen_json["tables"]] == [
        "backtests", "metrics", "trades", "equity_daily",
    ]


def _toolchain_disponible():
    """JDK + curl + mdbtools y los jars de Jackcess descargables."""
    for herramienta in ("java", "javac", "curl", "mdb-tables", "mdb-export"):
        if shutil.which(herramienta) is None:
            return False, f"falta {herramienta}"
    jar = ("https://repo1.maven.org/maven2/com/healthmarketscience/"
           "jackcess/jackcess/4.0.5/jackcess-4.0.5.jar")
    cabezal = subprocess.run(
        ["curl", "-sI", "--max-time", "10", jar],
        capture_output=True, text=True,
    )
    if cabezal.returncode != 0 or "200" not in cabezal.stdout.splitlines()[0]:
        return False, "no se puede descargar Jackcess de Maven Central"
    return True, ""


def test_construye_accdb_real(base_juguete, tmp_path):
    disponible, motivo = _toolchain_disponible()
    if not disponible:
        pytest.skip(f"sin toolchain de Access: {motivo}")
    # Copia del directorio access/ a tmp: el script escribe el .accdb,
    # los CSV y los jars dentro de su propio directorio.
    trabajo = tmp_path / "access"
    shutil.copytree(ACCESS_DIR, trabajo)
    accdb = trabajo / "signal-backtester.accdb"
    proc = subprocess.run(
        ["bash", str(trabajo / "build_access.sh"),
         str(base_juguete), "signal-backtester.accdb"],
        capture_output=True, text=True, cwd=trabajo,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert accdb.exists() and accdb.stat().st_size > 0

    tablas = subprocess.run(
        ["mdb-tables", "-1", str(accdb)],
        capture_output=True, text=True, check=True,
    ).stdout.split()
    assert set(tablas) == {"backtests", "metrics", "trades", "equity_daily"}
    for tabla, esperadas in (("backtests", 1), ("metrics", 2),
                             ("trades", 3), ("equity_daily", 251)):
        salida = subprocess.run(
            ["mdb-export", str(accdb), tabla],
            capture_output=True, text=True, check=True,
        ).stdout.strip().splitlines()
        assert len(salida) - 1 == esperadas, salida
    # El contenido también tiene que ser el mismo, no solo el conteo.
    salida = subprocess.run(
        ["mdb-export", str(accdb), "backtests"],
        capture_output=True, text=True, check=True,
    ).stdout
    assert "SYN" in salida


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
