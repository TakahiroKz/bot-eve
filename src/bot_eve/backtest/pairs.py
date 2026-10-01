"""Arbitraje estadístico de un par (largo uno / corto otro) con spread z-score. Una posición a la vez.

spread = ln(P1) − β·ln(P2), β por regresión móvil. La decisión se toma con la vela cerrada `t` y se ejecuta en la
apertura de `t+1` en ambas patas. Pesos de las patas 1/(1+|β|) y |β|/(1+|β|), así que el nocional bruto es 1 y el costo
total de ida y vuelta es 2·(comisión + slippage).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from bot_eve.backtest.scalp import ScalpCosts

_DEFAULT = ScalpCosts()


def spread_z(p1: pd.Series, p2: pd.Series, beta_win: int = 500, z_win: int = 200):
    l1, l2 = np.log(p1), np.log(p2)
    beta = l1.rolling(beta_win).cov(l2) / l2.rolling(beta_win).var()
    spread = l1 - beta * l2
    z = (spread - spread.rolling(z_win).mean()) / spread.rolling(z_win).std()
    return z, beta


def simulate_pairs(
    o1: np.ndarray, o2: np.ndarray, z: np.ndarray, beta: np.ndarray, index: pd.DatetimeIndex,
    entry_z: float = 2.5, exit_z: float = 0.0, stop_z: float = 4.5, max_hold: int = 96,
    costs: ScalpCosts = _DEFAULT, start=None, end=None,
) -> pd.DataFrame:  # fmt: skip
    n = len(z)
    i0 = 0 if start is None else int(index.searchsorted(start, "left"))
    i1 = n if end is None else int(index.searchsorted(end, "right"))
    rows, pos, e, side, w1, w2 = [], 0, 0, 0, 0.0, 0.0
    pending, pending_side, pending_reason = 0, 0, ""
    for i in range(i0, i1):
        # 1) ejecutar lo decidido al cierre de la vela anterior, en la apertura de esta
        if pending == 2 and pos:  # salida
            r1, r2 = np.log(o1[i] / o1[e]), np.log(o2[i] / o2[e])
            ret = side * (w1 * r1 - w2 * r2) - 2 * (costs.fee + costs.slip)
            rows.append((index[e], index[i], side, ret, pending_reason))
            pos = 0
        elif pending == 1 and not pos and np.isfinite(beta[i - 1]) and beta[i - 1] > 0:
            b = beta[i - 1]
            w1, w2, e, side, pos = 1 / (1 + b), b / (1 + b), i, pending_side, 1
        pending = 0
        # 2) decidir con la vela i cerrada
        if not np.isfinite(z[i]):
            continue
        if pos:
            if (side == 1 and z[i] >= -exit_z) or (side == -1 and z[i] <= exit_z):
                pending, pending_reason = 2, "revert"
            elif abs(z[i]) >= stop_z:
                pending, pending_reason = 2, "stop"
            elif i - e >= max_hold:
                pending, pending_reason = 2, "time"
        elif abs(z[i]) >= entry_z and abs(z[i]) < stop_z and i + 1 < i1:
            pending, pending_side = 1, (1 if z[i] < 0 else -1)  # z bajo: largo el spread
    return pd.DataFrame(rows, columns=["entry_time", "exit_time", "side", "ret", "reason"])
