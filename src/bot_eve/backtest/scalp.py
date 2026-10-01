"""Simulador de scalping largo/corto, una posición a la vez, resultados en múltiplos de R.

Reglas (conservadoras, sin look-ahead): la señal se calcula con la vela cerrada `t` y se entra en la apertura de
`t+1` con slippage adverso; el stop se evalúa antes que el objetivo dentro de una misma vela; un gap más allá del
stop se ejecuta a la apertura; el objetivo es límite (sin slippage); si se agota `max_hold`, se sale al cierre.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class ScalpCosts:
    fee: float = 0.0004  # comisión por lado (fracción)
    slip: float = 0.0002  # slippage adverso por lado (fracción)


TRADE_COLUMNS = ["entry_time", "exit_time", "side", "r_net", "r_gross", "ret", "reason"]


def simulate(
    df: pd.DataFrame,
    side: np.ndarray,
    atr: np.ndarray,
    sl_mult: float,
    tp_mult: float,
    max_hold: int = 24,
    costs: ScalpCosts = ScalpCosts(),  # noqa: B008
    start: pd.Timestamp | None = None,
    end: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """`side[t]` en {-1, 0, 1} decidido al cierre de `t`; `atr[t]` en unidades de precio."""
    idx = df.index
    o, h, lo, c = (df[k].to_numpy(dtype=float) for k in ("open", "high", "low", "close"))
    n = len(df)
    i0 = 0 if start is None else int(idx.searchsorted(start, "left"))
    i1 = n if end is None else int(idx.searchsorted(end, "right"))
    cand = np.flatnonzero((side[i0:i1] != 0) & np.isfinite(atr[i0:i1])) + i0
    out: list[tuple] = []
    free = i0
    for i in cand:
        e = i + 1
        if e >= i1 or e < free:
            continue
        s = int(side[i])
        d = sl_mult * atr[i]
        if not d > 0:
            continue
        px = o[e] * (1 + s * costs.slip)
        stop, tp = px - s * d, px + s * tp_mult * atr[i]
        last = min(e + max_hold, i1)  # velas e .. last-1
        ol, hl, ll = o[e:last], h[e:last], lo[e:last]
        hit_stop = (ll <= stop) if s == 1 else (hl >= stop)
        hit_tp = (hl >= tp) if s == 1 else (ll <= tp)
        js = np.flatnonzero(hit_stop)
        jt = np.flatnonzero(hit_tp)
        j_stop = js[0] if len(js) else 1 << 60
        j_tp = jt[0] if len(jt) else 1 << 60
        if j_stop <= j_tp and j_stop < (1 << 60):  # el stop gana los empates
            j = e + j_stop
            raw = min(ol[j_stop], stop) if s == 1 else max(ol[j_stop], stop)
            xp, reason = raw * (1 - s * costs.slip), "stop"
        elif j_tp < (1 << 60):
            j, xp, reason = e + j_tp, tp, "target"
        else:
            j = last - 1
            xp, reason = c[j] * (1 - s * costs.slip), "time"
        gross = s * (xp - px) / px
        net = gross - 2 * costs.fee
        r_unit = d / px
        out.append((idx[e], idx[j], s, net / r_unit, gross / r_unit, net, reason))
        free = j + 1  # la siguiente entrada no puede ser antes de que cierre ésta
    return pd.DataFrame(out, columns=TRADE_COLUMNS)


def summarize(trades: pd.DataFrame, risk: float = 0.005) -> dict:
    if trades.empty:
        return {"trades": 0, "win_rate": 0.0, "exp_r": 0.0, "exp_r_gross": 0.0, "pf": 0.0, "cost_r": 0.0, "max_dd": 0.0, "ret": 0.0}  # fmt: skip
    r = trades["r_net"].to_numpy()
    g, ls = r[r > 0].sum(), -r[r < 0].sum()
    eq = np.cumprod(1 + risk * r)
    return {
        "trades": len(r),
        "win_rate": float((r > 0).mean()),
        "exp_r": float(r.mean()),
        "exp_r_gross": float(trades["r_gross"].mean()),
        "pf": float(g / ls) if ls > 0 else float("inf"),
        "cost_r": float((trades["r_gross"] - trades["r_net"]).mean()),
        "max_dd": float((eq / np.maximum.accumulate(eq) - 1).min()),
        "ret": float(eq[-1] - 1),
    }  # fmt: skip
