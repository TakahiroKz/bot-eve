"""Reversión con Bandas de Bollinger (candidata, tomada de tecnicasdetrading.com).

Fuente: "Sistemas de scalping de bajo riesgo con Bandas de Bollinger".
Reglas de la fuente: el precio toca la banda exterior y la barra empieza a retroceder hacia
la línea central; stop como máximo la mitad de la amplitud de las bandas; objetivo del
5% al 10% de la amplitud. Aquí solo se opera el lado comprador (spot).
"""

from __future__ import annotations

import pandas as pd

from bot_eve.strategies import indicators as ind
from bot_eve.strategies.base import Strategy, build_signals
from bot_eve.strategies.registry import register


@register
class BollingerReversion(Strategy):
    """Compra cuando el cierre vuelve a entrar por la banda inferior.

    - Compra: el cierre anterior estaba bajo la banda inferior y el actual la recupera.
    - Stop: `stop_width_frac` * amplitud de las bandas bajo la entrada.
    - Objetivo: `target_width_frac` * amplitud sobre la entrada (0.5 ≈ banda central).
    - Venta: el cierre supera la banda superior.
    """

    name = "bollinger_reversion"
    description = "Candidata: reversión al entrar de nuevo por la banda inferior de Bollinger."
    default_grid = {
        "num_std": [2.0, 2.5],
        "stop_width_frac": [0.5, 1.0],
        "target_width_frac": [0.1, 0.5, 1.0],
    }

    def __init__(
        self,
        length: int = 20,
        num_std: float = 2.0,
        stop_width_frac: float = 0.5,
        target_width_frac: float = 0.5,
    ) -> None:
        self.length, self.num_std = int(length), num_std
        self.stop_width_frac, self.target_width_frac = stop_width_frac, target_width_frac
        self.warmup = self.length * 2

    @property
    def params(self) -> dict:
        return {
            "length": self.length,
            "num_std": self.num_std,
            "stop_width_frac": self.stop_width_frac,
            "target_width_frac": self.target_width_frac,
        }

    def generate(self, df: pd.DataFrame) -> pd.DataFrame:
        close = df["close"]
        _, upper, lower = ind.bollinger(close, self.length, self.num_std)
        buy = (close.shift(1) < lower.shift(1)) & (close >= lower)
        sell = close > upper
        width_pct = (upper - lower) / close
        return build_signals(
            df.index,
            buy,
            sell,
            stop_pct=width_pct * self.stop_width_frac,
            target_pct=width_pct * self.target_width_frac,
        )
