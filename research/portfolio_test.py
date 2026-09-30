"""Prueba pre-registrada (docs/CAPITAL_500.md §3.3): cartera con capital compartido, universo A vs B.
Ejecutar desde la raíz:  python research/portfolio_test.py
"""

import pandas as pd

from bot_eve.backtest.costs import Costs, SymbolRules
from bot_eve.backtest.engine import RiskSizing
from bot_eve.backtest.portfolio import PortfolioLeg, run_portfolio
from bot_eve.common.config import load_config
from bot_eve.data.store import CandleStore
from bot_eve.strategies import build_strategy

REF = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
NEW = ["SOLUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "LINKUSDT", "AVAXUSDT"]
cfg = load_config()
store = CandleStore(cfg.data.dir)
cut = pd.Timestamp(cfg.backtest.holdout_start, tz="UTC")
risk = RiskSizing(cfg.risk.risk_per_trade, cfg.risk.default_stop_pct)
RULES = SymbolRules(step_size=1e-6, min_qty=1e-6, min_notional=5.0)
HARD = Costs(fee_rate=0.001, slippage=0.001)
PARAMS = {"entry_len": 40, "exit_len": 20, "stop_atr": 2.0}


def legs(symbols):
    return [
        PortfolioLeg(s, store.read(s, "4h"), build_strategy("atr_breakout", **PARAMS),
                     cfg.backtest.costs(s) if s in REF else HARD, RULES)
        for s in symbols
    ]  # fmt: skip


def row(name, res):
    m = res.metrics
    return {"escenario": name, "ops": m["trades"], "retorno%": round(m["total_return"] * 100, 1),
            "CAGR%": round(m["cagr"] * 100, 1), "MaxDD%": round(m["max_drawdown"] * 100, 1),
            "PF": round(m["profit_factor"], 2), "gana%": round(m["win_rate"] * 100), "ops/mes": round(m["trades_per_month"], 1),
            "descartadas": res.skipped_no_slot, "max_abiertas": res.max_open}  # fmt: skip


dev_end = cut - pd.Timedelta(seconds=1)
rows, res = [], {}
for name, syms, mp in [("A (3 pares) mp=4", REF, 4), ("B (9 pares) mp=4", REF + NEW, 4),
                       ("B mp=3 (sensib.)", REF + NEW, 3), ("B mp=6 (sensib.)", REF + NEW, 6)]:  # fmt: skip
    # todos parten del mismo inicio para comparar: primera vela común a A y B
    r = run_portfolio(legs(syms), 500.0, risk, 0.25, mp, start="2020-01-01", end=dev_end)
    res[name] = r
    rows.append(row(name, r))
pd.set_option("display.width", 220)
print("DESARROLLO (< holdout)")
print(pd.DataFrame(rows).to_string(index=False))
a, b = res["A (3 pares) mp=4"].metrics, res["B (9 pares) mp=4"].metrics
ok = (
    b["cagr"] > a["cagr"]
    and b["max_drawdown"] > -0.25
    and b["profit_factor"] >= 1.3
    and b["trades"] >= 150
)
print("\nCriterios dev B:", {"CAGR>A": b["cagr"] > a["cagr"], "DD>-25%": b["max_drawdown"] > -0.25,
                              "PF>=1.3": b["profit_factor"] >= 1.3, "ops>=150": b["trades"] >= 150})  # fmt: skip
if not ok:
    print("VEREDICTO: B no pasa el desarrollo. El universo NO se amplía. (Holdout no consumido.)")
    raise SystemExit(0)
print("\nHOLDOUT (una vez)")
ra = run_portfolio(legs(REF), 500.0, risk, 0.25, 4, start=cut)
rb = run_portfolio(legs(REF + NEW), 500.0, risk, 0.25, 4, start=cut)
print(pd.DataFrame([row("A (3 pares)", ra), row("B (9 pares)", rb)]).to_string(index=False))
m = rb.metrics
print("VEREDICTO:", "APRUEBA" if m["total_return"] > 0 and m["profit_factor"] > 1 else "NO aprueba")
