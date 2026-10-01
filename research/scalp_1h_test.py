"""Prueba pre-registrada en 1h (docs/SCALPING_RESEARCH.md, «Marco 1h en cripto»)."""

import pandas as pd

from bot_eve.backtest.scalp import ScalpCosts, simulate, summarize
from bot_eve.data.store import CandleStore
from bot_eve.strategies.scalp_signals import (
    breakout_volume,
    pullback_momentum,
    random_entries,
    zscore_reversion,
)

PAIRS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]
CUT = pd.Timestamp("2025-07-01", tz="UTC")
END = CUT - pd.Timedelta(seconds=1)
F, S = ScalpCosts(0.0004, 0.0002), ScalpCosts(0.001, 0.0005)
store = CandleStore("data_store")
STRATS = {"A pullback": (pullback_momentum, 1.2, 1.8), "B z-score": (zscore_reversion, 1.5, 1.5),
          "C ruptura": (breakout_volume, 1.5, 3.0), "aleatoria": (None, 1.2, 1.8)}  # fmt: skip
cache = {}


def evaluate(name, costs, start=None, end=END):
    per = {}
    for p in PAIRS:
        if (p, name) not in cache:
            df, htf = store.read(p, "1h"), store.read(p, "4h")
            fn = STRATS[name][0]
            side, atr = random_entries(df) if fn is None else fn(df, htf, "1h", "4h")
            cache[(p, name)] = (df, side, atr)
        df, side, atr = cache[(p, name)]
        per[p] = simulate(df, side, atr, STRATS[name][1], STRATS[name][2], 24, costs, start, end)
    allt = pd.concat([t.assign(pair=p) for p, t in per.items()], ignore_index=True)
    m = summarize(allt)
    yrs = allt.groupby(allt.entry_time.dt.year)["r_net"].mean().loc[2021:2025]
    return {"estrategia": name, "ops": m["trades"], "gana%": round(m["win_rate"] * 100), "R_bruta": round(m["exp_r_gross"], 3),
            "R_neta": round(m["exp_r"], 3), "costo_R": round(m["cost_r"], 3), "PF": round(m["pf"], 2),
            "años+": f"{int((yrs > 0).sum())}/{len(yrs)}", "pares+": f"{sum(1 for t in per.values() if len(t) and t.r_net.mean() > 0)}/4",
            "_ok": m["trades"] >= 500 and m["exp_r"] >= 0.05 and m["pf"] >= 1.15 and (yrs > 0).sum() >= 4
            and sum(1 for t in per.values() if len(t) and t.r_net.mean() > 0) >= 3}  # fmt: skip


pd.set_option("display.width", 200)
f_rows = [evaluate(n, F) for n in STRATS]
print("DESARROLLO 1h, costos F\n", pd.DataFrame(f_rows).drop(columns="_ok").to_string(index=False))
print(
    "\nDESARROLLO 1h, costos S\n",
    pd.DataFrame([evaluate(n, S) for n in STRATS]).drop(columns="_ok").to_string(index=False),
)
ok = [r["estrategia"] for r in f_rows if r["_ok"] and r["estrategia"] != "aleatoria"]
print("\nPasan criterios con F:", ok or "ninguna")
for n in ok:
    if evaluate(n, S)["R_neta"] > 0:
        print(
            "HOLDOUT (una vez)",
            n,
            {k: v for k, v in evaluate(n, S, start=CUT, end=None).items() if k != "_ok"},
        )
