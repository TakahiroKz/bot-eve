"""Interfaz común de estrategias.

Una estrategia recibe velas y devuelve, para cada vela, la acción que decide **al cierre
de esa vela**. El motor la ejecuta en la apertura de la siguiente, así que la estrategia
nunca opera con un precio que ya conoce.

Regla de oro: la señal en la fila `t` solo puede depender de datos hasta `t` inclusive.
`check_no_lookahead` lo verifica de forma empírica.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np
import pandas as pd

BUY = 1
SELL = -1
HOLD = 0

SIGNAL_COLUMNS = ["signal", "stop_pct", "target_pct"]


class Strategy(ABC):
    """Estrategia long-only para spot."""

    name: str = "strategy"
    #: velas mínimas de historia que necesita antes de dar señales fiables
    warmup: int = 0

    @property
    def params(self) -> dict:
        return {}

    @abstractmethod
    def generate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Devuelve un DataFrame con el mismo índice que `df` y las columnas:

        - `signal`: BUY (1), SELL (-1) o HOLD (0).
        - `stop_pct`: distancia del stop-loss bajo el precio de entrada (p. ej. 0.01 = 1%);
          NaN si no hay. Solo se lee en filas BUY.
        - `target_pct`: distancia del objetivo sobre la entrada; NaN si no hay.
        """


def empty_signals(index: pd.Index) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "signal": np.zeros(len(index), dtype=np.int8),
            "stop_pct": np.nan,
            "target_pct": np.nan,
        },
        index=index,
    )


def check_no_lookahead(strategy: Strategy, df: pd.DataFrame, cuts: int = 8, seed: int = 0) -> None:
    """Falla si la señal de una vela cambia al recortar el futuro.

    Para varios puntos de corte `k`, las señales calculadas con `df[:k]` deben coincidir
    con las primeras `k` filas de las calculadas con `df` completo.
    """
    full = strategy.generate(df)
    rng = np.random.default_rng(seed)
    low = min(len(df) - 1, max(strategy.warmup + 1, 2))
    for k in sorted(rng.integers(low, len(df), size=cuts)):
        part = strategy.generate(df.iloc[:k])
        expected = full.iloc[:k]
        if not part.equals(expected):
            bad = (part != expected) & ~(part.isna() & expected.isna())
            first = bad.any(axis=1).idxmax()
            raise AssertionError(
                f"{strategy.name}: look-ahead detectado; la señal en {first} cambia "
                f"según cuántas velas futuras se conozcan (corte en {k})"
            )
