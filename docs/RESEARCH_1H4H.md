# Investigación 1h / 4h con gestión de riesgo

Registro de diseño, escrito **antes** de ejecutar los resultados de 4h y de ninguno con
sizing por riesgo. Sirve para que los criterios no se ajusten a lo que salga.

## Qué se sabe ya (transparencia)
- Se vieron los resultados **sin sizing por riesgo** (todo el capital en cada operación) de las
  5 estrategias en 5m, 15m y 1h (`reports/compare.csv`, ver docs/STRATEGIES.md). En 1h la línea
  base `sma_cross` fue la mejor (PF neto 1.04–1.11) y ninguna alcanzó los criterios.
- **No se ha visto nada de 4h** ni nada con sizing por riesgo. El holdout (desde 2025-07-01) no se ha tocado.

## Pregunta
¿Alguna de las 5 estrategias tiene ventaja neta de costos en 1h o 4h cuando se opera con las
mismas reglas de riesgo que usará el bot en vivo?

## Diseño (fijo)
- **Estrategias:** las 5 existentes, con su rejilla `default_grid` (sin añadir ni cambiar
  parámetros). No se añaden más estrategias: cada una extra aumenta el riesgo de falsos
  positivos. *«Túneles Vegas» se revisó y se descarta:* son reversiones en envolventes de
  Fibonacci medidas en pips con velas japonesas discrecionales; no es programable de forma fiel.
- **Pares e intervalos:** BTCUSDT, ETHUSDT, BNBUSDT × 1h, 4h.
- **Datos:** anteriores a 2025-07-01. **Walk-forward** fuera de muestra: 1h = 180d entrena / 60d
  prueba; 4h = 360d entrena / 120d prueba. Objetivo de optimización: retorno total, mínimo 10 operaciones.
- **Costos:** comisión 0.1% y slippage 0.05% por lado (los de siempre).
- **Riesgo (las reglas del bot en vivo):**
  - Riesgo por operación 1% del capital hasta el stop.
  - Stop de la estrategia si lo define; si no, **stop de emergencia del 3%**.
  - Tamaño = riesgo / distancia al stop, limitado por el capital disponible.
  - Una posición a la vez por par.

## Criterios de aprobación (para pasar a demo)
Una estrategia pasa en un intervalo solo si cumple **todo** esto:

1. Retorno neto fuera de muestra **> 0 en al menos 2 de los 3 pares**.
2. En esos pares: **profit factor neto ≥ 1.2** y **Sharpe neto ≥ 0.5**.
3. En esos pares: **≥ 100 operaciones (1h) / ≥ 60 (4h)**.
4. En esos pares: **máximo drawdown menor que el del buy & hold** del mismo par.
5. En esos pares: **PF antes de comisiones > 1.1** (hay ventaja antes de costos).
6. En esos pares: ventanas de prueba positivas **≥** ventanas negativas (se ignoran las planas).

Después, una **única** evaluación sobre el holdout (`--final`): retorno neto > 0 y PF > 1.
Si falla, la estrategia no pasa y no se reajusta.

## Qué NO se hará
- Cambiar criterios, parámetros, rejillas o costos después de ver los resultados.
- Superar el buy & hold en retorno total **no** se exige: con 1% de riesgo por operación no
  es comparable. Se compara en Sharpe y drawdown.
- Reportar solo la mejor fila: se publicará la tabla completa y el número de pruebas (`trials`).

## Lectura de los resultados
Con muchas combinaciones probadas, alguna parecerá buena por azar. Un resultado que pase
los criterios es una hipótesis a confirmar en el holdout y luego en demo, no una conclusión.
