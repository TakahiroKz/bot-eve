"""Informativo: scalping A/B con riesgo por operación más agresivo (costos F). No es prueba de aprobación."""

import numpy as np
import pandas as pd

from bot_eve.backtest.scalp import ScalpCosts, simulate
from bot_eve.data.store import CandleStore
from bot_eve.strategies.scalp_signals import pullback_momentum, zscore_reversion

PAIRS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]
CUT = pd.Timestamp("2025-07-01", tz="UTC")
F = ScalpCosts(0.0004, 0.0002)
store = CandleStore("data_store")
rows = []
for tf in ["15m", "5m"]:
    for name, fn, sl, tp in [("A", pullback_momentum, 1.2, 1.8), ("B", zscore_reversion, 1.5, 1.5)]:
        for sym in PAIRS:
            df, htf = store.read(sym, tf), store.read(sym, "1h")
            side, atr = fn(df, htf, tf)
            t = simulate(df, side, atr, sl, tp, 24, F, end=CUT - pd.Timedelta(seconds=1))
            t["pair"] = sym
            rows.append(t.assign(tf=tf, strat=name))
allt = pd.concat(rows, ignore_index=True).sort_values("entry_time")
allt["unit"] = (allt["ret"] / allt["r_net"]).abs()  # distancia al stop como fracción del precio
out = []
for (tf, strat), g in allt.groupby(["tf", "strat"]):
    for risk in (0.005, 0.01, 0.02, 0.03):
        eq = {p: np.cumprod(1 + risk * gp.r_net.to_numpy()) for p, gp in g.groupby("pair")}
        final = np.mean([e[-1] for e in eq.values()])
        ruin = np.mean([(e < 0.5).any() for e in eq.values()])  # cayó más de 50%
        out.append({"marco": tf, "estrat": strat, "riesgo%": risk * 100, "capital final (x)": round(final, 4),
                    "pares con -50%": f"{ruin:.0%}", "apalanc. medio": round((risk / g.unit).mean(), 1)})  # fmt: skip
pd.set_option("display.width", 200)
print(pd.DataFrame(out).to_string(index=False))
