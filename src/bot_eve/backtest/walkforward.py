"""Validación walk-forward y separación de un tramo final reservado (holdout).

Walk-forward: se optimiza en una ventana de entrenamiento, se evalúa en la ventana
siguiente (que el optimizador nunca vio) y se avanza. La curva fuera de muestra encadena
solo los tramos de prueba, reinvirtiendo el capital de una ventana a la siguiente.

Holdout: el tramo final de datos se aparta con `split_holdout` y no debe usarse para
diseñar ni ajustar nada. Se evalúa una sola vez, al final.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pandas as pd

from bot_eve.backtest.costs import Costs, SymbolRules
from bot_eve.backtest.engine import BacktestResult, buy_and_hold, run_backtest
from bot_eve.backtest.metrics import compute_metrics
from bot_eve.strategies.base import Strategy

OBJECTIVES = ("total_return", "sharpe", "profit_factor")


def split_holdout(
    df: pd.DataFrame, holdout_start: str | pd.Timestamp
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Divide en (desarrollo, holdout) por fecha. El holdout empieza en `holdout_start`."""
    cut = pd.Timestamp(holdout_start)
    cut = cut.tz_localize("UTC") if cut.tzinfo is None else cut
    return df[df.index < cut], df[df.index >= cut]


def param_combinations(grid: dict[str, list]) -> list[dict]:
    keys = list(grid)
    return [dict(zip(keys, values, strict=True)) for values in itertools.product(*grid.values())]


@dataclass
class WindowResult:
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp
    best_params: dict
    train_score: float
    test_metrics: dict


@dataclass
class WalkForwardResult:
    windows: list[WindowResult]
    equity: pd.Series
    benchmark: pd.Series
    trades: pd.DataFrame
    metrics: dict
    initial_cash: float


def walk_forward(
    df: pd.DataFrame,
    make_strategy: Callable[..., Strategy],
    grid: dict[str, list],
    train_bars: int,
    test_bars: int,
    objective: str = "total_return",
    min_trades: int = 10,
    costs: Costs = Costs(),  # noqa: B008
    rules: SymbolRules = SymbolRules(),  # noqa: B008
    initial_cash: float = 1000.0,
    size_fraction: float = 1.0,
) -> WalkForwardResult:
    """Walk-forward con ventanas deslizantes (sin solaparse en la parte de prueba)."""
    if objective not in OBJECTIVES:
        raise ValueError(f"objective debe ser uno de {OBJECTIVES}")
    combos = param_combinations(grid)
    if not combos:
        raise ValueError("La rejilla de parámetros está vacía")
    if len(df) < train_bars + test_bars:
        raise ValueError("No hay datos suficientes para una ventana completa")

    idx = df.index
    windows: list[WindowResult] = []
    equity_parts: list[pd.Series] = []
    trade_parts: list[pd.DataFrame] = []
    position_parts: list[np.ndarray] = []
    cash = float(initial_cash)

    pos = train_bars
    while pos + test_bars <= len(idx):
        tr_start, tr_end = idx[pos - train_bars], idx[pos - 1]
        te_start, te_end = idx[pos], idx[pos + test_bars - 1]

        best, best_score = None, -math.inf
        for params in combos:
            strat = make_strategy(**params)
            res = run_backtest(
                df.loc[:tr_end], strat, costs, rules, initial_cash, size_fraction,
                start=tr_start, end=tr_end,
            )  # fmt: skip
            score = _score(res, objective, min_trades)
            if score > best_score:
                best, best_score = params, score

        if best is None:  # ninguna combinación alcanzó el mínimo de operaciones
            best, best_score = combos[0], float("nan")
        strat = make_strategy(**best)
        test = run_backtest(
            df.loc[:te_end], strat, costs, rules, cash, size_fraction, start=te_start, end=te_end
        )
        windows.append(
            WindowResult(tr_start, tr_end, te_start, te_end, best, best_score, test.metrics)
        )
        equity_parts.append(test.equity)
        trade_parts.append(test.trades)
        position_parts.append(test.in_position)
        cash = float(test.equity.iloc[-1])
        pos += test_bars

    equity = pd.concat(equity_parts)
    # Buy & hold sobre todo el tramo fuera de muestra: una sola entrada y una sola salida.
    oos = df.loc[equity.index[0] : equity.index[-1]]
    benchmark = buy_and_hold(
        oos["open"].iloc[0], oos["close"].to_numpy(), initial_cash, costs, oos.index
    )
    trades = pd.concat(trade_parts, ignore_index=True)
    combined = BacktestResult(
        strategy=strat.name,
        params={"walk_forward": True, "grid": grid},
        initial_cash=float(initial_cash),
        equity=equity,
        benchmark=benchmark,
        trades=trades,
        rejected_entries=0,
        in_position=np.concatenate(position_parts),
    )
    metrics = compute_metrics(combined)
    metrics["windows"] = len(windows)
    metrics["rejected_entries"] = sum(w.test_metrics["rejected_entries"] for w in windows)
    return WalkForwardResult(windows, equity, benchmark, trades, metrics, float(initial_cash))


def _score(res: BacktestResult, objective: str, min_trades: int) -> float:
    if res.metrics["trades"] < min_trades:
        return -math.inf
    value = res.metrics[objective]
    return -math.inf if value != value else float(value)  # NaN nunca gana
