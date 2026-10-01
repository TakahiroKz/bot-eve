"""Prueba pre-registrada de impulso/ruptura (docs/SCALPING_RESEARCH.md, familia 2)."""

import numpy as np
import pandas as pd

from bot_eve.backtest.scalp import ScalpCosts, simulate, summarize
from bot_eve.data.store import CandleStore
from bot_eve.strategies.scalp_signals import breakout_volume

PAIRS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]
CUT = pd.Timestamp("2025-07-01", tz="UTC")
F, S = ScalpCosts(0.0004, 0.0002), ScalpCosts(0.001, 0.0005)
store = CandleStore("data_store")
END = CUT - pd.Timedelta(seconds=1)
cache = {}


def row(label, allt, per, col, k):
    r = allt[col].to_numpy()
    g, ls = r[r > 0].sum(), -r[r < 0].sum()
    yrs = allt.groupby(allt.entry_time.dt.year)[col].mean().loc[2021:2025]
    return {"prueba": label, "ops": len(r), "gana%": round((r > 0).mean() * 100), f"media_{k}": round(r.mean() * (1 if k == "R" else 1e4), 3),
            "PF": round(g / ls, 2) if ls else None, "años+": f"{int((yrs > 0).sum())}/{len(yrs)}",
            "pares+": f"{sum(1 for t in per.values() if len(t) and t[col].mean() > 0)}/4"}  # fmt: skip


def run_2a(tf, costs, start=None, end=END):
    per = {}
    for p in PAIRS:
        if (p, tf) not in cache:
            df, htf = store.read(p, tf), store.read(p, "1h")
            side, atr = breakout_volume(df, htf, tf)
            cache[(p, tf)] = (df, side, atr)
        df, side, atr = cache[(p, tf)]
        per[p] = simulate(df, side, atr, 1.5, 3.0, 24, costs, start, end)
    return row(
        f"2a ruptura {tf}", pd.concat(per.values(), ignore_index=True), per, "r_net", "R"
    ), per


def run_2b(costs, start=None, end=END):
    per = {}
    for p in PAIRS:
        df = store.read(p, "5m")
        o = df["open"]
        day = df.index.normalize()
        first = o.groupby(day).transform("first")
        # retorno 00:00-00:30: apertura de la barra 00:30 / apertura 00:00
        t0030 = o[(df.index.hour == 0) & (df.index.minute == 30)]
        t0030.index = t0030.index.normalize()
        o_day0 = o[(df.index.hour == 0) & (df.index.minute == 0)]
        o_day0.index = o_day0.index.normalize()
        sig = np.sign(t0030 / o_day0 - 1).dropna()
        t2330 = o[(df.index.hour == 23) & (df.index.minute == 30)]
        t2330.index = t2330.index.normalize()
        nxt = o_day0.copy()
        nxt.index = nxt.index - pd.Timedelta(days=1)  # apertura de las 00:00 del día siguiente
        ret = (nxt / t2330 - 1).dropna()
        d = pd.concat([sig.rename("s"), ret.rename("ret")], axis=1, sort=True).dropna()
        d["net"] = d["s"] * d["ret"] - 2 * (costs.fee + costs.slip)
        d["entry_time"] = d.index
        d["gross"] = d["s"] * d["ret"]
        d = d[(d.index >= (start or d.index[0])) & (d.index <= end)]
        per[p] = d[d.s != 0]
        del first
    allt = pd.concat(per.values(), ignore_index=True)
    return row("2b momentum intradía", allt, per, "net", "bp"), per


pd.set_option("display.width", 200)
rows_f = [run_2a("15m", F)[0], run_2a("5m", F)[0], run_2b(F)[0]]
rows_s = [run_2a("15m", S)[0], run_2a("5m", S)[0], run_2b(S)[0]]
print("DESARROLLO, costos F\n", pd.DataFrame(rows_f).to_string(index=False))
print("\nDESARROLLO, costos S\n", pd.DataFrame(rows_s).to_string(index=False))
for tf in ("15m", "5m"):
    m = summarize(pd.concat(run_2a(tf, F)[1].values(), ignore_index=True))
    print(tf, "R bruta", round(m["exp_r_gross"], 3), "costo R", round(m["cost_r"], 3))

print(
    "2b media bruta antes de costos (pb):",
    round(pd.concat(run_2b(F)[1].values())["gross"].mean() * 1e4, 2),
)
