"""Prueba pre-registrada (docs/CAPITAL_500.md §3): `atr_breakout` 4h con parámetros fijos en más pares.

Paso 1 (desarrollo, < holdout_start): criterio por par = PF neto >= 1.2, >= 40 operaciones y caída máxima menor
que la del buy & hold. Costos más duros (slippage 0.10% por lado). Sin reoptimizar nada.
Paso 2 (UNA sola vez): holdout para el conjunto que pase; la cartera equiponderada debe tener retorno > 0 y
PF > 1, y >= 2/3 de los pares con retorno positivo.
Ejecutar desde la raíz:  python research/universe_test.py
"""

import numpy as np
import pandas as pd

from bot_eve.backtest.costs import Costs, SymbolRules
from bot_eve.backtest.engine import RiskSizing, run_backtest
from bot_eve.common.config import load_config
from bot_eve.data.store import CandleStore
from bot_eve.strategies import build_strategy

NEW = ["SOLUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "LINKUSDT", "LTCUSDT", "AVAXUSDT", "DOTUSDT"]
REF = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
CASH, CAP = 500.0, 0.25
cfg = load_config()
store = CandleStore(cfg.data.dir)
cut = pd.Timestamp(cfg.backtest.holdout_start, tz="UTC")
risk = RiskSizing(cfg.risk.risk_per_trade, cfg.risk.default_stop_pct)
HARD = Costs(fee_rate=0.001, slippage=0.001)  # el doble de slippage que BTC/ETH/BNB
RULES = SymbolRules(step_size=1e-6, min_qty=1e-6, min_notional=5.0)
PARAMS = {"entry_len": 40, "exit_len": 20, "stop_atr": 2.0}


def run(sym, start=None, end=None):
    df = store.read(sym, "4h")
    return run_backtest(df, build_strategy("atr_breakout", **PARAMS), HARD, RULES, CASH, CAP,
                        start=start, end=end, risk=risk)  # fmt: skip


rows, passed = [], []
for sym in REF + NEW:
    if not store.months(sym, "4h"):
        rows.append({"par": sym, "nota": "sin datos"})
        continue
    m = run(sym, end=cut - pd.Timedelta(seconds=1)).metrics
    ok = (
        m["profit_factor"] >= 1.2
        and m["trades"] >= 40
        and m["max_drawdown"] > m["buy_and_hold_max_drawdown"]
    )
    rows.append({"par": sym, "grupo": "referencia" if sym in REF else "NUEVO", "desde": m["start"][:10],
                 "ops": m["trades"], "PF": round(m["profit_factor"], 2), "retorno%": round(m["total_return"] * 100, 1),
                 "MaxDD%": round(m["max_drawdown"] * 100, 1), "B&H_DD%": round(m["buy_and_hold_max_drawdown"] * 100, 1),
                 "aprueba": "SÍ" if ok else "no"})  # fmt: skip
    if ok and sym in NEW:
        passed.append(sym)
pd.set_option("display.width", 220)
print("PASO 1 - desarrollo (costos duros: comisión 0.1% + slippage 0.1% por lado)")
print(pd.DataFrame(rows).to_string(index=False))
print("\nPares NUEVOS que pasan:", passed or "ninguno")

if not passed:
    print("Ninguno pasa: el universo NO se amplía. (El holdout no se consume.)")
    raise SystemExit(0)

# correlación de retornos diarios entre los pares incluidos (desarrollo)
daily = pd.concat(  # noqa: E501
    {
        s: run(s, end=cut - pd.Timedelta(seconds=1)).equity.resample("1D").last().pct_change()
        for s in passed + REF
    },
    axis=1,
).dropna()
print(
    "\nCorrelación media de retornos diarios entre pares:",
    round(float(daily.corr().where(~np.eye(len(daily.columns), dtype=bool)).stack().mean()), 2),
)

print("\nPASO 2 - holdout (UNA sola evaluación) para", passed)
res = {s: run(s, start=cut) for s in passed}
trades = pd.concat([r.trades for r in res.values()])
eq = pd.concat({s: r.equity / CASH for s, r in res.items()}, axis=1).dropna().mean(axis=1)
gains, losses = trades.loc[trades.pnl > 0, "pnl"].sum(), -trades.loc[trades.pnl < 0, "pnl"].sum()
pf = gains / losses if losses else float("inf")
pos = sum(r.metrics["total_return"] > 0 for r in res.values())
print(pd.DataFrame([{"par": s, "ops": r.metrics["trades"], "retorno%": round(r.metrics["total_return"] * 100, 1),
                     "PF": round(r.metrics["profit_factor"], 2) if r.metrics["profit_factor"] == r.metrics["profit_factor"] else None}
                    for s, r in res.items()]).to_string(index=False))  # fmt: skip
ret = eq.iloc[-1] - 1
verdict = ret > 0 and pf > 1 and pos / len(res) >= 2 / 3
print(
    f"\nCartera equiponderada en holdout: retorno {ret:+.1%} | PF agregado {pf:.2f} | pares positivos {pos}/{len(res)}"
)
print(
    "VEREDICTO PRE-REGISTRADO:",
    "APRUEBA ampliar el universo a " + str(passed)
    if verdict
    else "NO aprueba: el universo no se amplía",
)
