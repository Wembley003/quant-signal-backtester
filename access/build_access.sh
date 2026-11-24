#!/usr/bin/env bash
# Construye el .accdb real de este proyecto desde su base SQLite.
#
# Qué hace, en orden:
#   1. Vuelca las tablas de SQLite a access/csv/*.csv + schema.txt
#      (dump_access.py, solo biblioteca estándar de Python).
#   2. Descarga los jars de Jackcess a access/lib/ si no están
#      (Jackcess escribe el formato ACE14 de Access sin Windows).
#   3. Compila AccessBuilder.java y construye el .accdb.
#   4. Si mdbtools está instalado, verifica el contenido tabla por
#      tabla contra los CSV (nombres de tabla y número de filas).
#
# Uso (desde cualquier directorio):
#   access/build_access.sh <base.sqlite> <nombre.accdb>
# Necesita: python3, java + javac (JDK 17), curl y conexión para la
# primera descarga de los jars. El .accdb que sale lo abre Access
# tal cual, sin importar nada a mano.
set -euo pipefail

if [ "$#" -ne 2 ]; then
    echo "uso: build_access.sh <base.sqlite> <nombre.accdb>" >&2
    exit 2
fi

SQLITE_PATH="$(realpath "$1")"
ACCDB_NAME="$2"
ACCESS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB_DIR="$ACCESS_DIR/lib"
BUILD_DIR="$ACCESS_DIR/build"
ACCDB_PATH="$ACCESS_DIR/$ACCDB_NAME"

JACKCESS_VER="4.0.5"
LANG_VER="3.14.0"
LOGGING_VER="1.3.4"
BASE_URL="https://repo1.maven.org/maven2"

echo "== 1/4 vuelco de SQLite a CSV =="
python3 "$ACCESS_DIR/dump_access.py" "$SQLITE_PATH" "$ACCESS_DIR"

echo "== 2/4 jars de Jackcess =="
mkdir -p "$LIB_DIR"
download() { # download <url> <destino>
    if [ ! -f "$2" ]; then
        echo "descargando $(basename "$2")..."
        curl -sL --max-time 120 -o "$2" "$1"
    fi
}
download "$BASE_URL/com/healthmarketscience/jackcess/jackcess/$JACKCESS_VER/jackcess-$JACKCESS_VER.jar" \
    "$LIB_DIR/jackcess-$JACKCESS_VER.jar"
download "$BASE_URL/org/apache/commons/commons-lang3/$LANG_VER/commons-lang3-$LANG_VER.jar" \
    "$LIB_DIR/commons-lang3-$LANG_VER.jar"
download "$BASE_URL/commons-logging/commons-logging/$LOGGING_VER/commons-logging-$LOGGING_VER.jar" \
    "$LIB_DIR/commons-logging-$LOGGING_VER.jar"

echo "== 3/4 construcción del .accdb =="
mkdir -p "$BUILD_DIR"
CP="$LIB_DIR/jackcess-$JACKCESS_VER.jar:$LIB_DIR/commons-lang3-$LANG_VER.jar:$LIB_DIR/commons-logging-$LOGGING_VER.jar"
javac -encoding UTF-8 -cp "$CP" -d "$BUILD_DIR" "$ACCESS_DIR/AccessBuilder.java"
java -cp "$BUILD_DIR:$CP" AccessBuilder "$ACCESS_DIR" "$ACCDB_PATH"

echo "== 4/4 verificación =="
if command -v mdb-tables >/dev/null 2>&1; then
    ok=1
    for table in $(awk -F'|' '$1 == "TABLE" {print $2}' "$ACCESS_DIR/schema.txt"); do
        esperadas=$(($(wc -l < "$ACCESS_DIR/csv/$table.csv") - 1))
        reales=$(mdb-export "$ACCDB_PATH" "$table" | tail -n +2 | wc -l)
        if [ "$esperadas" -eq "$reales" ]; then
            echo "OK  $table: $reales filas"
        else
            echo "FALLO $table: se esperaban $esperadas filas, hay $reales" >&2
            ok=0
        fi
    done
    [ "$ok" -eq 1 ] || exit 1
    echo "verificado con mdbtools: $ACCDB_PATH"
else
    echo "aviso: mdbtools no está instalado; no se pudo verificar el"
    echo "contenido del .accdb en esta máquina (verifica en Access)."
fi
