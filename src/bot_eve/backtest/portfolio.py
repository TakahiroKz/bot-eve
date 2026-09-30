"""Simulador de cartera long-only con capital compartido y máximo de posiciones simultáneas.

Mismas reglas de ejecución que `engine.run_backtest` (señal al cierre de `t`, ejecución en la apertura de
`t+1`, slippage/comisión por lado, stop antes que objetivo en la misma vela, gap al peor precio), pero con
una sola caja para todos los pares:

- Tamaño = patrimonio ACTUAL * riesgo / distancia al stop, con tope `position_cap` del patrimonio actual
  y limitado por el efectivo libre.
- Como máximo `max_positions` abiertas y una por par. Si hay más señales que huecos, las entradas se
  atienden en el orden en que se pasan los pares (determinista); las demás se descartan y se cuentan.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from bot_eve.backtest.costs import Costs, SymbolRules
from bot_eve.backtest.engine import RiskSizing, _check_signals, _utc
from bot_eve.strategies.base import BUY, SELL, Strategy

TRADE_COLUMNS = [
    "symbol", "entry_time", "exit_time", "entry_price", "exit_price", "qty", "pnl", "return_pct", "exit_reason",
]  # fmt: skip


@dataclass(frozen=True)
class PortfolioLeg:
    """Un par con su estrategia, costos y filtros de mercado."""

    symbol: str
    df: pd.DataFrame
    strategy: Strategy
    costs: Costs = Costs()  # noqa: B008
    rules: SymbolRules = SymbolRules()  # noqa: B008


@dataclass
class PortfolioResult:
    initial_cash: float
    equity: pd.Series
    trades: pd.DataFrame
    skipped_no_slot: int
    rejected_entries: int
    max_open: int
    metrics: dict


def run_portfolio(
    legs: list[PortfolioLeg],
    initial_cash: float = 500.0,
    risk: RiskSizing | None = None,
    position_cap: float = 0.25,
    max_positions: int = 4,
    start: str | pd.Timestamp | None = None,
    end: str | pd.Timestamp | None = None,
) -> PortfolioResult:
    if not legs:
        raise ValueError("Se necesita al menos un par")
    if not 0 < position_cap <= 1 or max_positions < 1:
        raise ValueError("position_cap en (0, 1] y max_positions >= 1")
    risk = risk or RiskSizing()

    idx = legs[0].df.index
    for leg in legs[1:]:
        idx = idx.union(leg.df.index)
    i0 = 0 if start is None else int(idx.searchsorted(_utc(start), "left"))
    i1 = len(idx) if end is None else int(idx.searchsorted(_utc(end), "right"))
    if i1 - i0 < 2:
        raise ValueError("El rango a simular tiene menos de 2 velas")

    n = len(legs)
    o, h, lo, c = ([None] * n for _ in range(4))
    sig, stp, tgt = [None] * n, [None] * n, [None] * n
    for k, leg in enumerate(legs):
        s = leg.strategy.generate(leg.df).reindex(leg.df.index)
        _check_signals(s)
        ri = leg.df.reindex(idx)
        o[k], h[k], lo[k], c[k] = (
            ri[x].to_numpy(dtype=float) for x in ("open", "high", "low", "close")
        )
        sig[k] = s["signal"].fillna(0).reindex(idx).fillna(0).to_numpy(dtype=np.int8)
        stp[k] = s["stop_pct"].reindex(idx).to_numpy(dtype=float)
        tgt[k] = s["target_pct"].reindex(idx).to_numpy(dtype=float)

    cash = float(initial_cash)
    pos: list[dict | None] = [None] * n
    pending = [(0, np.nan, np.nan)] * n
    last_c = [np.nan] * n
    equity = np.empty(i1 - i0)
    trades: list[tuple] = []
    skipped = rejected = max_open = 0

    def close(k: int, i: int, price: float, reason: str) -> None:
        nonlocal cash
        p, cs = pos[k], legs[k].costs
        proceeds = p["qty"] * price
        fee = proceeds * cs.exit_fee
        days = (idx[i] - p["time"]).total_seconds() / 86400
        swap = p["qty"] * p["px"] * cs.swap_pct_per_day * days
        cash += proceeds - fee - swap
        pnl = proceeds - fee - swap - p["cost"]
        trades.append(
            (legs[k].symbol, p["time"], idx[i], p["px"], price, p["qty"], pnl, pnl / p["cost"], reason)
        )  # fmt: skip
        pos[k] = None

    def mark() -> float:
        return cash + sum(p["qty"] * last_c[k] for k, p in enumerate(pos) if p)

    for i in range(i0, i1):
        for k in range(n):  # 1) ejecutar órdenes pendientes (las salidas liberan efectivo primero)
            side = pending[k][0]
            if side == SELL and o[k][i] == o[k][i]:
                if pos[k]:
                    close(k, i, o[k][i] * (1 - legs[k].costs.slippage), "signal")
                pending[k] = (0, np.nan, np.nan)
        for k in range(n):
            side, p_stop, p_tgt = pending[k]
            if side != BUY or o[k][i] != o[k][i]:
                continue
            pending[k] = (0, np.nan, np.nan)
            if pos[k]:
                continue
            if sum(p is not None for p in pos) >= max_positions:
                skipped += 1
                continue
            cs = legs[k].costs
            px = o[k][i] * (1 + cs.slippage + cs.spread_pct)
            frac = risk.stop_pct(p_stop)
            eq = mark()
            q = min(eq * position_cap, eq * risk.risk_per_trade / frac, cash) / (
                px * (1 + cs.entry_fee)
            )
            q = legs[k].rules.round_qty(q)
            if not legs[k].rules.is_valid(q, px):
                rejected += 1
                continue
            cost = q * px * (1 + cs.entry_fee)
            cash -= cost
            pos[k] = {
                "qty": q, "px": px, "cost": cost, "time": idx[i], "stop": px * (1 - frac),
                "target": px * (1 + p_tgt) if p_tgt == p_tgt else np.nan,
            }  # fmt: skip
        for k in range(n):  # 2) stop / objetivo dentro de la vela
            p = pos[k]
            if not p or o[k][i] != o[k][i]:
                continue
            if lo[k][i] <= p["stop"]:
                close(k, i, min(o[k][i], p["stop"]) * (1 - legs[k].costs.slippage), "stop")
            elif p["target"] == p["target"] and h[k][i] >= p["target"]:
                close(k, i, p["target"], "target")
        for k in range(n):
            if c[k][i] == c[k][i]:
                last_c[k] = c[k][i]
        equity[i - i0] = mark()
        max_open = max(max_open, sum(p is not None for p in pos))
        if i + 1 < i1:  # 3) leer señales al cierre para ejecutarlas en la siguiente vela
            for k in range(n):
                if sig[k][i] != 0:
                    pending[k] = (int(sig[k][i]), stp[k][i], tgt[k][i])

    for k in range(n):  # cierre forzado al final de los datos
        if pos[k]:
            close(k, i1 - 1, last_c[k] * (1 - legs[k].costs.slippage), "end")
    equity[-1] = cash

    eq = pd.Series(equity, index=idx[i0:i1], name="equity")
    tr = pd.DataFrame(trades, columns=TRADE_COLUMNS)
    return PortfolioResult(
        float(initial_cash),
        eq,
        tr,
        skipped,
        rejected,
        max_open,
        portfolio_metrics(eq, tr, initial_cash),
    )


def portfolio_metrics(eq: pd.Series, trades: pd.DataFrame, initial_cash: float) -> dict:
    gains = trades.loc[trades.pnl > 0, "pnl"].sum() if len(trades) else 0.0
    losses = -trades.loc[trades.pnl < 0, "pnl"].sum() if len(trades) else 0.0
    years = max((eq.index[-1] - eq.index[0]).total_seconds() / (365.25 * 86400), 1e-9)
    final = float(eq.iloc[-1])
    return {
        "start": str(eq.index[0]), "end": str(eq.index[-1]),
        "final_equity": final,
        "total_return": final / initial_cash - 1,
        "cagr": (final / initial_cash) ** (1 / years) - 1 if final > 0 else -1.0,
        "max_drawdown": float((eq / eq.cummax() - 1).min()),
        "trades": int(len(trades)),
        "win_rate": float((trades.pnl > 0).mean()) if len(trades) else 0.0,
        "profit_factor": float(gains / losses) if losses else float("inf"),
        "trades_per_month": len(trades) / (years * 12),
    }  # fmt: skip
