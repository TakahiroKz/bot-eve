# Cómo usar 500 USD (decisión de capital)

Decisión del usuario (2026-09-30): concentrar los 500 USD donde mejor resultado den, y diversificar/activar la otra
cuenta cuando el capital supere ~1.000 USD.

## 1. Qué cabe esperar (simulación, `research/capital_500.py`)
`atr_breakout` 4h, parámetros fijos (40/20/2×ATR), BTC/ETH/BNB con 500 USD: tres cuentas de 500 con tope del 25% por
posición y riesgo 1%; cartera = promedio. Costos de la configuración (0.30% ida y vuelta) y mínimos del exchange.

| Periodo | Retorno anualizado | Caída máxima |
|---|---|---|
| Todo (2020-2026) | **+9.5%** | −14.1% |
| Desarrollo (< 2025-07; en muestra) | +11.6% | −14.1% |
| Posterior (≥ 2025-07; ya usado una vez) | +0.9% | −9.3% |

Por año: 2020 +21%, 2021 +34%, 2022 −6%, 2023 +7%, 2024 +12%, 2025 +3%, 2026 (hasta ahora) −3%.
Dispersión de un año (20.000 remuestreos de sus propios meses): percentil 5 **−4.3%** (478 USD), mediana **+7.6%**
(538 USD), percentil 95 +32.6% (663 USD). Probabilidad de perder dinero en un año: **18%**.
~5 operaciones al mes entre los 3 pares; 0 entradas rechazadas por mínimos.

**Lectura honesta:** ≈ +38 USD en un año típico. A ese ritmo duplicar el capital tarda ~7.6 años: el capital crecerá sobre
todo por aportes, no por ganancias. El tramo reciente es el más débil. Sirve para aprender y validar la ejecución.

## 2. Otras opciones para 500 USD
| Opción | Estado | Comentario |
|---|---|---|
| Binance spot, `atr_breakout` 4h | Validada (walk-forward, holdout, demo en curso) | Única con evidencia |
| Libertex, `atr_breakout` 4h en cripto | No viable | Lote mínimo BTC/ETH exige ~4.000–5.000 USD |
| Libertex, scalping Forex | **Sin validar** | Costos bajos en demo, pero no hay ventaja demostrada (ver §4) |
| Claude/API | Coste propio | 25 USD/mes = 60% anual sobre 500 USD: debe salir de un presupuesto de aprendizaje, no del capital |

## 3. Ampliar el universo de pares (prueba pre-registrada, escrita antes de descargar datos)
**Hipótesis:** la misma regla fija (40/20/2×ATR, 4h, riesgo 1%) aplicada a más pares líquidos aumenta las operaciones sin
diluir la calidad. Es una prueba nueva: no se reoptimiza nada.

- **Universo (fijado ahora):** SOLUSDT, XRPUSDT, ADAUSDT, DOGEUSDT, LINKUSDT, LTCUSDT, AVAXUSDT, DOTUSDT. Se informan **todos**.
- **Datos:** solo anteriores a 2025-07-01 para decidir. Tope de posición 25%, riesgo 1%, 500 USD por cuenta.
- **Costos más duros para estos pares** (menos líquidos): slippage 0.10% por lado (el doble de BTC/ETH/BNB).
- **Criterio por par (desarrollo):** PF neto ≥ 1.2, ≥ 40 operaciones y caída máxima menor que la del buy & hold.
- **Confirmación única en el holdout (≥ 2025-07-01)** para el conjunto que pase: la cartera equiponderada debe tener
  retorno neto > 0 y PF > 1, y al menos 2/3 de los pares incluidos retorno positivo. Si falla, el universo no se amplía.
- **Correlación:** se informa la correlación de retornos entre pares; más pares no es diversificación real si van juntos.
- **Límites de cartera si se amplía:** máx. 4 posiciones abiertas a la vez y riesgo total en los stops ≤ 4% del capital.

### 3.1 Resultado (ejecutado una vez, `research/universe_test.py`)
**Paso 1, desarrollo** (costos duros 0.1% comisión + 0.1% slippage por lado): **6 de 8 pares pasan**.

| Par | Ops | PF neto | Retorno | Caída máx. | Caída del B&H | Pasa |
|---|---|---|---|---|---|---|
| SOL | 90 | 2.59 | +136% | −13.7% | −96.6% | sí |
| XRP | 106 | 2.11 | +128% | −27.3% | −84.5% | sí |
| ADA | 111 | 1.81 | +93% | −15.2% | −92.2% | sí |
| DOGE | 105 | 2.16 | +152% | −25.8% | −92.9% | sí |
| LINK | 117 | 1.26 | +26% | −24.5% | −90.4% | sí (por poco) |
| AVAX | 88 | 2.36 | +172% | −14.5% | −93.7% | sí |
| LTC | 113 | 1.07 | +5% | −19.8% | −89.7% | **no** |
| DOT | 110 | 0.81 | −15% | −34.6% | −94.2% | **no** |

Correlación media de retornos diarios entre los pares: 0.21.

**Paso 2, holdout (una sola evaluación)** para los 6 que pasan: cartera equiponderada **+4.7%** en 15 meses,
**PF agregado 1.31**, **6 de 6 pares positivos** (SOL +7.2%, XRP +2.6%, ADA +0.2%, DOGE +0.8%, LINK +10.2%, AVAX +7.4%;
21–26 operaciones cada uno). **Veredicto pre-registrado: aprueba ampliar el universo.** El holdout de estos pares queda consumido.

**Cautelas (importantes):**
1. **Sesgo de supervivencia:** los 8 pares se eligieron hoy entre las monedas grandes y líquidas, es decir, las que sobrevivieron.
   Monedas que colapsaron o se eliminaron no están en la prueba; el desarrollo sobrestima el resultado.
2. **Pocos datos por par en el holdout** (≈ 22 operaciones): ADA (+0.2%) y DOGE (+0.8%) son casi planos. Los 6 «positivos» no son 6
   confirmaciones independientes: es el mismo mercado.
3. **El desarrollo incluye el mercado alcista de 2020-2021**, muy favorable a estas monedas.
4. **Falta medir el efecto en la cartera con capital compartido:** el tope del 25% por posición y el capital de 500 USD limitan
   a ~4 posiciones a la vez; el rendimiento de la cartera con 9 pares no es la suma de los pares.
5. **Hoy el motor en vivo reparte `capital_fraction` entre TODAS las combinaciones** (con 9 pares cada posición sería ~8% del capital, no
   25%): antes de ampliar hay que implementar un máximo de posiciones simultáneas.

## 3.2 Interés compuesto o plano
El bot **reinvierte** (compuesto): el tamaño de cada posición sale del capital **actual** (riesgo 1% del capital actual, tope 25% del
capital actual). Tras pérdidas las posiciones se reducen solas; tras ganancias crecen. Simulación 500 USD, 6.7 años, 3 pares:
compuesto **922 USD (+9.5% anual)** vs tamaño fijo sobre 500 USD **≈ 856 USD (≈ +8.3%)** (aproximado: la curva plana no incluye el
marcado diario de posiciones abiertas). A este nivel de retorno la diferencia es pequeña; el compuesto amplifica en ambos sentidos.
Proyección con +9.5% anual sin aportes: 1 año 548 · 3 años 656 · 5 años 787 · 10 años 1.239 USD. Con 50 USD/mes de aporte:
1 año 1.173 · 3 años 2.718 · 5 años 4.569 · 10 años 10.975 USD (aportado 6.500; ganancia 4.475).

## 4. Cuándo activar Libertex (condiciones, no fechas)
Todas deben cumplirse:
1. Fase Q0-FX superada con los criterios fijados en `docs/AI_TRADER_PLAN.md` §10 (hoy: **costo aprobado en demo, ventaja sin demostrar**).
2. Costo **real** verificado con una prueba pequeña con dinero real (el demo suele tener spreads más estrechos que el real).
3. Política explícita de apalancamiento máximo e implementación de cortos (hoy el conector es solo largo y limita a 1x).
4. Capital total ≥ ~1.000 USD, para que cada mitad supere los mínimos útiles.

## 5. Mediciones de Forex en la demo (2026-09-30)
- **Roundtrip EURUSD (0.01 lotes, hora de baja liquidez):** compra 1.13308, venta 1.13307 → **0.1 pip** de spread y **costo de cierre 0**.
  La comisión de **entrada** no se leyó (corregido en el conector): se mide con el saldo antes y después.
- `base-rates` a 5m: costo provisional (0.3 pip) = 0.09–0.14 R; acierto necesario 43.7–45.7% vs 38.7–41% al azar (**+4 a +7 pts**).
  A 15m: 0.04–0.07 R, **+3.6 a +5.2 pts**. Con 1 pip de spread a 5m: +8 a +15 pts. La esperanza bruta al azar es ≈ 0.
- **Puerta 1 (costo ≤ 0.15 R mediano y ≤ 0.25 R en las peores horas): aprobada** con el costo provisional (peor bloque 0.19 R en EURUSD 00-04h),
  condicionada a la comisión de entrada y a que el spread real coincida con el de la demo.
- Aprobar la puerta de costos **no demuestra ventaja**: aún hay que ganarle al azar por +4 a +7 pts de acierto.
