"""Comparación de estrategias con walk-forward sobre varios pares e intervalos.

Solo usa datos anteriores a `backtest.holdout_start`: el holdout no se toca aquí.
Cada fila es un resultado **fuera de muestra** con la rejilla pequeña de la estrategia.
"""

from __future__ import annotations

import os
from concurrent.futures import ProcessPoolExecutor
from functools import partial
from pathlib import Path

import pandas as pd

from bot_eve.backtest.costs import rules_for
from bot_eve.backtest.engine import RiskSizing
from bot_eve.backtest.metrics import profit_factor, sharpe_ratio
from bot_eve.backtest.walkforward import param_combinations, split_holdout, walk_forward
from bot_eve.common.config import Config
from bot_eve.data.intervals import to_timedelta
from bot_eve.data.store import CandleStore
from bot_eve.strategies import REGISTRY, build_strategy

# (días de entrenamiento, días de prueba) según el intervalo
WINDOWS = {"5m": (90, 30), "15m": (90, 30), "1h": (180, 60), "4h": (360, 120)}


def windows_for(interval: str) -> tuple[int, int]:
    return WINDOWS.get(interval, (90, 30))


def run_one(job: tuple[Config, str, str, str, bool]) -> dict:
    cfg, strategy, symbol, interval, risk_sizing = job
    df = CandleStore(cfg.data.dir).read(symbol, interval)
    df, _holdout = split_holdout(df, cfg.backtest.holdout_start)
    cls = REGISTRY[strategy]
    grid = cls.default_grid
    train_days, test_days = windows_for(interval)
    per_day = int(pd.Timedelta(days=1) / to_timedelta(interval))
    bt = cfg.backtest
    res = walk_forward(
        df,
        partial(build_strategy, strategy),
        grid,
        train_days * per_day,
        test_days * per_day,
        objective="total_return",
        min_trades=10,
        costs=bt.costs(),
        rules=rules_for(symbol),
        initial_cash=bt.initial_cash,
        size_fraction=bt.size_fraction,
        risk=RiskSizing(cfg.risk.risk_per_trade, cfg.risk.default_stop_pct)
        if risk_sizing
        else None,
    )
    m = res.metrics
    gross = res.trades["pnl"] + res.trades["fees"] if len(res.trades) else pd.Series(dtype=float)
    return {
        "strategy": strategy,
        "symbol": symbol,
        "interval": interval,
        "return": m["total_return"],
        "buy_and_hold": m["buy_and_hold_return"],
        "sharpe": m["sharpe"],
        "max_drawdown": m["max_drawdown"],
        "trades": m["trades"],
        "win_rate": m["win_rate"],
        "profit_factor": m["profit_factor"],
        "pf_before_fees": profit_factor(gross) if len(gross) else float("nan"),
        "avg_trade": m["avg_trade_return"],
        "fees": m["total_fees"],
        "exposure": m["exposure"],
        "bh_sharpe": sharpe_ratio(res.benchmark),
        "bh_max_drawdown": m["buy_and_hold_max_drawdown"],
        "windows_pos": sum(w.test_metrics["total_return"] > 0 for w in res.windows),
        "windows_neg": sum(w.test_metrics["total_return"] < 0 for w in res.windows),
        "trials": len(param_combinations(grid)) * m["windows"],
    }


def compare(
    cfg: Config,
    strategies: list[str],
    symbols: list[str],
    intervals: list[str],
    workers: int | None = None,
    out: Path | None = None,
    risk_sizing: bool = False,
) -> pd.DataFrame:
    jobs = [
        (cfg, s, sym, itv, risk_sizing) for s in strategies for sym in symbols for itv in intervals
    ]
    workers = workers or os.cpu_count() or 1
    with ProcessPoolExecutor(workers) as pool:
        rows = list(pool.map(run_one, jobs))
    table = pd.DataFrame(rows)
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        table.to_csv(out, index=False)
    return table


def summarize(table: pd.DataFrame) -> pd.DataFrame:
    """Promedio por estrategia e intervalo (entre pares), para ver el panorama."""
    cols = ["return", "buy_and_hold", "sharpe", "max_drawdown", "profit_factor", "pf_before_fees"]
    out = table.groupby(["strategy", "interval"])[[*cols, "trades"]].mean()
    out["pairs_positive"] = (
        table.assign(pos=table["return"] > 0).groupby(["strategy", "interval"])["pos"].sum()
    )
    return out.sort_values("return", ascending=False)
