# Plan: bot de trading con IA (Claude), scalping

Estado: **solo planificación**. No hay código. Objetivo del usuario: scalping con Claude, primero en
cuenta demo y después en real con ~500 USD.

## 1. La realidad que condiciona el diseño (leer primero)

### 1.1 El scalping paga costos que la IA no elimina
Costo de ida y vuelta en Binance spot ≈ **0.20%** (0.15% de comisión + slippage). Tasa de aciertos
mínima para no perder, según el objetivo y el stop de cada operación:

| Objetivo / stop | Aciertos mínimos |
|---|---|
| +0.5% / −0.30% | **62.5%** |
| +0.7% / −0.35% | 52.4% |
| +1.0% / −0.50% | 46.7% |
| +1.5% / −0.75% | 42.2% |

Un scalping «de verdad» (objetivos de 0.3–0.5%) exige acertar más del 60% de las veces. Con objetivos
mayores la tasa exigida baja, pero ya no es scalping: son operaciones de horas.

### 1.2 Nuestra propia evidencia
En 5m y 15m, las 5 estrategias de reglas probadas perdieron con costos reales (profit factor antes
de comisiones ≈ 0.9–1.2; ver `docs/STRATEGIES.md`). No hay una ventaja bruta que la IA parta de aprovechar:
el punto de partida es **cero o negativo**. Claude tendría que generar esa ventaja, no solo filtrar.

### 1.3 Problemas propios de usar un LLM para decidir operaciones
| Problema | Consecuencia |
|---|---|
| **Backtests contaminados.** El modelo pudo ver precios, noticias y gráficos históricos al entrenarse. | Un backtest con Claude sobre datos pasados **no es fiable**. Solo vale la evaluación hacia adelante (forward). |
| **No determinismo.** Los modelos actuales no admiten fijar `temperature`. | Misma entrada, respuestas distintas. Hay que medir la variabilidad y registrar todo. |
| **Costo por llamada.** | Ver 1.4: llamar en cada vela es inviable con 500 USD. |
| **Latencia** (segundos por llamada). | Aceptable en velas de 5–15 min; inadecuado para scalping de alta frecuencia. |
| **Sobreconfianza y narrativas plausibles.** | Un LLM puede justificar cualquier entrada con un texto convincente. Solo cuentan los resultados medidos. |
| **Inyección de instrucciones** si algún día se le dan noticias o textos externos. | Nunca darle herramientas, claves ni ejecución; los textos externos son datos no confiables. |

### 1.4 Costo de la API (estimación; verificar con `usage` real)
Supuestos: 1.200 tokens de instrucciones fijas (en caché) + 1.300 dinámicos + 250 de salida por decisión.
Precios por millón de tokens (referencia del 2026-09-25): Haiku 4.5 $1/$5, Sonnet 5.5 $2/$10, Opus 5.5 $4/$20.

| Cuándo se llama a Claude | Haiku 4.5 | Sonnet 5.5 | Opus 5.5 |
|---|---|---|---|
| **En cada vela de 5 m** (3 pares, 864 llamadas/día) | $69/mes (14% de 500) | $138/mes (28%) | $271/mes (54%) |
| **Solo en ~15 candidatos al día** | $1.2/mes | $2.4/mes | $4.7/mes |

Llamar en cada vela consume entre el 14% y el 54% del capital **al mes**: imposible de recuperar. La
única arquitectura viable es **un filtro determinista que propone candidatos y Claude los juzga**.

### 1.5 Con 500 USD
- **Mínimo de Binance: 5 USD por orden** (no es problema). En spot sin apalancamiento la posición máxima es
  500 USD: con un stop de 0.5%, el riesgo real por operación es ~2.5 USD (0.5%), no el 1% del bot actual.
- **MT5/Libertex no sirve con 500 USD para BTC** (lote mínimo 0.01 BTC ≈ 840 USD) y el spread de ETH es 0.2%
  más 0.1% de comisión: el scalping es inviable ahí. **El entorno real posible es Binance spot (solo largos).**
- Solo largos reduce a la mitad las oportunidades del scalping (no se puede vender en corto).

## 2. Arquitectura propuesta (Claude decide poco, el código decide el riesgo)

```
velas 5m/15m ─► generador determinista de CANDIDATOS ─► Claude (juez, salida JSON estructurada)
                      │                                        │
                      └──────────────► validador determinista ◄┘
                                               │
                                     RiskManager existente (tamaño, stop, límites, kill switch)
                                               │
                                     Broker existente (Binance testnet → real)
```
Reglas de hierro:
1. **Claude no tiene herramientas, claves ni acceso a la cuenta.** Solo recibe números y devuelve un JSON.
2. **Solo puede reducir actividad**: aceptar o rechazar un candidato y acotar stop/objetivo dentro de límites
   fijos. **No decide el tamaño** (lo hace el gestor de riesgo) ni puede quitar el stop.
3. **Cualquier fallo = no operar** (API caída, respuesta inválida, rechazo de seguridad, timeout, límite de gasto).
4. Toda decisión queda registrada: prompt (versión), entrada, respuesta, tokens, latencia, costo, resultado.
5. **Presupuesto de API con tope diario y mensual**; al alcanzarlo, el bot deja de consultar y no opera.

Candidatos (deterministas, ~10–20 al día): ruptura de rango con volumen, pullback a EMA en tendencia de 1h,
rebote en banda de Bollinger con RSI. Cada candidato incluye contexto numérico: últimas N velas compactadas,
indicadores, tendencia 1h/4h, spread, volumen relativo y estado de riesgo del día. Sin texto externo.

Salida estructurada (esquema JSON validado; sin `tool_choice` forzado, con `output_config.format`):
`{accion: "entrar_largo" | "omitir", confianza: 0-1, stop_atr: 0.5-2, objetivo_atr: 0.5-4, motivo: ≤200 caracteres}`.
Fuera de rango o mal formado → omitir. Modelo inicial: **Haiku 4.5** y **Sonnet 5.5** en paralelo (Opus 5.5
solo si aporta); instrucciones fijas en caché; `max_tokens` bajo; razonamiento mínimo; `stop_reason: refusal` → omitir.

## 3. Cómo se evalúa sin engañarse (criterios fijados antes)

**Modo sombra hacia adelante** (sin órdenes): cada candidato recibe la decisión de Claude y, para **todos**
(aceptados y rechazados), el motor determinista calcula el resultado contrafactual con costos reales. Así se mide
el valor del filtro sin arriesgar dinero ni contaminar con datos históricos.

Comparaciones (mismos candidatos, mismos costos, **incluyendo el costo de la API por operación**):
- **A.** Tomar todos los candidatos (sin IA).  **B.** Filtro al azar con la misma tasa de aceptación.  **C.** Claude.
- Métricas: expectancy neta por operación, profit factor, tasa de aceptación, intervalo de confianza 95% (bootstrap).
- Muestra mínima: **≥ 300 candidatos resueltos y ≥ 100 aceptados por modelo** (≈ 3–4 semanas a 15/día).
- **Aprobado solo si** Claude supera a A y a B con el extremo inferior del IC95% > 0, la expectancy neta es
  positiva tras costos de API y hay ≥ 100 operaciones aceptadas.
- Variabilidad: re-consultar el 10% de candidatos 2 veces; si las decisiones difieren mucho, el filtro es ruido.
- El prompt queda **congelado** durante una evaluación; cambiarlo reinicia la muestra.
- Cota de realismo: para aportar algo, el subconjunto elegido debe tener un borde bruto ≥ ~0.25% por operación
  (el costo). Si «tomar todos» está en ≈ −0.2% neto, Claude tiene que elevar ~0.25 puntos por operación.

## 4. Fases y puertas

| Fase | Qué | Duración | Puerta para seguir |
|---|---|---|---|
| F0 | Generador de candidatos, registro, cuenta de API con tope de gasto | ~1 semana | Candidatos ≈ 10–20/día; registro completo |
| F1 | **Modo sombra**, datos reales, 2–3 modelos | 4 semanas | Criterios de la sección 3 cumplidos |
| F2 | **Demo con órdenes** en Binance Testnet (fricciones reales de fills y stops), mismo gestor de riesgo | 4+ semanas | Resultados coherentes con F1; sin incidentes |
| F3 | **Real**: ver abajo | continuo | Decisión explícita tuya |

**Criterio de parada (time-box):** si tras F1 el filtro no supera a «tomar todos», **se detiene**. No se reajusta el
prompt una y otra vez hasta que «funcione» (eso es sobreajuste).

### F3 con 500 USD (límites propuestos, tú decides)
- Empezar con **100–150 USD**, no con los 500. Escalar solo tras varias semanas dentro de lo esperado.
- **Pérdida máxima total: 15% del capital asignado** (≈ 75 USD sobre 500): al alcanzarla, se detiene todo y se revisa.
- Pérdida diaria máxima 2%, tope de operaciones por día, API keys sin retiros y con restricción de IP.
- Revisión semanal del dashboard; sin aumentar el tamaño por «confianza» del modelo ni promediar pérdidas.

## 5. Presupuesto
- **API:** con filtro de candidatos ≈ $1–5/mes; proponer **tope duro de $20–30/mes** (incluye pruebas y dos modelos).
- **Capital real:** hasta 500 USD, pero con los límites de 4. Comisión y slippage ≈ 0.20% por operación.

## 6. Riesgos principales
| Riesgo | Mitigación |
|---|---|
| Que no haya ventaja (lo más probable según la evidencia) | Modo sombra y criterio de parada antes de arriesgar nada |
| Sobreajuste del prompt | Prompt congelado por evaluación; muestra mínima; comparar contra azar |
| Costos de API fuera de control | Filtro de candidatos, tope diario/mensual, caché de instrucciones |
| Respuestas inválidas o rechazos | Validación estricta; ante cualquier duda, omitir |
| Inyección de instrucciones | Sin herramientas ni textos externos; solo datos numéricos |
| Dinero real por accidente | Las mismas dobles confirmaciones y la detección real/demo ya implementadas |
| Autoengaño («parece que acierta») | Solo cuentan métricas con IC; se registra todo |

## 7. Alternativa recomendada en paralelo (mejor relación costo/valor)
Usar Claude **como filtro de contexto de la estrategia de 4h ya validada** (`atr_breakout`): unas pocas llamadas al
día, ≈ $0.05/día, evaluación en modo sombra igual que arriba. Mucho más barato y con más probabilidad de aportar
(menos ruido, más contexto de régimen). Y como **analista del diario** (resumen semanal y post-mortem de operaciones)
sin decidir dinero.

## 8. Decisiones que necesito de ti
1. **Sede:** Binance spot (recomendada; demo = Testnet; real = 500 USD solo largos). MT5 queda descartado para esto.
2. **Presupuesto de API:** ¿tope de $20–30/mes te parece bien? Necesitarás una `ANTHROPIC_API_KEY` propia en `.env`
   (nunca en el chat) con límite de gasto configurado en la consola de Anthropic.
3. **Time-box:** ¿aceptas el criterio de parada si F1 no supera a «tomar todos»?
4. **Capital real:** ¿la pérdida máxima del 15% (≈ 75 USD) te parece aceptable?
5. **Empezar por:** (a) scalping con candidatos en modo sombra, (b) filtro sobre la estrategia de 4h, o ambos.


---

## 9. Versión 2: revisión de la propuesta «Claude supervisor + motor cuantitativo» (2026-09-30)

### 9.1 Medición previa: cuánta ventaja tendría que aportar el modelo
Entrando en **todas** las velas al azar (sin inteligencia), con triple barrera (objetivo, stop y plazo) sobre datos de
desarrollo, costo de ida y vuelta 0.20%. Script: `research/base_rates.py`.

| Vela | Objetivo / stop | P(objetivo) al azar | Acierto necesario | **Mejora necesaria** |
|---|---|---|---|---|
| 1m | +0.30% / −0.15% | 28–31% | 77.8% | **+47 a +50 pts** |
| 1m | +0.50% / −0.25% | 20–25% | 60.0% | +35 a +40 pts |
| 5m | +0.50% / −0.25% | 30–32% | 60.0% | +28 a +30 pts |
| 5m | +0.75% / −0.38% | 26–29% | 51.1% | +22 a +25 pts |
| 15m | +1.00% / −0.50% | 32–33% | 46.7% | **+14 pts** |
| 15m | +1.50% / −0.75% | 30–32% | 42.2% | +10 a +12 pts |
| 15m, solo con 4h alcista | +1.00% / −0.50% | BTC 33.5%, ETH 32.7% | 46.7% | BTC +13.2 / ETH +13.9 pts |

- **La esperanza bruta al azar es ≈ 0** (el precio se comporta casi como un paseo aleatorio): todo el resultado
  neto es −0.2% por operación, que es el costo. La ventaja tiene que venir de **información**.
- **1m y 5m con objetivos pequeños son inviables:** exigirían que un modelo suba la tasa de acierto entre 22 y 50
  puntos porcentuales. Ningún modelo basado en precios y volumen logra algo parecido de forma sostenida.
- **El filtro de 4h por sí solo casi no ayuda** (≈ +1 punto en BTC, 0 en ETH). Sirve como contexto, no como ventaja.
- **15m con objetivos ≥ 1%** es el rincón menos exigente (+10 a +14 pts): sigue siendo muy grande, pero es el único
  donde vale la pena probar un modelo.

### 9.2 Qué se conserva de la propuesta (está bien pensado)
- Claude como **supervisor** y no como quien genera cada compra/venta. Señal y riesgo **deterministas y cuantitativos**.
- Decisiones auditables (probabilidad, costo, régimen, estrategia, riesgo, validación) y registro de todo.
- Opus para diseñar e investigar, Sonnet para el trabajo frecuente y Haiku para tareas sencillas de bajo costo.
- Usar Opus en cada tick sería innecesariamente caro (tabla de la sección 1.4).
- La pregunta clave es el **modelo cuantitativo** que estime P(ganar). Coincido: ahí está todo el valor.

### 9.3 Qué cambiaría
1. **Mercado:** la propuesta habla de Forex, pips y WebSocket de broker. Nuestro mercado es **cripto spot en Binance**
   (solo largos; real posible con 500 USD) y CFD de cripto en MT5 (no viable con 500 USD). No aplican «0.4 pips» ni un
   «news engine» de forex; los costos relevantes son comisión y slippage (~0.20%).
2. **Claude no «solicita herramientas» de trading.** Sin claves ni ejecución: recibe datos, devuelve un JSON y solo
   puede **vetar o reducir**, nunca aumentar tamaño ni quitar el stop.
3. **Haiku no debe ejecutar órdenes.** Ejecución y gestión de posiciones son código determinista (ya existen:
   gestor de órdenes, reconciliación con el exchange, stops en el servidor). Un LLM en esa ruta añade riesgo sin beneficio.
   Uso correcto: Sonnet valida candidatos y anomalías; Haiku o Sonnet (por lotes) redactan el diario y el post-mortem;
   Opus investiga **fuera de línea**.
4. **Claude aporta auditoría, no ventaja.** Si el modelo cuantitativo no produce una ventaja neta, ningún supervisor
   la crea. Por eso **el supervisor se construye el último**.
5. **Acotar las llamadas al supervisor** (p. ej. ≤ 30 al día) para no volver al problema de costos de la sección 1.4.

### 9.4 El modelo cuantitativo: cómo hacerlo serio
- **Metaetiquetado con triple barrera (López de Prado):** reglas simples generan **candidatos**; el modelo predice si cada
  candidato alcanza el objetivo antes que el stop **con la mecánica y los costos reales**. Es mucho más fácil que predecir
  la dirección del precio y se alinea con la arquitectura de candidatos.
- **Validación sin fugas:** walk-forward **purgado con embargo** (las etiquetas miran hacia adelante y se solapan), solo
  velas cerradas y alineación de 4h por hora de cierre (ya implementada en la medición).
- **Modelos pequeños y línea base:** regresión logística y gradient boosting poco profundo; comparar siempre contra
  «tomar todos» y contra el azar.
- **Calibración:** «0.71» debe significar 71% real. Se mide con curvas de calibración antes de usar la probabilidad.
- **Esperanza neta con margen:** operar solo si `P·objetivo − (1−P)·stop − costos > umbral`, no si P > 0.5.
- **Pruebas de cordura:** barajar las etiquetas debe dar rendimiento ≈ azar; estabilidad de la importancia de variables;
  contar todas las combinaciones probadas (corrección por pruebas múltiples).
- **Datos:** tenemos velas de 1m desde 2020 (3,5 millones por par). Nuestro descargador **descartó** el volumen comprador
  de las velas (`taker_buy`), que da un indicador de flujo de órdenes gratis; se recupera. Sin libro de órdenes ni
  latencia, el techo de un scalping real es bajo (ahí está la ventaja de los profesionales y no es accesible).

### 9.5 Arquitectura v2
```
Velas 1m/5m/15m + flujo comprador ─► Feature engine (multi-timeframe, solo velas cerradas)
        ─► Generador de candidatos (reglas) ─► Modelo meta-label P(ganar), calibrado
        ─► Filtro de esperanza neta (P, objetivo, stop, costos)
        ─► [Claude supervisor: anomalías / régimen / noticias; solo puede vetar]  ← se construye al final
        ─► Risk Engine (existente) ─► Order/Position manager y Broker (existentes)
                                       └─► Dashboard + Telegram (existentes)
```
| Componente de tu propuesta | Estado |
|---|---|
| Backtesting engine, Risk engine, Broker adapter, Order/Position manager | ✅ existen |
| Logging y monitoring | ✅ registro, dashboard local y alertas |
| Estrategias y modo demo (Binance Testnet / MT5 demo) | ✅ |
| Feature engine multi-timeframe, etiquetado triple barrera | ❌ por construir |
| Modelo ML y validación purgada | ❌ por construir |
| Clasificador de régimen | ❌ (una versión simple, dentro del feature engine) |
| Motor de noticias | ❌ diferido: hoy sin ventaja demostrable, solo añadiría riesgo de inyección |
| Claude supervisor | ❌ al final, si el modelo cuantitativo sobrevive |

### 9.6 Siguiente paso: fase Q0, prueba de muerte barata (sin API de Claude ni dinero)
1. Recuperar el volumen comprador en las velas de 1m y reconstruir 5m/15m.
2. Feature engine multi-timeframe (4h/1h como contexto, 15m/5m como ejecución), sin mirar el futuro.
3. Generador de candidatos y etiquetas de triple barrera con costos reales (objetivo ≥ 1% en 15m como caso principal).
4. Modelo base (logística y boosting pequeño) con walk-forward purgado, calibración y prueba de barajado de etiquetas.
5. **Criterio fijado antes:** en validación purgada y una sola vez en un tramo sellado, la esperanza neta por operación
   debe ser > 0 con el extremo inferior del IC95% > 0 y ≥ 300 operaciones; y debe superar a «tomar todos» y al azar.
   Si no lo cumple, **se detiene aquí**: no se construye el supervisor Claude ni se arriesga dinero.


---

## 10. Propuesta «Propuesta_scapling.docx»: revisión (2026-09-30)

El documento plantea tres estrategias de scalping **para Forex** y una arquitectura con clasificador de régimen
(TREND / RANGE / EVENT / NO_TRADE), motor de costos en R y un protocolo de pruebas:
- **A. Momentum con retroceso:** contexto M15 (EMA50 > EMA200, ADX > 20), entrada M5 (retroceso a la EMA20 y ruptura de la
  vela previa), stop 1.2×ATR(M5), objetivo 1.8×ATR(M5).
- **B. Reversión a la media con z-score:** M1/M5, solo en rango (ADX < 18), entrada en z = ±2, salida en z ≈ 0, stop 1×ATR.
- **C. Reversión en los fixings** (Tokio, Fráncfort, Londres): confirmar la reversión *después* del fixing, salida por tiempo.
- Un solo mecanismo activo a la vez, decidido por el régimen; IA solo para selección/configuración/análisis.

### 10.1 Qué es muy valioso y se adopta
1. **El motor de costos medido en R.** Es la forma correcta de juzgar un scalping (ver 10.2).
2. **Un estado `NO_TRADE`** y un único mecanismo activo a la vez (coincide con nuestra regla de una posición por símbolo).
3. **Protocolo de datos:** desarrollo → validación → fuera de muestra real (2026), con datos bid/ask y no solo el precio medio.
4. **Monte Carlo sobre la secuencia de operaciones**, y medir expectancy neta, estabilidad del profit factor y trades/día.
5. **Parámetros iniciales como hipótesis** (1.2/1.8 no se optimizan hasta que se vean fuera de muestra).
6. La IA **no** decide «comprar EURUSD»: propone régimen/configuración; las reglas y el riesgo son deterministas.

### 10.2 El punto decisivo: costo en R según el instrumento
Con las reglas del propio documento (stop 1.2×ATR, objetivo 1.8×ATR, R:R 1.5), la probabilidad de tocar el objetivo
**al azar es 40%**. Acierto necesario = (1 + costo_R) / 2.5:

| Costo de ida y vuelta | Acierto necesario | Mejora necesaria sobre el azar |
|---|---|---|
| 0.05 R | 42.0% | +2 pts |
| **0.12 R** (ejemplo del documento) | 44.8% | **+4.8 pts** |
| 0.25 R | 50.0% | +10 pts |
| 0.50 R | 60.0% | +20 pts |
| 1.00 R | 80.0% | +40 pts |

En nuestros datos de cripto (ATR(14) mediano, datos de desarrollo), el stop de 1.2×ATR es muy corto frente al costo:

| Par / vela | Stop (1.2×ATR) | Costo en R (Binance spot) | Costo en R (CFD cripto MT5) | Mejora necesaria (Binance / MT5) |
|---|---|---|---|---|
| BTC 1m | 0.09% | 2.17 R | 1.68 R | imposible |
| BTC 5m | 0.24% | 0.84 R | 0.65 R | +33 / +26 pts |
| BTC 15m | 0.44% | 0.45 R | 0.35 R | +18 / +14 pts |
| ETH 5m | 0.31% | 0.65 R | 0.50 R | +26 / +20 pts |
| ETH 15m | 0.58% | 0.35 R | 0.27 R | +14 / +11 pts |

**Conclusión:** el esquema del documento tiene sentido cuando el costo es ≈ 0.05–0.15 R, típico de **Forex mayor con spread
bajo**; en cripto, con ~0.2% de costo, el costo es de 0.3 a más de 2 R y la ventaja exigida es irreal. No es una falla de la
propuesta: está escrita para otro mercado.

### 10.3 Lo que hay que corregir o cuidar
1. **Fuentes.** El documento cita estudios (momentum intradía en FX, reversión con régimen de 2026, fixings 1999–2019,
   Bank of Canada). **No pude verificarlos.** Son hipótesis: que un efecto exista en datos históricos no implica que siga
   existiendo ni que supere costos. Hay que leer los originales.
2. **Los fixings son una anomalía de FX**, con horario fijo (Tokio, Fráncfort, Londres). No existe en cripto. Además, el
   servidor de MT5 va en UTC+2/+3 con cambio de horario: requiere manejar zonas horarias con cuidado.
3. **El filtro de noticias** necesita un calendario económico (no tenemos). Empezar con ventanas de exclusión fijas alrededor
   de eventos conocidos y medir cuánto cambia el resultado.
4. **Las variantes SHORT** no funcionan en Binance spot (solo largos). Requieren CFD (MT5). Hoy **nuestro motor y el
   `Mt5Broker` son solo largos**: hay que añadir ventas en corto a backtest, motor en vivo y conector.
5. **El ejemplo del motor de costos (P = 56%, +1.5 R) es una suposición**, no un resultado: 56% exige +16 pts sobre el 40% del azar.
6. **El clasificador de régimen añade parámetros** (ADX, pendiente, percentiles…): más riesgo de sobreajuste. Empezar simple.
7. **Datos.** Las velas de MT5 traen el spread por barra (útil) pero la terminal limita las barras descargables
   (en FX, 1m ≈ 2 meses con 100.000 barras; 5m ≈ 1,3 años; 15m ≈ 4 años). Se puede subir el límite en MT5.

### 10.4 Decisión clave: dónde se probaría el scalping
| Opción | Ventajas | Inconvenientes |
|---|---|---|
| **Cripto en Binance spot** | Real con 500 USD, simple | Costo 0.3–2+ R: inviable en 1m/5m; +14 a +18 pts incluso en 15m |
| **Forex (y metales) en Libertex/MT5** | Costo potencialmente bajo (si el spread lo es), largos y cortos, apalancamiento | Hay que **medir** spread/comisión/swap reales; requiere cortos; datos limitados; apalancamiento alto = riesgo |

### 10.5 Fase Q0-FX (sin dinero y sin API de Claude): medir antes de construir
1. `python -m bot_eve.data mt5-info --symbols EURUSD GBPUSD USDJPY AUDUSD XAUUSD` → spread, comisión, swap, lote mínimo reales.
2. Subir en MT5 «Máx. barras en el gráfico/en la historia» y `python -m bot_eve.data mt5-sync --symbols EURUSD GBPUSD USDJPY AUDUSD --intervals 5m 15m 1h`.
3. Calcular el **costo en R** real por símbolo con el ATR y el spread medianos de esos datos.
4. **Puerta 1 (fijada antes):** solo se sigue con los símbolos donde el costo sea ≤ 0.15 R con spread mediano **y** ≤ 0.25 R en las horas
   de peor spread. Si ninguno lo cumple, el scalping en este broker se descarta.
5. Si hay símbolos que pasan: añadir cortos al motor; implementar la estrategia A con desarrollo/validación/fuera de muestra
   separados, probar contra el azar con triple barrera, y solo entonces B y C.
