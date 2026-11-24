#!/usr/bin/env bash
# run_tests.sh — corre las pruebas del backtester sin acordarse de rutas.
#
# Busca el venv compartido de quant-projects y si no lo hay usa el
# python3 del sistema (que debe tener pytest, pandas, numpy, yfinance,
# matplotlib y openpyxl). Acepta argumentos extra que se le pasan a pytest.
set -euo pipefail
cd "$(dirname "$0")"

if [[ -x ../.venv/bin/python ]]; then
    PY="../.venv/bin/python"
elif [[ -x .venv/bin/python ]]; then
    PY=".venv/bin/python"
else
    PY="python3"
fi

exec "$PY" -m pytest tests -q "$@"
