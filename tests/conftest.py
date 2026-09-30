from __future__ import annotations

import io
import zipfile

import numpy as np
import pandas as pd
import pytest


def make_candles(start: str, periods: int, freq: str = "1min", seed: int = 0) -> pd.DataFrame:
    """Velas sintéticas coherentes (high >= open/close >= low)."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start, periods=periods, freq=freq, tz="UTC", name="open_time")
    close = 100 + rng.normal(0, 0.1, periods).cumsum()
    open_ = np.concatenate([[100.0], close[:-1]])
    high = np.maximum(open_, close) + rng.uniform(0, 0.05, periods)
    low = np.minimum(open_, close) - rng.uniform(0, 0.05, periods)
    return pd.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": rng.uniform(1, 10, periods),
            "quote_volume": rng.uniform(100, 1000, periods),
            "trades": rng.integers(1, 100, periods),
        },
        index=idx,
    )


def klines_zip(df: pd.DataFrame, unit: str = "ms", header: bool = False) -> bytes:
    """Empaqueta velas en el formato CSV-en-zip de data.binance.vision."""
    epoch = pd.Timestamp("1970-01-01", tz="UTC")
    ts = (df.index - epoch) // pd.Timedelta(1, unit)
    raw = pd.DataFrame(
        {
            "open_time": ts,
            "open": df["open"],
            "high": df["high"],
            "low": df["low"],
            "close": df["close"],
            "volume": df["volume"],
            "close_time": ts + 59_999,
            "quote_volume": df["quote_volume"],
            "trades": df["trades"],
            "taker_buy_base": 0.0,
            "taker_buy_quote": 0.0,
            "ignore": 0,
        }
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("data.csv", raw.to_csv(index=False, header=header))
    return buf.getvalue()


@pytest.fixture
def candles() -> pd.DataFrame:
    return make_candles("2024-01-01", 600)


def volatile_candles(n: int = 2500, seed: int = 7, freq: str = "15min") -> pd.DataFrame:
    """Serie con tendencias, rangos y volatilidad variable, para probar estrategias."""
    rng = np.random.default_rng(seed)
    vol = 0.002 * (1 + np.sin(np.arange(n) / 150) ** 2)
    drift = 0.0004 * np.sin(np.arange(n) / 400)
    close = 100 * np.exp((rng.normal(0, 1, n) * vol + drift).cumsum())
    open_ = np.concatenate([[100.0], close[:-1]])
    spread = np.abs(rng.normal(0, 1, n)) * vol * close
    idx = pd.date_range("2024-01-01", periods=n, freq=freq, tz="UTC", name="open_time")
    return pd.DataFrame(
        {
            "open": open_,
            "high": np.maximum(open_, close) + spread,
            "low": np.minimum(open_, close) - spread,
            "close": close,
            "volume": rng.uniform(1, 10, n),
            "quote_volume": rng.uniform(100, 1000, n),
            "trades": rng.integers(1, 100, n),
        },
        index=idx,
    )
