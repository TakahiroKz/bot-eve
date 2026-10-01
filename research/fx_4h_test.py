"""`atr_breakout` 4h en FX (docs/SCALPING_RESEARCH.md, «Estrategia 4h validada en FX»).

En el PC de Leo:  python research/fx_4h_test.py --dir data_store/mt5 --symbols EURUSD GBPUSD USDJPY AUDUSD --cut 2026-01-01
Añade --holdout para evaluar el holdout (UNA vez) de lo que pase los criterios.
"""

import argparse

import pandas as pd

from bot_eve.backtest.costs import Costs, SymbolRules
from bot_eve.backtest.engine import RiskSizing
from bot_eve.backtest.portfolio import PortfolioLeg, run_portfolio
from bot_eve.data.store import CandleStore
from bot_eve.strategies import build_strategy

ap = argparse.ArgumentParser()
ap.add_argument("--dir", default="data_store/mt5")
ap.add_argument("--symbols", nargs="+", default=["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"])
ap.add_argument("--cut", default="2026-01-01")
ap.add_argument("--holdout", action="store_true")
args = ap.parse_args()

CUT = pd.Timestamp(args.cut, tz="UTC")
END = CUT - pd.Timedelta(seconds=1)
COSTS = {
    "FXo": Costs(fee_rate=0.0, slippage=0.00002),
    "FXr": Costs(fee_rate=0.0, slippage=0.00005, swap_pct_per_day=0.00005),
}
RISK = RiskSizing(0.005, 0.03)
RULES = SymbolRules(step_size=1e-9, min_qty=1e-9, min_notional=0.0)
PARAMS = {"entry_len": 40, "exit_len": 20, "stop_atr": 2.0}
store = CandleStore(args.dir)
AGG = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}


def h4(sym):
    h1 = store.read(sym, "1h")[["open", "high", "low", "close", "volume"]]
    g = h1.resample("4h", label="left", closed="left")
    out = g.agg(AGG)
    return out[g["open"].count() > 0]


def invert(df):
    return pd.DataFrame({"open": 1 / df["open"], "high": 1 / df["low"], "low": 1 / df["high"], "close": 1 / df["close"],
                         "volume": df["volume"]}, index=df.index)  # fmt: skip


def legs(costs, both):
    out = []
    for s in args.symbols:
        d = h4(s)
        out.append(PortfolioLeg(s, d, build_strategy("atr_breakout", **PARAMS), costs, RULES))
        if both:
            out.append(
                PortfolioLeg(
                    s + "_inv", invert(d), build_strategy("atr_breakout", **PARAMS), costs, RULES
                )
            )
    return out


def run(costs, both, start=None, end=END):
    return run_portfolio(
        legs(costs, both),
        500.0,
        RISK,
        10.0,
        4,
        max_leverage=10.0,
        start=start or "2020-01-01",
        end=end,
    )


def row(name, r):
    m, t = r.metrics, r.trades
    base = t["symbol"].str.replace("_inv", "", regex=False)
    both_open = 0
    if len(t):
        for s in set(base):
            x = t[base == s]
            a, b = x[~x.symbol.str.endswith("_inv")], x[x.symbol.str.endswith("_inv")]
            both_open += sum(
                (
                    (a.entry_time.values[:, None] < b.exit_time.values)
                    & (b.entry_time.values < a.exit_time.values[:, None])
                ).sum(1)
                > 0
            )
    pairs_pos = int((t.assign(b=base).groupby("b")["pnl"].mean() > 0).sum()) if len(t) else 0
    ok = (
        m["trades"] >= 150
        and m["cagr"] > 0
        and m["profit_factor"] >= 1.15
        and m["max_drawdown"] > -0.25
        and pairs_pos >= 3
    )
    return {"variante": name, "ops": m["trades"], "gana%": round(m["win_rate"] * 100), "CAGR%": round(m["cagr"] * 100, 1), "MaxDD%": round(m["max_drawdown"] * 100, 1),
            "PF": round(m["profit_factor"], 2), "ret%": round(m["total_return"] * 100, 1), "pares+": f"{pairs_pos}/{len(args.symbols)}",
            "solapes par/inv": both_open, "_ok": bool(ok)}  # fmt: skip


pd.set_option("display.width", 200)
rows = {}
for cn, c in COSTS.items():
    rows[cn] = [row("A solo largos", run(c, False)), row("B largos+cortos", run(c, True))]
    print(f"DESARROLLO (< {args.cut}), costos {cn}")
    print(pd.DataFrame(rows[cn]).drop(columns="_ok").to_string(index=False), "\n")
passed = [r["variante"] for r in rows["FXr"] if r["_ok"]]
print("Pasan criterios (costos FXr):", passed or "ninguna")
if args.holdout:
    for r in rows["FXr"]:
        if r["_ok"]:
            h = row(
                r["variante"], run(COSTS["FXr"], r["variante"].startswith("B"), start=CUT, end=None)
            )
            print("HOLDOUT (una vez)", {k: v for k, v in h.items() if k != "_ok"})
