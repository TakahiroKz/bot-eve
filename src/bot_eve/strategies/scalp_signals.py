"""Señales de scalping largo/corto con contexto de marco superior (1h) sin look-ahead.

Cada función devuelve `(side, atr)` alineados al índice de `df`: `side[t]` ∈ {-1, 0, 1} se decide con la vela `t`
CERRADA y `atr[t]` está en unidades de precio. El contexto 1h solo usa velas de 1h ya cerradas en ese momento.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from bot_eve.data.intervals import to_timedelta
from bot_eve.strategies.indicators import adx, atr, ema, sma


def align_htf(
    htf: pd.Series, ltf_index: pd.DatetimeIndex, ltf: str, htf_name: str = "1h"
) -> pd.Series:
    """Valor del marco superior vigente al CIERRE de cada vela del marco de entrada.

    Una vela de 1h con apertura T solo es conocida desde T+1h, así que se re-indexa por su cierre y se toma la
    última conocida en el cierre de la vela `t` (apertura + duración del marco de entrada).
    """
    shifted = htf.copy()
    shifted.index = shifted.index + to_timedelta(htf_name)
    return shifted.reindex(ltf_index + to_timedelta(ltf), method="ffill").set_axis(ltf_index)


def pullback_momentum(
    df: pd.DataFrame, htf_df: pd.DataFrame, ltf: str
) -> tuple[np.ndarray, np.ndarray]:
    """A: tendencia 1h (EMA50 vs EMA200) + retorno por encima/debajo de la EMA20 con vela a favor."""
    trend = np.sign(ema(htf_df["close"], 50) - ema(htf_df["close"], 200))
    t = align_htf(trend, df.index, ltf).to_numpy()
    c, o = df["close"], df["open"]
    e20 = ema(c, 20)
    up = (c.shift(1) < e20.shift(1)) & (c > e20) & (c > o)
    dn = (c.shift(1) > e20.shift(1)) & (c < e20) & (c < o)
    side = np.where(up.to_numpy() & (t > 0), 1, np.where(dn.to_numpy() & (t < 0), -1, 0))
    return side.astype(np.int8), atr(df, 14).to_numpy()


def zscore_reversion(
    df: pd.DataFrame, htf_df: pd.DataFrame, ltf: str
) -> tuple[np.ndarray, np.ndarray]:
    """B: solo si el 1h está en rango (ADX < 20); largo si z < -2.5, corto si z > 2.5."""
    rng = align_htf((adx(htf_df, 14) < 20).astype(float), df.index, ltf).to_numpy() > 0
    c = df["close"]
    z = ((c - sma(c, 48)) / c.rolling(48).std()).to_numpy()
    side = np.where(rng & (z < -2.5), 1, np.where(rng & (z > 2.5), -1, 0))
    return side.astype(np.int8), atr(df, 14).to_numpy()


def random_entries(
    df: pd.DataFrame, seed: int = 7, prob: float = 0.01
) -> tuple[np.ndarray, np.ndarray]:
    """Línea base: lado aleatorio en ~1% de las velas. Mide el costo de operar sin información."""
    rng = np.random.default_rng(seed)
    fire = rng.random(len(df)) < prob
    side = np.where(fire, rng.choice([-1, 1], len(df)), 0)
    return side.astype(np.int8), atr(df, 14).to_numpy()
