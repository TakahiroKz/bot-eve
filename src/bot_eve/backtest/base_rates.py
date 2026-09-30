"""Tasas base de entradas al azar con barreras en ATR y costo medido en R.

Pregunta que responde: «si entro en TODAS las velas con stop = sl_atr×ATR y objetivo = tp_atr×ATR,
¿qué acierto mínimo necesita un modelo para cubrir los costos del instrumento?»

- La entrada es la apertura de la vela siguiente; el ATR es el de la vela ya cerrada (sin mirar el futuro).
- Si stop y objetivo caen en la misma vela, se cuenta como **pérdida** (conservador).
- R = distancia al stop. El costo en R = costo de ida y vuelta (fracción del precio) / distancia al stop.
- Se descartan entradas cuya ventana, contando el paso de la señal a la entrada, cruza un hueco de datos
  (fines de semana, mantenimiento).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

from bot_eve.data.intervals import to_timedelta
from bot_eve.strategies import indicators as ind

DEFAULT_HORIZON = {"1m": 60, "5m": 48, "15m": 32, "1h": 24, "4h": 18}
_CHUNK = 200_000


def pip_size(symbol: str) -> float:
    """Tamaño del pip de un par de divisas (0.01 si incluye JPY, si no 0.0001)."""
    return 0.01 if "JPY" in symbol.upper() else 0.0001


@dataclass(frozen=True)
class Barriers:
    tp_atr: float = 1.8
    sl_atr: float = 1.2

    @property
    def rr(self) -> float:
        return self.tp_atr / self.sl_atr

    @property
    def random_win(self) -> float:
        """Probabilidad de tocar el objetivo antes que el stop en un paseo sin deriva."""
        return self.sl_atr / (self.tp_atr + self.sl_atr)


def outcomes(
    df: pd.DataFrame,
    interval: str,
    barriers: Barriers = Barriers(),  # noqa: B008
    horizon: int | None = None,
    atr_len: int = 14,
    step: int = 1,
) -> pd.DataFrame:
    """Resultado de entrar en cada vela. Columnas: outcome, r_gross, stop_pct (indexado por vela de señal)."""
    horizon = horizon or DEFAULT_HORIZON.get(interval, 48)
    atr = ind.atr(df, atr_len).to_numpy()
    o, h, low, c = (df[k].to_numpy(dtype=float) for k in ("open", "high", "low", "close"))
    times = df.index.to_numpy()
    n = len(df) - horizon - 2
    if n <= 0:
        raise ValueError("Muy pocas velas para el horizonte pedido")
    idx = np.arange(atr_len, n, step)
    idx = idx[np.isfinite(atr[idx])]
    # Sin cruzar huecos (fin de semana, mantenimiento): desde la vela de señal hasta el final de la ventana
    # debe haber transcurrido ~lo esperado. Así tampoco se entra en la apertura posterior a un hueco.
    span = (times[idx + horizon] - times[idx]) / np.timedelta64(1, "s")
    expected = horizon * to_timedelta(interval).total_seconds()
    idx = idx[span <= expected * 1.5]

    opens = o[1:]
    hi_w = sliding_window_view(h[1:], horizon)
    lo_w = sliding_window_view(low[1:], horizon)
    cl_w = sliding_window_view(c[1:], horizon)
    res = np.empty(len(idx), dtype="<U7")
    r_gross = np.empty(len(idx))
    stop_pct = np.empty(len(idx))
    for a in range(0, len(idx), _CHUNK):
        ii = idx[a : a + _CHUNK]
        entry, dist = opens[ii], atr[ii]
        tp_lvl, sl_lvl = entry + barriers.tp_atr * dist, entry - barriers.sl_atr * dist
        hit_tp = hi_w[ii] >= tp_lvl[:, None]
        hit_sl = lo_w[ii] <= sl_lvl[:, None]
        first_tp = np.where(hit_tp.any(1), hit_tp.argmax(1), horizon + 1)
        first_sl = np.where(hit_sl.any(1), hit_sl.argmax(1), horizon + 1)
        win, loss = first_tp < first_sl, first_sl <= first_tp
        loss &= hit_sl.any(1)
        timeout = ~(win | loss)
        risk = barriers.sl_atr * dist
        r_timeout = (cl_w[ii][:, -1] - entry) / risk
        r_gross[a : a + _CHUNK] = np.where(win, barriers.rr, np.where(loss, -1.0, r_timeout))
        res[a : a + _CHUNK] = np.where(win, "tp", np.where(loss, "sl", "timeout"))
        stop_pct[a : a + _CHUNK] = risk / entry
        del timeout
    return pd.DataFrame(
        {"outcome": res, "r_gross": r_gross, "stop_pct": stop_pct}, index=df.index[idx]
    )


def summarize(out: pd.DataFrame, cost_frac: float, barriers: Barriers = Barriers()) -> dict:  # noqa: B008
    """Resumen con un costo de ida y vuelta `cost_frac` (fracción del precio, p. ej. 0.0002)."""
    cost_r = cost_frac / out["stop_pct"]
    net_r = out["r_gross"] - cost_r
    p_tp = float((out["outcome"] == "tp").mean())
    mean_cost_r = float(cost_r.mean())
    win_needed = (1 + mean_cost_r) / (1 + barriers.rr)
    return {
        "n": len(out),
        "p_tp": p_tp,
        "p_sl": float((out["outcome"] == "sl").mean()),
        "p_timeout": float((out["outcome"] == "timeout").mean()),
        "stop_pct_median": float(out["stop_pct"].median()),
        "gross_R": float(out["r_gross"].mean()),
        "cost_R": mean_cost_r,
        "net_R": float(net_r.mean()),
        "win_needed": win_needed,
        "lift_pts": (win_needed - p_tp) * 100,
    }


def by_hour_block(out: pd.DataFrame, cost_frac: float, block: int = 4) -> pd.DataFrame:
    """Costo en R y esperanza neta por bloque de horas del día (hora del broker)."""
    blk = (out.index.hour // block) * block
    cost_r = cost_frac / out["stop_pct"]
    frame = pd.DataFrame(
        {"stop_pct": out["stop_pct"], "cost_R": cost_r, "net_R": out["r_gross"] - cost_r},
        index=out.index,
    )
    grouped = frame.groupby(blk)
    table = pd.DataFrame(
        {
            "n": grouped.size(),
            "stop_pct_mediano": grouped["stop_pct"].median(),
            "costo_R_mediano": grouped["cost_R"].median(),
            "esperanza_neta_R": grouped["net_R"].mean(),
        }
    )
    table.index = [f"{h:02d}-{h + block:02d}h" for h in table.index]
    return table


def cost_fraction(
    costs, spread_pips: float | None = None, symbol: str = "", price: float = 1.0
) -> float:
    """Costo de ida y vuelta como fracción del precio según el modelo de costos (o un spread en pips)."""
    if spread_pips is not None:
        spread = spread_pips * pip_size(symbol) / price
    else:
        spread = costs.spread_pct
    return spread + costs.entry_fee + costs.exit_fee + 2 * costs.slippage
