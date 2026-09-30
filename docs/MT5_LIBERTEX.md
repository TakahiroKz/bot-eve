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

## Lectura y cuentas (por confirmar)
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
