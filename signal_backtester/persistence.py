"""
Layer: Queries & analysis — the backtest saved here to be queried later.
Guardar backtests en SQLite: operaciones, equity diaria y métricas.

Un backtest que solo vive en un gráfico es un recuerdo, no un
resultado. Si dentro de un mes quiero saber en qué fechas entró y
salió la estrategia, o cuánto cayó el equity en su peor momento, tengo
que volver a correr todo. Con esto, cada backtest queda guardado con
sus operaciones (entrada, salida, rendimiento, si quedó abierta), su
curva de equity día a día y sus métricas por periodo — y se pueden
consultar con SQL en vez de re-ejecutar.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

__all__ = [
    "init_db",
    "store_backtest",
    "list_backtests",
    "get_backtest",
    "get_equity",
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS backtests (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at      TEXT NOT NULL,
    ticker          TEXT NOT NULL,
    strategy        TEXT NOT NULL,
    fast            INTEGER,
    slow            INTEGER,
    commission_bps  REAL NOT NULL,
    slippage_bps    REAL NOT NULL,
    start_date      TEXT NOT NULL,
    end_date        TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS metrics (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    backtest_id     INTEGER NOT NULL REFERENCES backtests (id),
    scope           TEXT NOT NULL,
    side            TEXT NOT NULL,
    total_return    REAL,
    cagr            REAL,
    ann_volatility  REAL,
    sharpe_ratio    REAL,
    max_drawdown    REAL,
    num_trades      INTEGER,
    closed_trades   INTEGER,
    hit_rate        REAL,
    avg_win         REAL,
    avg_loss        REAL,
    profit_factor   REAL,
    n_days          INTEGER,
    years           REAL
);
CREATE TABLE IF NOT EXISTS trades (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    backtest_id  INTEGER NOT NULL REFERENCES backtests (id),
    trade_no     INTEGER NOT NULL,
    entry_date   TEXT NOT NULL,
    exit_date    TEXT NOT NULL,
    return_      REAL NOT NULL,
    open         INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS equity_daily (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    backtest_id  INTEGER NOT NULL REFERENCES backtests (id),
    date         TEXT NOT NULL,
    equity       REAL NOT NULL,
    benchmark    REAL NOT NULL,
    position     REAL NOT NULL,
    signal       REAL,
    daily_return REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_metrics_bt ON metrics (backtest_id);
CREATE INDEX IF NOT EXISTS idx_trades_bt ON trades (backtest_id);
CREATE INDEX IF NOT EXISTS idx_equity_bt ON equity_daily (backtest_id);
"""

METRIC_FIELDS = [
    "total_return", "cagr", "ann_volatility", "sharpe_ratio",
    "max_drawdown", "num_trades", "closed_trades", "hit_rate",
    "avg_win", "avg_loss", "profit_factor", "n_days", "years",
]


def _clean(value):
    """NaN e infinito no caben en una base: se guardan como NULL."""
    if value is None:
        return None
    try:
        if value != value or abs(value) == float("inf"):
            return None
    except TypeError:
        return value
    return value


def _connect(db_path):
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path):
    """Crea las tablas si no existen."""
    with _connect(db_path) as conn:
        conn.executescript(SCHEMA)


def store_backtest(db_path, *, ticker, strategy, fast, slow,
                   commission_bps, slippage_bps, result, metrics_by_scope,
                   signal=None):
    """Guarda un backtest completo y devuelve su id.

    ``result`` es el dict que devuelve ``backtest()`` (equity,
    benchmark, position, returns, trades). ``metrics_by_scope`` es un
    dict periodo -> (métricas_estrategia, métricas_buy_and_hold), como
    las que calcula ``compute_metrics``. ``signal`` es la serie 0/1
    original (opcional): si se pasa, se guarda su valor día a día
    junto al equity, que es donde importa.
    """
    init_db(db_path)
    equity = result["equity"]
    created_at = datetime.now(timezone.utc).isoformat()
    with _connect(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO backtests
               (created_at, ticker, strategy, fast, slow,
                commission_bps, slippage_bps, start_date, end_date)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (created_at, ticker, strategy, fast, slow,
             commission_bps, slippage_bps,
             str(equity.index[0].date()), str(equity.index[-1].date())),
        )
        backtest_id = cur.lastrowid
        for scope, (strat, bench) in metrics_by_scope.items():
            for side, metrics in (("strategy", strat), ("buy_and_hold", bench)):
                conn.execute(
                    f"""INSERT INTO metrics (backtest_id, scope, side,
                        {", ".join(METRIC_FIELDS)})
                        VALUES (?, ?, ?, {", ".join("?" * len(METRIC_FIELDS))})""",
                    (backtest_id, scope, side,
                     *[_clean(metrics.get(f)) for f in METRIC_FIELDS]),
                )
        for i, trade in enumerate(result["trades"], start=1):
            conn.execute(
                """INSERT INTO trades
                   (backtest_id, trade_no, entry_date, exit_date, return_, open)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (backtest_id, i, str(trade["entry"].date()),
                 str(trade["exit"].date()), trade["return"],
                 1 if trade["open"] else 0),
            )
        rows = []
        for date, eq in equity.items():
            sig = None
            if signal is not None:
                value = signal.get(date)
                sig = None if value is None or value != value else float(value)
            rows.append((
                backtest_id, str(date.date()), float(eq),
                float(result["benchmark"].loc[date]),
                float(result["position"].loc[date]), sig,
                float(result["returns"].loc[date]),
            ))
        conn.executemany(
            """INSERT INTO equity_daily
               (backtest_id, date, equity, benchmark, position, signal,
                daily_return) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
    return backtest_id


def list_backtests(db_path):
    """Todos los backtests guardados, del más reciente al más viejo."""
    init_db(db_path)
    with _connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM backtests ORDER BY id DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def get_backtest(db_path, backtest_id):
    """Un backtest con sus métricas y sus operaciones."""
    init_db(db_path)
    with _connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM backtests WHERE id = ?", (backtest_id,)
        ).fetchone()
        if row is None:
            return None
        backtest = dict(row)
        backtest["metrics"] = [
            dict(m) for m in conn.execute(
                "SELECT scope, side, " + ", ".join(METRIC_FIELDS) +
                " FROM metrics WHERE backtest_id = ? ORDER BY scope, side",
                (backtest_id,),
            ).fetchall()
        ]
        backtest["trades"] = [
            dict(t) for t in conn.execute(
                "SELECT trade_no, entry_date, exit_date, return_, open"
                " FROM trades WHERE backtest_id = ? ORDER BY trade_no",
                (backtest_id,),
            ).fetchall()
        ]
    return backtest


def get_equity(db_path, backtest_id):
    """La curva de equity diaria de un backtest, como lista de dicts."""
    init_db(db_path)
    with _connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT date, equity, benchmark, position, signal, daily_return"
            " FROM equity_daily WHERE backtest_id = ? ORDER BY date",
            (backtest_id,),
        ).fetchall()
    return [dict(row) for row in rows]
