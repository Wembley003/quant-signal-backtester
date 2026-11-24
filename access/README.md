# Access: base `.accdb` real del backtester

`signal-backtester.accdb` es una base de Microsoft Access de verdad
(formato ACE14, Access 2010 en adelante), con las tablas `backtests`,
`metrics`, `trades` y `equity_daily` y sus filas. No es un esquema en
papel: se construyó con Jackcess desde la base SQLite y se verificó
con mdbtools (los conteos de filas coinciden tabla por tabla).

## Regenerarla

Desde la raíz del repo, con una base SQLite que tenga backtests
guardados (por ejemplo, creada con `persistence.store_backtest`):

```bash
bash access/build_access.sh backtests.db signal-backtester.accdb
```

El script hace cuatro cosas: vuelca SQLite a `access/csv/*.csv` +
`access/schema.txt` + `access/schema.json` (`dump_access.py`),
descarga los jars de Jackcess a `access/lib/` la primera vez,
compila `AccessBuilder.java` y construye el `.accdb`, y lo verifica
con mdbtools si está instalado. Necesita JDK 17, `curl` y conexión
para la primera descarga de los jars.

## Abrirla en Access

Doble clic al `.accdb` en Windows: las tablas `backtests`, `metrics`,
`trades` y `equity_daily` ya están ahí con sus tipos y sus filas, sin
importar nada a mano.

## Nota honesta sobre GitHub

El `.accdb` es binario, y el push por lotes de GitHub solo lleva
archivos de texto: por eso este archivo se sube por la web desde el
celular, no por `git push`. Los CSV de `access/csv/` y el esquema
(`schema.txt` y `schema.json`) son el pack de importación en texto:
con ellos cualquiera puede reconstruir la base sin el binario
(`access/build_access.sh` lo hace solo).
