"""Cruce de medias móviles simples (estrategia de prueba para validar el motor)."""

from __future__ import annotations

import pandas as pd

from bot_eve.strategies.base import BUY, SELL, Strategy, empty_signals


class SmaCross(Strategy):
    name = "sma_cross"

    def __init__(
        self,
        fast: int = 10,
        slow: int = 30,
        stop_pct: float | None = None,
        target_pct: float | None = None,
    ) -> None:
        if fast >= slow:
            raise ValueError("fast debe ser menor que slow")
        self.fast, self.slow = int(fast), int(slow)
        self.stop_pct, self.target_pct = stop_pct, target_pct
        self.warmup = self.slow + 1

    @property
    def params(self) -> dict:
        return {
            "fast": self.fast,
            "slow": self.slow,
            "stop_pct": self.stop_pct,
            "target_pct": self.target_pct,
        }

    def generate(self, df: pd.DataFrame) -> pd.DataFrame:
        out = empty_signals(df.index)
        fast = df["close"].rolling(self.fast).mean()
        slow = df["close"].rolling(self.slow).mean()
        above = fast > slow
        prev_above = above.shift(1, fill_value=False)
        valid = slow.notna() & slow.shift(1).notna()
        cross_up = (above & ~prev_above & valid).to_numpy()
        cross_down = (~above & prev_above & valid).to_numpy()
        sig = out["signal"].to_numpy().copy()
        sig[cross_up] = BUY
        sig[cross_down] = SELL
        out["signal"] = sig
        if self.stop_pct:
            out.loc[cross_up, "stop_pct"] = self.stop_pct
        if self.target_pct:
            out.loc[cross_up, "target_pct"] = self.target_pct
        return out
