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

## Replanteo: scalping multi-timeframe 15m/5m/1m e intradía 1h/15m/5m — pre-registro (escrito ANTES de ejecutar)
Código: `bot_eve/strategies/mtf.py` (señales, con test de causalidad), `bot_eve/backtest/scalp.py` (simulador con salida por falta de momentum y cierre de sesión),
`research/mtf_test.py`. Cortos y largos. Todo el contexto usa velas cerradas. Parámetros fijos de abajo, sin optimizar.

**Contexto 15m** (EMA9/EMA20 y ADX14 sobre velas de 15m): *tendencia alcista* = EMA9 > EMA20, EMA20 subiendo (vs hace 3 velas) y ADX >= 20 (bajista: espejo); *rango* = ADX < 20.
**Estrategia S1, reversión (solo en rango 15m):** en 5m el máximo (mínimo) tocó o superó la banda de Bollinger(20, 2) superior (inferior) en las últimas 3 velas de 5m cerradas;
gatillo en 1m: vela de rechazo (estrella fugaz/martillo con mecha >= 2× cuerpo y cierre en el tercio opuesto, o envolvente) con RSI(14) de 1m > 70 (< 30) en esa vela o la anterior; entrada en sentido contrario.
**S2, impulso EMA 9/20 (solo en tendencia 15m):** en 5m el mínimo (máximo) tocó la EMA9 en las últimas 3 velas de 5m con cierre sobre (bajo) la EMA20; gatillo en 1m: vela a favor que cierra por encima
del máximo (debajo del mínimo) de la anterior.
**S3, ruptura de micro-caja (cualquier contexto):** rango de las 6 velas de 1m previas <= 2×ATR14(1m); la vela de 1m cierra fuera de la caja con volumen > 2× el promedio de esas 6 velas.
**Gestión (S1–S3):** stop detrás del mínimo/máximo de las últimas 5 velas de 1m (+0.1 ATR, mínimo 0.5 ATR); objetivo 2R (variante informativa 1.5R); si al cierre de la 3.ª vela
de 1m no va en positivo, se cierra (sin momentum); máximo 15 velas de 1m. Simplificación declarada: no se modela el cierre parcial del 80% ni el trailing (un solo objetivo).
**Intradía I1 (barrido y rechazo):** vela de 15m que perfora el máximo (mínimo) del día previo y cierra de vuelta dentro con vela de rechazo (cualquier tendencia 1h);
**I2 (continuación):** tendencia 1h (EMA20 vs EMA50) y la vela de 15m cierra de nuevo por encima (debajo) de su EMA20 tras estar por debajo (encima). Setup válido 3 velas de 15m.
Gatillo en 5m: envolvente/rechazo a favor, o cierre por encima (debajo) del máximo (mínimo) de las 3 velas previas con volumen > 1.5× el promedio de 20. Stop detrás del extremo de las últimas 6 velas de 5m
(+0.1 ATR, mínimo 0.5 ATR); objetivo 2R, y la operación se descarta si el siguiente nivel clave (máx./mín. del día previo) queda a menos de 2R; se cierra al final de la sesión (cripto: 00:00 UTC; FX: 21:00 UTC); sin overnight.

**Costos por lado.** Cripto: F = 0.04% comisión + 0.02% slippage; S = 0.10% + 0.05%. FX (provisionales, el spread histórico de las velas es 0): FXo = 0.002% (≈ 0.2 pip en EURUSD); FXr = 0.005% (≈ 0.5 pip).
**Datos.** Cripto 1m/5m/15m/1h desde 2020. FX (PC de Leo): 5m desde 2025-05-29, 15m desde 2022-09, 1h desde 2020; 1m de FX no sincronizado (el broker entrega ~100.000 velas ≈ 2.5 meses): S1–S3 en FX solo cuando se sincronice 1m, y como
verificación corta, no como validación.
**Criterios.** Cripto (desarrollo < 2025-07-01, costos F, 4 pares): S1–S3: >= 500 ops; I1–I2: >= 300 ops; R neta >= +0.05; PF >= 1.15; >= 4/5 años (2021–2025) positivos; >= 3/4 pares positivos. Quien pase se mide con S (> 0) y luego holdout una vez.
FX (5m, desarrollo 2025-06 a 2025-12, costos FXo, 4 pares): >= 150 ops, R neta >= +0.05, PF >= 1.15, >= 3/4 pares positivos; luego FXr > 0; luego holdout (2026-01-01 en adelante) una vez.
Pruebas: 3 (S1–S3) + 2 (I1–I2) en cripto, y las mismas en FX donde haya datos: se informa el número de pruebas; un aprobado marginal no cuenta como evidencia sólida.

### Resultado del replanteo en cripto (desarrollo < 2025-07-01, 4 pares, RR 2.0; `research/mtf_test.py`)
Costos optimistas (F) / realistas (S):

| Estrategia | Ops | Gana % | R bruta | R neta (F) | PF (F) | Costo (R, F) | R neta (S) |
|---|---|---|---|---|---|---|---|
| S1 reversión (1m) | 38.354 | 22 | −0.53 | −1.75 | 0.12 | 1.22 | −4.45 |
| S2 impulso EMA9/20 (1m) | 460.405 | 21 | −0.27 | −0.92 | 0.20 | 0.65 | −2.54 |
| S3 ruptura micro-caja (1m) | 206.247 | 19 | −0.27 | −0.85 | 0.19 | 0.58 | −2.16 |
| I1 barrido y rechazo (5m) | 5.897 | 35 | −0.04 | −0.23 | 0.70 | 0.19 | −0.66 |
| I2 continuación (5m) | 29.690 | 34 | −0.07 | −0.33 | 0.62 | 0.26 | −0.93 |

**Ninguna pasa**, 0/5 años y 0/4 pares en todas; holdout NO consumido. Lectura: con stops de micro-estructura de 1m (≈ 0.05–0.1% del precio) el costo de ida y vuelta
equivale a 0.6–1.2 R incluso con costos de futuros; la tasa de acierto (19–22%) queda muy por debajo del 33% que exige un RR 2:1 aun sin costos. En 5m (I1, I2) el costo baja a 0.19–0.26 R,
pero la R bruta sigue negativa (−0.04 / −0.07): no hay ventaja en la señal. La salida «sin momentum a los 3 min» cierra 23–45% de las operaciones de 1m y no cambia el signo.
Pendiente FX (datos en el PC de Leo): `python research/mtf_test.py --suite intraday --fx --dir data_store/mt5 --symbols EURUSD GBPUSD USDJPY AUDUSD --cut 2026-01-01`
(5m desde 2025-05-29: ~7 meses de desarrollo y ~9 de holdout; muestra corta). S1–S3 en FX requieren sincronizar 1m (`mt5-sync --intervals 1m`, ~2.5 meses).

### Resultado intradía en FX (PC de Leo, 5m desde 2025-05-29; desarrollo 2025-06 a 2025-12, 4 pares; costos FXo = 0.002%/lado, FXr = 0.005%/lado)
| Estrategia | Ops | Gana % | R neta (FXo) | PF (FXo) | Pares + | R neta (FXr) | PF (FXr) |
|---|---|---|---|---|---|---|---|
| I1 barrido y rechazo | 431 | 33 | −0.092 | 0.86 | 1/4 | −0.205 | 0.72 |
| I2 continuación | 1.979 | 34 | −0.061 | 0.91 | 1/4 | −0.180 | 0.76 |
**No pasa** (R neta negativa incluso con costos optimistas). Nota de lectura: la columna «costo_R» sale 0 porque en FX no hay comisión y el spread/slippage ya está dentro del precio de entrada y
salida, es decir, dentro de la R «bruta»; el costo no es cero, solo no se muestra por separado. Con costos casi nulos la R bruta sigue negativa: **no hay ventaja en la señal**, lo mismo que en cripto.
Muestra corta (7 meses de desarrollo): es un indicio, no una prueba; pero coincide con cripto (5/5 pruebas intradía negativas). Holdout (2026-01-01 en adelante) NO consumido.

## Ruptura con volumen (C) en 2h y 4h — pre-registro (escrito ANTES de ejecutar)
Hipótesis nueva (la señal bruta de C en 1h fue +0.10 R, 5/5 años, 4/4 pares, pero no cubrió costos): con marcos más largos el costo en R baja. Misma estrategia C sin cambios
(cierre > máximo / < mínimo de las 48 velas previas, volumen > 1.5× el promedio de 20, tendencia del marco de contexto EMA50/EMA200 a favor; stop 1.5×ATR14, objetivo 3×ATR, salida por tiempo a 24 velas).
Marcos de entrada: **2h** (remuestreado de 1h, solo velas completas) y **4h**; contexto: **1d** (remuestreado de 1h) para ambos. Referencia (ya medida, 1h con contexto 4h): R neta F +0.044.
Cripto (BTC, ETH, BNB, SOL; desarrollo < 2025-07-01; costos F/S como siempre) y FX (EURUSD, GBPUSD, USDJPY, AUDUSD en el PC de Leo; 1h desde 2020; desarrollo < 2026-01-01; costos FXo/FXr).
Criterios (por marco, costos optimistas): >= 300 ops, R neta >= +0.05, PF >= 1.15, >= 4/5 años (2021–2025) positivos, >= 3/4 pares positivos; luego costos realistas > 0; luego holdout UNA vez.
Son 2 marcos × 2 mercados = 4 pruebas (más la referencia 1h) sobre datos ya vistos en parte; si exactamente una pasa por margen mínimo no se considera evidencia sólida, y se exigiría coherencia entre cripto y FX.

### Resultado ruptura con volumen 2h/4h en cripto (`research/breakout_htf_test.py`)
Desarrollo (< 2025-07-01, 4 pares), costos F / S:
| Marco | Ops | Gana % | R bruta | R neta (F) | PF (F) | Años + | Pares + | R neta (S) |
|---|---|---|---|---|---|---|---|---|
| 1h (ref.) | 2.734 | 39 | +0.10 | +0.044 | 1.07 | 5/5 | 4/4 | −0.070 |
| 2h | 1.202 | 39 | +0.10 | +0.060 | 1.10 | 4/5 | 3/4 | −0.022 |
| **4h** | 624 | 43 | +0.22 | **+0.192** | **1.33** | 5/5 | 4/4 | **+0.141** |
2h no pasa (PF 1.10 < 1.15). **4h pasa los criterios de desarrollo y sigue positivo con costos S**, así que se evaluó el holdout (una sola vez, costos S, 154 ops):
**R bruta +0.089, R neta +0.001, PF 1.00, pares + 3/4** → **expectativa ≈ 0: no aprueba** (hay que cubrir costos con margen; un 0.001 R no es evidencia). El edge bruto cae de +0.21 R (desarrollo) a +0.09 R (reciente), como el 4h ya validado.
**Análisis posterior (informativo, NO pre-registrado, no se usa para aprobar):** desarrollo largos +0.16 R (437 ops) / cortos +0.10 R (186); holdout largos **+0.175 R** (71 ops) / cortos **−0.149 R** (83 ops):
el aporte positivo reciente es de los largos; los cortos (que exigirían futuros/CFD) destruyen el resultado. Es una hipótesis para una prueba nueva (largos solamente), no un hallazgo.
Pendiente: confirmar en FX (`python research/breakout_htf_test.py --fx --dir data_store/mt5 --symbols EURUSD GBPUSD USDJPY AUDUSD --cut 2026-01-01`) por coherencia entre mercados.

### Resultado ruptura con volumen en FX (PC de Leo; desarrollo < 2026-01-01; EURUSD, GBPUSD, USDJPY, AUDUSD; costos FXo / FXr)
| Marco | Ops | R bruta | R neta (FXo) | PF | Años + | Pares + | R neta (FXr) |
|---|---|---|---|---|---|---|---|
| 1h | 1.551 | +0.039 | +0.039 | 1.06 | 3/5 | 2/4 | +0.021 |
| 2h | 631 | −0.044 | −0.044 | 0.93 | 2/5 | 2/4 | −0.056 |
| 4h | 261 | +0.024 | +0.024 | 1.04 | 2/5 | 3/4 | +0.019 |
**Ninguno pasa** (R neta < +0.05, PF < 1.15, años positivos < 4/5). La señal bruta existe a 1h y 4h pero es mínima (+0.02 a +0.04 R). No hay coherencia entre cripto (4h: +0.19 R) y FX (4h: +0.02 R) y el
holdout de cripto 4h dio equilibrio, así que **la línea de ruptura con volumen queda cerrada**. Una prueba de «solo largos» en cripto sería una hipótesis nueva sobre un holdout ya consumido: no se hace sin datos frescos (forward en demo).

## Estrategia 4h validada (`atr_breakout`) en FX — pre-registro (escrito ANTES de ejecutar)
Pregunta: ¿generaliza la ruptura de 4h (mismos parámetros fijos 40/20/2×ATR, sin reoptimizar) a EURUSD, GBPUSD, USDJPY, AUDUSD? Datos: 1h de MT5 (desde 2020, PC de Leo) remuestreado a 4h
(velas en hora del servidor, no coinciden con Binance). Cartera de capital compartido (`portfolio.py`, ahora con modo margen `max_leverage`), riesgo 0.5% del patrimonio por operación, nocional máx. por posición
10× el patrimonio y bruto máx. 10× (sin intereses), máx. 4 posiciones. **A:** solo largos de cada par. **B:** largos + cortos, donde el corto = ruptura larga del par invertido (O,H,L,C → 1/O, 1/L, 1/H, 1/C;
equivalente exacto para un par de divisas). Costos por lado: FXo = slippage 0.002%, sin swap; FXr = slippage 0.005% + swap 0.005%/día sobre el nocional (≈ 1.8% anual, pesimista; el swap real por par se medirá con `mt5-info`).
Desarrollo: < 2026-01-01; holdout: desde 2026-01-01 (reservado en config/mt5_fx.yaml; nunca visto).
Criterios (por variante, costos FXr, desarrollo): >= 150 operaciones; CAGR > 0; PF >= 1.15; caída máxima mejor que −25%; >= 3/4 pares con retorno positivo (por trade medio). Luego holdout UNA vez: retorno > 0 y PF > 1.
2 variantes = 2 pruebas. Limitaciones declaradas: sin spread histórico real (provisional), swap por par desconocido, cortos y apalancamiento requieren cuenta CFD (Libertex), un par y su inverso podrían abrirse a la vez en B (se informa).
