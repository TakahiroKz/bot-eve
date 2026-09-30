"""Breakout de canal (Donchian) con stop y objetivo según la volatilidad (ATR)."""

from __future__ import annotations

import pandas as pd

from bot_eve.strategies import indicators as ind
from bot_eve.strategies.base import Strategy, build_signals
from bot_eve.strategies.registry import register


@register
class AtrBreakout(Strategy):
    """Seguimiento de tendencia por ruptura.

    - Compra: el cierre supera el máximo de las `entry_len` velas anteriores y la
      volatilidad (ATR/precio) es al menos `min_atr_pct`.
    - Venta: el cierre pierde el mínimo de las `exit_len` velas anteriores.
    - Stop: `stop_atr` * ATR bajo la entrada; objetivo opcional `target_atr` * ATR.
    """

    name = "atr_breakout"
    description = "Seguimiento de tendencia: ruptura de máximos con stop basado en ATR."
    default_grid = {"entry_len": [20, 40, 80], "exit_len": [10, 20], "stop_atr": [2.0, 3.0]}

    def __init__(
        self,
        entry_len: int = 20,
        exit_len: int = 10,
        atr_len: int = 14,
        stop_atr: float | None = 2.0,
        target_atr: float | None = None,
        min_atr_pct: float = 0.0,
    ) -> None:
        if exit_len > entry_len:
            raise ValueError("exit_len no debe superar entry_len")
        self.entry_len, self.exit_len, self.atr_len = int(entry_len), int(exit_len), int(atr_len)
        self.stop_atr, self.target_atr, self.min_atr_pct = stop_atr, target_atr, min_atr_pct
        self.warmup = max(self.entry_len, self.atr_len) * 2

    @property
    def params(self) -> dict:
        return {
            "entry_len": self.entry_len,
            "exit_len": self.exit_len,
            "atr_len": self.atr_len,
            "stop_atr": self.stop_atr,
            "target_atr": self.target_atr,
            "min_atr_pct": self.min_atr_pct,
        }

    def generate(self, df: pd.DataFrame) -> pd.DataFrame:
        close = df["close"]
        upper = df["high"].rolling(self.entry_len).max().shift(1)  # solo velas anteriores
        lower = df["low"].rolling(self.exit_len).min().shift(1)
        atr_pct = ind.atr(df, self.atr_len) / close
        buy = (close > upper) & (atr_pct >= self.min_atr_pct)
        sell = close < lower
        stop = atr_pct * self.stop_atr if self.stop_atr else None
        target = atr_pct * self.target_atr if self.target_atr else None
        return build_signals(df.index, buy, sell, stop, target)
