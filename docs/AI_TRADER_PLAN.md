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
