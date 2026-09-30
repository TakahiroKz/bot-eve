"""¿Qué cabe esperar de `atr_breakout` (4h) con 500 USD en Binance? Simulación de cartera y remuestreo.

Cada par corre su propia cuenta de 500 USD con tope de posición del 25% y riesgo 1% (las reglas del bot); la cartera es el
promedio de las tres curvas. Incluye los costos por defecto de la configuración y los mínimos del exchange.
Ejecutar desde la raíz:  python research/capital_500.py
Nota: el periodo de desarrollo es en muestra (los parámetros se eligieron allí); el posterior ya se usó una vez.
"""

import numpy as np
import pandas as pd

from bot_eve.backtest.costs import rules_for
from bot_eve.backtest.engine import RiskSizing, run_backtest
from bot_eve.common.config import load_config
from bot_eve.data.store import CandleStore
from bot_eve.strategies import build_strategy

CASH = 500.0
cfg = load_config()
bt = cfg.backtest
risk = RiskSizing(cfg.risk.risk_per_trade, cfg.risk.default_stop_pct)
cut = pd.Timestamp(bt.holdout_start, tz="UTC")
params = {"entry_len": 40, "exit_len": 20, "stop_atr": 2.0}

curves, trades = {}, []
for sym in ("BTCUSDT", "ETHUSDT", "BNBUSDT"):
    df = CandleStore(cfg.data.dir).read(sym, "4h")
    res = run_backtest(
        df, build_strategy("atr_breakout", **params), bt.costs(sym), rules_for(sym), CASH, 0.25, risk=risk
    )
    curves[sym] = res.equity / CASH
    t = res.trades.copy()
    t["symbol"] = sym
    trades.append(t)
eq = pd.concat(curves, axis=1).dropna().mean(axis=1) * CASH  # cartera equiponderada
trades = pd.concat(trades)


def stats(e: pd.Series, label: str) -> dict:
    yrs = (e.index[-1] - e.index[0]).days / 365.25
    dd = (e / e.cummax() - 1).min()
    return {"periodo": label, "años": round(yrs, 2), "final USD": round(e.iloc[-1], 0),
            "retorno total": f"{e.iloc[-1] / e.iloc[0] - 1:+.0%}",
            "anualizado": f"{(e.iloc[-1] / e.iloc[0]) ** (1 / yrs) - 1:+.1%}", "caída máx.": f"{dd:.1%}"}  # fmt: skip


rows = [stats(eq, "todo")]
for label, part in (("desarrollo (<2025-07)", eq[eq.index < cut]), ("posterior (≥2025-07)", eq[eq.index >= cut])):
    if len(part) > 10:
        rows.append(stats(part, label))
pd.set_option("display.width", 200)
print(pd.DataFrame(rows).to_string(index=False))

m = eq.resample("ME").last().pct_change().dropna()
yearly = eq.resample("YE").last().pct_change()
yearly.iloc[0] = eq.resample("YE").last().iloc[0] / CASH - 1
print("\nRetorno por año natural:", {str(i.year): f"{v:+.1%}" for i, v in yearly.items()})
print(f"Meses: {len(m)} | positivos {(m > 0).mean():.0%} | mejor {m.max():+.1%} | peor {m.min():+.1%}")

# remuestreo de meses (con reemplazo) para ver la dispersión de un año cualquiera
rng = np.random.default_rng(0)
sims = np.prod(1 + rng.choice(m.to_numpy(), size=(20000, 12)), axis=1) - 1
print("\nDispersión de un año (20.000 remuestreos de 12 meses de la propia historia):")
for q in (0.05, 0.25, 0.5, 0.75, 0.95):
    print(f"  percentil {int(q * 100):>2}: {np.quantile(sims, q):+.1%}  ({CASH * (1 + np.quantile(sims, q)):,.0f} USD)")
print(f"  P(perder dinero en el año) = {(sims < 0).mean():.0%} | P(perder más del 10%) = {(sims < -0.10).mean():.0%} | "
      f"P(ganar más del 20%) = {(sims > 0.20).mean():.0%}")  # fmt: skip
n = len(trades)
yrs = (eq.index[-1] - eq.index[0]).days / 365.25
print(f"\nOperaciones: {n} en {yrs:.1f} años = {n / yrs / 12:.1f} al mes entre los 3 pares | "
      f"rechazadas por mínimos: 0 con 500 USD (posición típica ~{CASH * 0.25:.0f} USD)")
print(f"Costos pagados (comisiones): {trades['fees'].sum():,.0f} USD sobre {CASH * 3:,.0f} USD de capital simulado (3 cuentas)")
