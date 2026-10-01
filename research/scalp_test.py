"""Prueba pre-registrada de scalping (docs/SCALPING_RESEARCH.md). Ejecutar:  python research/scalp_test.py"""

import sys

import pandas as pd

from bot_eve.backtest.scalp import ScalpCosts, simulate, summarize
from bot_eve.data.store import CandleStore
from bot_eve.strategies.scalp_signals import pullback_momentum, random_entries, zscore_reversion

PAIRS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]
TFS = sys.argv[1].split(",") if len(sys.argv) > 1 else ["15m", "5m", "1m"]
CUT = pd.Timestamp("2025-07-01", tz="UTC")
F, S = ScalpCosts(0.0004, 0.0002), ScalpCosts(0.001, 0.0005)
store = CandleStore("data_store")
STRATS = {
    "A pullback": (pullback_momentum, 1.2, 1.8),
    "B z-score": (zscore_reversion, 1.5, 1.5),
    "aleatoria": (None, 1.2, 1.8),
}


def trades_for(sym, tf, name, costs, start=None, end=None, cache={}):  # noqa: B006
    key = (sym, tf, name)
    if key not in cache:
        df, htf = store.read(sym, tf), store.read(sym, "1h")
        fn, sl, tp = STRATS[name]
        side, atr = random_entries(df) if fn is None else fn(df, htf, tf)
        cache[key] = (df, side, atr, sl, tp)
    df, side, atr, sl, tp = cache[key]
    return simulate(df, side, atr, sl, tp, 24, costs, start, end)


def evaluate(name, tf, costs, start=None, end=None):
    per = {p: trades_for(p, tf, name, costs, start, end) for p in PAIRS}
    allt = pd.concat([t.assign(pair=p) for p, t in per.items()], ignore_index=True)
    m = summarize(allt)
    yrs = (
        allt.groupby(allt.entry_time.dt.year)["r_net"].mean()
        if len(allt)
        else pd.Series(dtype=float)
    )
    m["years_pos"] = (
        f"{int((yrs.loc[2021:2025] > 0).sum())}/{len(yrs.loc[2021:2025])}" if len(yrs) else "0/0"
    )
    m["pairs_pos"] = sum(1 for t in per.values() if len(t) and t.r_net.mean() > 0)
    return m


def fmt(name, tf, m):
    return {"estrategia": name, "marco": tf, "ops": m["trades"], "gana%": round(m["win_rate"] * 100), "R_bruta": round(m["exp_r_gross"], 3),
            "R_neta": round(m["exp_r"], 3), "costo_R": round(m["cost_r"], 3), "PF": round(m["pf"], 2), "años+": m["years_pos"],
            "pares+": f"{m['pairs_pos']}/4"}  # fmt: skip


pd.set_option("display.width", 220)
dev_end = CUT - pd.Timedelta(seconds=1)
rows, passed = [], []
for tf in TFS:
    for name in STRATS:
        m = evaluate(name, tf, F, end=dev_end)
        rows.append(fmt(name, tf, m))
        if name != "aleatoria":
            yp = int(m["years_pos"].split("/")[0])
            ok = (
                m["trades"] >= 500
                and m["exp_r"] >= 0.05
                and m["pf"] >= 1.15
                and yp >= 4
                and m["pairs_pos"] >= 3
            )
            if ok:
                passed.append((name, tf))
print("DESARROLLO, costos F (comisión 0.04% + slip 0.02% por lado)")
print(pd.DataFrame(rows).to_string(index=False))
print("\nPasan 1-5 con costos F:", passed or "ninguna")
print("\nMisma prueba con costos S (0.10% + 0.05%) para referencia:")
print(
    pd.DataFrame(
        [fmt(n, tf, evaluate(n, tf, S, end=dev_end)) for tf in TFS for n in STRATS]
    ).to_string(index=False)
)
rows = []
for name, tf in passed:
    ms = evaluate(name, tf, S, end=dev_end)
    if ms["exp_r"] > 0:
        rows.append(fmt(name, tf, evaluate(name, tf, S, start=CUT)))  # HOLDOUT, una vez
        rows[-1]["estrategia"] += " (HOLDOUT, costos S)"
if rows:
    print("\nHOLDOUT (una vez):")
    print(pd.DataFrame(rows).to_string(index=False))
