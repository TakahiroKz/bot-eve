# Checklist de las demos (Binance Testnet 4h con 9 pares + MT5 BTCUSD/ETHUSD 4h)

Objetivo: comparar lo REAL con lo que predijo el backtest antes de poner dinero real. Revisar 1 vez al día (2 min) y hacer la revisión larga cada semana.
Backtest de referencia (9 pares, riesgo 0.5%, tope 15%, máx. 4 posiciones): ≈ 9 operaciones/mes, acierto 26–30%, ganancia media ≈ 5× la pérdida media, PF 1.2–2.0,
caída máxima histórica −24%, 7% anual en el tramo reciente. **Las primeras semanas son ruido**: 4–6 semanas dan solo 8–12 operaciones; no se saca ninguna conclusión de rentabilidad con menos de ~30 operaciones.

## A. Diario (2 minutos)
- [ ] El proceso sigue vivo (`python -m bot_eve.engine status` o el panel `python -m bot_eve.dashboard`): hora de la última pasada reciente (< 2 min en demo con `poll_seconds: 20`).
- [ ] Sin archivo `KILL` ni alertas ⛔ / 🔴 de Telegram sin leer; errores consecutivos = 0.
- [ ] **Toda posición abierta tiene su stop en el exchange** (en el panel, columna de stop; en Testnet, órdenes abiertas). Posición sin stop = detener el bot y revisar.
- [ ] Ningún par con más de una posición; nunca más de 4 posiciones abiertas.
- [ ] El PC no se durmió ni reinició (si lo hizo: el bot debe retomar el estado de `state/state.json` sin duplicar órdenes).

## B. Por cada operación cerrada (en `state/trades.jsonl` o el panel)
- [ ] **Slippage de entrada:** precio de llenado vs. la apertura de la vela siguiente a la señal. Backtest asume 0.05% (BTC/ETH/BNB) y 0.10% (el resto de pares). Anotar la diferencia real.
- [ ] **Comisión real:** 0.1% por lado en Testnet; en real se paga con BNB (0.075%) si está activado. Comparar con el 0.1% supuesto.
- [ ] **Tamaño:** pérdida si salta el stop ≈ 0.5% del capital (≈ 2.5 USD con 500); la posición nunca supera el 15% del capital.
- [ ] **Señal correcta:** entrada tras un cierre > máximo de 40 velas; salida por cierre < mínimo de 20 velas o por stop (2×ATR). Revisar 1 operación al azar contra el gráfico de 4h cada semana.
- [ ] Motivo de salida (`stop` / `signal` / `kill`) coherente; si un stop se ejecutó muy lejos del precio del stop, anotarlo (gap/slippage de stop).

## C. Semanal (15 minutos)
- [ ] **Frecuencia:** operaciones abiertas/mes por par vs. ≈ 9/mes entre los 9 pares (un rango de 4–15 es normal). Muy por debajo → revisar que las señales se evalúan (velas de 4h actualizadas, pares de Testnet disponibles).
- [ ] **Señales omitidas** por `max_positions` o por mínimos del par (log: «máximo de 4 posiciones» / «tamaño 0»). Pares con mínimos que impiden operar con 500 USD.
- [ ] **Retorno acumulado y caída:** dentro de lo esperable (caída hasta −25% no invalida; > −35% sí hay que parar y revisar). Compararlo con comprar y mantener BTC el mismo periodo.
- [ ] **Divergencia con el backtest:** repetir el backtest del mismo periodo con los datos reales (`python -m bot_eve.backtest ...` con holdout del periodo en vivo) y comparar operación por operación: mismas entradas/salidas ± 1 vela. Cada diferencia sin explicar es un bug potencial.
- [ ] Telegram: resumen diario llegando; alertas de compra/venta/stop coinciden con el panel.
- [ ] Testnet no es el mercado real: su libro de órdenes es delgado, así que el slippage medido ahí NO es representativo. Para costos reales usar `--roundtrip` en la cuenta real con una operación mínima (condición previa a dinero real).

## D. MT5 (BTCUSD/ETHUSD CFD, demo)
- [ ] Algo Trading en verde en la terminal tras cada reinicio o cambio de cuenta.
- [ ] Spread y swap reales vs. los supuestos (BTCUSD 0.035%, ETHUSD 0.23%, swap ≈ −0.044%/día en largos): una posición de 3 semanas paga ≈ 0.9% de swap, relevante frente a una ganancia media del 15%.
- [ ] Margen/apalancamiento: el conector limita a ≤ 1× el capital; verificar que no rechaza órdenes por mínimos de lote.
- [ ] Hora del servidor (UTC+3 aprox.): las velas de 4h no coinciden con las de Binance; las señales pueden diferir y es normal.

## E. Criterios para pasar de demo a dinero real (todos, no uno)
1. >= 30 operaciones cerradas en demo (o >= 8–12 semanas) con comportamiento operativo correcto (stops siempre colocados, cero órdenes duplicadas, cero errores sin explicar).
2. Slippage + comisión medidos dentro de ±50% de lo supuesto en el backtest.
3. Divergencia backtest vs. demo explicada operación por operación.
4. Prueba de ida y vuelta con dinero real mínimo (`--roundtrip`) que confirme el costo real.
5. Capital que puedes perder sin cambiar tu vida (500 USD de riesgo total) y la regla de parada escrita: caída del 25% o 3 meses sin cumplir lo esperado → se detiene y se revisa.
6. Doble confirmación del código para live (`i_understand_real_money` + `--yes-real-money`) y KILL probado.

## F. Cuándo parar y avisarme
- Posición sin stop, orden duplicada, saldo que no cuadra con el estado, errores repetidos, caída > 15% en < 4 semanas, o cualquier comportamiento que no entiendas: `python -m bot_eve.engine kill`, no abrir nada a mano y pegarme el `status` y las últimas líneas del log.
