"""Métricas de rendimiento y riesgo de un backtest."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from bot_eve.backtest.engine import BacktestResult

DAYS_PER_YEAR = 365  # cripto opera todos los días


def max_drawdown(equity: pd.Series) -> float:
    """Mayor caída porcentual desde un máximo previo (valor negativo o 0)."""
    peak = equity.cummax()
    return float((equity / peak - 1).min())


def sharpe_ratio(equity: pd.Series) -> float:
    """Sharpe anualizado con retornos diarios y tasa libre de riesgo 0."""
    daily = equity.resample("1D").last().dropna().pct_change().dropna()
    if len(daily) < 2 or daily.std() < 1e-12:
        return float("nan")
    return float(daily.mean() / daily.std() * math.sqrt(DAYS_PER_YEAR))


def profit_factor(pnl: pd.Series) -> float:
    gains = pnl[pnl > 0].sum()
    losses = -pnl[pnl < 0].sum()
    if losses == 0:
        return float("inf") if gains > 0 else float("nan")
    return float(gains / losses)


def compute_metrics(result: BacktestResult) -> dict:
    eq, bench, trades = result.equity, result.benchmark, result.trades
    initial = result.initial_cash
    total_return = float(eq.iloc[-1] / initial - 1)
    years = (eq.index[-1] - eq.index[0]).total_seconds() / (DAYS_PER_YEAR * 86400)
    # Anualizar periodos de menos de un mes no es informativo (y explota numéricamente).
    if years >= 30 / DAYS_PER_YEAR and eq.iloc[-1] > 0:
        cagr = float(math.exp(math.log(eq.iloc[-1] / initial) / years) - 1)
    else:
        cagr = float("nan")
    n = len(trades)
    wins = int((trades["pnl"] > 0).sum()) if n else 0
    return {
        "initial_cash": initial,
        "final_equity": float(eq.iloc[-1]),
        "total_return": total_return,
        "cagr": cagr,
        "sharpe": sharpe_ratio(eq),
        "max_drawdown": max_drawdown(eq),
        "trades": n,
        "win_rate": wins / n if n else float("nan"),
        "profit_factor": profit_factor(trades["pnl"]) if n else float("nan"),
        "avg_trade_return": float(trades["return_pct"].mean()) if n else float("nan"),
        "total_fees": float(trades["fees"].sum()) if n else 0.0,
        "exposure": float(np.mean(result.in_position)),
        "rejected_entries": result.rejected_entries,
        "buy_and_hold_return": float(bench.iloc[-1] / initial - 1),
        "buy_and_hold_max_drawdown": max_drawdown(bench),
        "start": eq.index[0].isoformat(),
        "end": eq.index[-1].isoformat(),
    }
