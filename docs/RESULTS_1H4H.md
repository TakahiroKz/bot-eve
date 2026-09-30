# Resultados: 1h / 4h con gestión de riesgo

Ejecutado con el diseño y los criterios fijados **antes** en `docs/RESEARCH_1H4H.md`, sin
cambiarlos. Datos anteriores a 2025-07-01 (el holdout no se ha tocado). Walk-forward fuera de
muestra, comisión 0.1% + slippage 0.05% por lado, riesgo 1% por operación, stop de la
estrategia o 3% de emergencia. Pruebas totales: 3.369 combinaciones de parámetros.

## Veredicto según los criterios pre-registrados
| Estrategia | 1h | 4h |
|---|---|---|
| `atr_breakout` | No pasa (0/3 pares; PF 1.04–1.12) | **Pasa (3/3 pares)** |
| `sma_cross` (base) | No pasa (0/3; PF 1.16–1.26) | **Pasa (2/3 pares)** |
| `rsi_trend` | No pasa | No pasa (muy pocas operaciones: 8–31) |
| `bollinger_reversion` | No pasa (PF 0.63–0.84) | No pasa |
| `ema_adx` | No pasa (PF 0.52–0.67) | No pasa |

## Resultados fuera de muestra en 4h de las que pasan
| Estrategia | Par | Retorno | PF neto | Sharpe | Máx. DD | B&H Máx. DD | Operaciones |
|---|---|---|---|---|---|---|---|
| atr_breakout | BTC | +83% | 2.05 | 1.19 | −10% | −77% | 97 |
| atr_breakout | ETH | +33% | 1.41 | 0.65 | −17% | −81% | 96 |
| atr_breakout | BNB | +92% | 1.69 | 0.71 | −26% | −72% | 107 |
| sma_cross | BTC | +123% | 2.90 | 1.53 | −13% | −77% | 69 |
| sma_cross | ETH | +45% | 1.35 | 0.61 | −19% | −81% | 139 |
| sma_cross | BNB | +25% | 1.31 | 0.43 | −22% | −72% | 101 |

El buy & hold rindió mucho más en retorno total (BTC +231%, BNB +1.660% en el mismo tramo de
4h), pero con caídas de −72% a −81%. La ventaja de estas estrategias es el **control del
riesgo** (caídas de −10% a −26%), no el retorno absoluto.

## Robustez (solo datos de desarrollo)
- **Rejilla completa rentable:** con parámetros fijos sobre todo el periodo de desarrollo, las
  12 combinaciones de `atr_breakout` (PF 1.47–2.89) y las 9 de `sma_cross` (PF 1.13–3.27) son
  rentables en los 3 pares. No hay un único ajuste «afortunado». (Es en muestra: sirve para
  ver la forma del resultado, no como prueba.)
- **Por año (fuera de muestra):** positivo en 2021, 2023 y 2024; pérdidas pequeñas en 2022
  (mercado bajista, −5% a +5%) y **negativo en el primer semestre de 2025 en los 6 casos
  (−3% a −5%)**. Es poca muestra, pero conviene vigilarlo: puede ser un cambio de régimen.
- **Periodo favorable:** 2020–2025 incluyó dos grandes subidas. Una estrategia long-only de
  tendencia se beneficia de eso.

## Limitaciones
- Son hipótesis. Con 3.369 pruebas, parte del resultado puede ser azar; por eso falta la
  confirmación en el holdout.
- Solo ~100 operaciones por par en 4h: el profit factor tiene incertidumbre considerable.
- El backtest supone ejecución al precio de apertura con 0.05% de slippage; el stop real es
  STOP_LOSS_LIMIT y en un gap fuerte podría no ejecutarse.
- Con 3.54 USDT no se alcanza el mínimo de 5 USDT por orden con estos tamaños (≈20% del
  capital por operación). Solo tiene sentido en demo (testnet) o con más capital.

## Holdout (evaluación única, 2025-07-01 a 2026-09-29, 4h)
Parámetros fijos decididos solo con datos de desarrollo: `atr_breakout` 40/20/2×ATR y
`sma_cross` 10/100. Mismo riesgo y costos. Criterio: retorno neto > 0 y PF > 1 en al menos
2 de 3 pares. **El holdout queda consumido: no se vuelve a usar para decidir.**

| Estrategia | Par | Retorno | B&H | PF | Sharpe | Máx. DD | B&H DD | Operaciones |
|---|---|---|---|---|---|---|---|---|
| atr_breakout | BTC | +6.3% | −22.2% | 1.37 | 0.46 | −12.8% | −53.4% | 23 |
| atr_breakout | ETH | +8.6% | +7.4% | 1.57 | 0.65 | −10.9% | −68.0% | 22 |
| atr_breakout | BNB | +12.1% | +15.1% | 1.42 | 0.69 | −20.8% | −59.6% | 30 |
| sma_cross | BTC | −5.0% | −22.2% | 0.64 | −0.49 | −14.3% | −53.4% | 21 |
| sma_cross | ETH | +4.2% | +7.4% | 1.29 | 0.31 | −13.4% | −68.0% | 22 |
| sma_cross | BNB | +2.5% | +15.1% | 1.22 | 0.22 | −18.7% | −59.6% | 21 |

- **`atr_breakout` aprueba (3/3 pares).** Retorno positivo y PF 1.37–1.57 con caídas de −11% a −21%.
- **`sma_cross` aprueba por poco (2/3):** pierde en BTC y sus retornos son pequeños.
- **Muestra pequeña:** solo 21–30 operaciones por par en 15 meses; el PF tiene mucha incertidumbre.
- **Periodo con mercado lateral/bajista en BTC** (buy & hold −22%): favorable a una estrategia
  que se queda fuera. No prueba que funcione en un mercado alcista fuerte.
- El backtest trata cada par como una cuenta independiente con capital completo; en vivo el
  capital se reparte, por eso `atr_breakout` se asigna 0.25 por par (equivale a ~20% de riesgo
  por posición con stop 2×ATR). Con `sma_cross` y `atr_breakout` a la vez el capital no alcanzaría
  sin alterar los resultados, así que `sma_cross` queda en backtest hasta diseñar ese reparto.

## Decisión
`atr_breakout` pasa a **stage: demo** (Binance Testnet) con parámetros fijos. Nada pasa a `live`.
