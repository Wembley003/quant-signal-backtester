-- Esquema para Microsoft Access (.accdb): backtests, metrics, trades
-- y equity_daily.
--
-- Esto es SOLO el esquema (DDL), no una integración con Access. No hay
-- base .accdb aquí y no se ejecutó en Access: en Linux no hay Access.
-- Para usarlo: en Access, Crear > Diseño de consulta > vista SQL,
-- pegar este script y ejecutarlo; las relaciones se crean después en
-- Herramientas de base de datos > Relaciones.
-- Nota: los nombres de columna con guion bajo (return_) evitan la
-- palabra reservada RETURN de Access; en SQLite la columna también se
-- llama return_ para que todo coincida.

CREATE TABLE backtests (
    id              AUTOINCREMENT PRIMARY KEY,
    created_at      DATETIME NOT NULL,
    ticker          TEXT(20) NOT NULL,
    strategy        TEXT(100) NOT NULL,
    fast            LONG,
    slow            LONG,
    commission_bps  DOUBLE NOT NULL,
    slippage_bps    DOUBLE NOT NULL,
    start_date      DATETIME NOT NULL,
    end_date        DATETIME NOT NULL
);

CREATE TABLE metrics (
    id              AUTOINCREMENT PRIMARY KEY,
    backtest_id     LONG NOT NULL,
    scope           TEXT(30) NOT NULL,
    side            TEXT(20) NOT NULL,
    total_return    DOUBLE,
    cagr            DOUBLE,
    ann_volatility  DOUBLE,
    sharpe_ratio    DOUBLE,
    max_drawdown    DOUBLE,
    num_trades      LONG,
    closed_trades   LONG,
    hit_rate        DOUBLE,
    avg_win         DOUBLE,
    avg_loss        DOUBLE,
    profit_factor   DOUBLE,
    n_days          LONG,
    years           DOUBLE
);

CREATE TABLE trades (
    id              AUTOINCREMENT PRIMARY KEY,
    backtest_id     LONG NOT NULL,
    trade_no        LONG NOT NULL,
    entry_date      DATETIME NOT NULL,
    exit_date       DATETIME NOT NULL,
    return_         DOUBLE NOT NULL,
    open            YESNO NOT NULL
);

CREATE TABLE equity_daily (
    id              AUTOINCREMENT PRIMARY KEY,
    backtest_id     LONG NOT NULL,
    date            DATETIME NOT NULL,
    equity          DOUBLE NOT NULL,
    benchmark       DOUBLE NOT NULL,
    position        DOUBLE NOT NULL,
    signal          DOUBLE,
    daily_return    DOUBLE NOT NULL
);
