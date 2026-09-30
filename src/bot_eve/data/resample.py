"""Remuestreo de velas OHLCV a intervalos mayores (5m, 15m, 1h, 4h...)."""

from __future__ import annotations

import pandas as pd

from bot_eve.data.intervals import to_pandas_rule, to_timedelta

_AGG = {
    "open": "first",
    "high": "max",
    "low": "min",
    "close": "last",
    "volume": "sum",
    "quote_volume": "sum",
    "trades": "sum",
}


def resample_ohlcv(df: pd.DataFrame, interval: str, base_interval: str = "1m") -> pd.DataFrame:
    """Agrega velas base a `interval`.

    - `open` = primer valor, `high` = máximo, `low` = mínimo, `close` = último,
      `volume`/`quote_volume`/`trades` = suma.
    - Cada vela se etiqueta con su hora de apertura (`label='left'`).
    - Los intervalos sin velas base no generan vela (no se inventan datos).
    - `n_base` indica cuántas velas base componen cada vela; menos de las esperadas
      significa que hubo huecos en ese periodo.
    """
    if df.empty:
        return df.assign(n_base=pd.Series(dtype="int64"))
    grouped = df.resample(to_pandas_rule(interval), label="left", closed="left")
    out = grouped.agg(_AGG)
    out["n_base"] = grouped["open"].count().astype("int64")
    out = out[out["n_base"] > 0]
    out["trades"] = out["trades"].astype("int64")
    out.index.name = "open_time"
    return out


def expected_base_candles(interval: str, base_interval: str = "1m") -> int:
    return int(to_timedelta(interval) / to_timedelta(base_interval))
