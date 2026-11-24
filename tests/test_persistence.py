"""Pruebas de la persistencia en SQLite.

Se corre el backtest completo sobre el SPY en caché (datos reales
2005–2025, sin descargar nada) y se guarda. Después se verifica que
lo guardado sea lo mismo que lo calculado: 11 operaciones, la métrica
de CAGR que ya conocemos y la curva de equity día a día con sus
5,057 filas. Si algo se pierde o se cambia al guardar, el test lo caza.
"""

from pathlib import Path

import pytest

from signal_backtester.backtester import backtest
from signal_backtester.data import load_prices
from signal_backtester.metrics import compute_metrics
from signal_backtester import persistence
from signal_backtester.signals import sma_crossover_signal

DATA = Path(__file__).resolve().parent.parent / "data" / "spy_daily.csv"


@pytest.fixture(scope="module")
def stored(tmp_path_factory):
    """Corre el backtest una vez y lo guarda; los tests leen de la base."""
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
    return {"db": db, "id": backtest_id, "result": result, "metrics": metrics}


def test_backtest_guardado_con_sus_11_trades(stored):
    backtest = persistence.get_backtest(stored["db"], stored["id"])
    assert backtest is not None
    assert backtest["ticker"] == "SPY"
    assert backtest["strategy"] == "sma_crossover_50_200"
    assert len(backtest["trades"]) == 11
    closed = [t for t in backtest["trades"] if not t["open"]]
    assert len(closed) == 10
    # La primera operación es la que ya conocemos: entró en 2005.
    assert backtest["trades"][0]["entry_date"].startswith("2005")


def test_metricas_guardadas_son_las_conocidas(stored):
    backtest = persistence.get_backtest(stored["db"], stored["id"])
    strat = next(
        m for m in backtest["metrics"]
        if m["scope"] == "full_period" and m["side"] == "strategy"
    )
    # Las cifras del README (SPY 2005–2025, señal 50/200).
    assert strat["cagr"] == pytest.approx(0.0878, abs=1e-3)
    assert strat["sharpe_ratio"] == pytest.approx(0.6774, abs=1e-3)
    assert strat["max_drawdown"] == pytest.approx(0.3372, abs=1e-3)
    assert strat["num_trades"] == 11
    bench = next(
        m for m in backtest["metrics"]
        if m["scope"] == "full_period" and m["side"] == "buy_and_hold"
    )
    assert bench["cagr"] == pytest.approx(0.1089, abs=1e-3)


def test_equity_diaria_completa(stored):
    equity = persistence.get_equity(stored["db"], stored["id"])
    result = stored["result"]
    assert len(equity) == len(result["equity"])
    assert equity[0]["date"] == str(result["equity"].index[0].date())
    assert equity[-1]["equity"] == pytest.approx(float(result["equity"].iloc[-1]))
    # La posición guardada tiene que ser la misma que calculó el backtest.
    assert equity[-1]["position"] == pytest.approx(
        float(result["position"].iloc[-1])
    )


def test_list_backtests_y_get_inexistente(stored):
    assert len(persistence.list_backtests(stored["db"])) == 1
    assert persistence.get_backtest(stored["db"], 99) is None
