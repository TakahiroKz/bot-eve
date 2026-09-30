# PLAN: Bot de trading automático (Binance spot)

Estado: **planificación**. Aún no hay código del bot.

## 1. Decisiones tomadas

| Tema | Decisión |
|---|---|
| Mercado | Cripto, Binance **spot** |
| Estilo inicial | Scalping en velas de **5m y 15m** |
| Futuras versiones | Intradía en **1h y 4h** |
| Autonomía final | Totalmente automático, con controles de riesgo duros |
| Stack | Python 3.11+ con dashboard web (FastAPI) |
| Ejecución | PC local (VPS como opción futura) |
| Conexión demo | **Binance Testnet** (spot), actualmente activa |
| Conexión live | **MetaTrader 5** con un broker (ver sección 4, supuestos por confirmar) |
| Capital real | 3.54 USDT (solo para probar ejecución, no como objetivo de rentabilidad) |
| Pares candidatos | BTCUSDT, ETHUSDT, BNBUSDT |

## 2. Advertencias y expectativas

- **Min notional:** Binance exige un valor mínimo por orden (normalmente ~5 USDT, varía por par). Con 3.54 USDT puede ser imposible operar en real. El bot debe leer los filtros del par (`LOT_SIZE`, `NOTIONAL`) y negarse a operar si no se cumplen.
- **Comisiones:** 0.1% por lado (0.075% pagando con BNB). Ida y vuelta ≈ 0.15–0.20%. En 5–15m los movimientos típicos son de 0.2–0.5%, así que la ventaja debe superar ese costo.
- **Entrenamiento y validación** se hacen con datos históricos y testnet (capital virtual), no con los 3.54 USDT.
- **Resultado posible:** que ninguna estrategia de scalping supere las comisiones. Eso es un resultado válido y llevaría a pasar a 1h/4h.
- La mayoría de bots minoristas pierden dinero. El objetivo es validar con rigor antes de arriesgar capital.
- Verificar que la cuenta y la API de Binance estén habilitadas para Colombia.

## 3. Arquitectura

```
bot-eve/
├─ pyproject.toml
├─ config/
│  └─ default.yaml          # pares, timeframes, comisiones, riesgo
├─ src/botEve/
│  ├─ data/                 # descarga, almacenamiento, remuestreo, validación
│  ├─ strategies/           # interfaz común + estrategias
│  ├─ backtest/             # simulador, métricas, informes
│  ├─ risk/                 # tamaño de posición, límites, kill-switch
│  ├─ execution/
│  │  ├─ base.py            # interfaz Broker común
│  │  ├─ binance_demo.py    # ccxt sobre Binance Testnet (demo)
│  │  ├─ mt5_live.py        # MetaTrader5 (live)
│  │  └─ simulated.py       # broker simulado del backtest
│  ├─ engine/               # bucle en vivo
│  ├─ dashboard/            # FastAPI + frontend
│  └─ common/               # config, logging, tipos
└─ tests/
```

Principio clave: **la misma estrategia corre igual en backtest, paper y real**. Solo cambia el "broker" (simulado, testnet o real).

## 4. Conexiones (brokers): demo en Binance, live en MetaTrader

El motor y las estrategias solo conocen la interfaz `Broker`. Hay tres implementaciones intercambiables por configuración:

| Modo | Implementación | Uso |
|---|---|---|
| `backtest` | `simulated.py` | Pruebas con datos históricos |
| `demo` | `binance_demo.py` (ccxt, Binance Testnet) | Paper trading; **activo hoy** |
| `live` | `mt5_live.py` (librería `MetaTrader5`) | Dinero real vía broker MT5 |

Interfaz mínima de `Broker`: `get_candles`, `get_balance`, `get_position`, `place_order`, `cancel_order`, `get_symbol_rules` (tamaño mínimo, paso, min notional), `close_all`.

### Supuestos por confirmar
- **MetaTrader no conecta con Binance.** El live en MT5 implica un broker MT5 distinto. Para operar cripto ahí, ese broker debe ofrecer **CFDs de cripto** (BTCUSD, ETHUSD, etc.), que **no son spot**: hay spread, apalancamiento y swaps.
- Si el objetivo era tener el live en el propio Binance, MT5 no es el camino; habría que usar la API de Binance con claves reales.
- La librería `MetaTrader5` de Python **solo funciona en Windows** y requiere la terminal MT5 abierta y con sesión iniciada. La ejecución en PC debe ser Windows.
- Confirmar que el broker MT5 elegido sea legal y esté disponible en Colombia.

### Consecuencias de diseño
- **Modelo de costos por broker:** en Binance, comisión porcentual por lado; en MT5, spread + swap + posible comisión por lote. El backtest debe poder usar cualquiera de los dos según el destino.
- **Datos del broker live:** los precios de un CFD difieren de los de Binance. Antes de operar en live hay que descargar el histórico del mismo símbolo desde MT5 (`copy_rates_range`) y **re-validar la estrategia con esos datos**, no solo con los de Binance.
- **Reglas del símbolo:** lote mínimo, paso de lote, tamaño de contrato y horarios cambian por broker; se leen de `get_symbol_rules`.
- **Riesgo:** los CFDs permiten apalancamiento. El módulo de riesgo debe limitar el apalancamiento efectivo (por ejemplo ≤ 1x al inicio) para comportarse como spot.
- **Demo y live no son idénticos.** Un buen resultado en Binance Testnet no garantiza el mismo resultado en MT5. Por eso, antes de dinero real, conviene una fase adicional en una **cuenta demo del propio broker MT5**.
- **Selector de modo explícito:** `mode: backtest | demo | live`. El modo `live` exige una bandera de confirmación adicional en la configuración y muestra una advertencia visible en el dashboard.

## 5. Fases

### Fase 1: Fundamentos y datos

Entregables:
- `pyproject.toml`, estructura de paquetes, `ruff` + `pytest`.
- `common/config.py`: carga de YAML y variables de entorno (`.env` ignorado por git).
- `common/logging.py`: logging estructurado a consola y archivo.
- `data/downloader.py`: descarga de velas de 1m desde `data.binance.vision` (2020 → hoy) para los pares candidatos, con reanudación si se corta.
- `data/store.py`: almacenamiento en Parquet (una partición por par y mes).
- `data/resample.py`: remuestreo de 1m a 5m, 15m, 1h y 4h (OHLCV correcto: open=primero, high=máx, low=mín, close=último, volume=suma).
- `data/validate.py`: detección de huecos, duplicados, timestamps desordenados y outliers (velas con high < low, precios ≤ 0, saltos anómalos).

Criterios de aceptación:
- Datos de BTC/ETH/BNB cargados sin huecos sin explicar (los huecos se reportan y documentan).
- Tests unitarios de remuestreo y validación con datos sintéticos.
- Un comando `python -m botEve.data sync` deja el dataset actualizado.

### Fase 2: Motor de backtest

Entregables:
- `strategies/base.py`: interfaz `Strategy` que recibe velas cerradas y devuelve una señal (`buy`, `sell`, `hold`) con parámetros opcionales de stop y objetivo.
- `backtest/engine.py`: simulación vela a vela.
  - La señal usa la vela **cerrada**; la ejecución ocurre en la **apertura de la siguiente** (sin look-ahead).
  - Comisión configurable (por defecto 0.1% por lado) y slippage configurable.
  - Respeto de filtros de Binance (tamaño mínimo, paso de cantidad, min notional).
  - Stops y objetivos evaluados con high/low de cada vela, con regla conservadora si ambos se tocan en la misma vela (se asume el stop primero).
- `backtest/metrics.py`: retorno total, Sharpe, drawdown máximo, win rate, profit factor, número de trades, exposición y comparación contra buy & hold.
- `backtest/walkforward.py`: validación walk-forward y un tramo final de datos reservado que no se toca hasta la evaluación final.
- `backtest/report.py`: informe HTML con curva de equity y tabla de trades.
- Estrategia de prueba trivial (cruce de medias) para validar el motor.

Criterios de aceptación:
- Resultados reproducibles (misma entrada → mismo resultado).
- Tests que prueban ausencia de look-ahead, cálculo correcto de comisiones y manejo de stops.
- Informe HTML generado para la estrategia de prueba.

### Fase 3: Estrategias v1
- 2–3 estrategias simples: cruce de medias con filtro de tendencia, RSI con tendencia, breakout con ATR.
- Búsqueda de parámetros con cuidado del sobreajuste (walk-forward, pocos parámetros).
- Comparación contra buy & hold y contra el costo de comisiones.
- Opcional: modelo ML (por ejemplo LightGBM) como filtro de señales.
- Decisión basada en datos: continuar con 5–15m o pasar a 1h/4h.

### Fase 4: Paper trading en demo (Binance Testnet)
- Interfaz `Broker` e implementación `binance_demo.py` con ccxt sobre Binance Testnet (la conexión demo ya está activa).
- Bucle en vivo (`engine/`) con estado persistido en disco para reiniciar sin perder posiciones.
- Mínimo **4–8 semanas** de operación simulada.
- Comparar resultados en vivo contra el backtest del mismo periodo.

### Fase 5: Gestión de riesgo (obligatoria antes de dinero real)
- Riesgo máximo por operación (por ejemplo 0.5–1% del capital).
- Límite de pérdida diaria y semanal.
- Kill-switch automático por drawdown, errores de API o datos obsoletos.
- Stops colocados **en el exchange** (órdenes OCO), no solo en el bot, por si el PC se apaga.
- API keys sin permiso de retiro y con restricción de IP.
- Los controles viven en un módulo que la estrategia no puede saltarse.

### Fase 6: Dashboard
- FastAPI con endpoints de estado, posiciones, historial y métricas.
- Frontend ligero (Streamlit al inicio, React opcional): curva de equity, posiciones abiertas, trades, logs, estado del bot.
- Botón de pausa y parada de emergencia.
- Alertas por Telegram.

### Fase 6b: Conector MetaTrader 5 (live)
- Implementar `mt5_live.py` sobre la librería `MetaTrader5` (Windows).
- Descargar histórico del símbolo del broker y re-validar la estrategia con esos datos y su modelo de costos (spread + swap).
- **Cuenta demo del broker MT5** durante al menos unas semanas antes de usar dinero real.
- Tests del conector con un `MetaTrader5` simulado (mock), para que la suite corra en cualquier sistema.

### Fase 7: Producción gradual
- Modo `live` vía MT5 con capital mínimo real, respetando el lote mínimo y el depósito requerido por el broker.
- En Binance, solo si se cumple el min notional.
- Ejecución en PC con reconexión automática; evaluar VPS.
- Escalar solo si el comportamiento coincide con el paper trading.
- Versión 2: estrategias intradía 1h/4h.

## 6. Stack

Python 3.11+, `ccxt`, `MetaTrader5` (Windows), `pandas`, `numpy`, `pyarrow` (Parquet), `httpx`, `pydantic`, `pyyaml`, `fastapi`, `uvicorn`, `pytest`, `ruff`. Opcionales: `vectorbt`, `lightgbm`, `streamlit`, `docker`.

## 7. Seguridad

- Secretos solo en variables de entorno o `.env` (en `.gitignore`), nunca en el repo.
- Sin permiso de retiro en las API keys; restricción por IP.
- Testnet por defecto; el modo real requiere activarse explícitamente en la configuración.
- Logs sin claves ni datos sensibles.

## 8. Riesgos abiertos

| Riesgo | Mitigación |
|---|---|
| Comisiones superan la ventaja del scalping | Backtest realista; pasar a 1h/4h si es necesario |
| Sobreajuste | Walk-forward, tramo reservado, pocos parámetros |
| Min notional imposible con 3.54 USDT | Validar filtros antes de operar; seguir en testnet |
| PC apagado o sin internet con posición abierta | Stops OCO en el exchange |
| Cambios de API o límites de Binance | Capa de abstracción con ccxt, manejo de rate limits |
| Bug que abre posiciones descontroladas | Kill-switch, límites duros, testnet primero |
| MT5 en live opera CFDs, no spot (spread, apalancamiento, swaps) | Modelo de costos propio, límite de apalancamiento, demo del broker |
| Diferencia de precios entre Binance (entrenamiento) y el broker MT5 (live) | Re-validar con el histórico del propio broker |
| `MetaTrader5` solo funciona en Windows | Ejecutar el bot en un PC Windows; mocks para tests |
| Broker MT5 no disponible o no regulado en Colombia | Verificar antes de depositar |

## 9. Próximo paso

Iniciar la **Fase 1** cuando se dé luz verde.
