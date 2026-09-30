# bot-eve

Bot de trading automático (Binance spot y MetaTrader 5). Ver [PLAN.md](PLAN.md) para el plan completo.

Estado: **Fases 1 (datos) y 2 (backtest) completadas; Fase 3 (estrategias) evaluada (ninguna aprobada); Fase 4 (demo en Binance Testnet) implementada y pendiente de probar con tus claves.**

## Instalación

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (Linux/macOS: source .venv/bin/activate)
pip install -e ".[dev]"
```

## Datos (Fase 1)

Descarga velas de 1m desde `data.binance.vision` (datos públicos, sin API key) y genera 5m, 15m, 1h y 4h.

```bash
python -m bot_eve.data sync                        # todos los pares desde 2020-01
python -m bot_eve.data sync --symbols BTCUSDT --start 2024-01
python -m bot_eve.data validate                    # revisa calidad y escribe informes JSON
```

- Se guarda en `data_store/<SÍMBOLO>/<intervalo>/<YYYY-MM>.parquet` (ignorado por git).
- `sync` es reanudable: los meses cerrados y completos no se vuelven a descargar; el mes en curso se refresca siempre.
- `validate` deja informes en `data_store/reports/` con el detalle de huecos y outliers.
- Configuración en `config/default.yaml` (pares, mes inicial, intervalos).

Leer velas desde Python:

```python
from bot_eve.data.store import CandleStore
df = CandleStore("data_store").read("BTCUSDT", "15m", start="2024-01-01")
```

Cada vela remuestreada incluye `n_base` (cuántas velas de 1m la componen); si es menor que el intervalo, hubo un hueco.

## Backtest (Fase 2)

```bash
python -m bot_eve.backtest run --symbol BTCUSDT --interval 15m --strategy sma_cross \
    --params fast=10 slow=30 --report reports/sma.html
python -m bot_eve.backtest walkforward --symbol BTCUSDT --interval 15m --strategy sma_cross \
    --grid fast=5,10,20 slow=30,50,100 --train-days 90 --test-days 30 --report reports/wf.html
```

Reglas del simulador (conservadoras, sin look-ahead):
- La señal usa la vela **cerrada** y se ejecuta en la **apertura de la siguiente**.
- Comisión (0.1% por lado) y slippage (0.05% por lado) configurables en `config/default.yaml`.
- Stop y objetivo se evalúan con high/low; si una vela toca ambos, **gana el stop**; si abre más allá del stop, se ejecuta en la apertura.
- Respeta los filtros del par: paso de cantidad, cantidad mínima y **min notional** (las entradas que no los cumplen se rechazan y se cuentan).
- Métricas: retorno, buy & hold, Sharpe, máx. drawdown, win rate, profit factor, comisiones, exposición.

Sin sobreajustar:
- `walkforward` optimiza en una ventana, evalúa en la siguiente y encadena solo los tramos de prueba.
- Los datos desde `backtest.holdout_start` (2025-07-01) están **reservados**: los comandos normales no los ven. `--final` los evalúa, y debe usarse **una sola vez**, con la estrategia ya decidida.
- Para crear una estrategia: heredar de `Strategy` (`strategies/base.py`), registrarla en `strategies/__init__.py` y validar con `check_no_lookahead`.

## Estrategias (Fase 3)

```bash
python -m bot_eve.backtest list                                   # estrategias y su estado
python -m bot_eve.backtest compare --intervals 5m 15m 1h          # walk-forward de todas
```

Hay 5 estrategias (1 línea base, 2 núcleo y 2 candidatas tomadas de tecnicasdetrading.com).
Añadir una es crear un archivo con `@register`; quitarla, `enabled: false` o borrar el archivo.
Criterios de aprobación, revisión de la página y cómo añadir/quitar: [docs/STRATEGIES.md](docs/STRATEGIES.md).

## Demo en Binance Testnet (Fase 4)

Necesita claves del testnet en `.env` (ver `.env.example`). Comandos:

```bash
python -m bot_eve.engine check                        # verifica claves, saldo, reglas y datos; NO opera
python -m bot_eve.engine check --roundtrip BTCUSDT    # compra/stop/cancela/vende el mínimo en el testnet
python -m bot_eve.engine run                          # arranca el bot (Ctrl+C lo detiene; los stops quedan en el exchange)
python -m bot_eve.engine status                       # posiciones y operaciones
python -m bot_eve.engine kill                         # cierra todo y detiene el bot
```

Cómo opera:
- Señales con velas del **mercado real** (API pública); las órdenes van al **testnet**.
- La señal sale de la vela cerrada y se ejecuta de inmediato, como en el backtest.
- **Toda posición lleva un stop en el exchange** (STOP_LOSS_LIMIT). Si no se puede colocar, se cierra al instante.
- Tamaño por riesgo (1% del capital hasta el stop), una posición por par, límite de pérdida diaria (3%), kill switch por archivo o por errores seguidos, y datos obsoletos no abren posiciones.
- El estado se guarda en `state/` para reiniciar sin duplicar órdenes.
- Solo corren las estrategias con `enabled: true`, `stage: demo` (o `live`) y `capital_fraction > 0`. **Hoy todas están en `backtest`**: ninguna superó los criterios de `docs/STRATEGIES.md`. Para probar la conexión, `check --roundtrip` no necesita ninguna estrategia.
- El modo `live` (dinero real) exige `execution.i_understand_real_money: true` **y** `--yes-real-money`.

## MetaTrader 5 / Libertex (en investigación)

Solo Windows, con la terminal MT5 abierta y la cuenta demo conectada. Detalles y especificaciones
del broker en [docs/MT5_LIBERTEX.md](docs/MT5_LIBERTEX.md).

```bash
python -m bot_eve.data mt5-info      # cuenta y costos reales de los símbolos (sin login ni nombre)
python -m bot_eve.data mt5-sync      # historial de BTCUSD y ETHUSD
python -m bot_eve.backtest --config config/mt5.yaml compare --intervals 1h 4h --risk-sizing
```

### Demo en MT5 (cuenta demo únicamente)
`config/mt5.yaml` deja `atr_breakout` en `stage: demo` para BTCUSD y ETHUSD (4h). Con MT5 abierto,
la cuenta **demo** conectada y **Algo Trading en verde**:

```powershell
python -m bot_eve.engine --config config/mt5.yaml check                       # no opera
python -m bot_eve.engine --config config/mt5.yaml check --roundtrip BTCUSD    # compra, SL, vende (mínimo)
python -m bot_eve.engine --config config/mt5.yaml run
```
Si la cuenta conectada es real, el modo demo se rechaza. Con poco capital el lote mínimo impide
operar (BTCUSD necesita ~4.000–5.000 USD). Estado separado en `state/mt5/`.

## Desarrollo

```bash
pytest          # tests
ruff check .    # lint
ruff format .   # formato
```
