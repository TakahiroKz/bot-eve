"""RSI con filtro de tendencia: comprar el rebote tras una sobreventa dentro de una tendencia alcista."""

from __future__ import annotations

import pandas as pd

from bot_eve.strategies import indicators as ind
from bot_eve.strategies.base import Strategy, build_signals
from bot_eve.strategies.registry import register


@register
class RsiTrend(Strategy):
    """Reversión a la media dentro de una tendencia alcista.

    - Tendencia alcista: cierre por encima de la EMA(`trend_len`).
    - Compra: el RSI cruza hacia arriba `buy_level` (sale de la sobreventa).
    - Venta: el RSI cruza hacia arriba `exit_level`.
    - Stop: `stop_atr` * ATR bajo la entrada; objetivo opcional `target_atr` * ATR.
    """

    name = "rsi_trend"
    description = "Reversión a la media: rebote del RSI en sobreventa con tendencia alcista."
    default_grid = {"buy_level": [25, 30, 35], "exit_level": [55, 65], "stop_atr": [1.5, 2.5]}

    def __init__(
        self,
        rsi_len: int = 14,
        buy_level: float = 30,
        exit_level: float = 60,
        trend_len: int = 200,
        atr_len: int = 14,
        stop_atr: float | None = 2.0,
        target_atr: float | None = None,
    ) -> None:
        if not 0 < buy_level < exit_level < 100:
            raise ValueError("Se requiere 0 < buy_level < exit_level < 100")
        self.rsi_len, self.buy_level, self.exit_level = int(rsi_len), buy_level, exit_level
        self.trend_len, self.atr_len = int(trend_len), int(atr_len)
        self.stop_atr, self.target_atr = stop_atr, target_atr
        self.warmup = max(self.trend_len, self.rsi_len, self.atr_len) * 2

    @property
    def params(self) -> dict:
        return {
            "rsi_len": self.rsi_len,
            "buy_level": self.buy_level,
            "exit_level": self.exit_level,
            "trend_len": self.trend_len,
            "atr_len": self.atr_len,
            "stop_atr": self.stop_atr,
            "target_atr": self.target_atr,
        }

    def generate(self, df: pd.DataFrame) -> pd.DataFrame:
        close = df["close"]
        rsi = ind.rsi(close, self.rsi_len)
        uptrend = close > ind.ema(close, self.trend_len)
        buy = ind.cross_up(rsi, self.buy_level) & uptrend
        sell = ind.cross_up(rsi, self.exit_level)
        atr_pct = ind.atr(df, self.atr_len) / close
        stop = atr_pct * self.stop_atr if self.stop_atr else None
        target = atr_pct * self.target_atr if self.target_atr else None
        return build_signals(df.index, buy, sell, stop, target)
