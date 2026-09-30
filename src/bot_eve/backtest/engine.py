"""Motor de backtest vela a vela para spot long-only.

Reglas de ejecución (todas conservadoras y sin look-ahead):

- La señal se calcula con la vela **cerrada** `t` y se ejecuta en la **apertura de `t+1`**.
- Compras y ventas de mercado pagan slippage adverso y comisión por lado.
- Stop-loss y objetivo se evalúan con el high/low de cada vela, incluida la de entrada.
  Si una misma vela toca ambos, se asume que el **stop se ejecutó primero**.
  Si la vela abre más allá del stop (gap), se ejecuta en la apertura (peor precio).
  El objetivo es una orden límite: se ejecuta en su precio, sin slippage.
- Se respetan los filtros del par: cantidad redondeada al paso y mínimos de cantidad y notional.
  Las entradas que no los cumplen se rechazan y se cuentan.
- Al final de los datos, cualquier posición abierta se cierra al último cierre.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from bot_eve.backtest.costs import Costs, SymbolRules
from bot_eve.strategies.base import BUY, SELL, SIGNAL_COLUMNS, Strategy

TRADE_COLUMNS = [
    "entry_time", "exit_time", "entry_price", "exit_price", "qty",
    "fees", "pnl", "return_pct", "exit_reason",
]  # fmt: skip


@dataclass
class BacktestResult:
    strategy: str
    params: dict
    initial_cash: float
    equity: pd.Series
    benchmark: pd.Series
    trades: pd.DataFrame
    rejected_entries: int
    in_position: np.ndarray = field(repr=False)
    metrics: dict = field(default_factory=dict)


def run_backtest(
    df: pd.DataFrame,
    strategy: Strategy,
    costs: Costs = Costs(),  # noqa: B008
    rules: SymbolRules = SymbolRules(),  # noqa: B008
    initial_cash: float = 1000.0,
    size_fraction: float = 1.0,
    start: str | pd.Timestamp | None = None,
    end: str | pd.Timestamp | None = None,
) -> BacktestResult:
    """Simula `strategy` sobre `df`.

    Las señales se calculan con todo `df` (para tener historia de calentamiento), pero solo
    se opera dentro de [start, end]. Así un tramo de prueba puede usar velas previas para
    sus indicadores sin operar en ellas.
    """
    from bot_eve.backtest.metrics import compute_metrics  # evita import circular

    if not 0 < size_fraction <= 1:
        raise ValueError("size_fraction debe estar en (0, 1]")
    if df.empty:
        raise ValueError("No hay velas para simular")

    signals = strategy.generate(df).reindex(df.index)
    _check_signals(signals)

    idx = df.index
    i0 = 0 if start is None else int(idx.searchsorted(_utc(start), "left"))
    i1 = len(idx) if end is None else int(idx.searchsorted(_utc(end), "right"))
    if i1 - i0 < 2:
        raise ValueError("El rango a simular tiene menos de 2 velas")

    o, h, lo, c = (df[k].to_numpy(dtype=float) for k in ("open", "high", "low", "close"))
    sig = signals["signal"].fillna(0).to_numpy(dtype=np.int8)
    stop_arr = signals["stop_pct"].to_numpy(dtype=float)
    target_arr = signals["target_pct"].to_numpy(dtype=float)
    fee, slip = costs.fee_rate, costs.slippage

    cash = float(initial_cash)
    qty = entry_px = entry_cost = 0.0
    entry_i = -1
    stop = target = np.nan
    pending, pending_stop, pending_target = 0, np.nan, np.nan
    rejected = 0
    equity = np.empty(i1 - i0)
    in_pos = np.zeros(i1 - i0, dtype=bool)
    trades: list[tuple] = []

    def close_position(i: int, price: float, reason: str) -> None:
        nonlocal cash, qty
        proceeds = qty * price
        exit_fee = proceeds * fee
        cash += proceeds - exit_fee
        total_fees = entry_cost_fee + exit_fee
        pnl = (proceeds - exit_fee) - entry_cost
        trades.append(
            (idx[entry_i], idx[i], entry_px, price, qty, total_fees, pnl,
             pnl / entry_cost, reason)
        )  # fmt: skip
        qty = 0.0

    entry_cost_fee = 0.0
    for i in range(i0, i1):
        # 1) Ejecutar la orden decidida al cierre de la vela anterior.
        if pending == BUY and qty == 0.0:
            px = o[i] * (1 + slip)
            q = rules.round_qty(cash * size_fraction / (px * (1 + fee)))
            if rules.is_valid(q, px):
                notional = q * px
                entry_cost_fee = notional * fee
                entry_cost = notional + entry_cost_fee
                cash -= entry_cost
                qty, entry_px, entry_i = q, px, i
                stop = px * (1 - pending_stop) if pending_stop == pending_stop else np.nan
                target = px * (1 + pending_target) if pending_target == pending_target else np.nan
            else:
                rejected += 1
        elif pending == SELL and qty > 0.0:
            close_position(i, o[i] * (1 - slip), "signal")
        pending = 0

        # 2) Stop / objetivo dentro de la vela.
        if qty > 0.0:
            if stop == stop and lo[i] <= stop:
                close_position(i, min(o[i], stop) * (1 - slip), "stop")
            elif target == target and h[i] >= target:
                close_position(i, target, "target")

        equity[i - i0] = cash + qty * c[i]
        in_pos[i - i0] = qty > 0.0

        # 3) Leer la señal al cierre de esta vela para ejecutarla en la siguiente.
        if i + 1 < i1 and sig[i] != 0:
            pending = int(sig[i])
            pending_stop, pending_target = stop_arr[i], target_arr[i]

    if qty > 0.0:  # cierre forzado al final de los datos
        close_position(i1 - 1, c[i1 - 1] * (1 - slip), "end")
        equity[-1] = cash

    index = idx[i0:i1]
    eq = pd.Series(equity, index=index, name="equity")
    bench = buy_and_hold(o[i0], c[i0:i1], initial_cash, costs, index)
    trade_df = pd.DataFrame(trades, columns=TRADE_COLUMNS)
    result = BacktestResult(
        strategy=strategy.name,
        params=strategy.params,
        initial_cash=float(initial_cash),
        equity=eq,
        benchmark=bench,
        trades=trade_df,
        rejected_entries=rejected,
        in_position=in_pos,
    )
    result.metrics = compute_metrics(result)
    return result


def _utc(ts: str | pd.Timestamp) -> pd.Timestamp:
    ts = pd.Timestamp(ts)
    return ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")


def buy_and_hold(
    first_open: float, closes: np.ndarray, cash: float, costs: Costs, index: pd.Index
) -> pd.Series:
    """Comprar al inicio (con slippage y comisión) y mantener; se valora al cierre."""
    units = cash / (first_open * (1 + costs.slippage) * (1 + costs.fee_rate))
    bench = units * closes
    bench[-1] *= 1 - costs.slippage - costs.fee_rate  # coste de salir al final
    return pd.Series(bench, index=index, name="buy_and_hold")


def _check_signals(signals: pd.DataFrame) -> None:
    missing = [c for c in SIGNAL_COLUMNS if c not in signals.columns]
    if missing:
        raise ValueError(f"La estrategia no devolvió las columnas: {missing}")
    bad = ~signals["signal"].fillna(0).isin([-1, 0, 1])
    if bad.any():
        raise ValueError("`signal` solo admite -1, 0 o 1")
