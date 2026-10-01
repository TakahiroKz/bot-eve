"""Pruebas pre-registradas multi-timeframe (docs/SCALPING_RESEARCH.md, «Replanteo»).

Cripto (desarrollo < 2025-07-01):   python research/mtf_test.py --suite scalp|intraday
FX en el PC de Leo (5m desde 2025-05-29): python research/mtf_test.py --suite intraday --fx --dir data_store/mt5 \
    --symbols EURUSD GBPUSD USDJPY AUDUSD --cut 2026-01-01
"""

import argparse

import numpy as np
import pandas as pd

from bot_eve.backtest.scalp import ScalpCosts, simulate, summarize
from bot_eve.data.store import CandleStore
from bot_eve.strategies.mtf import intraday_signal, scalp_signal

ap = argparse.ArgumentParser()
ap.add_argument("--suite", choices=["scalp", "intraday"], required=True)
ap.add_argument("--fx", action="store_true")
ap.add_argument("--dir", default="data_store")
ap.add_argument("--symbols", nargs="+", default=["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"])
ap.add_argument("--cut", default="2025-07-01")
ap.add_argument(
    "--holdout", action="store_true", help="evalúa el holdout (UNA vez) si hay aprobados"
)
ap.add_argument("--rr", type=float, default=2.0)
args = ap.parse_args()

CUT = pd.Timestamp(args.cut, tz="UTC")
END = CUT - pd.Timedelta(seconds=1)
COSTS = ({"opt": ScalpCosts(0.0, 0.00002), "real": ScalpCosts(0.0, 0.00005)} if args.fx
         else {"opt": ScalpCosts(0.0004, 0.0002), "real": ScalpCosts(0.001, 0.0005)})  # fmt: skip
SESSION_END = 21 * 60 if args.fx else 1440
store = CandleStore(args.dir)
cache: dict = {}


def prepare(sym, which):
    if (sym, which) in cache:
        return cache[(sym, which)]
    if args.suite == "scalp":
        d1, d5, d15 = (store.read(sym, x) for x in ("1m", "5m", "15m"))
        side, dist = scalp_signal(which, d1, d5, d15)
        out = (d1, side, dist, 15, 3)
    else:
        d5, d15, d1h = (store.read(sym, x) for x in ("5m", "15m", "1h"))
        side, dist, nxt, hold = intraday_signal(which, d5, d15, d1h, SESSION_END)
        side = np.where(nxt >= args.rr * dist, side, 0).astype(np.int8)
        out = (d5, side, dist, hold, None)
    cache[(sym, which)] = out
    return out


def evaluate(which, costs, start=None, end=END):
    per = {}
    for sym in args.symbols:
        df, side, dist, hold, stall = prepare(sym, which)
        per[sym] = simulate(df, side, dist, 1.0, args.rr, hold, costs, start, end, stall_bars=stall)
    allt = pd.concat([t.assign(pair=p) for p, t in per.items()], ignore_index=True)
    m = summarize(allt)
    yrs = (
        allt.groupby(allt.entry_time.dt.year)["r_net"].mean()
        if len(allt)
        else pd.Series(dtype=float)
    )
    yp = yrs.loc[2021:2025] if not args.fx else yrs
    pairs_pos = sum(1 for t in per.values() if len(t) and t.r_net.mean() > 0)
    n_req = 150 if args.fx else (500 if args.suite == "scalp" else 300)
    ok = (
        m["trades"] >= n_req
        and m["exp_r"] >= 0.05
        and m["pf"] >= 1.15
        and pairs_pos >= (3 if True else 0)
        and (args.fx or (yp > 0).sum() >= 4)
    )
    exits = allt.reason.value_counts(normalize=True).round(2).to_dict() if len(allt) else {}
    return {"est": which, "ops": m["trades"], "gana%": round(m["win_rate"] * 100), "R_bruta": round(m["exp_r_gross"], 3),
            "R_neta": round(m["exp_r"], 3), "costo_R": round(m["cost_r"], 3), "PF": round(m["pf"], 2),
            "años+": "-" if args.fx else f"{int((yp > 0).sum())}/{len(yp)}", "pares+": f"{pairs_pos}/{len(args.symbols)}",
            "salidas": exits, "_ok": bool(ok)}  # fmt: skip


suite = ["S1", "S2", "S3"] if args.suite == "scalp" else ["I1", "I2"]
pd.set_option("display.width", 220)
res = {k: [evaluate(w, c) for w in suite] for k, c in COSTS.items()}
for k in ("opt", "real"):
    print(f"DESARROLLO ({args.suite}), costos {k}: {COSTS[k]}, RR {args.rr}")
    print(pd.DataFrame(res[k]).drop(columns="_ok").to_string(index=False), "\n")
passed = [r["est"] for r in res["opt"] if r["_ok"]]
print("Pasan criterios con costos optimistas:", passed or "ninguna")
if args.holdout:
    for w in passed:
        if evaluate(w, COSTS["real"])["R_neta"] > 0:
            r = evaluate(w, COSTS["real"], start=CUT, end=None)
            print("HOLDOUT (una vez)", w, {k: v for k, v in r.items() if k != "_ok"})
