"""Señales multi-timeframe de scalping (15m contexto / 5m confirmación / 1m gatillo) e intradía (1h / 15m / 5m).

Todo el contexto usa solo velas CERRADAS en el momento de decidir (`align_htf`). Cada función devuelve
`(side, dist)`: `side[t]` ∈ {-1, 0, 1} decidido al cierre de la vela `t` y `dist[t]` = distancia al stop en unidades de
precio, detrás del último micro-extremo (con un pequeño colchón y un mínimo). Definiciones en docs/SCALPING_RESEARCH.md.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from bot_eve.strategies.indicators import adx, atr, ema, rsi, sma
from bot_eve.strategies.scalp_signals import align_htf


def _al(s: pd.Series, index: pd.DatetimeIndex, ltf: str, htf: str) -> np.ndarray:
    return align_htf(s.astype(float), index, ltf, htf).to_numpy() > 0


def _micro_stop(df: pd.DataFrame, n: int, a: pd.Series) -> tuple[np.ndarray, np.ndarray]:
    """Distancia al stop detrás del mínimo/máximo de las últimas `n` velas (incluida la del gatillo)."""
    c = df["close"]
    lo_d = (c - df["low"].rolling(n).min()) + 0.1 * a
    hi_d = (df["high"].rolling(n).max() - c) + 0.1 * a
    floor = 0.5 * a
    return np.maximum(lo_d, floor).to_numpy(), np.maximum(hi_d, floor).to_numpy()


def _candles(df: pd.DataFrame) -> dict[str, pd.Series]:
    o, h, lo, c = df["open"], df["high"], df["low"], df["close"]
    body, rng = (c - o).abs(), (h - lo)
    up_w, lo_w = h - np.maximum(o, c), np.minimum(o, c) - lo
    po, pc = o.shift(1), c.shift(1)
    return {
        "bear_rej": ((up_w >= 2 * body) & (c <= lo + rng / 3) & (rng > 0))
        | ((c < o) & (pc > po) & (o >= pc) & (c <= po)),
        "bull_rej": ((lo_w >= 2 * body) & (c >= h - rng / 3) & (rng > 0))
        | ((c > o) & (pc < po) & (o <= pc) & (c >= po)),
    }  # fmt: skip


def scalp_signal(which: str, d1: pd.DataFrame, d5: pd.DataFrame, d15: pd.DataFrame):
    """`which` ∈ {"S1" reversión (rango 15m), "S2" impulso EMA 9/20 (tendencia 15m), "S3" ruptura de micro-caja}."""
    idx = d1.index
    c1, o1, h1, l1, v1 = d1["close"], d1["open"], d1["high"], d1["low"], d1["volume"]
    a1 = atr(d1, 14)
    dist_up, dist_dn = _micro_stop(
        d1, 5, a1
    )  # dist_up: stop de un largo; dist_dn: stop de un corto
    if which == "S3":
        box_hi, box_lo = h1.shift(1).rolling(6).max(), l1.shift(1).rolling(6).min()
        narrow = (box_hi - box_lo) <= 2 * a1.shift(1)
        vol = v1 > 2 * v1.shift(1).rolling(6).mean()
        long_, short_ = (
            ((c1 > box_hi) & vol & narrow).to_numpy(),
            ((c1 < box_lo) & vol & narrow).to_numpy(),
        )
    else:
        e9, e20, ad = ema(d15["close"], 9), ema(d15["close"], 20), adx(d15, 14)
        if which == "S1":
            rng = _al(ad < 20, idx, "1m", "15m")
            c5 = d5["close"]
            m, sd = sma(c5, 20), c5.rolling(20).std()
            hi_t = _al((d5["high"] >= m + 2 * sd).rolling(3).max(), idx, "1m", "5m")
            lo_t = _al((d5["low"] <= m - 2 * sd).rolling(3).max(), idx, "1m", "5m")
            r = rsi(c1, 14)
            ob, os_ = (r.rolling(2).max() > 70).to_numpy(), (r.rolling(2).min() < 30).to_numpy()
            cd = _candles(d1)
            short_ = rng & hi_t & ob & cd["bear_rej"].to_numpy()
            long_ = rng & lo_t & os_ & cd["bull_rej"].to_numpy()
        else:  # S2
            up15 = _al((e9 > e20) & (e20 > e20.shift(3)) & (ad >= 20), idx, "1m", "15m")
            dn15 = _al((e9 < e20) & (e20 < e20.shift(3)) & (ad >= 20), idx, "1m", "15m")
            x9, x20 = ema(d5["close"], 9), ema(d5["close"], 20)
            pb_up = _al(
                ((d5["low"] <= x9) & (d5["close"] >= x20)).rolling(3).max(), idx, "1m", "5m"
            )
            pb_dn = _al(
                ((d5["high"] >= x9) & (d5["close"] <= x20)).rolling(3).max(), idx, "1m", "5m"
            )
            long_ = up15 & pb_up & (c1 > o1).to_numpy() & (c1 > h1.shift(1)).to_numpy()
            short_ = dn15 & pb_dn & (c1 < o1).to_numpy() & (c1 < l1.shift(1)).to_numpy()
    side = np.where(long_, 1, np.where(short_, -1, 0)).astype(np.int8)
    dist = np.where(side == 1, dist_up, dist_dn)
    side[~np.isfinite(dist)] = 0
    return side, dist


def intraday_signal(
    setup: str, d5: pd.DataFrame, d15: pd.DataFrame, d1h: pd.DataFrame, session_end_min: int = 1440
):
    """Intradía 1h/15m/5m. `setup` ∈ {"I1" barrido y rechazo de máx/mín del día previo, "I2" continuación de tendencia 1h}.

    Devuelve `(side, dist, nxt, hold)`: `nxt[t]` = distancia al siguiente nivel clave en la dirección de la operación
    (inf si no hay) para exigir R/B >= 2; `hold[t]` = velas de 5m hasta el fin de la sesión (UTC, en minutos del día).
    """
    idx = d5.index
    c5, o5, h5, l5, v5 = d5["close"], d5["open"], d5["high"], d5["low"], d5["volume"]
    a5 = atr(d5, 14)
    day = d1h.index.normalize()
    daily_hi, daily_lo = d1h["high"].groupby(day).max(), d1h["low"].groupby(day).min()
    pdh = (
        daily_hi.shift(1).reindex(idx.normalize()).to_numpy()
    )  # máximo/mínimo del día previo (ya cerrado)
    pdl = daily_lo.shift(1).reindex(idx.normalize()).to_numpy()
    c15 = d15["close"]
    p15h = daily_hi.shift(1).reindex(d15.index.normalize()).to_numpy()
    p15l = daily_lo.shift(1).reindex(d15.index.normalize()).to_numpy()
    cd15 = _candles(d15)
    if setup == "I1":
        s_short = pd.Series(
            (d15["high"].to_numpy() > p15h) & (c15.to_numpy() < p15h) & cd15["bear_rej"].to_numpy(),
            index=d15.index,
        )
        s_long = pd.Series(
            (d15["low"].to_numpy() < p15l) & (c15.to_numpy() > p15l) & cd15["bull_rej"].to_numpy(),
            index=d15.index,
        )
    else:
        e20 = ema(c15, 20)
        t_up = ema(d1h["close"], 20) > ema(d1h["close"], 50)
        t_dn = ema(d1h["close"], 20) < ema(d1h["close"], 50)
        t_up15, t_dn15 = (
            align_htf(t_up.astype(float), d15.index, "15m", "1h") > 0,
            align_htf(t_dn.astype(float), d15.index, "15m", "1h") > 0,
        )
        s_long = (c15 > e20) & (c15.shift(1) < e20.shift(1)) & t_up15
        s_short = (c15 < e20) & (c15.shift(1) > e20.shift(1)) & t_dn15
    act_l = _al(s_long.astype(float).rolling(3).max(), idx, "5m", "15m")
    act_s = _al(s_short.astype(float).rolling(3).max(), idx, "5m", "15m")
    prev3_hi, prev3_lo = h5.shift(1).rolling(3).max(), l5.shift(1).rolling(3).min()
    volx = v5 > 1.5 * v5.rolling(20).mean()
    cd5 = _candles(d5)
    trig_l = (cd5["bull_rej"] & (c5 > o5)) | ((c5 > prev3_hi) & volx)
    trig_s = (cd5["bear_rej"] & (c5 < o5)) | ((c5 < prev3_lo) & volx)
    side = np.where(
        act_l & trig_l.to_numpy(), 1, np.where(act_s & trig_s.to_numpy(), -1, 0)
    ).astype(np.int8)
    dist_up, dist_dn = _micro_stop(d5, 6, a5)
    dist = np.where(side == 1, dist_up, dist_dn)
    cv = c5.to_numpy()
    nxt = np.where(
        side == 1, np.where(pdh > cv, pdh - cv, np.inf), np.where(pdl < cv, cv - pdl, np.inf)
    )
    minute = (idx.hour * 60 + idx.minute).to_numpy()
    hold = np.maximum((session_end_min - (minute + 5)) // 5, 0)
    side[~np.isfinite(dist)] = 0
    return side, dist, nxt, hold
