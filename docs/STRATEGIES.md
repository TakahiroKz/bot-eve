# Estrategias

Estado: todas están en etapa **backtest**. Ninguna opera en demo ni live hasta cumplir los
criterios de la sección 4.

Actualización: en 5m/15m/1h ninguna pasó. La investigación en **4h con gestión de riesgo**
(`docs/RESEARCH_1H4H.md`, resultados en `docs/RESULTS_1H4H.md`) aprobó el walk-forward para
`atr_breakout` y `sma_cross`; el holdout (evaluación única) la confirmó: `atr_breakout` pasa a **demo**; `sma_cross`
queda en backtest (aprobó por poco y falta el reparto de capital entre estrategias).

## 1. Estrategias actuales

| Nombre | Rol | Idea | Fuente |
|---|---|---|---|
| `sma_cross` | **Línea base** (control) | Cruce de dos medias simples | Clásica |
| `rsi_trend` | **Núcleo** | Comprar el rebote del RSI desde sobreventa con tendencia alcista (EMA 200) | Clásica |
| `atr_breakout` | **Núcleo** | Comprar la ruptura del máximo de N velas; salir al perder el mínimo de M; stop por ATR | Canal Donchian |
| `bollinger_reversion` | **Candidata** (solo backtest) | Comprar cuando el precio vuelve a entrar por la banda inferior de Bollinger | tecnicasdetrading.com |
| `ema_adx` | **Candidata** (solo backtest) | Cruce EMA(cierre) sobre EMA(apertura) confirmado por ADX | tecnicasdetrading.com |

Las candidatas están implementadas y se pueden probar con `compare`, pero están con
`enabled: false`: no entrarán al bot en vivo hasta que superen la validación.

## 2. Revisión de https://www.tecnicasdetrading.com/estrategias-de-trading

La página es un índice de unos 160 sistemas, en su mayoría pensados para forex. Se leyeron
las reglas exactas de tres artículos (Dos EMA y ADX, Bandas Bollinger scalping, Doble RSI);
del resto solo se conoce el nombre y la categoría, así que la clasificación siguiente es
**provisional**.

### Seleccionadas (candidatas)
- **Dos EMA y ADX** (H1): EMA 5 al cierre cruza EMA 6 a la apertura, ADX(14) > 20, filtro
  opcional EMA 55 > EMA 89. *La fuente no define stop ni salida*: aquí se sale por el cruce
  contrario.
- **Bandas Bollinger scalping** (M1/M5): precio toca la banda exterior y retrocede hacia la
  media; stop ≤ mitad de la amplitud de las bandas; objetivo del 5–10% de la amplitud.
  *Solo se opera el lado comprador (spot).* Advertencia: un objetivo del 5–10% de la amplitud
  suele ser menor que el costo de ida y vuelta (~0.3%), por eso la rejilla prueba también
  objetivos de 0.5 y 1.0 de la amplitud.

### Pendientes para después (reglas cuantificables, compatibles con spot)
- **Doble RSI** (RSI 2 cruza RSI 12, con indicador Fisher): requiere implementar Fisher.
- **Túneles Vegas** (canales de medias móviles, diario/1h): tendencia de largo plazo.
- **MACD + EMA 20** (M15), **Ichimoku King** (1h), **Camarilla** (rupturas con pivotes diarios).
- **Estocástico scalping / Cowabunga**: necesitan multi-timeframe (el motor aún usa un solo intervalo).

### Descartadas (y por qué)
- **Martingala y Grid trading:** aumentan el tamaño tras pérdidas; riesgo de ruina, incompatible con capital pequeño y con el módulo de riesgo.
- **Noticias y fundamental** (NFP, ventas minoristas, carry trade): necesitan datos y calendario que no tenemos.
- **Renko, Kagi:** otro tipo de gráfico, no son velas temporales.
- **Patrones armónicos, pinbar, Hikkake, patrón 1-2-3, soportes/resistencias, Fibonacci:** son discrecionales; programarlos obliga a decisiones subjetivas que sesgan el backtest.
- **Sistemas para oro/metales:** dependen de las sesiones del mercado forex.

## 3. Cómo se añade o se quita una estrategia

- **Añadir:** crear `src/bot_eve/strategies/<nombre>.py` con una clase `Strategy` decorada con
  `@register` (nombre, descripción, `default_grid` pequeña). Se descubre sola. Después:
  `python -m bot_eve.backtest list` y `compare`.
- **Validar que no mira el futuro:** `check_no_lookahead(strategy, df)` (los tests lo aplican a todas).
- **Configurar:** añadir su bloque en `strategies:` de `config/default.yaml`.
- **Quitar del bot:** `enabled: false`. **Eliminar del todo:** borrar su archivo y su bloque.
- **Reparto de capital** (para cuando haya varias en vivo): cada una declara `capital_fraction`
  y la suma de las activas no puede superar 1 (se valida al cargar la configuración).
  Regla prevista para la Fase 4: **una sola posición por par**; si dos estrategias quieren
  operar el mismo par, gana la que lo abrió primero.

## 4. Criterios para pasar de backtest a demo (fijados antes de ver resultados)

Se evalúan con `python -m bot_eve.backtest compare`: walk-forward fuera de muestra, datos
anteriores a `backtest.holdout_start`, comisión 0.1% y slippage 0.05% por lado.

Una estrategia pasa a **demo** solo si, en un mismo intervalo:
1. Retorno neto fuera de muestra **positivo en al menos 2 de los 3 pares**.
2. **Profit factor neto ≥ 1.2** en esos pares.
3. **Al menos 100 operaciones** por par (evita resultados por suerte).
4. **Máximo drawdown mejor que el del buy & hold** del mismo par.
5. El profit factor **antes de comisiones** debe ser claramente > 1: si solo es rentable sin
   costos, no tiene ventaja real.

Cautela estadística: se prueban varias estrategias, pares e intervalos (columna `trials`), y
por puro azar alguna combinación parecerá buena. Por eso:
- Un resultado que pase estos criterios se confirma **una sola vez** con `--final` sobre el
  holdout (2025-07-01 en adelante). Debe mantener el signo (retorno neto > 0 y PF > 1).
- Si el holdout no lo confirma, la estrategia **no pasa**, y no se reajustan parámetros para
  volver a probarlo.
- Superar el buy & hold en retorno total no se exige (en cripto es muy exigente), pero sí se
  reporta para tener la referencia.
