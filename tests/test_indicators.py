import numpy as np
import pandas as pd
import pytest
from conftest import volatile_candles

from bot_eve.strategies import indicators as ind


def wilder_rsi_reference(close, n):
    """RSI de Wilder calculado con un bucle explícito, independiente de pandas ewm."""
    out = [np.nan] * len(close)
    gains = [max(close[i] - close[i - 1], 0) for i in range(1, len(close))]
    losses = [max(close[i - 1] - close[i], 0) for i in range(1, len(close))]
    avg_g = sum(gains[:n]) / n
    avg_l = sum(losses[:n]) / n
    for i in range(n, len(close)):
        if i > n:
            avg_g = (avg_g * (n - 1) + gains[i - 1]) / n
            avg_l = (avg_l * (n - 1) + losses[i - 1]) / n
        out[i] = 100.0 if avg_l == 0 else 100 - 100 / (1 + avg_g / avg_l)
    return out


def test_rsi_extremes_and_constant():
    up = pd.Series(np.arange(1, 60, dtype=float))
    assert ind.rsi(up, 14).iloc[-1] == 100
    assert ind.rsi(up[::-1].reset_index(drop=True), 14).iloc[-1] == pytest.approx(0, abs=1e-9)
    assert ind.rsi(pd.Series(50.0, index=range(40)), 14).iloc[-1] == 50


def test_rsi_bounded_and_close_to_reference():
    close = volatile_candles(300)["close"]
    value = ind.rsi(close, 14)
    assert value.dropna().between(0, 100).all()
    ref = wilder_rsi_reference(close.tolist(), 14)
    # La semilla de pandas (ewm) difiere de la SMA inicial de Wilder; converge rápido.
    assert np.allclose(value.iloc[120:], ref[120:], atol=0.5)


def test_atr_of_constant_range_bars():
    n = 50
    df = pd.DataFrame({"high": [101.0] * n, "low": [99.0] * n, "close": [100.0] * n})
    assert ind.atr(df, 14).iloc[-1] == pytest.approx(2.0)


def test_true_range_uses_gaps():
    df = pd.DataFrame({"high": [10.0, 21.0], "low": [9.0, 20.0], "close": [10.0, 20.5]})
    assert ind.true_range(df).iloc[1] == pytest.approx(11.0)  # |21 - 10|, no high-low=1


def test_bollinger_known_values():
    s = pd.Series([1.0, 2, 3, 4, 5])
    mid, up, low = ind.bollinger(s, 5, 2.0)
    assert mid.iloc[-1] == 3
    assert up.iloc[-1] == pytest.approx(3 + 2 * np.sqrt(2))  # std poblacional de 1..5 = sqrt(2)
    assert low.iloc[-1] == pytest.approx(3 - 2 * np.sqrt(2))
    assert mid.iloc[:4].isna().all()


def test_adx_high_in_trend_low_in_noise():
    n = 400
    trend = pd.DataFrame({"high": np.arange(n) + 1.0, "low": np.arange(n) - 1.0})
    trend["close"] = np.arange(n, dtype=float)
    assert ind.adx(trend, 14).iloc[-1] > 80
    rng = np.random.default_rng(0)
    c = 100 + rng.normal(0, 0.5, n)
    noise = pd.DataFrame({"high": c + 0.5, "low": c - 0.5, "close": c})
    assert ind.adx(noise, 14).iloc[-50:].mean() < 30
    assert ind.adx(volatile_candles(500), 14).dropna().between(0, 100).all()


def test_cross_helpers_fire_once():
    a = pd.Series([1, 2, 3, 2, 1.0])
    assert ind.cross_up(a, 2.0).tolist() == [False, False, True, False, False]
    assert ind.cross_down(a, 2.0).tolist() == [False, False, False, False, True]
    assert ind.cross_up(a, pd.Series([2.0] * 5)).sum() == 1


@pytest.mark.parametrize(
    "fn",
    [
        lambda d: ind.rsi(d["close"], 14),
        lambda d: ind.atr(d, 14),
        lambda d: ind.adx(d, 14),
        lambda d: ind.ema(d["close"], 20),
        lambda d: ind.bollinger(d["close"], 20)[2],
    ],
)
def test_indicators_are_causal(fn):
    df = volatile_candles(600)
    full = fn(df)
    for k in (150, 333, 599):
        part = fn(df.iloc[:k])
        pd.testing.assert_series_equal(part, full.iloc[:k], check_names=False)
