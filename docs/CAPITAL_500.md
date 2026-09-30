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
