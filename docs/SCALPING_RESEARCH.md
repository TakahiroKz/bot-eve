# Investigación de scalping (1m / 5m / 15m) — pre-registro

Escrito ANTES de ejecutar. Objetivo: ver números rápido y decidir si alguna estrategia de scalping merece pasar a demo.

## Qué se prueba (parámetros fijos, sin optimizar)
Datos: Binance BTC, ETH, BNB, SOL (SOL desde 2020-08). Marcos de entrada 1m, 5m, 15m; contexto de 1h (solo velas CERRADAS: sin look-ahead).
Largos y cortos simulados (los cortos requieren futuros/CFD: el motor en vivo hoy es solo largo).

- **A, pullback de momentum:** 1h EMA50 > EMA200 (alcista) o < (bajista). Entrada: en el marco de entrada el cierre previo estaba al otro lado de la EMA20
  y la vela actual cierra del lado de la tendencia con cuerpo a favor (alcista: cierre > EMA20 y > apertura; bajista: espejo).
- **B, reversión por z-score:** 1h ADX(14) < 20 (rango). Entrada largo si z = (cierre − SMA48)/desv48 < −2.5; corto si z > +2.5.
- **Línea base aleatoria:** lado aleatorio (semilla fija) en ~1% de las velas, mismo stop/objetivo: mide cuánto cuesta operar sin información.
- Salidas: stop = 1.2×ATR14 (A) o 1.5×ATR14 (B); objetivo = 1.8×ATR (A) o 1.5×ATR (B); salida por tiempo a las 24 velas (cierre).
  Una posición a la vez por par; entrada en la apertura de la vela siguiente a la señal; si la vela toca stop y objetivo, gana el stop;
  gap más allá del stop se ejecuta a la apertura.
- Resultados en múltiplos de R (R = distancia al stop) y compuesto con 0.5% de riesgo por operación.

## Costos (por lado)
- **F (optimista, futuros):** comisión 0.04% + slippage 0.02%. Se usa como filtro: si falla incluso aquí, está muerta.
- **S (realista spot/CFD):** comisión 0.10% + slippage 0.05%. Los supervivientes de F se vuelven a medir aquí.

## Criterios (desarrollo = antes de 2025-07-01, costos F, 4 pares agregados), por estrategia × marco (6 combinaciones)
1. >= 500 operaciones. 2. Expectativa neta >= +0.05 R. 3. PF >= 1.15. 4. Expectativa positiva en >= 4 de los 5 años 2021-2025 (2025 = primer semestre).
5. Expectativa positiva en >= 3 de los 4 pares.
Quien cumple 1-5 se mide con costos S: debe seguir con expectativa > 0. Solo entonces se evalúa el holdout (UNA vez): expectativa > 0 y PF > 1.
Son 6 combinaciones sobre los mismos datos: se reporta el número de pruebas; un único aprobado marginal no se considera evidencia sólida.
Si nada pasa: scalping de cripto con estos métodos queda descartado y se documenta.

## Resultado (desarrollo, 2020 a 2025-06, 4 pares; `research/scalp_test.py`)
«R bruta» = ya con el slippage pero sin comisiones. Costos F = 0.04% comisión + 0.02% slippage por lado.

| Estrategia | Marco | Ops | Gana % | R bruta | R neta (F) | Costo (R) | PF (F) | Años + | Pares + |
|---|---|---|---|---|---|---|---|---|---|
| A pullback | 15m | 35.047 | 39 | −0.068 | −0.244 | 0.18 | 0.67 | 0/5 | 0/4 |
| B z-score | 15m | 8.582 | 46 | −0.102 | −0.248 | 0.15 | 0.61 | 0/5 | 0/4 |
| aleatoria | 15m | 6.919 | 39 | −0.046 | −0.211 | 0.17 | 0.71 | 0/5 | 0/4 |
| A pullback | 5m | 110.944 | 36 | −0.136 | −0.478 | 0.34 | 0.47 | 0/5 | 0/4 |
| B z-score | 5m | 23.410 | 45 | −0.128 | −0.414 | 0.29 | 0.45 | 0/5 | 0/4 |
| aleatoria | 5m | 21.018 | 36 | −0.134 | −0.457 | 0.32 | 0.48 | 0/5 | 0/4 |
| A pullback | 1m | 580.589 | 30 | −0.350 | −1.264 | 0.92 | 0.17 | 0/5 | 0/4 |
| B z-score | 1m | 101.763 | 35 | −0.375 | −1.319 | 0.95 | 0.12 | 0/5 | 0/4 |
| aleatoria | 1m | 107.796 | 30 | −0.380 | −1.321 | 0.94 | 0.17 | 0/5 | 0/4 |

Con costos S (realistas) es peor: expectativa neta de −0.56 R (15m) a −3.4 R (1m). **Ninguna combinación pasa los criterios, ni siquiera con
costos F. El holdout NO se consumió.** Lectura: A y B no se distinguen de la entrada aleatoria (incluso B queda un poco peor): no hay información
en esas señales; el costo (0.15–0.95 R por operación) hace el resto. El ruido de 1m/5m no es explotable con costos de retail.
Limitaciones (para no sobreinterpretar): solo cripto, solo 2 estrategias con parámetros fijados de antemano (no optimizados a propósito),
sin sesgo por sesión/horario ni datos de libro de órdenes. No prueba que ningún scalping funcione; prueba que ESTOS no funcionan en cripto con estos costos.
