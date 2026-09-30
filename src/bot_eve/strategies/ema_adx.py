"""Dos EMA con filtro ADX (candidata, tomada de tecnicasdetrading.com).

Fuente: "Sistema de trading Dos EMA y ADX" (H1). Reglas de la fuente: EMA 5 calculada al
cierre cruza la EMA 6 calculada a la apertura, con ADX(14) sobre 20; filtro conservador
opcional EMA 55 sobre EMA 89. La fuente no define stop, objetivo ni salida: aquí se sale
por el cruce contrario y hay un stop opcional.
"""

from __future__ import annotations

import pandas as pd

from bot_eve.strategies import indicators as ind
from bot_eve.strategies.base import Strategy, build_signals
from bot_eve.strategies.registry import register


@register
class EmaAdx(Strategy):
    name = "ema_adx"
    description = "Candidata: cruce EMA(cierre) / EMA(apertura) confirmado por ADX."
    default_grid = {"adx_min": [20, 30], "trend_filter": [False, True]}

    def __init__(
        self,
        fast: int = 5,
        slow: int = 6,
        adx_len: int = 14,
        adx_min: float = 20,
        trend_filter: bool = False,
        min_diff_pct: float = 0.0,
        stop_pct: float | None = None,
    ) -> None:
        self.fast, self.slow, self.adx_len = int(fast), int(slow), int(adx_len)
        self.adx_min, self.trend_filter = adx_min, bool(trend_filter)
        self.min_diff_pct, self.stop_pct = min_diff_pct, stop_pct
        self.warmup = max(89 * 2, self.adx_len * 3)

    @property
    def params(self) -> dict:
        return {
            "fast": self.fast,
            "slow": self.slow,
            "adx_len": self.adx_len,
            "adx_min": self.adx_min,
            "trend_filter": self.trend_filter,
            "min_diff_pct": self.min_diff_pct,
            "stop_pct": self.stop_pct,
        }

    def generate(self, df: pd.DataFrame) -> pd.DataFrame:
        fast = ind.ema(df["close"], self.fast)
        slow = ind.ema(df["open"], self.slow)
        strong = ind.adx(df, self.adx_len) > self.adx_min
        buy = ind.cross_up(fast, slow) & strong & ((fast - slow) / df["close"] >= self.min_diff_pct)
        if self.trend_filter:
            buy &= ind.ema(df["close"], 55) > ind.ema(df["close"], 89)
        sell = ind.cross_down(fast, slow)
        return build_signals(df.index, buy, sell, stop_pct=self.stop_pct)
