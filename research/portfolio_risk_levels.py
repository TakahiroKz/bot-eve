"""Informativo: cartera 4h de 9 pares con tres niveles de riesgo más agresivos (no es una prueba de aprobación)."""

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
RULES = SymbolRules(step_size=1e-6, min_qty=1e-6, min_notional=5.0)
HARD = Costs(fee_rate=0.001, slippage=0.001)
PARAMS = {"entry_len": 40, "exit_len": 20, "stop_atr": 2.0}


def legs(symbols):
    return [
        PortfolioLeg(s, store.read(s, "4h"), build_strategy("atr_breakout", **PARAMS),
                     cfg.backtest.costs(s) if s in REF else HARD, RULES)
        for s in symbols
    ]  # fmt: skip


LEVELS = [("Base 0.5% / tope 15%", 0.005, 0.15), ("Agresivo 1 : 1% / 25%", 0.01, 0.25),
          ("Agresivo 2 : 2% / 40%", 0.02, 0.40), ("Agresivo 3 : 3% / 50%", 0.03, 0.50)]  # fmt: skip
rows = []
for name, rp, cap in LEVELS:
    rk = RiskSizing(rp, cfg.risk.default_stop_pct)
    full = run_portfolio(legs(REF + NEW), 500.0, rk, cap, 4, start="2020-01-01")
    dev = run_portfolio(
        legs(REF + NEW), 500.0, rk, cap, 4, start="2020-01-01", end=cut - pd.Timedelta(seconds=1)
    )
    hold = run_portfolio(legs(REF + NEW), 500.0, rk, cap, 4, start=cut)
    yr = full.equity.resample("YE").last()
    yrs = (yr / yr.shift(1).fillna(500.0) - 1) * 100
    rows.append({"nivel": name, "dev CAGR%": round(dev.metrics["cagr"] * 100, 1), "dev MaxDD%": round(dev.metrics["max_drawdown"] * 100, 1),
                 "dev PF": round(dev.metrics["profit_factor"], 2), "hold ret%": round(hold.metrics["total_return"] * 100, 1),
                 "hold MaxDD%": round(hold.metrics["max_drawdown"] * 100, 1), "peor año%": round(yrs.min()),
                 "mejor año%": round(yrs.max()), "500 USD hoy": round(full.metrics["final_equity"])})  # fmt: skip
pd.set_option("display.width", 220)
print(pd.DataFrame(rows).to_string(index=False))
