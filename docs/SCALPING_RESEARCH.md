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

## Sensibilidad al riesgo del scalping (informativo, `research/scalp_risk_levels.py`; costos F, desarrollo)
Una cuenta por par, capital final como múltiplo del inicial: con riesgo 0.5% 15m-A queda en 0.001×, 15m-B en 0.09×; con 1%, 2% y 3% todo cae a ~0×
(100% de los pares pierde más del 50%), con apalancamiento medio 1–13×. Con expectativa negativa, más riesgo solo acelera la ruina. No se cambió nada
de la configuración (el 4h sigue con 0.5% / 15%).

## Familias de scalping a probar una por una (investigación web, resumen)
1. **Arbitraje estadístico / reversión a la media.** Evidencia mixta: hay estudios de pares cripto rentables y otros (26 monedas, varias frecuencias) donde
   rinden menos que el benchmark, muy sensibles a parámetros y costos; si la vida media de la reversión es larga frente al horizonte, no compensa.
   ([Amberdata](https://blog.amberdata.io/empirical-results-performance-analysis), [Pairs Trading in Crypto, tesis EUR](https://thesis.eur.nl/pub/67552/Thesis-Pairs-trading-.pdf),
   [Coin Bureau](https://coinbureau.com/guides/how-to-backtest-your-crypto-trading-strategy))
2. **Impulso / ruptura.** Hay evidencia académica de momentum intradía en Bitcoin (la primera media hora predice la última), más fuerte con volumen/volatilidad alta,
   pero estudios con rupturas de rango en alta frecuencia dan retornos de compra negativos no significativos.
   ([Bitcoin intraday time-series momentum](https://research.birmingham.ac.uk/en/publications/bitcoin-intraday-time-series-momentum/),
   [Intraday return predictability in crypto](https://www.sciencedirect.com/science/article/abs/pii/S1062940822000833),
   [OHLCV intraday momentum, falsificación](https://arxiv.org/pdf/2605.04004))
3. **Market making.** Requiere libro de órdenes y posición en la cola; en pruebas con datos en vivo de Binance spot los rellenos quedan 1–1.5 pb en contra a los 5 s
   (selección adversa) y el punto de equilibrio exige un rebate de maker de 1.2–2 pb: con comisiones retail la pérdida es 6–9 veces mayor.
   ([crypto-mm-sim](https://github.com/HelloBryte/crypto-mm-sim), [Avellaneda-Stoikov](https://github.com/dmb369/avellaneda-stoikov-mm))
   Con solo velas OHLC NO se puede validar de forma honesta; solo se puede dar una cota optimista.

## Familia 1: arbitraje estadístico (pares) — pre-registro (escrito ANTES de ejecutar)
`bot_eve/backtest/pairs.py`. Pares: todos los emparejamientos de BTC, ETH, BNB, SOL (6 pares). Marcos 15m y 1h. Spread = ln P1 − β ln P2 con β de regresión móvil
(500 velas), z con ventana 200. Entrada |z| >= 2.5 (largo el spread si z < 0), salida cuando z cruza 0, stop |z| >= 4.5, salida por tiempo a 96 velas.
Ejecución en la apertura de la vela siguiente, ambas patas, nocional bruto 1, costo de ida y vuelta 2·(comisión + slippage). Parámetros fijos.
Criterios (desarrollo < 2025-07-01, costos F, agregado de los 6 pares): >= 300 operaciones; retorno medio neto por operación > 0 con PF >= 1.15;
positivo en >= 4 de los 5 años 2021-2025; positivo en >= 4 de los 6 pares. Luego costos S debe seguir > 0; solo entonces holdout (una vez): media > 0 y PF > 1.
Nota: el corto de la pata requiere futuros/CFD (no spot); los costos F lo asumen. 2 marcos = 2 pruebas.

### Resultado familia 1 (desarrollo, 6 pares; `research/pairs_test.py`)
| Marco | Costos | Ops | Gana % | Media neta/op | PF | Años + | Pares + |
|---|---|---|---|---|---|---|---|
| 15m | F | 3.156 | 45 | −5.8 pb | 0.91 | 1/5 | 2/6 |
| 1h | F | 763 | 47 | −8.0 pb | 0.94 | 2/5 | 2/6 |
| 15m | S | 3.156 | 38 | −23.8 pb | 0.68 | 0/5 | 0/6 |
| 1h | S | 763 | 44 | −26.0 pb | 0.83 | 2/5 | 2/6 |
**No pasa** (media negativa incluso con costos F). El 81% de las salidas (15m) y 82% (1h) son por tiempo: el spread no revierte dentro de 96 velas, justo el riesgo
que advierte la literatura (vida media larga frente al horizonte). Holdout NO consumido.

## Familia 2: impulso y ruptura — pre-registro (escrito ANTES de ejecutar)
**2a, ruptura con volumen (C):** cierre > máximo (o < mínimo) de las 48 velas previas, volumen > 1.5× el promedio de 20 velas y tendencia 1h EMA50/EMA200 a favor;
stop 1.5×ATR, objetivo 3×ATR, salida por tiempo a 24 velas (mismo simulador, 4 pares, marcos 5m y 15m). Criterios idénticos a los de A/B (>= 500 ops, R neta >= +0.05,
PF >= 1.15, >= 4/5 años, >= 3/4 pares con costos F; luego S > 0; luego holdout una vez).
**2b, momentum intradía de la literatura:** signo del retorno de la primera media hora del día UTC (00:00–00:30) -> posición en esa dirección de 23:30 a 00:00 UTC del mismo día
(largo/corto); costo de ida y vuelta 2·(comisión + slippage). Criterios (desarrollo, costos F, 4 pares): >= 1000 operaciones; media neta > 0 con PF >= 1.15; positivo en >= 4/5 años y >= 3/4 pares;
luego S > 0; luego holdout una vez. 3 pruebas en esta familia (2a ×2 marcos + 2b).

### Resultado familia 2 (desarrollo, 4 pares, costos F; `research/breakout_test.py`)
| Prueba | Ops | Gana % | Media neta | PF (F) | Años + | Pares + | Con costos S |
|---|---|---|---|---|---|---|---|
| 2a ruptura 15m | 10.823 | 34 | −0.145 R | 0.80 | 0/5 | 0/4 | −0.394 R |
| 2a ruptura 5m | 31.201 | 32 | −0.330 R | 0.62 | 0/5 | 0/4 | −0.852 R |
| 2b momentum intradía | 7.745 | 36 | −10.4 pb | 0.58 | 0/5 | 0/4 | −28.4 pb |
**No pasa ninguna.** En 2a la R bruta ya es negativa (−0.03 R a 15m, −0.10 R a 5m) antes de comisiones. En 2b sí hay una señal estadística pequeña (media bruta +1.58 pb por operación,
coherente con la literatura), pero el costo de ida y vuelta es 12 pb (F) o 30 pb (S): la señal es ~8 veces menor que el costo. Holdout NO consumido.

## Familia 3: market making — cota optimista con velas de 1m (pre-registro, escrito ANTES de ejecutar)
`research/mm_bound.py`. BTC y ETH, 1m, desarrollo. Cotiza bid/ask a ±h del cierre previo (h = 5, 10, 20 pb). Si se toca solo un lado, se abre inventario y se pone la salida a +2h
del precio de entrada (límite maker); si no sale en 60 velas, se liquida a mercado con comisión taker 0.04%+0.02% de slippage. Si en la misma vela se tocan ambos lados, se asume
el viaje completo (+2h, sesgo optimista). Rellenos a precio límite sin cola ni selección adversa (otro sesgo optimista). Comisión maker: 0.075% (retail con BNB), 0.02% (nivel alto), −0.01% (rebate).
Criterio: media neta por viaje > 0 con 0.075% Y 0.02%. Esto es una COTA SUPERIOR: pasar no prueba nada; fallar descarta el market making con velas y capital retail.

### Resultado familia 3 (cota optimista, 1m, desarrollo; `research/mm_bound.py`)
Media neta por viaje (pb), BTC / ETH, según h (media distancia de la cotización) y comisión maker:
| h | maker 0.075% | maker 0.02% | rebate −0.01% |
|---|---|---|---|
| 5 pb | −15.9 / −17.0 | −5.9 / −6.9 | −0.4 / −1.3 |
| 10 pb | −14.9 / −16.5 | −5.4 / −6.8 | −0.2 / −1.5 |
| 20 pb | −13.3 / −16.1 | −4.6 / −7.2 | +0.15 / −2.3 |
**No pasa:** negativo con comisión 0.075% y con 0.02%, incluso con rellenos perfectos y sin selección adversa. Solo con rebate (nivel de market maker institucional) queda en ~0, y
sigue siendo una cota superior. Entre 15% y 41% de los viajes terminan liquidados a mercado: ahí aparece el costo del inventario. Coherente con la literatura (selección adversa 1–1.5 pb).
Conclusión: market making no es viable con 500 USD y comisiones retail; con velas no se puede ir más allá. Holdout NO consumido.

## Conclusión del scalping cripto (3 familias, 6 estrategias, 3 marcos)
Ninguna pasa en desarrollo, ni siquiera con costos optimistas de futuros. Lo más cercano a señal real es 2b (+1.6 pb brutos por operación) y es 8 veces menor que el costo.
Línea de scalping en cripto cerrada. Pendientes con más sentido: 1h en cripto y FX (spread/comisión mucho menores).

## Marco 1h en cripto — pre-registro (escrito ANTES de ejecutar)
Mismas estrategias A (pullback), B (z-score) y C (ruptura con volumen) y línea base aleatoria, con entrada en 1h y contexto de **4h** (EMA50/EMA200 y ADX < 20 sobre velas de 4h cerradas),
mismos parámetros fijos, salida por tiempo a 24 velas (1 día), mismos 4 pares, desarrollo < 2025-07-01. Criterios idénticos a los de A/B: >= 500 ops, R neta >= +0.05 (costos F),
PF >= 1.15, >= 4/5 años positivos, >= 3/4 pares; luego costos S > 0; luego holdout una vez. 3 pruebas (A, B, C) sobre los mismos datos. Se reporta también la línea base aleatoria.
Nota: a 1h el costo en R baja mucho (≈ 0.04–0.1 R), así que aquí sí puede aparecer un resultado distinto al de 5m/15m.

### Resultado 1h (desarrollo, 4 pares; `research/scalp_1h_test.py`)
| Estrategia | Ops | Gana % | R bruta | R neta (F) | PF (F) | Años + | Pares + | R neta (S) |
|---|---|---|---|---|---|---|---|---|
| A pullback | 8.164 | 40 | −0.010 | −0.089 | 0.86 | 0/5 | 0/4 | −0.260 |
| B z-score | 2.178 | 43 | −0.153 | −0.221 | 0.64 | 0/5 | 0/4 | −0.357 |
| **C ruptura** | 2.734 | 39 | +0.100 | +0.044 | 1.07 | 5/5 | 4/4 | −0.070 |
| aleatoria | 1.675 | 39 | −0.042 | −0.123 | 0.81 | 1/5 | 0/4 | −0.293 |
**Ninguna pasa los criterios** (C: R neta +0.044 < +0.05 y PF 1.07 < 1.15 con F; negativa con S). Holdout NO consumido. C es la primera con señal bruta positiva
(+0.10 R, consistente: 5/5 años y 4/4 pares), pero no cubre costos realistas. No se ajustan umbrales ni parámetros a posteriori para «rescatarla»; si se quisiera seguir, sería una
hipótesis nueva pre-registrada (p. ej. otro marco como 2h/4h, donde el costo en R es menor).
