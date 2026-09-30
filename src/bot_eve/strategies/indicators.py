"""Indicadores técnicos causales: el valor en `t` solo usa datos hasta `t` inclusive.

Los suavizados de Wilder usan `ewm(alpha=1/n, adjust=False)`, que es recursivo hacia
adelante, así que recortar el futuro nunca cambia valores pasados.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n).mean()


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False, min_periods=n).mean()


def _wilder(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    delta = close.diff()
    avg_up = _wilder(delta.clip(lower=0), n)
    avg_down = _wilder(-delta.clip(upper=0), n)
    value = 100 - 100 / (1 + avg_up / avg_down)
    value = value.where(avg_down != 0, 100.0)  # sin pérdidas -> 100
    value = value.where((avg_down != 0) | (avg_up != 0), 50.0)  # precio constante -> neutro
    return value.where(avg_up.notna() & avg_down.notna())


def true_range(df: pd.DataFrame) -> pd.Series:
    prev_close = df["close"].shift(1)
    ranges = pd.concat(
        [df["high"] - df["low"], (df["high"] - prev_close).abs(), (df["low"] - prev_close).abs()],
        axis=1,
    )
    return ranges.max(axis=1, skipna=False)


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    return _wilder(true_range(df), n)


def bollinger(close: pd.Series, n: int = 20, k: float = 2.0):
    """Devuelve (media, banda superior, banda inferior) con desviación poblacional."""
    mid = close.rolling(n).mean()
    std = close.rolling(n).std(ddof=0)
    return mid, mid + k * std, mid - k * std


def adx(df: pd.DataFrame, n: int = 14) -> pd.Series:
    """ADX de Wilder."""
    up = df["high"].diff()
    down = -df["low"].diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=df.index)
    valid = up.notna()
    plus_dm, minus_dm = plus_dm.where(valid), minus_dm.where(valid)
    atr_w = _wilder(true_range(df), n)
    plus_di = 100 * _wilder(plus_dm, n) / atr_w
    minus_di = 100 * _wilder(minus_dm, n) / atr_w
    total = plus_di + minus_di
    dx = 100 * (plus_di - minus_di).abs() / total.where(total != 0)
    return _wilder(dx, n)


def cross_up(a: pd.Series, b: pd.Series | float) -> pd.Series:
    """True en la vela donde `a` pasa de <= `b` a > `b`."""
    b_prev = b.shift(1) if isinstance(b, pd.Series) else b
    return (a > b) & (a.shift(1) <= b_prev)


def cross_down(a: pd.Series, b: pd.Series | float) -> pd.Series:
    """True en la vela donde `a` pasa de >= `b` a < `b`."""
    b_prev = b.shift(1) if isinstance(b, pd.Series) else b
    return (a < b) & (a.shift(1) >= b_prev)
