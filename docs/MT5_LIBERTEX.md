# MetaTrader 5 con Libertex (CFD de cripto)

Datos tomados de la especificación de los símbolos en la cuenta demo (capturas del usuario).
Lo marcado «por confirmar» es una inferencia, no un dato leído.

## Especificación observada
| | BTCUSD | ETHUSD |
|---|---|---|
| Tipo | CFD de cripto (bolsa XCCC) | CFD de cripto |
| Contrato | 1 BTC | 1 ETH |
| Lote mín. / paso / máx. | 0.01 / 0.01 / 10 | 0.1 / 0.1 / 250 |
| Dígitos (punto) | 3 (0.001) | 3 (0.001) |
| Spread | Flotante (valor no visible) | Flotante |
| Nivel de stops | 0 | 1000 puntos |
| Swap largo / corto (puntos) | −37 079.08 / −9 269.87 | −1 134.5 / −283.56 |
| Comisión | 0.1% en USD por lote, **solo transacciones de salida** | igual |
| Horario | 24 h, 7 días | 24 h, 7 días |
| Ejecución | A mercado, todo-o-nada | igual |
| Margen | ~83.79 USD/lote | ~2.68 USD/lote |

## Medición real con `mt5-info` (cuenta demo, servidor «ForexClub-MT5 Demo Server»)
| | BTCUSD | ETHUSD |
|---|---|---|
| Precio | 83.904,75 | 2.677,57 |
| Spread (instantánea) | 26.800 pts = **0.032%** | 5.356 pts = **0.200%** |
| Swap largo | −0.044% por día (≈ −16% anual) | −0.042% por día (≈ −15.5% anual) |
| Apalancamiento de la cuenta | 1:1000 | |
| Modo de margen | hedging | |
| Saldo demo | 50.000 USD | |

- El spread es flotante: esta es una sola instantánea. El histórico (`mt5-sync`) dará el mediano.
- En la primera lectura el trading algorítmico de la terminal estaba desactivado; hay que
  activarlo con el botón «Algo Trading» (queda apagado al cambiar de cuenta por la casilla de seguridad).
- El servidor se llama «ForexClub», no «Libertex» (probablemente el mismo grupo: confirmar).

## ¿Sobreviven los costos de CFD? Estimación con el historial de Binance
Costos reales de arriba aplicados a las velas de 4h de Binance (BTC, ETH), **solo datos de
desarrollo**, parámetros fijos y riesgo del bot. Es **en muestra y con precios de Binance**:
sirve para medir el efecto de los costos, no como validación.

| Estrategia | Par | Costos | Retorno | PF | Sharpe | Días/posición | Costo por op.* |
|---|---|---|---|---|---|---|---|
| atr_breakout | BTC | Binance spot | +264% | 2.89 | 1.62 | 7.6 | 0.20% |
| atr_breakout | BTC | Libertex CFD | +239% | 2.78 | 1.51 | 7.6 | 0.44% |
| atr_breakout | ETH | Binance spot | +113% | 1.89 | 1.08 | 5.7 | 0.20% |
| atr_breakout | ETH | Libertex CFD | +101% | 1.82 | 1.00 | 5.7 | 0.34% |
| sma_cross | BTC | Binance spot | +217% | 2.68 | 1.50 | 9.9 | 0.20% |
| sma_cross | BTC | Libertex CFD | +189% | 2.52 | 1.38 | 9.9 | 0.54% |
| sma_cross | ETH | Binance spot | +272% | 2.40 | 1.27 | 8.1 | 0.20% |
| sma_cross | ETH | Libertex CFD | +241% | 2.31 | 1.19 | 8.0 | 0.45% |

\* comisiones + swap, sin contar spread ni slippage.

Con los costos de Libertex el profit factor baja un 3–7% (p. ej. 2.89 → 2.78 en BTC). Las
posiciones duran ~6–10 días, así que el swap (≈0.3–0.4% por operación) pesa más que en Binance,
pero las ganancias medias de una estrategia de tendencia son mucho mayores. **Conclusión
provisional: los costos de CFD no son el obstáculo; falta validar con el historial propio
del broker y con un spread mediano realista** (en ETH el spread de 0.2% es el punto débil).

## Lectura y cuentas (estimación inicial, previa a la medición)
- Margen de 83.79 USD por lote ⇒ precio de BTC ≈ 84 mil con **apalancamiento 1:1000** (inferido).
- Swap en puntos × 0.001 = **−37.08 USD por lote y día en BTC** (largo), ≈ **0.04% diario ≈ 15%
  anual** si BTC ≈ 84 mil. En corto también es negativo: el broker cobra financiación en ambos lados.
- Una posición de ~7 días (la duración típica de `atr_breakout` en 4h) paga ≈ 0.3% de swap,
  más 0.1% de comisión de salida, más el spread (desconocido). **Comparable o mayor** que el
  ~0.3% de ida y vuelta de Binance spot.
- **Lote mínimo:** 0.01 BTC ≈ 840 USD de valor. Con stop del 5% y riesgo del 1%, una posición
  de ese tamaño solo encaja con un capital de ~4.000 USD. Con menos, el gestor de riesgo
  calculará 0 lotes y **no operará**, en lugar de sobrearriesgar.
- **Apalancamiento alto:** el margen no limita la pérdida. El tamaño lo fija el riesgo hasta el stop.

## Flujo para validar con datos de Libertex
En tu PC Windows, con MT5 abierto y la cuenta demo conectada:
```powershell
python -m pip install -e ".[dev]"                 # instala MetaTrader5 en Windows
python -m bot_eve.data mt5-info                   # cuenta y especificaciones (sin login ni nombre)
python -m bot_eve.data mt5-sync                   # historial 15m/1h/4h de BTCUSD y ETHUSD
```
1. **`mt5-info`** imprime el spread actual, el swap y su equivalente en % por día. Copia esos
   valores a `config/mt5.yaml` (`spread_pct`, `swap_pct_per_day`). Hoy son provisionales.
2. **`mt5-sync`** descarga lo que el broker tenga (la profundidad histórica puede ser corta) y mide el spread mediano real.
3. Con eso se repite la investigación con los costos de CFD:
   `python -m bot_eve.backtest --config config/mt5.yaml compare --intervals 1h 4h --risk-sizing`

## Advertencias
- Las velas de MT5 vienen en **hora del servidor del broker**, no en UTC, y los precios del CFD
  no coinciden exactamente con los de Binance. Por eso se re-valida con el propio historial.
- Una ventaja validada en Binance **no garantiza** el mismo resultado aquí (otros costos, otros precios).
- Falta por construir el conector de órdenes de MT5 (`Mt5Broker`); se hará cuando la
  re-validación con estos datos justifique usarlo.
