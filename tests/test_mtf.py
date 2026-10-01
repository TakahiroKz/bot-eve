import numpy as np
import pandas as pd
import pytest

from bot_eve.strategies.mtf import intraday_signal, scalp_signal

AGG = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}


def synth(n=30000, seed=5):
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(
        np.cumsum(rng.normal(0, 0.0007, n) + 0.00002 * np.sin(np.arange(n) / 2000))
    )
    open_ = np.r_[close[0], close[:-1]]
    spread = np.abs(rng.normal(0, 0.0005, n)) * close
    idx = pd.date_range("2024-01-01", periods=n, freq="1min", tz="UTC")
    df = pd.DataFrame({"open": open_, "high": np.maximum(open_, close) + spread, "low": np.minimum(open_, close) - spread,
                       "close": close, "volume": rng.gamma(2.0, 50.0, n)}, index=idx)  # fmt: skip
    return df


def frames(d1):
    return (
        d1,
        d1.resample("5min").agg(AGG),
        d1.resample("15min").agg(AGG),
        d1.resample("1h").agg(AGG),
    )


@pytest.mark.parametrize("which", ["S1", "S2", "S3"])
def test_scalp_signals_are_causal(which):
    d1, d5, d15, _ = frames(synth())
    side, dist = scalp_signal(which, d1, d5, d15)
    k = 20000  # corte en una frontera de 15m y 1h
    c1, c5, c15, _ = frames(d1.iloc[:k])
    side2, dist2 = scalp_signal(which, c1, c5, c15)
    np.testing.assert_array_equal(side[:k], side2)
    np.testing.assert_allclose(dist[:k][side2 != 0], dist2[side2 != 0])
    assert set(np.unique(side)) <= {-1, 0, 1}
    assert (dist[side != 0] > 0).all()


@pytest.mark.parametrize("setup", ["I1", "I2"])
def test_intraday_signals_are_causal_and_respect_session(setup):
    d1, d5, d15, d1h = frames(synth(60000, seed=9))
    side, dist, nxt, hold = intraday_signal(setup, d5, d15, d1h)
    k5 = 8000  # 5m
    side2, dist2, _, _ = intraday_signal(
        setup, d5.iloc[:k5], d15[d15.index < d5.index[k5]], d1h[d1h.index < d5.index[k5]]
    )
    np.testing.assert_array_equal(side[: k5 - 6], side2[: k5 - 6])
    assert (hold >= 0).all() and hold.max() <= 288
    # al final del día UTC no queda tiempo para entrar
    last_bar = np.flatnonzero((d5.index.hour == 23) & (d5.index.minute == 55))[0]
    assert hold[last_bar] == 0
    assert hold[np.flatnonzero((d5.index.hour == 0) & (d5.index.minute == 0))[0]] == 287
