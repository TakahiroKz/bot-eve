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
| Conexión 1: Binance (API) | Demo en **Binance Testnet** (activa hoy) y live con API real (spot) |
| Conexión 2: MetaTrader 5 | Broker **Libertex**, con cuenta demo y cuenta live (dinero real) |
| Sistema operativo | Windows (requerido por la librería `MetaTrader5`) |
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
│  │  ├─ binance.py         # ccxt: Binance Testnet (demo) o API real (live)
│  │  ├─ mt5.py             # MetaTrader5: cuenta demo o live (Libertex)
│  │  └─ simulated.py       # broker simulado del backtest
│  ├─ engine/               # bucle en vivo
│  ├─ dashboard/            # FastAPI + frontend
│  └─ common/               # config, logging, tipos
└─ tests/
```

Principio clave: **la misma estrategia corre igual en backtest, paper y real**. Solo cambia el "broker" (simulado, testnet o real).

## 4. Conexiones (brokers)

El motor y las estrategias solo conocen la interfaz `Broker`. Hay dos conexiones reales, cada una con su entorno demo y live, más el simulador del backtest:

| Modo | Implementación | Entorno | Uso |
|---|---|---|---|
| `backtest` | `simulated.py` | Datos históricos | Investigación y validación |
| `binance_demo` | `binance.py` (ccxt) | Binance Testnet | Paper trading; **activo hoy** |
| `binance_live` | `binance.py` (ccxt) | Binance API real (spot) | Dinero real; solo si se cumple el min notional |
| `mt5_demo` | `mt5.py` (`MetaTrader5`) | Cuenta demo de Libertex | Validación final antes de live |
| `mt5_live` | `mt5.py` (`MetaTrader5`) | Cuenta real de Libertex | Dinero real (CFDs) |

Cada conexión usa el mismo código con credenciales y servidor distintos según el entorno. Interfaz mínima de `Broker`: `get_candles`, `get_balance`, `get_position`, `place_order`, `cancel_order`, `get_symbol_rules` (tamaño mínimo, paso, min notional o lote), `close_all`.

### Diferencias importantes entre las dos conexiones
- **Binance spot:** compras y vendes el activo real; comisión porcentual por lado; sin apalancamiento.
- **MT5 con Libertex:** operas **CFDs**, no el activo real. Hay spread, swaps (costo por mantener posiciones abiertas), apalancamiento y horarios propios de cada símbolo.
- **Modelo de costos por conexión:** el backtest debe poder usar el de Binance (comisión) o el de MT5 (spread + swap + posible comisión por lote).
- **Datos por conexión:** los precios de un CFD difieren de los de Binance. Antes de operar en MT5 hay que descargar el histórico del mismo símbolo desde MT5 (`copy_rates_range`) y **re-validar la estrategia con esos datos**.
- **Reglas del símbolo:** lote mínimo, paso de lote, tamaño de contrato y horarios cambian por broker; se leen de `get_symbol_rules`.
- **Riesgo:** con CFDs, el módulo de riesgo limita el apalancamiento efectivo (por ejemplo ≤ 1x al inicio) para comportarse como spot.
- **Demo no es igual a live.** Los precios de un demo pueden ser más limpios que los reales, con menos slippage y requotes. Un buen resultado en demo no garantiza el mismo resultado en live.
- **Selector de modo explícito:** cualquier modo `*_live` exige una bandera de confirmación adicional en la configuración y una advertencia visible en el dashboard.

### Requisitos técnicos de MT5 (Windows)
- Terminal MT5 instalada, abierta y con sesión iniciada en la cuenta correcta.
- Habilitar "Algo Trading" (trading algorítmico) en la terminal.
- Instalar el paquete Python `MetaTrader5`.
- Tener un símbolo de cripto disponible en el Market Watch (por ejemplo BTCUSD).
- Los tests del conector usan un mock de `MetaTrader5` para poder correr sin la terminal.

### Verificaciones pendientes sobre Libertex
No he podido comprobar esto, así que debe confirmarse en la cuenta demo y en la documentación del broker antes de programar:
- Que ofrezca MT5 y permita trading algorítmico (Expert Advisors / API de Python) en la cuenta demo **y** en la live.
- Qué símbolos de cripto ofrece en MT5, con su spread, swap, lote mínimo y horarios.
- Tipo de cuenta (netting o hedging) y si restringe el scalping o tiene un tiempo mínimo de permanencia.
- Depósito mínimo y condiciones para cuentas live desde Colombia.

### Broker adicional solo para demo (desarrollo)
Recomendación para desarrollar sin depender de Libertex:
1. **MetaQuotes-Demo (servidor demo integrado en MT5).** Sin registro ni verificación, incluye símbolos de cripto y sirve para desarrollar el conector y los tests de integración.
2. **Demo de un broker ECN con MT5 y cripto** (por ejemplo IC Markets, Pepperstone o Exness) para comparar spreads y comportamiento con otro broker. Comprobar antes que su demo esté disponible desde Colombia.
3. **La demo de Libertex** queda como validación final, porque es la que replica las condiciones del live.

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

### Fase 4: Paper trading en Binance Testnet (`binance_demo`)
- Interfaz `Broker` e implementación `binance.py` con ccxt sobre Binance Testnet (la conexión demo ya está activa).
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

### Fase 6b: Conector MetaTrader 5 (`mt5_demo` y `mt5_live`)
- Implementar `mt5.py` sobre la librería `MetaTrader5` (Windows), con el mismo código para demo y live.
- Empezar con MetaQuotes-Demo para el desarrollo, luego la **cuenta demo de Libertex**.
- Descargar el histórico del símbolo del broker y re-validar la estrategia con esos datos y su modelo de costos (spread + swap).
- Operar en la demo de Libertex durante al menos unas semanas antes de usar dinero real.
- Tests del conector con un `MetaTrader5` simulado (mock), para que la suite corra en cualquier sistema.

### Fase 7: Producción gradual
- `mt5_live` (Libertex) con capital mínimo real, respetando el lote mínimo y el depósito requerido por el broker.
- `binance_live` solo si se cumple el min notional.
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
| MT5 opera CFDs, no spot (spread, apalancamiento, swaps) | Modelo de costos propio, límite de apalancamiento, demo de Libertex |
| Diferencia de precios entre Binance (entrenamiento) y el broker MT5 (live) | Re-validar con el histórico del propio broker |
| `MetaTrader5` requiere terminal abierta en Windows | Bot en el PC Windows; reconexión automática; mocks para tests |
| Libertex no permite trading algorítmico, restringe scalping o no opera desde Colombia | Verificar en la demo y en su documentación antes de depositar |

## 9. Próximo paso

Iniciar la **Fase 1** cuando se dé luz verde.
