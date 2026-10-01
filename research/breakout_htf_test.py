"""Ruptura con volumen (C) en 2h y 4h (docs/SCALPING_RESEARCH.md).

Cripto:  python research/breakout_htf_test.py
FX:      python research/breakout_htf_test.py --fx --dir data_store/mt5 --symbols EURUSD GBPUSD USDJPY AUDUSD --cut 2026-01-01
Añade --holdout para evaluar el holdout (UNA vez) de lo que pase los criterios.
"""

import argparse

import pandas as pd

from bot_eve.backtest.scalp import ScalpCosts, simulate, summarize
from bot_eve.data.store import CandleStore
from bot_eve.strategies.scalp_signals import breakout_volume

ap = argparse.ArgumentParser()
ap.add_argument("--fx", action="store_true")
ap.add_argument("--dir", default="data_store")
ap.add_argument("--symbols", nargs="+", default=["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"])
ap.add_argument("--cut", default="2025-07-01")
ap.add_argument("--holdout", action="store_true")
args = ap.parse_args()

CUT = pd.Timestamp(args.cut, tz="UTC")
END = CUT - pd.Timedelta(seconds=1)
COSTS = ({"opt": ScalpCosts(0.0, 0.00002), "real": ScalpCosts(0.0, 0.00005)} if args.fx
         else {"opt": ScalpCosts(0.0004, 0.0002), "real": ScalpCosts(0.001, 0.0005)})  # fmt: skip
store = CandleStore(args.dir)
AGG = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}


def resample(df, rule, full):
    g = df.resample(rule, label="left", closed="left")
    out = g.agg(AGG)
    n = g["open"].count()
    return out[(n == full) if full else (n > 0)]


def frames(sym, tf):
    h1 = store.read(sym, "1h")[["open", "high", "low", "close", "volume"]]
    if tf == "1h":
        return h1, resample(h1, "4h", None), "4h"
    entry = resample(h1, tf, int(tf[:-1]))  # solo velas completas
    return entry, resample(h1, "1D", None), "1d"


cache = {}


def evaluate(tf, costs, start=None, end=END):
    per = {}
    for sym in args.symbols:
        if (sym, tf) not in cache:
            df, htf, name = frames(sym, tf)
            side, atr = breakout_volume(df, htf, tf, name)
            cache[(sym, tf)] = (df, side, atr)
        df, side, atr = cache[(sym, tf)]
        per[sym] = simulate(df, side, atr, 1.5, 3.0, 24, costs, start, end)
    allt = pd.concat([t.assign(pair=p) for p, t in per.items()], ignore_index=True)
    m = summarize(allt)
    yrs = (
        allt.groupby(allt.entry_time.dt.year)["r_net"].mean().loc[2021:2025]
        if len(allt)
        else pd.Series(dtype=float)
    )
    pp = sum(1 for t in per.values() if len(t) and t.r_net.mean() > 0)
    ok = (
        m["trades"] >= 300
        and m["exp_r"] >= 0.05
        and m["pf"] >= 1.15
        and (yrs > 0).sum() >= 4
        and pp >= 3
    )
    return {"marco": tf, "ops": m["trades"], "gana%": round(m["win_rate"] * 100), "R_bruta": round(m["exp_r_gross"], 3),
            "R_neta": round(m["exp_r"], 3), "PF": round(m["pf"], 2), "años+": f"{int((yrs > 0).sum())}/{len(yrs)}",
            "pares+": f"{pp}/{len(args.symbols)}", "_ok": bool(ok)}  # fmt: skip


pd.set_option("display.width", 200)
res = {k: [evaluate(tf, c) for tf in ("1h", "2h", "4h")] for k, c in COSTS.items()}
for k in ("opt", "real"):
    print(f"DESARROLLO, costos {k}: {COSTS[k]}")
    print(pd.DataFrame(res[k]).drop(columns="_ok").to_string(index=False), "\n")
passed = [r["marco"] for r in res["opt"] if r["_ok"] and r["marco"] != "1h"]
print("Pasan criterios (2h/4h, costos optimistas):", passed or "ninguno")
if args.holdout:
    for tf in passed:
        if evaluate(tf, COSTS["real"])["R_neta"] > 0:
            print(
                "HOLDOUT (una vez)",
                tf,
                {
                    k: v
                    for k, v in evaluate(tf, COSTS["real"], start=CUT, end=None).items()
                    if k != "_ok"
                },
            )
